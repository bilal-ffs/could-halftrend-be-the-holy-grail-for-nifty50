from src.backtest import TRADING_SESSIONS_PER_YEAR, run_backtest
from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend
from src.portfolio import build_equity_curve, equity_to_returns
from src.trading import generate_trade_ledger

DATA_PATH = r"C:\Users\beqmd\Documents\QuantResearch" r"\data\NIFTY_50_minute.csv"


df = load_minute_data(DATA_PATH)
df15 = resample_to_15m(df, minute_label="start").iloc[:1000]

ht = calculate_halftrend(df15)

trade_results = generate_trade_ledger(ht).net_pnl

equity = build_equity_curve(ht)

returns = equity_to_returns(equity)

backtest = run_backtest(
    df=ht,
    equity=equity,
    returns=returns,
    trade_results=trade_results,
)

print("HalfTrend Backtest")
print("==================")
print()
print(
    "Annualization:",
    f"{TRADING_SESSIONS_PER_YEAR:,} daily sessions/year; "
    "CAGR uses elapsed calendar time",
)
print()
print(backtest.to_dataframe().to_string(index=False))
print()
print("JSON:")
print(backtest.to_json())
