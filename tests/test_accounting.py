import numpy as np
import pandas as pd
import pytest

from src.accounting import InsolvencyError, reconcile_portfolio, simulate_portfolio
from src.costs import apply_transaction_costs, build_cost_adjusted_equity_curve
from src.portfolio import build_equity_curve, equity_to_returns
from src.trading import generate_trade_ledger
from tests.check_cost_reconciliation import check_reconciliation


def closed_trade():
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 110.0],
            "close": [100.0, 105.0, 110.0],
            "buy_signal": [True, False, False],
            "sell_signal": [False, True, False],
        },
        index=pd.date_range(
            "2024-01-02 09:15", periods=3, freq="15min", tz="Asia/Kolkata"
        ),
    )


def test_actual_entry_exit_fees_residual_cash_and_fixed_quantity():
    result = simulate_portfolio(closed_trade(), initial_capital=1000, cost_bps=5)
    # Independent arithmetic for legacy q=C*(1-r)/P, with actual-notional fees.
    assert result.quantities.tolist() == pytest.approx([0, 9.995, 0])
    assert result.cash.iloc[1] == pytest.approx(0.00025)
    row = result.trades.iloc[0]
    assert row.quantity == pytest.approx(9.995)
    assert row.entry_notional == pytest.approx(999.5)
    assert row.exit_notional == pytest.approx(1099.45)
    assert row.entry_cost == pytest.approx(0.49975)
    assert row.exit_cost == pytest.approx(0.549725)
    assert row.gross_pnl == pytest.approx(99.95)
    assert row.net_pnl == pytest.approx(98.900525)
    assert result.equity.tolist() == pytest.approx([1000, 1049.47525, 1098.900525])
    assert result.fills.price.tolist() == [100, 110]  # fees do not alter fills/slippage
    assert result.fills.quantity.tolist() == pytest.approx([9.995, 9.995])
    assert result.fills.time.iloc[0] == closed_trade().index[1]
    assert result.fills.signal_time.iloc[0] == closed_trade().index[0] + pd.Timedelta(
        minutes=15
    )
    assert reconcile_portfolio(result)["difference"] == pytest.approx(0, abs=1e-9)


def test_open_position_reconciliation_does_not_charge_fictitious_exit():
    data = closed_trade().iloc[:2].copy()
    data.loc[data.index[-1], "close"] = 90.0
    result = simulate_portfolio(data, initial_capital=1000, cost_bps=5)
    assert result.trades.empty
    assert len(result.fills) == 1
    assert result.open_position["gross_pnl"] == pytest.approx(-99.95)
    assert result.equity.iloc[-1] == pytest.approx(899.55025)
    audit = reconcile_portfolio(result)
    assert audit["open_entry_fee"] == pytest.approx(0.49975)
    assert audit["closed_net_pnl"] == 0
    assert audit["expected_final_equity"] == pytest.approx(1000 - 99.95 - 0.49975)


def test_closed_and_open_trades_reconcile_without_double_counting_fees():
    data = closed_trade()
    later = pd.DataFrame(
        {
            "open": [110.0, 80.0, 90.0],
            "close": [110.0, 85.0, 92.0],
            "buy_signal": [True, False, False],
            "sell_signal": [False] * 3,
        },
        index=pd.date_range(
            data.index[-1] + pd.Timedelta(minutes=15), periods=3, freq="15min"
        ),
    )
    result = simulate_portfolio(
        pd.concat([data, later]), initial_capital=1000, cost_bps=5
    )
    q2 = 1098.900525 * 0.9995 / 80
    assert result.quantities.iloc[-2] == pytest.approx(q2)
    assert result.quantities.iloc[-1] == pytest.approx(q2)
    expected = 1000 + 98.900525 + q2 * 12 - q2 * 80 * 0.0005
    assert result.equity.iloc[-1] == pytest.approx(expected)
    assert reconcile_portfolio(result)["expected_final_equity"] == pytest.approx(
        expected
    )


def test_ledger_fees_do_not_assume_unit_quantity():
    ledger = pd.DataFrame(
        {
            "quantity": [3.0],
            "entry_price": [100.0],
            "exit_price": [110.0],
            "gross_pnl": [30.0],
        }
    )
    costed = apply_transaction_costs(ledger, 5)
    assert costed.entry_cost.iloc[0] == pytest.approx(0.15)
    assert costed.exit_cost.iloc[0] == pytest.approx(0.165)
    assert costed.net_pnl.iloc[0] == pytest.approx(29.685)
    with pytest.raises(ValueError, match="quantity"):
        apply_transaction_costs(ledger.drop(columns="quantity"), 5)


