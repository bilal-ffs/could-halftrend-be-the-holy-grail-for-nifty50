"""Trade and position wrappers around the shared research accounting model."""

from src.accounting import simulate_portfolio


def generate_trade_ledger(df, *, initial_capital=100_000.0, cost_bps=0.0):
    """Actual-quantity cash ledger; pnl_points retains per-unit price changes."""
    return simulate_portfolio(
        df, initial_capital=initial_capital, cost_bps=cost_bps
    ).trades


def generate_long_only_trades(df):
    """Legacy points interface; research runners use the actual cash ledger."""
    result = simulate_portfolio(df)
    return result.positions, result.trades.pnl_points.reset_index(drop=True).rename(
        "trade_results"
    )
