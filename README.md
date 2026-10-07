# HalfTrend research on NIFTY 50

This project asks a simple question: **would following HalfTrend's buy and sell
signals have worked after trading costs?** It studies historical NIFTY 50 prices
from January 2015 to July 2025. It is a research project, not a live trading system.

HalfTrend is a trend-following indicator. Here, the strategy buys when it turns
bullish and exits when it turns bearish. It does not take bearish short positions.
Signals use completed 15-minute candles; trades happen at the next available
candle's opening price. The main setting is amplitude 3, channel deviation 2.

**Overall finding:** costs reduce the apparent profits substantially. Results also
change when we change how the CSV timestamps are interpreted. The simulated
option spreads show small drawdowns, but their profits do not survive all the
cost and pricing assumptions. We have not established a dependable live-trading edge.

## How to read the results

- **Net return** is the total gain or loss after the modeled fees. It is not an
  annual return. Annual growth spreads that result over the actual elapsed years.
- **Largest drop**, also called maximum drawdown, is the biggest fall from a
  previous account-value peak. Starting capital is included as the first peak.
- **Buy-and-hold** means buying the NIFTY price-index equivalent at the beginning
  and holding it. This comparison excludes dividends.
- **Start-labeled / end-labeled** means a timestamp identifies the beginning or
  end of its minute. The Kaggle data does not confirm which meaning is correct.
  We test both, keep their matching comparison dates, and do not choose the winner.
- **Earlier period (IS):** January 2015-January 2022. **Later period (OOS):** January
  2022-July 2025. The later period was examined previously, so it is not a fresh,
  untouched test. Each period starts with a fresh account; the full-history run
  carries its account through the whole period.

## Stage 1: fix the data and calculations

Stage 1 repaired the research process. It was **not a full strategy evaluation**.

| Problem found | What changed |
| --- | --- |
| Dates could be misread | Dates now use day-month-year and Indian local time |
| Four timestamps had conflicting prices | The eight conflicting rows are recorded and explicitly excluded in the research runs |
| Incomplete and evening candles could enter the test | The runs use complete, regular-session candles only |
| Annual returns and trading fees were inconsistent | Growth uses real elapsed time; fees use each actual purchase and sale |
| Trade records did not agree with account value | Cash, holdings, fees and trade records now reconcile independently |
| Later-period signals could lose earlier history | Indicators retain earlier history and are checked against future-data changes |

A small verification sample used only the **first 1,000 retained candles**, from
January 9 to March 11, 2015, with start-labeled minutes:

| Verification sample | Result |
| --- | ---: |
| Starting account | INR 100,000 |
| Ending account, after fees | INR 98,491.96 |
| Net loss | INR 1,508.04 (-1.51%) |
| Completed trades | 16 |
| Total modeled fees, already deducted | INR 1,597.52 |
| Difference between independently checked and recorded account value | INR 0 |
| Tests passing at Stage 1 completion | 85 |

This sample checks that the calculations work; it does not establish long-term
profitability. Earlier result files were preserved rather than presented as
corrected results.

[Stage 1 correction report](DISCREPANCY_RESOLUTION.md) |
[Sample verification evidence](verification/discrepancy_fix/real_data_verification.json)

## Stage 2: index-based futures proxy

This is a **simulation using index prices as a futures proxy**, not a backtest
using actual futures contracts. Each run starts with **INR 500,000 (5 lakh)**.
It uses no borrowing or leverage, allows fractional research units, and keeps the
quantity fixed until the trade closes. Idle cash earns nothing.

The main fee is **5 bps per side = 0.05% of the underlying trade value**, on both
entry and exit. The main run assumes no extra price disadvantage when filling
orders; separate tests add that disadvantage, called slippage.

### Before fees, after fees, and buy-and-hold

| Minute labels | Period | HalfTrend before fees | HalfTrend after fees | Buy-and-hold after fees | HalfTrend largest drop, after fees |
| --- | --- | ---: | ---: | ---: | ---: |
| Start | Earlier | 282.30% | 71.61% | 114.95% | 18.28% |
| End | Earlier | 205.64% | 40.10% | 114.73% | 20.70% |
| Start | Later | 98.66% | 33.16% | 38.56% | 12.61% |
| End | Later | 61.09% | 7.98% | 38.55% | 15.76% |
| Start | Full history | 659.47% | 128.52% | 199.56% | 18.28% |
| End | Full history | 392.34% | 51.29% | 199.41% | 20.70% |

