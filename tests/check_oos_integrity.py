"""Prefix/future perturbation checks of historical indicator values and fills."""

import pandas as pd

from src.accounting import simulate_portfolio
from src.halftrend import calculate_halftrend


def check_causality(bars, cutoff, *, cost_bps=5.0):
    full = calculate_halftrend(bars)
    prefix = calculate_halftrend(bars.iloc[:cutoff])
    columns = [c for c in full.columns if c not in bars.columns]
    pd.testing.assert_frame_equal(prefix[columns], full.iloc[:cutoff][columns])
    altered = bars.copy()
    altered.iloc[
        cutoff:, altered.columns.get_indexer(["open", "high", "low", "close"])
    ] = (altered.iloc[cutoff:][["open", "high", "low", "close"]].to_numpy() * 1.5)
    future = calculate_halftrend(altered)
    pd.testing.assert_frame_equal(
        full.iloc[:cutoff][columns], future.iloc[:cutoff][columns]
    )
    before = simulate_portfolio(full, cost_bps=cost_bps)
    after = simulate_portfolio(future, cost_bps=cost_bps)
    sliced = simulate_portfolio(prefix, cost_bps=cost_bps)
    boundary = before.mark_times[cutoff - 1]
    prior_fills = before.fills.loc[before.fills.time < boundary].reset_index(drop=True)
    future_fills = after.fills.loc[after.fills.time < boundary].reset_index(drop=True)
    pd.testing.assert_frame_equal(prior_fills, future_fills)
    pd.testing.assert_frame_equal(prior_fills, sliced.fills.reset_index(drop=True))
    pd.testing.assert_series_equal(before.equity.iloc[:cutoff], sliced.equity)
    return {"cutoff": cutoff, "historical_fills": len(prior_fills), "causal": True}
