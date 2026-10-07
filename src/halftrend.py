from __future__ import annotations

import numpy as np
import pandas as pd

from src.validation import finite_scalar, numeric_columns, validate_index


def calculate_halftrend(
    df: pd.DataFrame,
    amplitude: int = 3,
    channel_deviation: int = 2,
) -> pd.DataFrame:
    """
    Calculate the HalfTrend indicator using the canonical Pine implementation.

    Parameters
    ----------
    df:
        OHLC DataFrame indexed by datetime. Must contain:
        open, high, low, close.

    amplitude:
        HalfTrend amplitude. Canonical Pine default: 3.

    channel_deviation:
        ATR channel deviation multiplier.
        Canonical Pine default: 2.

    Returns
    -------
    pandas.DataFrame
        Input OHLC data with HalfTrend state, channel values,
        and buy/sell signals.

    Notes
    -----
    This implementation follows the supplied Pine Script:

        atr2 = ta.atr(100) / 2
        dev  = channelDeviation * atr2

    and reproduces its stateful trend logic.
    """
    if isinstance(amplitude, bool) or not isinstance(amplitude, (int, np.integer)):
        raise TypeError("amplitude must be a positive integer.")
    finite_scalar(channel_deviation, "channel_deviation", nonnegative=True)
    validate_index(df.index)
    numeric_columns(df, ["open", "high", "low", "close"], positive=True)
    if (df.high < df[["open", "low", "close"]].max(axis=1)).any() or (
        df.low > df[["open", "high", "close"]].min(axis=1)
    ).any():
        raise ValueError("Inconsistent OHLC bounds.")
    if df.empty:
        raise ValueError("Indicator input cannot be empty.")
    if amplitude < 1:
        raise ValueError("amplitude must be >= 1")

    if channel_deviation < 0:
        raise ValueError("channel_deviation must be >= 0")

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = df.copy()

    high = data["high"].to_numpy(dtype=float)
    low = data["low"].to_numpy(dtype=float)
    close = data["close"].to_numpy(dtype=float)

    n = len(data)

    # ------------------------------------------------------------------
    # Pine equivalents:
    #
    # atr2 = ta.atr(100) / 2
    # dev  = channelDeviation * atr2
    #
    # TradingView ta.atr() uses Wilder's RMA of True Range.
    # ------------------------------------------------------------------

    prev_close = np.empty(n, dtype=float)

    if n:
        prev_close[0] = close[0]
    if n > 1:
        prev_close[1:] = close[:-1]

    true_range = np.maximum.reduce(
        [
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ]
    )

    # Wilder RMA.
    atr = np.full(n, np.nan, dtype=float)

    if n >= 100:
        atr[99] = np.mean(true_range[:100])

        alpha = 1.0 / 100.0

        for i in range(100, n):
            atr[i] = (1.0 - alpha) * atr[i - 1] + alpha * true_range[i]

    atr2 = atr / 2.0
    dev = channel_deviation * atr2

    # ------------------------------------------------------------------
    # Pine:
    #
    # highPrice = high[abs(ta.highestbars(amplitude))]
    # lowPrice  = low[abs(ta.lowestbars(amplitude))]
    #
    # These are the highest/lowest values over the amplitude window.
    # ------------------------------------------------------------------

    high_price = np.full(n, np.nan, dtype=float)
    low_price = np.full(n, np.nan, dtype=float)

    for i in range(n):
        start = max(0, i - amplitude + 1)

        high_price[i] = np.max(high[start : i + 1])
        low_price[i] = np.min(low[start : i + 1])

    # ------------------------------------------------------------------
    # Pine:
    #
    # highma = ta.sma(high, amplitude)
    # lowma  = ta.sma(low, amplitude)
    # ------------------------------------------------------------------

    high_ma = data["high"].rolling(amplitude).mean().to_numpy(dtype=float)

    low_ma = data["low"].rolling(amplitude).mean().to_numpy(dtype=float)

    # ------------------------------------------------------------------
    # Stateful HalfTrend variables.
    #
    # Pine:
    #
    # var int trend = 0
    # var int nextTrend = 0
    # var float maxLowPrice = nz(low[1], low)
    # var float minHighPrice = nz(high[1], high)
    #
    # var float up = 0.0
    # var float down = 0.0
    # ------------------------------------------------------------------

    trend = np.zeros(n, dtype=int)
    next_trend = np.zeros(n, dtype=int)

    max_low_price = np.full(n, np.nan, dtype=float)
    min_high_price = np.full(n, np.nan, dtype=float)

    up = np.zeros(n, dtype=float)
    down = np.zeros(n, dtype=float)

    atr_high = np.zeros(n, dtype=float)
    atr_low = np.zeros(n, dtype=float)

    arrow_up = np.full(n, np.nan, dtype=float)
    arrow_down = np.full(n, np.nan, dtype=float)

    halftrend = np.full(n, np.nan, dtype=float)

    buy_signal = np.zeros(n, dtype=bool)
    sell_signal = np.zeros(n, dtype=bool)

    for i in range(n):
        # Pine:
        # maxLowPrice = nz(low[1], low)
        # minHighPrice = nz(high[1], high)
        #
        # At subsequent bars these values are state variables,
        # so only initialize them on the first bar.
        if i == 0:
            max_low_price[i] = low[i]
            min_high_price[i] = high[i]
        else:
            max_low_price[i] = max_low_price[i - 1]
            min_high_price[i] = min_high_price[i - 1]

        # Pine `var` state persists from the previous bar.
        if i > 0:
            trend[i] = trend[i - 1]
            next_trend[i] = next_trend[i - 1]

        # Previous-bar values.
        previous_low = low[i - 1] if i > 0 else low[i]
        previous_high = high[i - 1] if i > 0 else high[i]

        previous_trend = trend[i - 1] if i > 0 else np.nan
        previous_up = up[i - 1] if i > 0 else np.nan
        previous_down = down[i - 1] if i > 0 else np.nan

        # --------------------------------------------------------------
        # TREND LOGIC
        #
        # if nextTrend == 1
        #     maxLowPrice := max(lowPrice, maxLowPrice)
        #     if highma < maxLowPrice and close < low[1]
        #         trend := 1
        #         nextTrend := 0
        #         minHighPrice := highPrice
        #
        # else
        #     minHighPrice := min(highPrice, minHighPrice)
        #     if lowma > minHighPrice and close > high[1]
        #         trend := 0
        #         nextTrend := 1
        #         maxLowPrice := lowPrice
        # --------------------------------------------------------------

        if next_trend[i] == 1:
            max_low_price[i] = max(
                low_price[i],
                max_low_price[i],
            )

            if (
                not np.isnan(high_ma[i])
                and high_ma[i] < max_low_price[i] - 1e-10
                and close[i] < previous_low
            ):
                trend[i] = 1
                next_trend[i] = 0
                min_high_price[i] = high_price[i]

        else:
            min_high_price[i] = min(
                high_price[i],
                min_high_price[i],
            )

            if (
                not np.isnan(low_ma[i])
                and low_ma[i] > min_high_price[i] + 1e-10
                and close[i] > previous_high
            ):
                trend[i] = 0
                next_trend[i] = 1
                max_low_price[i] = low_price[i]

        # --------------------------------------------------------------
        # TREND LINE
        #
        # if trend == 0:
        #     if trend[1] != 0:
        #         up := na(down[1]) ? down : down[1]
        #         arrowUp := up - atr2
        #     else
        #         up := na(up[1]) ? maxLowPrice : max(maxLowPrice, up[1])
        #
        # else:
        #     if trend[1] != 1:
        #         down := na(up[1]) ? up : up[1]
        #         arrowDown := down + atr2
        #     else
        #         down := na(down[1]) ? minHighPrice : min(minHighPrice, down[1])
        # --------------------------------------------------------------

        if trend[i] == 0:
            if i > 0 and previous_trend != 0:
                if np.isnan(previous_down):
                    up[i] = down[i]
                else:
                    up[i] = previous_down

                arrow_up[i] = up[i] - atr2[i]

            else:
                if i == 0 or np.isnan(previous_up):
                    up[i] = max_low_price[i]
                else:
                    up[i] = max(
                        max_low_price[i],
                        previous_up,
                    )

            atr_high[i] = up[i] + dev[i]
            atr_low[i] = up[i] - dev[i]

        else:
            if i > 0 and previous_trend != 1:
                if np.isnan(previous_up):
                    down[i] = up[i]
                else:
                    down[i] = previous_up

                arrow_down[i] = down[i] + atr2[i]

            else:
                if i == 0 or np.isnan(previous_down):
                    down[i] = min_high_price[i]
                else:
                    down[i] = min(
                        min_high_price[i],
                        previous_down,
                    )

            atr_high[i] = down[i] + dev[i]
            atr_low[i] = down[i] - dev[i]

        # Pine:
        # ht = trend == 0 ? up : down
        halftrend[i] = up[i] if trend[i] == 0 else down[i]

        # Pine:
        # buySignal =
        #     not na(arrowUp)
        #     and trend == 0
        #     and trend[1] == 1
        #
        # sellSignal =
        #     not na(arrowDown)
        #     and trend == 1
        #     and trend[1] == 0

        if i > 0:
            buy_signal[i] = (
                not np.isnan(arrow_up[i]) and trend[i] == 0 and trend[i - 1] == 1
            )

            sell_signal[i] = (
                not np.isnan(arrow_down[i]) and trend[i] == 1 and trend[i - 1] == 0
            )

    result = data.copy()

    result["trend"] = trend
    result["next_trend"] = next_trend
    result["max_low_price"] = max_low_price
    result["min_high_price"] = min_high_price
    result["up"] = up
    result["down"] = down
    result["atr"] = atr
    result["atr2"] = atr2
    result["dev"] = dev
    result["atr_high"] = atr_high
    result["atr_low"] = atr_low
    result["halftrend"] = halftrend
    result["arrow_up"] = arrow_up
    result["arrow_down"] = arrow_down
    result["buy_signal"] = buy_signal
    result["sell_signal"] = sell_signal

    return result