### What happened to INR 5 lakh in the later period?

| Minute labels | Net profit | Ending account | Annual growth | Total fees | Completed trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| Start | INR 165,819.57 | INR 665,819.57 | 8.43% | INR 224,248.57 | 400 |
| End | INR 39,900.86 | INR 539,900.86 | 2.19% | INR 197,014.71 | 400 |

Fees are already deducted from profit. They accumulate across hundreds of trades;
5 bps is not a one-time charge on starting capital. The difference between the
before-fee and after-fee runs also includes changes in later account sizes and
compounding, so that difference is not simply the fees paid.

HalfTrend earned less than buy-and-hold in both interpretations, but experienced
smaller drops: buy-and-hold's later-period largest drop was about **17.12-17.13%**.
Average profit per completed HalfTrend trade was about **INR 415** for start labels
and **INR 100** for end labels.

Adding two index points of adverse slippage per fill lowered later-period returns
to **22.87% (start)** and **-0.39% (end)**. That changes the profitability conclusion.
The five best completed trades accounted for about 68% of net profit with start
labels; with end labels they exceeded the entire net profit because other trades
lost money overall. This describes concentration, not a rerun with those trades removed.

**Stage 2 verdict: inconclusive.** Timestamp meaning and execution costs matter
materially. Actual futures prices, contract changes, funding, lot sizes and
margin requirements were not verified.

### Futures-proxy equity curves

These show account value after fees, using the last available value each session.
Each panel starts at INR 5 lakh. Full history and the later test are separate runs.
Both timestamp interpretations use the same vertical scale within each period.

[![Stage 2 account-value curves comparing HalfTrend with buy-and-hold for both timestamp interpretations](docs/images/futures_proxy_equity.png)](docs/images/futures_proxy_equity.png)

[Full Stage 2 report, annual results and sensitivity tests](results/stage2_futures_proxy_20261007_completed/REPORT.md)

## Stage 3: SIMULATED bullish call calendar spreads

Instead of holding index exposure directly, this strategy **buys a longer-dated
call and sells a shorter-dated call at the same strike**. A call benefits from a
rise in the underlying price, although the combined spread's behavior is more
complex. Every position has both legs; there is no standalone long-call strategy.

The amounts are chosen to approximately balance the options' expected daily time
loss under the pricing model. This is called **theta matching**. It is checked at
entry; a separate version checks once each session and adjusts when the imbalance
becomes large. It is not permanently neutral or risk-free.

Option prices are **SIMULATED**, using historical index prices and a mathematical
pricing model. The main scenario uses approximate 60/30-day maturities, volatility
at 1.2 times the previous 21 sessions' estimate, 6% pricing interest rate and 1%
dividend yield. These are assumptions, not observed option prices or market IV.

Each run starts with INR 5 lakh. The bought call's premium plus both entry fees
cannot exceed 5% of account value. Cash equal to the sold units times the strike
is reserved as conservative collateral; it stays in account value and is not
counted twice. Research units are integers, not exchange lots. Idle cash earns zero.

### Later-period results after fees

| Minute labels | Entry-only net profit | Entry-only return | Daily-check return | Largest drop, both versions | Entry-only total fees |
| --- | ---: | ---: | ---: | ---: | ---: |
| Start | INR 37,386.17 | 7.48% | 7.31% | 1.54% | INR 5,791.11 |
| End | INR 20,245.94 | 4.05% | 3.96% | 2.11% | INR 5,689.42 |

The main fee is **3 bps per side = 0.03% of each leg's premium value**, with no
primary slippage. The study also tests 2 bps fees and 10/25 bps adverse premium
slippage. For example, a fill worth INR 10,000 in premium incurs INR 3 at 3 bps.
Fees apply to purchases, sales and adjustments, not to the index value here.
These are research cost assumptions, not an all-inclusive broker/tax quotation.

