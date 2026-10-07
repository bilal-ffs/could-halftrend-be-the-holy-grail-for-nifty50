from __future__ import annotations

import pandas as pd

from src.data import load_minute_data, resample_to_15m
from src.research import prepare_evaluation_windows
from src.trading import generate_trade_ledger

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"

OLD_PATH = "results/halftrend_oos_trades.csv"


def main():

    old = pd.read_csv(OLD_PATH)["trade_results"].reset_index(drop=True)

    minute_data = load_minute_data(DATA_PATH)

    data_15m = resample_to_15m(minute_data, minute_label="start")

    _, _, halftrend = prepare_evaluation_windows(data_15m)

    ledger = generate_trade_ledger(halftrend)

    new = ledger.reset_index(drop=True)

    print()
    print("=" * 80)
    print("OOS TRADE SEQUENCE DIAGNOSTIC")
    print("=" * 80)

    print()
    print(f"Old trade results: {len(old)}")
    print(f"New trade ledger:  {len(new)}")

    # ----------------------------------------------------------
    # Print first 20 old P&Ls.
    # ----------------------------------------------------------
    print()
    print("OLD — first 20 trade P&Ls")
    print("-" * 80)

    for i, pnl in old.head(20).items():
        print(f"{i + 1:4d}  {pnl:12.2f}")

    # ----------------------------------------------------------
    # Print first 20 canonical trades.
    # ----------------------------------------------------------
    print()
    print("NEW — first 20 canonical trades")
    print("-" * 80)

    print(
        new.head(20)[
            [
                "trade",
                "entry_time",
                "entry_price",
                "exit_time",
                "exit_price",
                "pnl_points",
            ]
        ].to_string(index=False)
    )

    # ----------------------------------------------------------
    # Find first P&L sequence difference.
    # ----------------------------------------------------------
    print()
    print("FIRST P&L SEQUENCE DIFFERENCE")
    print("-" * 80)

    common = min(len(old), len(new))

    for i in range(common):

        old_pnl = float(old.iloc[i])
        new_pnl = float(new.iloc[i]["pnl_points"])

        if abs(old_pnl - new_pnl) > 1e-6:

            print(f"Old index: {i + 1}")
            print(f"Old P&L:   {old_pnl:.10f}")

            print()

            print(f"New index: {i + 1}")
            print(f"New P&L:   {new_pnl:.10f}")

            print()

            print("Canonical trade:")
            print(
                new.iloc[i][
                    [
                        "trade",
                        "entry_time",
                        "entry_price",
                        "exit_time",
                        "exit_price",
                        "pnl_points",
                    ]
                ].to_string()
            )

            break

    else:

        print("No P&L difference within the common sequence.")

    # ----------------------------------------------------------
    # Print old P&Ls around the end.
    # ----------------------------------------------------------
    print()
    print("OLD — last 10 P&Ls")
    print("-" * 80)

    print(old.tail(10).to_string())

    print()
    print("NEW — last 10 trades")
    print("-" * 80)

    print(
        new.tail(10)[
            [
                "trade",
                "entry_time",
                "entry_price",
                "exit_time",
                "exit_price",
                "pnl_points",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
