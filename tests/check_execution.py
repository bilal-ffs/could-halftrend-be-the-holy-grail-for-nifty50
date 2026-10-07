from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend
from src.portfolio import build_equity_curve
from src.trading import generate_long_only_trades

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"

INITIAL_CAPITAL = 100_000.0

df = load_minute_data(DATA_PATH)
df15 = resample_to_15m(df, minute_label="start").iloc[:1000]

ht = calculate_halftrend(df15)

positions, trade_results = generate_long_only_trades(ht)

equity = build_equity_curve(
    ht,
    initial_capital=INITIAL_CAPITAL,
)

# --------------------------------------------------------------
# Reconstruct completed-trade compounded equity independently.
# --------------------------------------------------------------

trade_equity = INITIAL_CAPITAL

in_position = False
entry_price = None

completed_trades = 0

for i in range(1, len(ht)):
    if ht["buy_signal"].iloc[i - 1] and not in_position:
        entry_price = float(ht["open"].iloc[i])
        in_position = True

    elif ht["sell_signal"].iloc[i - 1] and in_position:
        exit_price = float(ht["open"].iloc[i])

        trade_return = exit_price / entry_price - 1.0

        trade_equity *= 1.0 + trade_return

        completed_trades += 1

        in_position = False
        entry_price = None


print("Portfolio audit")
print("----------------")
print(f"Completed trades: {completed_trades}")
print(f"Trade P&Ls:       {len(trade_results)}")
print()
print(f"Equity curve:     {equity.iloc[-1]:.10f}")
print(f"Trade compounding:{trade_equity:.10f}")
print()
print(
    "Difference:",
    f"{equity.iloc[-1] - trade_equity:.10f}",
)
