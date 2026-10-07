"""Plot saved research equity; no strategies or results are recalculated."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter


def daily_curve(path):
    """Use actual session-end equity, preceded by the recorded starting capital."""
    frame = (
        pd.read_csv(path / "equity.csv", index_col=0)
        if (path / "equity.csv").exists()
        else pd.read_csv(path / "equity.csv.gz", index_col=0)
    )
    times = pd.to_datetime(frame.mark_time).dt.tz_convert("Asia/Kolkata")
    curve = pd.Series(frame.equity.to_numpy(), index=pd.DatetimeIndex(times))
    daily = curve.groupby(curve.index.normalize()).tail(1)
    metrics = json.loads((path / "metrics.json").read_text())
    assert abs(daily.iloc[-1] - metrics["final_equity"]) < 1e-6
    start = pd.Timestamp(metrics["start_time"]).tz_convert("Asia/Kolkata")
    daily = pd.concat([pd.Series([500_000.0], index=[start]), daily])
    daily.index = daily.index.tz_localize(None)
    assert daily.index.is_monotonic_increasing
    assert daily.notna().all() and (daily > 0).all()
    return daily


def plot(stage2, stage3, output, options):
    fig, axes = plt.subplots(
        2, 2, figsize=(13, 8), constrained_layout=True, sharey="col"
    )
    for row, interpretation in enumerate(["start", "end"]):
        for column, period in enumerate(["FULL", "OOS"]):
            ax = axes[row, column]
            if options:
                root = stage3 / interpretation / "primary"
                lines = [
                    (root / "entry" / period, "Match at entry only", "#176b87", "-"),
                    (root / "daily" / period, "Daily checks", "#d16b18", "--"),
                ]
            else:
                root = stage2 / interpretation / "a3" / period
                lines = [
                    (root / "net", "HalfTrend after fees", "#176b87", "-"),
                    (root / "buy_hold_net", "Buy-and-hold after fees", "#838b38", "--"),
                ]
            for path, name, color, style in lines:
                curve = daily_curve(path)
                ax.plot(
                    curve.index,
                    curve / 100_000,
                    label=name,
                    color=color,
                    linestyle=style,
                    linewidth=1.7,
                )
            window = (
                "Full history: 2015-2025"
                if period == "FULL"
                else "Later test: 2022-2025"
            )
            ax.set_title(f"{interpretation.capitalize()}-labeled minutes | {window}")
            ax.set_ylabel("Account value (INR lakh)")
            decimals = 2 if options else 1
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda x, _: f"{x:.{decimals}f}")
            )
            ax.xaxis.set_major_locator(mdates.YearLocator(2 if period == "FULL" else 1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            ax.axhline(5, color="#626262", linewidth=0.8, alpha=0.6)
            ax.grid(alpha=0.2)
            ax.legend(loc="upper left", fontsize=9)
    name = "SIMULATED call calendar spreads" if options else "Index-based futures proxy"
    fig.suptitle(
        f"{name}: account value after fees\n"
        "Each panel starts at INR 5 lakh; actual session-end marks, not forecasts",
        fontsize=14,
    )
    file = output / (
        "simulated_calendar_equity.png" if options else "futures_proxy_equity.png"
    )
    fig.savefig(file, dpi=170, facecolor="white")
    plt.close(fig)
    print(f"Saved {file}; final chart values match saved metrics.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage2",
        type=Path,
        default=Path("results/stage2_futures_proxy_20261007_completed"),
    )
    parser.add_argument(
        "--stage3",
        type=Path,
        default=Path("results/stage3_SIMULATED_calendars_20261007_completed"),
    )
    parser.add_argument("--output", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for options in [False, True]:
        plot(args.stage2, args.stage3, args.output, options)


if __name__ == "__main__":
    main()
