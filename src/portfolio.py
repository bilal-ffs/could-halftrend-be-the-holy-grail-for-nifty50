"""Gross equity wrapper and validated return conversion."""

import numpy as np
import pandas as pd

from src.accounting import simulate_portfolio
from src.validation import finite_scalar, numeric_columns, validate_index


def build_equity_curve(df, initial_capital=100_000.0):
    return simulate_portfolio(df, initial_capital=initial_capital, cost_bps=0.0).equity


def equity_to_returns(equity, *, initial_capital=None):
    """Periodic returns; explicit capital includes a possible first-period loss.

    If omitted, first equity is the starting baseline (legacy wrapper behavior).
    No forward filling missing marks and no replacement of invalid ratios.
    """
    validate_index(equity.index)
    if equity.empty:
        raise ValueError("Equity cannot be empty.")
    numeric_columns(pd.DataFrame({"equity": equity}), ["equity"], positive=True)
    values = equity.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(
            "Equity must be finite and positive; insolvency is not masked."
        )
    baseline = (
        values[0]
        if initial_capital is None
        else finite_scalar(initial_capital, "initial_capital", positive=True)
    )
    returns = equity.pct_change(fill_method=None)
    returns.iloc[0] = values[0] / baseline - 1
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Equity returns are nonfinite.")
    return returns.rename("strategy_return")
