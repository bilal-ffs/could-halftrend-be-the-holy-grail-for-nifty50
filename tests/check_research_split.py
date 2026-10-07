from src.data import load_minute_data, resample_to_15m
from src.research import (
    IS_END,
    IS_START,
    OOS_END,
    OOS_START,
    split_is_oos,
)

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"


df = load_minute_data(DATA_PATH)
df15 = resample_to_15m(df, minute_label="start")

is_data, oos_data = split_is_oos(df15)

print("Research split")
print("==============")
print()
print(f"IS:  {is_data.index.min()} → {is_data.index.max()}")
print(f"OOS: {oos_data.index.min()} → {oos_data.index.max()}")
print()
print(f"IS bars:  {len(is_data)}")
print(f"OOS bars: {len(oos_data)}")
print()
print(f"IS configured:  {IS_START} → {IS_END}")
print(f"OOS configured: {OOS_START} → {OOS_END}")
print()
print("Overlap:", len(is_data.index.intersection(oos_data.index)))
