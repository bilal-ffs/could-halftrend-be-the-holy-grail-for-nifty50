"""Opt-in OOS runner; use pure evaluate_oos for verification without output writes."""

from pathlib import Path

from src.data import load_minute_data, resample_to_15m
from src.research import evaluate_oos

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"


def run_oos_research(
    *, data_path=DATA_PATH, duplicate_policy="reject", minute_label, output_dir=None
):
    from src.run_research import save_evaluation

    minute = load_minute_data(data_path, duplicate_policy=duplicate_policy)
    bars = resample_to_15m(minute, minute_label=minute_label)
    backtest, result = evaluate_oos(bars)
    if output_dir is not None:
        save_evaluation(backtest, result, Path(output_dir), "halftrend_oos")
    print(backtest.to_dataframe().to_string(index=False))
    return backtest


if __name__ == "__main__":
    from src.run_research import runner_arguments

    options = runner_arguments()
    run_oos_research(**vars(options))
