"""Actual-quantity fees on underlying notional, separately from zero slippage."""

import numpy as np

from src.accounting import simulate_portfolio
from src.validation import finite_scalar, numeric_columns


def apply_transaction_costs(trades, cost_bps):
    """Apply fees to an explicit-quantity ledger, never assuming one unit.

    Does not resize historical trades. Cost-dependent sizing must be generated
    by simulate_portfolio; editing a fee rate on an existing ledger alone cannot
    reconstruct a different capital allocation history.
    """
    rate = finite_scalar(cost_bps, "cost_bps", nonnegative=True) / 10000
    numeric_columns(trades, ["quantity", "entry_price", "exit_price"], positive=True)
    numeric_columns(trades, ["gross_pnl"])
    expected = trades.quantity * (trades.exit_price - trades.entry_price)
    if not np.allclose(trades.gross_pnl, expected, rtol=1e-10, atol=1e-8):
        raise ValueError("gross_pnl must match actual quantity and fill prices.")
    result = trades.copy()
    result["entry_notional"] = result.quantity * result.entry_price
    result["exit_notional"] = result.quantity * result.exit_price
    result["entry_cost"] = result.entry_notional * rate
    result["exit_cost"] = result.exit_notional * rate
    result["total_cost"] = result.entry_cost + result.exit_cost
    result["net_pnl"] = result.gross_pnl - result.total_cost
    numeric_columns(
        result,
        [
            "entry_notional",
            "exit_notional",
            "entry_cost",
            "exit_cost",
            "total_cost",
            "net_pnl",
        ],
    )
    return result


def build_cost_adjusted_equity_curve(df, initial_capital, cost_bps):
    """Compatibility wrapper around the shared cash/position/fee calculation."""
    return simulate_portfolio(
        df, initial_capital=initial_capital, cost_bps=cost_bps
    ).equity
