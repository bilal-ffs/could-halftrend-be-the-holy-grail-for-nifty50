"""Calendar CAGR and daily marked-to-market risk statistics."""

import json

import numpy as np
import pandas as pd
from quanttools.statistics import (
    average_loss,
    average_win,
    expectancy,
    payoff_ratio,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)

from src.portfolio import equity_to_returns
from src.validation import finite_scalar, local_index, numeric_columns, validate_index

TRADING_SESSIONS_PER_YEAR = 252
NSE_15M_PERIODS_PER_YEAR = 252 * 25  # descriptive only, NOT ratio annualization
SECONDS_PER_YEAR = 365.25 * 86400


class HalfTrendBacktest:
    """Calendar growth and daily ratios, with an explicit initial equity timestamp.

    risk_free_rate is annual, arithmetically divided by 252 for daily ratios.
    Sortino preserves QuantTools' sample std of negative daily excess observations.
    Undefined metrics are NaN, with reasons in undefined_metrics, not zero.
    """

    def __init__(
        self,
        returns,
        trade_results,
        *,
        equity,
        initial_capital,
        start_time,
        end_time,
        mark_times=None,
        risk_free_rate=0.0,
    ):
        self.initial_capital = finite_scalar(
            initial_capital, "initial_capital", positive=True
        )
        self.risk_free_rate = finite_scalar(risk_free_rate, "risk_free_rate")
        validate_index(equity.index)
        if not equity.index.equals(returns.index):
            raise ValueError("Equity and returns must share the same index.")
        expected = equity_to_returns(equity, initial_capital=self.initial_capital)
        if not np.allclose(returns, expected, rtol=1e-10, atol=1e-12):
            raise ValueError(
                "Returns do not reconcile with equity and starting capital."
            )
        self.equity = equity.copy()
        self.returns = expected
        if not isinstance(trade_results, pd.Series):
            raise TypeError("trade_results must be a Series of cash net P&L.")
        numeric_columns(
            pd.DataFrame({"trade_results": trade_results}), ["trade_results"]
        )
        self.trade_results = trade_results.astype(float).copy()
        if not np.isfinite(self.trade_results.to_numpy()).all():
            raise ValueError("Trade P&L must be finite.")

        def stamp(value):
            time = pd.Timestamp(value)
            if pd.isna(time):
                raise ValueError("Equity timestamps must be valid.")
            return (
                time.tz_localize("Asia/Kolkata")
                if time.tz is None
                else time.tz_convert("Asia/Kolkata")
            )

        self.start_time = stamp(start_time)
        self.end_time = stamp(end_time)
        marks = local_index(
            equity.index if mark_times is None else pd.DatetimeIndex(mark_times)
        )
        if (
            len(marks) != len(equity)
            or marks[0] < self.start_time
            or marks[-1] != self.end_time
        ):
            raise ValueError("Mark timestamps must span the specified equity interval.")
        if self.end_time <= self.start_time:
            raise ValueError("Ending equity timestamp must be after starting capital.")
        daily = (
            pd.Series(equity.to_numpy(), index=marks).groupby(marks.normalize()).last()
        )
        self.daily_returns = equity_to_returns(
            daily, initial_capital=self.initial_capital
        )
        self.undefined_metrics = {}

    def _metric(self, name, function, *args, **kwargs):
        try:
            value = float(function(*args, **kwargs))
            if not np.isfinite(value):
                raise ValueError("Result is nonfinite.")
        except ValueError as error:
            self.undefined_metrics[name] = str(error)
            return float("nan")
        self.undefined_metrics.pop(name, None)
        return value

    def cagr(self):
        years = (self.end_time - self.start_time).total_seconds() / SECONDS_PER_YEAR
        with np.errstate(over="ignore", invalid="ignore"):
            value = np.expm1(
                np.log(self.equity.iloc[-1] / self.initial_capital) / years
            )
        return self._metric("cagr", lambda: value)

    def sharpe_ratio(self):
        return self._metric(
            "sharpe_ratio",
            sharpe_ratio,
            self.daily_returns,
            risk_free_rate=self.risk_free_rate,
            periods_per_year=252,
        )

    def sortino_ratio(self):
        return self._metric(
            "sortino_ratio",
            sortino_ratio,
            self.daily_returns,
            risk_free_rate=self.risk_free_rate,
            periods_per_year=252,
        )

    def drawdowns(self):
        peaks = self.equity.cummax().clip(lower=self.initial_capital)
        return self.equity / peaks - 1

    def max_drawdown(self):
        return float(self.drawdowns().min())

    def drawdown_duration(self):
        longest = current = 0
        for value in self.drawdowns():
            current = current + 1 if value < 0 else 0
            longest = max(longest, current)
        return longest

    def calmar_ratio(self):
        drawdown = abs(self.max_drawdown())

        def ratio():
            if drawdown == 0:
                raise ValueError("Maximum drawdown is zero.")
            return self.cagr() / drawdown

        return self._metric("calmar_ratio", ratio)

    def summary(self):
        summary = {
            "cagr": self.cagr(),
            "sharpe_ratio": self.sharpe_ratio(),
            "sortino_ratio": self.sortino_ratio(),
            "calmar_ratio": self.calmar_ratio(),
            "max_drawdown": self.max_drawdown(),
            "drawdown_duration": self.drawdown_duration(),
        }
        for name, fn in [
            ("profit_factor", profit_factor),
            ("expectancy", expectancy),
            ("win_rate", win_rate),
            ("average_win", average_win),
            ("average_loss", average_loss),
            ("payoff_ratio", payoff_ratio),
        ]:
            summary[name] = self._metric(name, fn, self.trade_results)
        return summary

    def to_dataframe(self):
        return pd.DataFrame(self.summary().items(), columns=["Metric", "Value"])

    def to_json(self):
        summary = self.summary()
        return json.dumps(
            {
                key: None if not np.isfinite(value) else value
                for key, value in summary.items()
            },
            indent=4,
            allow_nan=False,
        )


def run_backtest(
    df,
    equity,
    returns,
    trade_results,
    *,
    initial_capital=100_000.0,
    start_time=None,
    end_time=None,
    risk_free_rate=0.0,
):
    """Start capital is at first observed bar open; last equity is at last bar end.

    Callers can override timestamps explicitly. Bar labels themselves are starts;
    resampling provides bar_open/bar_end so marks aren't misdated by 15 minutes.
    """
    if not df.index.equals(equity.index) or not df.index.equals(returns.index):
        raise ValueError("Data, equity and returns must share the same index.")
    starts = local_index(
        pd.DatetimeIndex(df.bar_open) if "bar_open" in df else df.index
    )
    marks = (
        local_index(pd.DatetimeIndex(df.bar_end))
        if "bar_end" in df
        else starts + pd.Timedelta(minutes=15)
    )
    return HalfTrendBacktest(
        returns,
        trade_results,
        equity=equity,
        initial_capital=initial_capital,
        start_time=starts[0] if start_time is None else start_time,
        end_time=marks[-1] if end_time is None else end_time,
        mark_times=marks,
        risk_free_rate=risk_free_rate,
    )
