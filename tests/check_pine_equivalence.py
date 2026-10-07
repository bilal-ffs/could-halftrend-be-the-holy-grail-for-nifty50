from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"

AMPLITUDE = 3
CHANNEL_DEVIATION = 2


def pine_reference(df: pd.DataFrame) -> pd.DataFrame:
    """
    Independent reference implementation of the supplied
    HalfTrend Pine Script logic.

    This is intentionally kept separate from src.halftrend.
    """

    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)

    n = len(df)

    trend = np.zeros(n, dtype=int)
    next_trend = np.zeros(n, dtype=int)

    max_low_price = np.full(n, np.nan)
    min_high_price = np.full(n, np.nan)

    up = np.zeros(n, dtype=float)
    down = np.zeros(n, dtype=float)

    halftrend = np.full(n, np.nan)

    buy_signal = np.zeros(n, dtype=bool)
    sell_signal = np.zeros(n, dtype=bool)

    # --------------------------------------------------------------
    # Pine ta.atr(100)
    #
    # True range:
    # max(
    #     high-low,
    #     abs(high-prev_close),
    #     abs(low-prev_close)
    # )
    #
    # Pine's ta.rma() is Wilder's moving average.
    # --------------------------------------------------------------

    prev_close = np.full(n, np.nan)

    if n > 1:
        prev_close[1:] = close[:-1]

    true_range = np.empty(n, dtype=float)

    for i in range(n):
        if i == 0:
            true_range[i] = high[i] - low[i]
        else:
            true_range[i] = max(
                high[i] - low[i],
                abs(high[i] - prev_close[i]),
                abs(low[i] - prev_close[i]),
            )

    atr = np.full(n, np.nan)

    length = 100

    if n >= length:
        atr[length - 1] = true_range[:length].mean()

        for i in range(length, n):
            atr[i] = (atr[i - 1] * (length - 1) + true_range[i]) / length

    atr2 = atr / 2.0

    # --------------------------------------------------------------
    # Stateful HalfTrend logic.
    # --------------------------------------------------------------

    current_trend = 0
    current_next_trend = 0

    current_max_low = low[0]
    current_min_high = high[0]

    current_up = 0.0
    current_down = 0.0

    previous_trend = np.nan
    previous_up = np.nan
    previous_down = np.nan

    for i in range(n):

        # ----------------------------------------------------------
        # Pine highestbars(amplitude) / lowestbars(amplitude)
        #
        # We need the offset of the most recent highest/lowest
        # value inside the rolling window.
        # ----------------------------------------------------------

        start = max(0, i - AMPLITUDE + 1)

        high_window = high[start : i + 1]
        low_window = low[start : i + 1]

        highest_value = np.max(high_window)
        lowest_value = np.min(low_window)

        # Most recent occurrence, matching Pine's offset behavior.
        high_positions = np.where(high_window == highest_value)[0]

        low_positions = np.where(low_window == lowest_value)[0]

        high_index = start + high_positions[-1]
        low_index = start + low_positions[-1]

        high_price = high[high_index]
        low_price = low[low_index]

        # ----------------------------------------------------------
        # Pine ta.sma(high, amplitude)
        # ----------------------------------------------------------

        if i + 1 >= AMPLITUDE:
            highma = high[i - AMPLITUDE + 1 : i + 1].mean()

            lowma = low[i - AMPLITUDE + 1 : i + 1].mean()
        else:
            highma = np.nan
            lowma = np.nan

        previous_low = low[i - 1] if i > 0 else low[i]

        previous_high = high[i - 1] if i > 0 else high[i]

        # ----------------------------------------------------------
        # TREND LOGIC
        # ----------------------------------------------------------

        if current_next_trend == 1:

            current_max_low = max(
                low_price,
                current_max_low,
            )

            if (
                not np.isnan(highma)
                and highma < current_max_low
                and close[i] < previous_low
            ):
                current_trend = 1
                current_next_trend = 0
                current_min_high = high_price

        else:

            current_min_high = min(
                high_price,
                current_min_high,
            )

            if (
                not np.isnan(lowma)
                and lowma > current_min_high
                and close[i] > previous_high
            ):
                current_trend = 0
                current_next_trend = 1
                current_max_low = low_price

        # ----------------------------------------------------------
        # TREND LINE
        # ----------------------------------------------------------

        arrow_up = False
        arrow_down = False

        if current_trend == 0:

            if not np.isnan(previous_trend) and previous_trend != 0:
                current_up = current_down if np.isnan(previous_down) else previous_down

                if not np.isnan(atr2[i]):
                    arrow_up = True

            else:

                if np.isnan(previous_up):
                    current_up = current_max_low
                else:
                    current_up = max(
                        current_max_low,
                        previous_up,
                    )

        else:

            if not np.isnan(previous_trend) and previous_trend != 1:
                current_down = current_up if np.isnan(previous_up) else previous_up

                if not np.isnan(atr2[i]):
                    arrow_down = True

            else:

                if np.isnan(previous_down):
                    current_down = current_min_high
                else:
                    current_down = min(
                        current_min_high,
                        previous_down,
                    )

        if current_trend == 0:
            current_halftrend = current_up
        else:
            current_halftrend = current_down

        # ----------------------------------------------------------
        # Signals
        # ----------------------------------------------------------

        previous_trend_value = previous_trend if not np.isnan(previous_trend) else None

        buy_signal[i] = arrow_up and current_trend == 0 and previous_trend_value == 1

        sell_signal[i] = arrow_down and current_trend == 1 and previous_trend_value == 0

        # ----------------------------------------------------------
        # Store state for next bar.
        # ----------------------------------------------------------

        trend[i] = current_trend
        next_trend[i] = current_next_trend

        max_low_price[i] = current_max_low
        min_high_price[i] = current_min_high

        up[i] = current_up
        down[i] = current_down

        halftrend[i] = current_halftrend

        previous_trend = current_trend
        previous_up = current_up
        previous_down = current_down

    return pd.DataFrame(
        {
            "trend": trend,
            "next_trend": next_trend,
            "halftrend": halftrend,
            "buy_signal": buy_signal,
            "sell_signal": sell_signal,
        },
        index=df.index,
    )


