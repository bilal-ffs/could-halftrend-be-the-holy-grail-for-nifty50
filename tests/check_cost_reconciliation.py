"""Audit actual costed ledgers and open positions; no results are regenerated."""

import json

import pandas as pd

from src.accounting import BASE_COST_BPS, reconcile_portfolio, simulate_portfolio
from src.costs import apply_transaction_costs


def check_reconciliation(df, *, cost_bps=BASE_COST_BPS, initial_capital=100_000.0):
    result = simulate_portfolio(df, initial_capital=initial_capital, cost_bps=cost_bps)
    costed = apply_transaction_costs(result.trades, cost_bps)
    pd.testing.assert_frame_equal(costed, result.trades)
    result.trades = costed  # THIS ledger is inspected by independent identities.
    return reconcile_portfolio(result)


if __name__ == "__main__":
    # Hand-verifiable baseline: q=9.995, entry fee=.49975, exit fee=.549725.
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 110.0],
            "close": [100.0, 105.0, 110.0],
            "buy_signal": [True, False, False],
            "sell_signal": [False, True, False],
        },
        index=pd.date_range(
            "2024-01-02 09:15", periods=3, freq="15min", tz="Asia/Kolkata"
        ),
    )
    print(json.dumps(check_reconciliation(df, initial_capital=1000), indent=2))
