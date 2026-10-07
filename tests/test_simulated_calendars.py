from math import floor

import numpy as np
import pandas as pd
import pytest

from src.calendar_spread import reconcile_calendar, simulate_calendar
from src.option_model import Call, call, causal_volatility, expiry, integer_spread
from src.simulated_calendars import benchmark_comparison, prepare, verify_causality
from tests.test_causality import synthetic_bars


def bars(index=None):
    index = (
        pd.date_range("2025-01-02 09:15", periods=4, freq="15min", tz="Asia/Kolkata")
        if index is None
        else pd.DatetimeIndex(index, tz="Asia/Kolkata")
    )
    n = len(index)
    return pd.DataFrame(
        dict(
            open=np.full(n, 100.0),
            close=np.full(n, 100.0),
            buy_signal=[True] + [False] * (n - 1),
            sell_signal=[False] * n,
            trend=np.zeros(n),
            causal_sigma=np.full(n, 0.20),
        ),
        index=index,
    )


def test_known_price_signs_and_independent_finite_difference_greeks():
    assert call(100, 100, 1, 0.2, rate=0, dividend=0).price == pytest.approx(
        7.965567455405804
    )
    model = call(100, 100, 0.5, 0.2)
    assert (
        model.price > 0
        and model.delta > 0
        and model.gamma > 0
        and model.vega > 0
        and model.theta < 0
    )
    ds, dt, dv = 0.01, 0.00001, 0.00001
    delta = (
        call(100 + ds, 100, 0.5, 0.2).price - call(100 - ds, 100, 0.5, 0.2).price
    ) / (2 * ds)
    gamma = (
        call(100 + ds, 100, 0.5, 0.2).price
        - 2 * model.price
        + call(100 - ds, 100, 0.5, 0.2).price
    ) / ds**2
    theta = (
        call(100, 100, 0.5 - dt, 0.2).price - call(100, 100, 0.5 + dt, 0.2).price
    ) / (2 * dt * 365)
    vega = (
        call(100, 100, 0.5, 0.2 + dv).price - call(100, 100, 0.5, 0.2 - dv).price
    ) / (2 * dv * 100)
    assert model.delta == pytest.approx(delta, rel=1e-6)
    assert model.gamma == pytest.approx(gamma, rel=1e-5)
    assert model.theta == pytest.approx(theta, rel=1e-6)
    assert model.vega == pytest.approx(vega, rel=1e-6)
    assert (
        call(100, 100, 0.5, 0.2, dividend=0.01).price
        < call(100, 100, 0.5, 0.2, dividend=0).price
    )


@pytest.mark.parametrize("spot,expected", [(90, 0), (100, 0), (110, 10)])
def test_expiry_intrinsic_no_fictional_time_value(spot, expected):
    value = call(spot, 100, -0.01, 0.2)
    assert value.price == expected
    assert value.theta == value.gamma == value.vega == 0


def test_synthetic_expiry_weekend_and_local_clock():
    entry = pd.Timestamp("2025-01-03 09:15", tz="Asia/Kolkata")
    assert expiry(entry, 30) == pd.Timestamp("2025-02-03 15:30", tz="Asia/Kolkata")
    assert expiry(entry, 60) > expiry(entry, 30)


def test_integer_ratio_globally_matches_independent_exhaustive_feasible_set():
    long, short = call(100, 100, 60 / 365, 0.24), call(100, 100, 30 / 365, 0.24)
    capital, fee, slip = 1000, 0.0003, 0.001
    chosen, _ = integer_spread(
        long, short, 100, capital, capital, fee_rate=fee, slippage_rate=slip
    )
    target = abs(long.theta) / abs(short.theta)
    maximum = floor(0.05 * capital / (long.price * (1 + slip) * (1 + fee)))
    feasible = []
    for ql in range(1, maximum + 1):
        for qs in range(1, ql + 1):
            debit = ql * long.price * (1 + slip) * (1 + fee) - qs * short.price * (
                1 - slip
            ) * (1 - fee)
            budget = (
                ql * long.price * (1 + slip) * (1 + fee)
                + qs * short.price * (1 - slip) * fee
            )
            if (
                ql * long.delta - qs * short.delta > 0
                and capital - debit >= qs * 100
                and budget <= 0.05 * capital
            ):
                feasible.append((abs(qs / ql - target), -ql, qs))
    score = min(feasible)
    assert chosen[:2] == (-score[1], score[2])
    assert isinstance(chosen[0], int) and isinstance(chosen[1], int)
    assert chosen[1] >= 1 and chosen[0] >= chosen[1]


def test_insufficient_premium_budget_never_substitutes_standalone_call():
    long, short = call(100, 100, 60 / 365, 0.24), call(100, 100, 30 / 365, 0.24)
    construction, reason = integer_spread(
        long, short, 100, 1, 1, fee_rate=0.0003, slippage_rate=0
    )
    assert construction is None and reason
    result = simulate_calendar(bars(), initial_capital=1)
    assert result.fills.empty
    assert result.events.reason.str.contains("no_integer").any()


