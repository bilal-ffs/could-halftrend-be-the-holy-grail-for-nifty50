import numpy as np
import pandas as pd
import pytest

from src.halftrend import calculate_halftrend
from src.research import evaluate_oos, prepare_evaluation_windows
from tests.check_oos_integrity import check_causality
from tests.run_cost_stress import assert_zero_cost_oos_equivalence, run_scenario


def synthetic_bars():
    days = pd.bdate_range("2021-12-01", "2022-01-28", tz="Asia/Kolkata")
    index = pd.DatetimeIndex(
        [
            day + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=15 * i)
            for day in days
            for i in range(25)
        ]
    )
    rng = np.random.default_rng(123)
    close = 100 + 8 * np.sin(np.arange(len(index)) / 8) + rng.normal(0, 0.3, len(index))
    opens = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, close) + 0.5,
            "low": np.minimum(opens, close) - 0.5,
            "close": close,
            "volume": np.nan,
            "bar_open": index,
            "bar_end": index + pd.Timedelta(minutes=15),
        },
        index=index,
    )


@pytest.mark.parametrize("cutoff", [100, 450, 700])
def test_prefix_future_perturbation_values_signals_and_fills(cutoff):
    checked = check_causality(synthetic_bars(), cutoff)
    assert checked["causal"]
    if cutoff > 100:
        assert checked["historical_fills"] > 0  # avoid a vacuous no-fill test


def test_oos_zero_cost_stress_exactly_matches_main_runner():
    bars = synthetic_bars()
    _, _, oos = prepare_evaluation_windows(bars)
    assert_zero_cost_oos_equivalence(bars, oos)
    main, portfolio = evaluate_oos(bars)
    cost, equity, _, ledger = run_scenario(oos, 0)
    pd.testing.assert_series_equal(equity, portfolio.equity)
    pd.testing.assert_frame_equal(ledger, portfolio.trades)
    assert main.start_time == cost.start_time
    assert main.end_time == cost.end_time
    assert portfolio.positions.iloc[0] == 0
    assert portfolio.start_time == oos.bar_open.iloc[0]
    assert not portfolio.trades.empty


def test_every_cost_scenario_uses_same_signals_boundaries_and_reset():
    bars = synthetic_bars()
    _, _, oos = prepare_evaluation_windows(bars)
    gross, _, _, gross_ledger = run_scenario(oos, 0)
    original = oos.copy(deep=True)
    for fee in [5, 8, 10]:
        cost, _, _, ledger = run_scenario(oos, fee)
        pd.testing.assert_frame_equal(oos, original)
        pd.testing.assert_frame_equal(
            ledger[["entry_time", "entry_price", "exit_time", "exit_price"]],
            gross_ledger[["entry_time", "entry_price", "exit_time", "exit_price"]],
        )
        assert cost.start_time == gross.start_time
        assert cost.end_time == gross.end_time
        assert cost.portfolio_result.positions.iloc[0] == 0


def test_indicator_state_is_full_history_state_at_oos_boundary():
    bars = synthetic_bars()
    full, _, oos = prepare_evaluation_windows(bars)
    pd.testing.assert_frame_equal(oos, full.loc[oos.index])
    assert len(full) > len(oos)
    assert oos.atr.iloc[0] > 0
    cold = calculate_halftrend(bars.loc[oos.index])
    assert np.isnan(cold.atr.iloc[0])


@pytest.mark.parametrize(
    "options",
    [
        {"amplitude": 0},
        {"amplitude": 1.5},
        {"amplitude": True},
        {"channel_deviation": np.inf},
        {"channel_deviation": -1},
    ],
)
def test_indicator_parameter_validation(options):
    with pytest.raises((ValueError, TypeError)):
        calculate_halftrend(synthetic_bars().iloc[:200], **options)
