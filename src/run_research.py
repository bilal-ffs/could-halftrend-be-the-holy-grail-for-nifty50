"""Explicit research runner; existing results are never overwritten."""

import argparse
import json
from pathlib import Path

from src.data import load_minute_data, resample_to_15m
from src.research import evaluate_window, prepare_evaluation_windows

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"


def save_evaluation(backtest, result, output_dir, prefix):
    output_dir = Path(output_dir)
    paths = [
        output_dir / f"{prefix}_{suffix}"
        for suffix in ["summary.json", "equity.csv", "trades.csv"]
    ]
    if any(path.exists() for path in paths):
        raise FileExistsError("Research output already exists; choose a new directory.")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(backtest.to_json(), encoding="utf-8")
    result.equity.to_csv(paths[1])
    result.trades.to_csv(paths[2], index=False)
    (output_dir / f"{prefix}_conventions.json").write_text(
        json.dumps(
            {
                "starting_capital_time": str(result.start_time),
                "ending_equity_time": str(result.end_time),
                "initial_capital": result.initial_capital,
                "cost_bps_per_side": result.cost_bps,
                "slippage": "none simulated",
                "position_reset": "flat, discard prior pending signal",
                "quantity": "fixed within each trade; cash*(1-fee_rate)/entry_open",
                "cagr": "elapsed seconds / (365.25*86400)",
                "ratios": "daily equity, 252 sessions/year",
                "undefined_metrics": backtest.undefined_metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_is_research(
    *, data_path=DATA_PATH, duplicate_policy="reject", minute_label, output_dir=None
):
    minute = load_minute_data(data_path, duplicate_policy=duplicate_policy)
    bars = resample_to_15m(minute, minute_label=minute_label)
    _, is_window, _ = prepare_evaluation_windows(bars)
    backtest, result = evaluate_window(is_window)
    if output_dir is not None:
        save_evaluation(backtest, result, output_dir, "halftrend_is")
    print(backtest.to_dataframe().to_string(index=False))
    return backtest


def runner_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default=DATA_PATH)
    parser.add_argument(
        "--duplicate-policy",
        choices=["reject", "exclude", "first", "last"],
        default="reject",
    )
    parser.add_argument("--minute-label", choices=["start", "end"], required=True)
    parser.add_argument("--output-dir", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    run_is_research(**vars(runner_arguments()))