def test_strike_previous_completed_close_next_open_and_short_liability():
    data = bars()
    data.loc[data.index[1] :, "open"] = 105
    result = simulate_calendar(data, initial_capital=10000, fee_bps=3, slippage_bps=10)
    assert len(result.fills) == 2
    assert result.fills.time.eq(data.index[1]).all()
    assert result.fills.strike.eq(100).all()  # not execution open 105
    entry = result.events.loc[result.events.action == "entry"].iloc[0]
    assert entry.long_premium_with_fees <= 0.05 * entry.pre_entry_equity
    assert result.marks.free_cash.min() >= -1e-7
    mark = result.marks.iloc[-1]
    expected = (
        10000
        + result.fills.cash_flow.sum()
        + mark.long_quantity * mark.long_price
        - mark.short_quantity * mark.short_price
    )
    assert mark.equity == pytest.approx(expected)
    assert mark.collateral == mark.short_quantity * mark.strike
    assert mark.cash + mark.long_value - mark.short_liability == pytest.approx(
        mark.equity
    )
    assert mark.equity != pytest.approx(
        mark.cash + mark.collateral + mark.long_value - mark.short_liability
    )
    assert reconcile_calendar(result, 3, 10)["passed"]


def test_bearish_exit_groups_both_legs_net_fees_and_slippage():
    data = bars()
    data.loc[data.index[2], "sell_signal"] = True
    result = simulate_calendar(data, initial_capital=10000, fee_bps=3, slippage_bps=25)
    assert len(result.fills) == 4 and len(result.signals) == 1
    assert result.signals.net_pnl.iloc[0] == pytest.approx(result.fills.cash_flow.sum())
    assert result.signals.fees.iloc[0] == pytest.approx(result.fills.fee.sum())
    assert (
        result.fills.loc[result.fills.side == "buy", "fill_price"]
        .gt(result.fills.loc[result.fills.side == "buy", "model_price"])
        .all()
    )
    assert (
        result.fills.loc[result.fills.side == "sell", "fill_price"]
        .lt(result.fills.loc[result.fills.side == "sell", "model_price"])
        .all()
    )
    assert reconcile_calendar(result, 3, 25)["passed"]


def test_roll_freezes_strike_per_spread_and_keeps_signal_group():
    data = bars(
        [
            "2025-01-02 09:15",
            "2025-01-03 09:15",
            "2025-01-29 09:15",
            "2025-01-30 09:15",
            "2025-01-31 09:15",
        ]
    )
    data["close"] = [100, 101, 102, 103, 104]
    data.loc[data.index[3], "sell_signal"] = True
    result = simulate_calendar(data, initial_capital=10000)
    assert len(result.signals) == 1 and result.signals.spreads.iloc[0] == 2
    assert result.signals.rolls.iloc[0] == 1
    assert len(result.fills) == 8
    assert result.fills.groupby("spread").strike.nunique().eq(1).all()
    assert result.fills.loc[result.fills.spread == 2, "strike"].eq(101).all()
    assert (
        result.fills.loc[result.fills.reason == "five_day_roll", "time"]
        .eq(data.index[2])
        .all()
    )
    assert result.signals.fees.iloc[0] == pytest.approx(result.fills.fee.sum())
    assert reconcile_calendar(result, 3, 0)["passed"]


def test_missing_session_expiry_crossing_is_explicit_intrinsic_fallback():
    data = bars(["2025-01-02 09:15", "2025-01-03 09:15", "2025-02-10 09:15"])
    data.loc[data.index[2], "open"] = 110
    result = simulate_calendar(data, initial_capital=10000)
    crossing = result.fills.loc[
        (result.fills.reason == "expiry_crossing_gap") & (result.fills.leg == "short")
    ]
    assert len(crossing) == 1 and crossing.model_price.iloc[0] == 10
    assert result.events.reason.eq("expiry_crossing_gap").any()
    assert reconcile_calendar(result, 3, 0)["passed"]


def test_daily_prior_marks_fixed_long_and_adjustment_costs():
    data = bars(
        ["2025-01-02 09:15", "2025-01-03 09:15", "2025-01-24 09:15", "2025-01-27 09:15"]
    )
    data["open"] = [100, 100, 100, 100]
    data["close"] = [100, 100, 100, 100]
    result = simulate_calendar(
        data, initial_capital=10000, management="daily", fee_bps=3, slippage_bps=25
    )
    adjustments = result.fills.loc[result.fills.reason == "theta_adjustment"]
    assert len(adjustments) > 0
    assert adjustments.leg.eq("short").all()
    assert adjustments.fee.gt(0).all()
    assert adjustments.decision_time.iloc[0] == data.index[2] + pd.Timedelta(minutes=15)
    assert adjustments.time.iloc[0] == data.index[3]
    assert (
        result.marks.loc[result.marks.long_quantity > 0, "long_quantity"].nunique() == 1
    )
    assert result.marks.free_cash.min() >= -1e-7
    assert (
        result.marks.loc[result.marks.long_quantity > 0, "short_quantity"].ge(1).all()
    )
    assert reconcile_calendar(result, 3, 25)["passed"]
    entry = simulate_calendar(data, initial_capital=10000, management="entry")
    assert not entry.fills.reason.eq("theta_adjustment").any()


