from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.costs import (
    apply_transaction_costs,
)
from src.data import load_minute_data, resample_to_15m
from src.research import evaluate_window, prepare_evaluation_windows

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"

INITIAL_CAPITAL = 100_000.0

COST_SCENARIOS = {
    "gross_0bps": 0.0,
    "base_5bps": 5.0,
    "stress_8bps": 8.0,
    "severe_10bps": 10.0,
}

RESULTS_DIR = Path("verification/cost_stress")


def run_scenario(
    df: pd.DataFrame,
    cost_bps: float,
) -> tuple:

    # df is already calculated over full history; NEVER restart at OOS here.
    backtest, result = evaluate_window(
        df, initial_capital=INITIAL_CAPITAL, cost_bps=cost_bps
    )
    ledger = result.trades.copy()
    costed_ledger = apply_transaction_costs(ledger, cost_bps=cost_bps)
    pd.testing.assert_frame_equal(costed_ledger, ledger)
    return backtest, result.equity, ledger, costed_ledger


def save_scenario_results(
    period_name: str,
    scenario_name: str,
    cost_bps: float,
    backtest,
    equity: pd.Series,
    costed_ledger: pd.DataFrame,
) -> None:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    prefix = f"halftrend_" f"{period_name.lower()}_" f"{scenario_name}"

    # --------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------
    summary = json.loads(backtest.to_json())

    summary["cost_bps_per_side"] = cost_bps
    summary["initial_equity"] = INITIAL_CAPITAL
    summary["final_equity"] = float(equity.iloc[-1])

    summary_path = RESULTS_DIR / f"{prefix}_summary.json"

    if summary_path.exists():
        raise FileExistsError(f"Refusing to overwrite {summary_path}")

    with summary_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
        )

    # --------------------------------------------------------------
    # Equity curve
    # --------------------------------------------------------------
    equity_path = RESULTS_DIR / f"{prefix}_equity.csv"

    equity.rename("equity").to_csv(
        equity_path,
        index=True,
    )

    # --------------------------------------------------------------
    # Trade ledger
    # --------------------------------------------------------------
    trades_path = RESULTS_DIR / f"{prefix}_trades.csv"

    costed_ledger.to_csv(
        trades_path,
        index=False,
    )


def print_scenario(
    scenario_name: str,
    cost_bps: float,
    backtest,
    equity: pd.Series,
    costed_ledger: pd.DataFrame,
) -> None:

    summary = backtest.summary()

    total_cost = float(costed_ledger["total_cost"].sum())

    gross_pnl = float(costed_ledger["gross_pnl"].sum())

    net_pnl = float(costed_ledger["net_pnl"].sum())

    print()
    print(f"{scenario_name.upper()} " f"({cost_bps:.0f} bps/side)")
    print("-" * 60)

    print(f"Completed trades: " f"{len(costed_ledger):,}")

    print(f"Gross trade P&L:  " f"{gross_pnl:,.2f}")

    print(f"Transaction costs: " f"{total_cost:,.2f}")

    print(f"Net trade P&L:    " f"{net_pnl:,.2f}")

    print()

    print(f"CAGR:             " f"{summary['cagr']:.4%}")

    print(f"Sharpe:            " f"{summary['sharpe_ratio']:.4f}")

    print(f"Sortino:           " f"{summary['sortino_ratio']:.4f}")

    print(f"Calmar:            " f"{summary['calmar_ratio']:.4f}")

    print(f"Max drawdown:      " f"{summary['max_drawdown']:.4%}")

    print(f"Profit factor:     " f"{summary['profit_factor']:.4f}")

    print(f"Expectancy:        " f"{summary['expectancy']:.4f}")

    print(f"Win rate:          " f"{summary['win_rate']:.4%}")

    print(f"Payoff ratio:      " f"{summary['payoff_ratio']:.4f}")

    print()

    print(f"Final equity:      " f"₹{equity.iloc[-1]:,.2f}")


def run_period(
    period_name: str,
    df: pd.DataFrame,
) -> None:

    print()
    print("=" * 70)
    print(f"HALFTREND — " f"{period_name.upper()} COST STRESS TEST")
    print("=" * 70)

    print(f"Period: " f"{df.index.min()} → {df.index.max()}")

    print(f"Bars: {len(df):,}")

    for scenario_name, cost_bps in COST_SCENARIOS.items():

        (
            backtest,
            equity,
            _ledger,
            costed_ledger,
        ) = run_scenario(
            df,
            cost_bps,
        )

        print_scenario(
            scenario_name,
            cost_bps,
            backtest,
            equity,
            costed_ledger,
        )

        save_scenario_results(
            period_name,
            scenario_name,
            cost_bps,
            backtest,
            equity,
            costed_ledger,
        )


def assert_zero_cost_oos_equivalence(data_15m, oos_halftrend):
    from src.research import evaluate_oos

    _, gross = evaluate_oos(data_15m, initial_capital=INITIAL_CAPITAL)
    scenario, equity, _, ledger = run_scenario(oos_halftrend, 0.0)
    pd.testing.assert_series_equal(equity, gross.equity)
    pd.testing.assert_frame_equal(ledger, gross.trades)
    pd.testing.assert_frame_equal(scenario.portfolio_result.fills, gross.fills)


def main():
    from src.run_research import runner_arguments

    options = runner_arguments()

    print()
    print("=" * 70)
    print("HALFTREND — TRANSACTION COST ROBUSTNESS")
    print("=" * 70)

    minute_data = load_minute_data(
        options.data_path, duplicate_policy=options.duplicate_policy
    )

    data_15m = resample_to_15m(minute_data, minute_label=options.minute_label)

    _, is_data, oos_data = prepare_evaluation_windows(data_15m)
    assert_zero_cost_oos_equivalence(data_15m, oos_data)

    run_period(
        "IS",
        is_data,
    )

    run_period(
        "OOS",
        oos_data,
    )

    print()
    print("=" * 70)
    print("COST STRESS TEST COMPLETE")
    print("=" * 70)

    print()
    print("Saved results under:")
    print(f"  {RESULTS_DIR}")


if __name__ == "__main__":
    main()
