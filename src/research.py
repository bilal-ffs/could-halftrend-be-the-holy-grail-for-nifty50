from __future__ import annotations

import pandas as pd

IS_START = "2015-01-09"
IS_END = "2022-01-08"

OOS_START = "2022-01-09"
OOS_END = "2025-07-25"


def split_is_oos(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split the dataset into fixed in-sample and out-of-sample periods.

    In-Sample:
        2015-01-09 → 2022-01-08

    Out-of-Sample:
        2022-01-09 → 2025-07-25

    Parameters
    ----------
    df:
        OHLCV DataFrame indexed by datetime.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame]
        In-sample and out-of-sample datasets.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame must have a DatetimeIndex.")

    if not df.index.is_unique or df.index.hasnans:
        raise ValueError("Data timestamps must be unique and valid.")

    if not df.index.is_monotonic_increasing:
        raise ValueError("DataFrame index must be sorted.")

    is_data = df.loc[IS_START:IS_END].copy()

    oos_data = df.loc[OOS_START:OOS_END].copy()

    if is_data.empty:
        raise ValueError("In-sample dataset is empty.")

    if oos_data.empty:
        raise ValueError("Out-of-sample dataset is empty.")

    if is_data.index.max() >= oos_data.index.min():
        raise ValueError("In-sample and OOS periods overlap.")

    return is_data, oos_data


def prepare_evaluation_windows(data_15m, *, amplitude=3, channel_deviation=2):
    """Calculate once over full history, then slice fixed IS/OOS windows.

    Historical indicator state is retained; evaluation portfolios start flat,
    discard pre-boundary pending signals, and do not liquidate at the end.
    """
    from src.halftrend import calculate_halftrend

    is_data, oos_data = split_is_oos(data_15m)
    full = calculate_halftrend(
        data_15m, amplitude=amplitude, channel_deviation=channel_deviation
    )
    return full, full.loc[is_data.index].copy(), full.loc[oos_data.index].copy()


def evaluate_window(
    halftrend, *, initial_capital=100_000.0, cost_bps=0.0, risk_free_rate=0.0
):
    """One evaluation convention for gross runners and every cost scenario."""
    from src.accounting import reconcile_portfolio, simulate_portfolio
    from src.backtest import run_backtest
    from src.portfolio import equity_to_returns

    result = simulate_portfolio(
        halftrend, initial_capital=initial_capital, cost_bps=cost_bps
    )
    reconcile_portfolio(result)
    returns = equity_to_returns(result.equity, initial_capital=initial_capital)
    backtest = run_backtest(
        halftrend,
        result.equity,
        returns,
        result.trades.net_pnl,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
    )
    backtest.portfolio_result = result
    return backtest, result


def evaluate_oos(
    data_15m, *, initial_capital=100_000.0, cost_bps=0.0, risk_free_rate=0.0
):
    """Pure main OOS path: full historical state, flat at fixed OOS boundary."""
    _, _, oos = prepare_evaluation_windows(data_15m)
    return evaluate_window(
        oos,
        initial_capital=initial_capital,
        cost_bps=cost_bps,
        risk_free_rate=risk_free_rate,
    )