Matching time decay improved primary return compared with equal quantities of the
two calls, but increased drawdown. Daily adjustments slightly worsened the primary
later-period result. The main annual growth was only about **1.1-2.1%**, below the
6% comparison rate used for its risk ratios. Smaller drawdowns partly reflect
much lower directional exposure than the futures proxy; this is not an equal-risk
comparison.

At 25 bps adverse premium slippage, both timestamp interpretations lost money.
Changing the assumed volatility relationship between the two maturities could
also reverse profitability. Positive directional exposure is required at entry
and adjustment, but any subsequent drift is recorded rather than hidden.

**Stage 3 verdict: inconclusive robustness.** Real premiums, volatility across
maturities, bid/ask spreads, liquidity, expiries, exchange lots and broker margin
remain unverified. Historical positions did not reach a roll; roll and expiry-gap
handling were verified with synthetic tests.

### Simulated-option equity curves

Solid lines match at entry only; dashed lines use daily checks. They often overlap
because the differences are small. Account value includes both the bought option
and the liability from the sold option, after fees.
The option charts use a different vertical scale from the futures-proxy charts.

[![Stage 3 simulated calendar-spread account-value curves comparing entry-only matching with daily checks for both timestamp interpretations](docs/images/simulated_calendar_equity.png)](docs/images/simulated_calendar_equity.png)

[Full SIMULATED Stage 3 report and sensitivity tests](results/stage3_SIMULATED_calendars_20261007_completed/REPORT.md)

## Data and measurement rules

- Source: the local Kaggle-derived `NIFTY_50_minute.csv`; no market downloads.
  The raw CSV remains unchanged. Conflicting rows are audited; the loader rejects
  them by default and research runs explicitly exclude them.
- Regular hours are 09:15-15:30, Asia/Kolkata: normally **25 complete 15-minute
  candles**. Incomplete candles and evening observations are excluded. Missing
  prices are not invented. Zero volume means volume information is unavailable.
- Start labels retain 64,951 candles; end labels retain 62,349. Each interpretation
  uses its own matching buy-and-hold observations. Neither interpretation is confirmed.
- Indicators and volatility estimates use only information available at the time.
  The earlier and later tests start without positions or pending earlier signals.
  Positions still open at the end are valued at the last price, not forced closed.
- Annual growth uses actual elapsed calendar time. Risk ratios use daily account
  changes and 252 sessions/year. Their annual comparison rate is 0% in Stage 2 and
  6% in Stage 3; additional zero-rate Stage 3 ratios are saved. Undefined ratios
  are reported as unavailable, not replaced with zero. Detailed calculation
  conventions are in the stage reports and source code.

## Reproduce the research

Run from the repository root with the project's Python dependencies installed.
Use a **new output directory** for each research run; existing directories are
rejected. Change the data path to your local CSV location if needed.

```powershell
python -m src.futures_proxy --data "C:/Users/beqmd/Documents/QuantResearch/data/NIFTY_50_minute.csv" --output results/stage2_futures_proxy_repeat
python -m src.simulated_calendars --data "C:/Users/beqmd/Documents/QuantResearch/data/NIFTY_50_minute.csv" --output results/stage3_simulated_calendars_repeat
```

Recreate the README charts from saved results, without rerunning the strategies
(requires Matplotlib):

```powershell
python scripts/plot_equity_curves.py
```

## Verification

At each stage's completion: **85 tests passed in Stage 1, 103 in Stage 2, and 129
in Stage 3**. All 60 Stage 2 runs and all 180 Stage 3 runs were independently
checked against their trade records and account values. Stage 3 option prices
and sensitivities were also independently recalculated. Future-data changes did
not change earlier signals, trades or account values. Ruff and Black checks passed.

```powershell
python -m pytest -q
python -m ruff check .
python -m black --check .
python -m tests.verify_futures_proxy_outputs results/stage2_futures_proxy_20261007_completed
python -m tests.verify_simulated_calendar_outputs results/stage3_SIMULATED_calendars_20261007_completed
```

Detailed trade records, account curves, fees, assumptions and verification logs
are saved with the completed stage reports. Older result files and clearly marked
incomplete attempts remain historical records; they are not the headline results.