def test_costed_ledger_is_actually_checked_and_corruption_fails():
    result = simulate_portfolio(closed_trade(), initial_capital=1000, cost_bps=5)
    result.trades.loc[0, "net_pnl"] += 1
    with pytest.raises(AssertionError):
        reconcile_portfolio(result)
    checked = check_reconciliation(closed_trade(), initial_capital=1000)
    assert checked["actual_final_equity"] == pytest.approx(1098.900525)


def test_gross_wrappers_use_identical_accounting_and_ledger():
    data = closed_trade()
    pd.testing.assert_series_equal(
        build_equity_curve(data), build_cost_adjusted_equity_curve(data, 100000, 0)
    )
    pd.testing.assert_frame_equal(
        generate_trade_ledger(data), simulate_portfolio(data).trades
    )
    result = simulate_portfolio(data, initial_capital=1000)
    assert result.equity.iloc[-1] == pytest.approx(1100)
    assert result.trades.gross_pnl.iloc[0] == pytest.approx(100)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -1, True, "5"])
def test_invalid_cost_parameters(bad):
    with pytest.raises((ValueError, TypeError)):
        simulate_portfolio(closed_trade(), cost_bps=bad)


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf, True])
def test_invalid_starting_capital(bad):
    with pytest.raises((ValueError, TypeError)):
        simulate_portfolio(closed_trade(), initial_capital=bad)


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf])
def test_invalid_prices(bad):
    data = closed_trade()
    data.iloc[1, data.columns.get_loc("open")] = bad
    with pytest.raises(ValueError):
        simulate_portfolio(data)


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf])
def test_invalid_ledger_quantities(bad):
    ledger = pd.DataFrame(
        {
            "quantity": [bad],
            "entry_price": [100.0],
            "exit_price": [110.0],
            "gross_pnl": [10.0],
        }
    )
    with pytest.raises(ValueError):
        apply_transaction_costs(ledger, 5)


def test_mathematical_quantity_limit_without_arbitrary_cost_cap():
    # Positive-quantity legacy sizing needs 1-rate>0, not an arbitrary 10/100bps cap.
    result = simulate_portfolio(closed_trade(), initial_capital=1000, cost_bps=9000)
    assert result.trades.quantity.iloc[0] == pytest.approx(1)
    reconcile_portfolio(result)
    with pytest.raises(ValueError, match="quantity"):
        simulate_portfolio(closed_trade(), cost_bps=10000)
    # Standalone fee arithmetic has no sizing limit: explicit fixed quantity allowed.
    ledger = pd.DataFrame(
        {
            "quantity": [1.0],
            "entry_price": [100.0],
            "exit_price": [110.0],
            "gross_pnl": [10.0],
        }
    )
    assert apply_transaction_costs(ledger, 10001).net_pnl.iloc[0] < 0


def test_nonfinite_intermediate_equity_is_explicit_insolvency():
    data = closed_trade()
    data.iloc[1, data.columns.get_loc("close")] = 1e308
    with pytest.raises(InsolvencyError):
        simulate_portfolio(data, initial_capital=1000)


def test_nonpositive_equity_is_not_filled_as_zero_return():
    with pytest.raises(ValueError, match="positive"):
        equity_to_returns(pd.Series([1000.0, 0.0], index=closed_trade().index[:2]))


def test_ambiguous_signals_and_bad_intervals_are_rejected():
    data = closed_trade()
    data.iloc[0, data.columns.get_loc("sell_signal")] = True
    with pytest.raises(ValueError, match="Simultaneous"):
        simulate_portfolio(data)
    data = closed_trade()
    data["bar_end"] = data.index + pd.Timedelta(minutes=30)
    with pytest.raises(ValueError, match="nonoverlapping"):
        simulate_portfolio(data)


def test_underflow_to_zero_equity_is_explicit_insolvency():
    data = closed_trade()
    data.iloc[1, data.columns.get_loc("open")] = float(2**1000)
    data.iloc[1, data.columns.get_loc("close")] = 2.0**-1000
    with pytest.raises(InsolvencyError, match="Insolvent"):
        simulate_portfolio(data, initial_capital=1)


@pytest.mark.parametrize("value", [True, "100", 1 + 2j])
def test_non_real_prices_are_rejected(value):
    data = closed_trade().astype({"open": object})
    data.iloc[1, data.columns.get_loc("open")] = value
    with pytest.raises((ValueError, TypeError)):
        simulate_portfolio(data)
