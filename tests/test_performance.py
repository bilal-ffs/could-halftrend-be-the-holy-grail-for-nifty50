import json

import numpy as np
import pandas as pd
import pytest

from src.backtest import HalfTrendBacktest, run_backtest
from src.portfolio import equity_to_returns


def backtest(equity, *, start_time, initial_capital=1000, risk_free_rate=0):
    return HalfTrendBacktest(
        equity_to_returns(equity, initial_capital=initial_capital),
        pd.Series([50.0, -20.0]),
        equity=equity,
        initial_capital=initial_capital,
        start_time=start_time,
        end_time=equity.index[-1],
        risk_free_rate=risk_free_rate,
    )


def test_calendar_cagr_exact_365_25_day_interval():
    start = pd.Timestamp("2020-01-01 09:15", tz="Asia/Kolkata")
    end = start + pd.Timedelta(days=365.25)
    bt = backtest(pd.Series([1100.0], index=pd.DatetimeIndex([end])), start_time=start)
    assert bt.cagr() == pytest.approx(0.1)
    # Same time interval and terminal equity, with arbitrary intermediate marks.
    equity = pd.Series(
        [1020.0, 1040.0, 1100.0],
        index=pd.DatetimeIndex(
            [start + pd.Timedelta(days=1), start + pd.Timedelta(days=30), end]
        ),
    )
    assert backtest(equity, start_time=start).cagr() == pytest.approx(0.1)


def test_daily_sharpe_sortino_and_calendar_calmar_are_independent():
    returns = np.array([-0.10, 0.05, -0.02, 0.04])
    times = pd.DatetimeIndex(
        [
            "2024-01-02 15:30",
            "2024-01-03 15:30",
            "2024-01-05 15:30",
            "2024-01-08 15:30",
        ],
        tz="Asia/Kolkata",
    )
    equity = pd.Series(1000 * np.cumprod(1 + returns), index=times)
    start = pd.Timestamp("2024-01-02 09:15", tz="Asia/Kolkata")
    bt = backtest(equity, start_time=start, risk_free_rate=0.06)
    excess = returns - 0.06 / 252
    expected_sharpe = excess.mean() / np.std(excess, ddof=1) * np.sqrt(252)
    expected_sortino = excess.mean() / np.std(excess[excess < 0], ddof=1) * np.sqrt(252)
    years = (times[-1] - start).total_seconds() / (365.25 * 86400)
    expected_cagr = (equity.iloc[-1] / 1000) ** (1 / years) - 1
    peaks = np.maximum.accumulate(np.r_[1000, equity.to_numpy()])[1:]
    expected_mdd = np.min(equity.to_numpy() / peaks - 1)
    assert bt.daily_returns.tolist() == pytest.approx(returns)
    assert bt.sharpe_ratio() == pytest.approx(expected_sharpe)
    assert bt.sortino_ratio() == pytest.approx(expected_sortino)
    assert bt.cagr() == pytest.approx(expected_cagr)
    assert bt.max_drawdown() == pytest.approx(expected_mdd)
    assert bt.calmar_ratio() == pytest.approx(expected_cagr / abs(expected_mdd))


def test_first_period_losses_use_starting_capital_as_peak():
    marks = pd.date_range("2024-01-02 15:30", periods=2, freq="D", tz="Asia/Kolkata")
    equity = pd.Series([900.0, 945.0], index=marks)
    bt = backtest(equity, start_time=marks[0] - pd.Timedelta(hours=6, minutes=15))
    assert bt.drawdowns().tolist() == pytest.approx([-0.1, -0.055])
    assert bt.drawdown_duration() == 2
    assert bt.max_drawdown() == pytest.approx(-0.1)
    assert bt.returns.tolist() == pytest.approx([-0.1, 0.05])


def test_daily_returns_use_last_observed_mark_without_fake_weekend_rows():
    marks = pd.DatetimeIndex(
        [
            "2024-01-05 10:00",
            "2024-01-05 15:30",
            "2024-01-08 10:00",
            "2024-01-08 15:30",
        ],
        tz="Asia/Kolkata",
    )
    bt = backtest(
        pd.Series([900.0, 950.0, 980.0, 1045.0], index=marks),
        start_time="2024-01-05 09:15",
    )
    assert len(bt.daily_returns) == 2
    assert bt.daily_returns.tolist() == pytest.approx([-0.05, 0.1])


def test_bar_start_labels_do_not_misdate_equity_marks():
    starts = pd.date_range(
        "2024-01-02 09:15", periods=2, freq="15min", tz="Asia/Kolkata"
    )
    df = pd.DataFrame(
        {"bar_open": starts, "bar_end": starts + pd.Timedelta(minutes=15)}, index=starts
    )
    equity = pd.Series([1000.0, 1010.0], index=starts)
    bt = run_backtest(
        df,
        equity,
        equity_to_returns(equity, initial_capital=1000),
        pd.Series(dtype=float),
        initial_capital=1000,
    )
    assert bt.start_time == starts[0]
    assert bt.end_time == starts[-1] + pd.Timedelta(minutes=15)


def test_undefined_metrics_are_explicit_nan_and_json_null():
    marks = pd.date_range("2024-01-02 15:30", periods=3, freq="D", tz="Asia/Kolkata")
    bt = backtest(pd.Series([1000.0] * 3, index=marks), start_time="2024-01-02 09:15")
    summary = bt.summary()
    assert np.isnan(summary["sharpe_ratio"])
    assert np.isnan(summary["sortino_ratio"])
    assert np.isnan(summary["calmar_ratio"])
    assert {
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
    } <= bt.undefined_metrics.keys()
    assert json.loads(bt.to_json())["sharpe_ratio"] is None


def test_calendar_interval_and_return_mismatch_are_rejected():
    marks = pd.date_range("2024-01-02 15:30", periods=2, freq="D", tz="Asia/Kolkata")
    equity = pd.Series([1000.0, 1010.0], index=marks)
    with pytest.raises(ValueError, match="timestamp|interval"):
        backtest(equity, start_time=marks[-1])
    with pytest.raises(ValueError, match="reconcile"):
        HalfTrendBacktest(
            pd.Series([0.0, 0.0], index=marks),
            pd.Series([1.0]),
            equity=equity,
            initial_capital=1000,
            start_time=marks[0],
            end_time=marks[-1],
        )


@pytest.mark.parametrize("value", [0, -1, np.inf, np.nan])
def test_invalid_equity_is_rejected(value):
    marks = pd.date_range("2024-01-02 15:30", periods=2, freq="D", tz="Asia/Kolkata")
    with pytest.raises(ValueError):
        backtest(pd.Series([1000.0, value], index=marks), start_time="2024-01-02 09:15")


@pytest.mark.parametrize("value", [np.inf, np.nan, True, "0.05"])
def test_risk_free_rate_validation(value):
    marks = pd.date_range("2024-01-02 15:30", periods=2, freq="D", tz="Asia/Kolkata")
    with pytest.raises((ValueError, TypeError)):
        backtest(
            pd.Series([1000.0, 1010.0], index=marks),
            start_time="2024-01-02 09:15",
            risk_free_rate=value,
        )
