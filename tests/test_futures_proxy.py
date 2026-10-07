import json

import numpy as np
import pandas as pd
import pytest

from src.accounting import reconcile_portfolio, simulate_portfolio
from src.futures_proxy import (
    annual_performance,
    build_report,
    concentration,
    export_run,
    summarize,
)
from tests.test_accounting import closed_trade
from tests.verify_futures_proxy_outputs import check_run


def test_adverse_fills_fees_and_collateral_independently():
    bars = closed_trade()
    result = simulate_portfolio(
        bars, initial_capital=1000, cost_bps=5, slippage_points=2
    )
    q = 999.5 / 102
    entry_fee = q * 102 * 0.0005
    exit_fee = q * 108 * 0.0005
    expected = 1000 + q * 6 - entry_fee - exit_fee
    assert result.fills.price.tolist() == [102, 108]
    assert result.trades.quantity.iloc[0] == pytest.approx(q)
    assert q * 102 + entry_fee <= 1000
    assert result.equity.iloc[-1] == pytest.approx(expected)
    assert result.trades.net_pnl.iloc[0] == pytest.approx(expected - 1000)
    reconcile_portfolio(result)


def test_extra_observed_bar_delay_and_pending_terminal_exit():
    bars = closed_trade()
    result = simulate_portfolio(bars, initial_capital=1000, execution_delay=2)
    assert result.fills.time.tolist() == [bars.index[2]]
    assert result.fills.signal_time.iloc[0] == bars.index[0] + pd.Timedelta(minutes=15)
    assert result.open_position["quantity"] == pytest.approx(1000 / 110)
    assert len(result.trades) == 0
    assert result.equity.iloc[-1] == pytest.approx(1000)
    reconcile_portfolio(result)


def test_buy_hold_first_open_fixed_quantity_no_terminal_exit_fee():
    bars = closed_trade()
    bars["buy_signal"] = False
    bars["sell_signal"] = False
    result = simulate_portfolio(
        bars, initial_capital=1000, cost_bps=5, enter_first_bar=True
    )
    assert len(result.fills) == 1
    assert result.fills.time.iloc[0] == bars.index[0]
    assert result.quantities.tolist() == pytest.approx([9.995] * 3)
    assert result.equity.iloc[-1] == pytest.approx(1099.45025)
    assert result.open_position["gross_pnl"] == pytest.approx(99.95)
    metrics = summarize(bars, result)
    assert metrics["open_net_pnl"] == pytest.approx(99.45025)
    assert metrics["total_fees"] == pytest.approx(0.49975)
    assert metrics["exposure_calendar_fraction"] == 1
    assert metrics["trade_count"] == 0
    reconcile_portfolio(result)


@pytest.mark.parametrize("slip", [-1, np.nan, np.inf, True])
def test_invalid_slippage(slip):
    with pytest.raises((ValueError, TypeError)):
        simulate_portfolio(closed_trade(), slippage_points=slip)


@pytest.mark.parametrize("delay", [0, -1, 1.5, True])
def test_invalid_delay(delay):
    with pytest.raises(ValueError):
        simulate_portfolio(closed_trade(), execution_delay=delay)


def test_nonpositive_adverse_exit_rejected():
    with pytest.raises(ValueError, match="exit fill price"):
        simulate_portfolio(closed_trade(), slippage_points=110)


def test_annual_returns_use_prior_year_mark_and_initial_capital():
    bars = closed_trade()
    bars.index = pd.DatetimeIndex(
        ["2023-12-29 09:15", "2023-12-29 09:30", "2024-01-02 09:15"], tz="Asia/Kolkata"
    )
    result = simulate_portfolio(bars, initial_capital=1000)
    annual = annual_performance(result)
    assert annual.year.tolist() == [2023, 2024]
    assert annual.total_return.tolist() == pytest.approx([0.05, 1100 / 1050 - 1])
    assert annual.starting_equity.tolist() == [1000, 1050]


def test_concentration_does_not_remove_trades_or_rescale_equity():
    result = simulate_portfolio(closed_trade(), initial_capital=1000)
    before = result.equity.copy()
    top, stats = concentration(result)
    assert len(top) == 1
    assert stats["top_five_net_pnl"] == pytest.approx(100)
    assert stats["fraction_of_closed_net"] == 1
    pd.testing.assert_series_equal(result.equity, before)


def test_export_run_reconciles_and_merges_concentration(tmp_path):
    bars = closed_trade()
    result = simulate_portfolio(bars, initial_capital=1000, cost_bps=5)
    row = export_run(
        tmp_path / "run", bars, result, {"label": "index-based futures proxy"}
    )
    assert row["closed_net_pnl"] == pytest.approx(98.900525)
    assert (tmp_path / "run" / "reconciliation.json").exists()
    assert (tmp_path / "run" / "annual_performance.csv").exists()


def test_report_inconclusive_when_timestamp_stress_reverses_expectancy(tmp_path):
    rows = []
    for label in ["start", "end"]:
        for period in ["IS", "OOS", "FULL"]:
            scenarios = ["net", "buy_hold_net", "slip_2"]
            for scenario in scenarios:
                bars = closed_trade()
                if label == "end" and period == "OOS" and scenario == "slip_2":
                    bars.loc[bars.index[2], "open"] = 100
                result = simulate_portfolio(bars, initial_capital=1000, cost_bps=5)
                meta = dict(
                    label="index-based futures proxy",
                    interpretation=label,
                    period=period,
                    amplitude=3,
                    scenario=scenario,
                    cost_bps=5,
                )
                rows.append(
                    export_run(
                        tmp_path / label / "a3" / period / scenario, bars, result, meta
                    )
                )
    build_report(tmp_path, pd.DataFrame(rows), {})

    verdict = json.loads((tmp_path / "verdict.json").read_text())
    assert verdict["timestamp_direction_changed"] is True
    assert verdict["verdict"].startswith("INCONCLUSIVE")
    assert (tmp_path / "annual_net_performance.csv").exists()


@pytest.mark.parametrize("benchmark", [False, True])
def test_independent_export_reconstruction_with_closed_or_open_position(
    tmp_path, benchmark
):
    bars = closed_trade()
    bars["bar_end"] = bars.index + pd.Timedelta(minutes=15)
    if benchmark:
        bars["buy_signal"] = False
        bars["sell_signal"] = False
    result = simulate_portfolio(
        bars, initial_capital=500000, cost_bps=5, enter_first_bar=benchmark
    )
    meta = dict(
        label="index-based futures proxy",
        cost_bps=5,
        slippage_points=0,
        execution_delay=1,
        scenario="buy_hold_net" if benchmark else "net",
    )
    export_run(tmp_path / "run", bars, result, meta)
    assert check_run(tmp_path / "run", bars)["passed"] is True
    curve = pd.read_csv(tmp_path / "run" / "equity.csv")
    curve.loc[1, "equity"] += 100
    curve.to_csv(tmp_path / "run" / "equity.csv", index=False)
    with pytest.raises(AssertionError):
        check_run(tmp_path / "run", bars)
