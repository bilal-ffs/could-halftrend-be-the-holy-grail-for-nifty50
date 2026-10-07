"""Explicit optional ledger export using the same cash/quantity model.

Not run during discrepancy verification. Refuses to overwrite existing files.
"""

from pathlib import Path

from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend
from src.trading import generate_trade_ledger


def main():
    from src.run_research import runner_arguments

    options = runner_arguments()
    if options.output_dir is None:
        raise ValueError(
            "An explicit new output directory is required for full exports."
        )
    destination = Path(options.output_dir) / "halftrend_full_trade_ledger.csv"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    minute = load_minute_data(
        options.data_path, duplicate_policy=options.duplicate_policy
    )
    bars = resample_to_15m(minute, minute_label=options.minute_label)
    ledger = generate_trade_ledger(calculate_halftrend(bars))
    destination.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(destination, index=False)
    print(f"Saved {len(ledger)} completed actual-quantity trades to {destination}")


if __name__ == "__main__":
    main()