def compare_series(
    name: str,
    reference: pd.Series,
    implementation: pd.Series,
    tolerance: float = 1e-8,
) -> bool:
    """
    Compare two series and print diagnostic information.
    """

    if not reference.index.equals(implementation.index):
        raise ValueError("Reference and implementation indices differ.")
    masks_match = reference.isna().equals(implementation.isna())
    if reference.dtype == bool:
        matches = reference.equals(implementation)
    else:
        valid = reference.notna() & implementation.notna()

        matches = masks_match and np.allclose(
            reference[valid].to_numpy(),
            implementation[valid].to_numpy(),
            atol=tolerance,
            rtol=0,
        )

    print(f"{name:<15} : " f"{'PASS' if matches else 'FAIL'}")

    if not matches:

        if reference.dtype == bool:

            differences = reference != implementation

        else:

            differences = ((reference - implementation).abs() > tolerance) | (
                reference.isna() != implementation.isna()
            )

        diff_count = int(differences.sum())

        print(f"  Differences: {diff_count:,}")

        first = differences[differences].index[0]

        print(f"  First difference: {first}")

        print(
            "  Reference:",
            reference.loc[first],
        )

        print(
            "  Python:",
            implementation.loc[first],
        )

    return matches


def main():
    print("=" * 60)
    print("HALFTREND — PINE / PYTHON EQUIVALENCE")
    print("=" * 60)
    print()

    # --------------------------------------------------------------
    # Load the same 15-minute dataset used by the research.
    # --------------------------------------------------------------

    minute_data = load_minute_data(DATA_PATH)

    data_15m = resample_to_15m(minute_data, minute_label="start")

    # Use the full dataset.
    # --------------------------------------------------------------

    reference = pine_reference(data_15m)

    implementation = calculate_halftrend(data_15m)

    print(f"Bars tested: {len(data_15m):,}")

    print()

    # --------------------------------------------------------------
    # Compare state variables.
    # --------------------------------------------------------------

    results = []

    results.append(
        compare_series(
            "trend",
            reference["trend"],
            implementation["trend"],
        )
    )

    results.append(
        compare_series(
            "next_trend",
            reference["next_trend"],
            implementation["next_trend"],
        )
    )

    results.append(
        compare_series(
            "halftrend",
            reference["halftrend"],
            implementation["halftrend"],
            tolerance=1e-6,
        )
    )

    results.append(
        compare_series(
            "buy_signal",
            reference["buy_signal"],
            implementation["buy_signal"],
        )
    )

    results.append(
        compare_series(
            "sell_signal",
            reference["sell_signal"],
            implementation["sell_signal"],
        )
    )

    print()
    print("-" * 60)

    if all(results):
        print(
            "RESULT: PASS — "
            "Python implementation matches "
            "the independent Pine reference."
        )
    else:
        print(
            "RESULT: FAIL — "
            "Python implementation differs "
            "from the Pine reference."
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
