from src.costs import apply_transaction_costs


def main():

    trades = [
        {
            "trade": 1,
            "quantity": 1.0,
            "entry_price": 20_000.0,
            "exit_price": 20_500.0,
            "gross_pnl": 500.0,
        }
    ]

    import pandas as pd

    df = pd.DataFrame(trades)

    for bps in [0, 5, 8, 10]:

        result = apply_transaction_costs(
            df,
            cost_bps=bps,
        )

        row = result.iloc[0]

        print(
            f"{bps:>2} bps/side | "
            f"Entry cost: {row['entry_cost']:.4f} | "
            f"Exit cost: {row['exit_cost']:.4f} | "
            f"Total: {row['total_cost']:.4f} | "
            f"Net P&L: {row['net_pnl']:.4f}"
        )


if __name__ == "__main__":
    main()