def test_21_session_volatility_is_independent_and_lagged():
    days = pd.bdate_range("2024-01-01", periods=30, tz="Asia/Kolkata")
    closes = 100 * np.exp(np.cumsum(np.arange(30) * 0.0001))
    data = pd.DataFrame(
        dict(close=closes), index=days + pd.Timedelta(hours=9, minutes=15)
    )
    values = causal_volatility(data)
    assert values.iloc[:22].isna().all()
    expected = np.std(np.diff(np.log(closes[:22])), ddof=1) * np.sqrt(252)
    assert values.iloc[22] == pytest.approx(expected)
    changed = data.copy()
    changed.loc[changed.index[22] :, "close"] *= 5
    pd.testing.assert_series_equal(
        values.iloc[:23], causal_volatility(changed).iloc[:23]
    )


def test_realistic_prefix_future_perturbation_of_vol_indicator_fills_marks():
    data = synthetic_bars()
    assert verify_causality(data, prepare(data), 700)["indicator_and_volatility_causal"]


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(fee_bps=-1),
        dict(fee_bps=np.inf),
        dict(slippage_bps=-1),
        dict(slippage_bps=10000),
        dict(vol_multiplier=0),
        dict(near_multiplier=np.nan),
        dict(initial_capital=0),
        dict(management="bad"),
    ],
)
def test_invalid_inputs(kwargs):
    with pytest.raises((ValueError, TypeError)):
        simulate_calendar(bars(), **kwargs)


def test_reconciliation_detects_corrupted_cash_or_liability():
    result = simulate_calendar(bars(), initial_capital=10000)
    result.marks.loc[result.marks.index[-1], "cash"] += 1
    with pytest.raises(AssertionError):
        reconcile_calendar(result, 3, 0)


def test_stage2_alignment_normalizes_csv_timezone_before_pairing(tmp_path):
    from src.accounting import simulate_portfolio
    from src.futures_proxy import export_run
    from tests.test_accounting import closed_trade

    data = closed_trade()
    for scenario in ["net", "buy_hold_net"]:
        result = simulate_portfolio(data, initial_capital=500000, cost_bps=5)
        export_run(
            tmp_path / "start" / "a3" / "OOS" / scenario,
            data,
            result,
            {"label": "index-based futures proxy"},
        )
    rows = benchmark_comparison(tmp_path, tmp_path, {"OOS": data}, "start")
    assert len(rows) == 2
    assert rows[0]["total_return"] == pytest.approx(0.098900525)


def test_independent_artifact_pricing_and_unit_accounting(tmp_path):
    from src.simulated_calendars import export
    from tests.verify_simulated_calendar_outputs import audit_run, independent_call

    data = bars()
    data["open"] *= 100
    data["close"] *= 100
    data["bar_end"] = data.index + pd.Timedelta(minutes=15)
    result = simulate_calendar(data, fee_bps=3, slippage_bps=25)
    config = dict(
        label="SIMULATED",
        fee_bps=3,
        slippage_bps=25,
        vol_multiplier=1.2,
        near_multiplier=1.0,
    )
    export(tmp_path / "run", data, result, config)
    proof = audit_run(tmp_path / "run", data, data[["causal_sigma"]])
    assert proof["independent_repricing"] and proof["collateral_counted_once"]
    np.testing.assert_allclose(
        independent_call(100, 100, 0.5, 0.2), call(100, 100, 0.5, 0.2), rtol=1e-12
    )
    curve = pd.read_csv(tmp_path / "run" / "equity.csv.gz")
    curve.loc[3, "short_quantity"] += 1
    curve.to_csv(tmp_path / "run" / "equity.csv.gz", index=False)
    with pytest.raises(AssertionError):
        audit_run(tmp_path / "run", data, data[["causal_sigma"]])


def test_premium_budget_includes_both_entry_fees_without_short_receipt_credit():
    long = Call(4.995, 0.6, 0.01, 0.1, -1.0)
    short = Call(3.0, 0.5, 0.02, 0.1, -1.4)
    construction, _ = integer_spread(
        long, short, 80, 100, 100, fee_rate=0.001, slippage_rate=0
    )
    assert (
        long.price * (1 + 0.001) < 5
    )  # long's own fee fits but both entry fees do not
    assert construction is None
    free, _ = integer_spread(long, short, 80, 100, 100, fee_rate=0, slippage_rate=0)
    assert free[:2] == (1, 1)
