from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"


df = resample_to_15m(load_minute_data(DATA_PATH), minute_label="start")

ht = calculate_halftrend(df)


start = "2021-11-10 10:00:00"
end = "2021-11-10 15:15:00"


cols = [
    "open",
    "high",
    "low",
    "close",
    "trend",
    "next_trend",
    "max_low_price",
    "min_high_price",
    "up",
    "down",
    "atr",
    "atr2",
    "dev",
    "halftrend",
    "buy_signal",
    "sell_signal",
]


print(ht.loc[start:end, cols].to_string())
