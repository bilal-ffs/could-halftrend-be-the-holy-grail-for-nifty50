# HalfTrend on NIFTY 50

This repository contains a historical study of a long-only HalfTrend rule on NIFTY 50 minute data from January 2015 to July 2025. The study asks how the recorded results change with transaction costs, execution assumptions, timestamp grouping, and a modeled call calendar spread. It does not establish a reliable trading edge or statistical evidence of alpha.

## Main documents

- [Publication candidate (PDF)](paper/publication_candidate/HalfTrend_NIFTY50_Publication_Candidate.pdf)
- [Editable manuscript (Word)](paper/publication_candidate/HalfTrend_NIFTY50_Publication_Candidate.docx)
- [Supplementary results (PDF)](paper/publication_candidate/Supplementary_Results.pdf)
- [Outstanding author-information checklist](paper/publication_candidate/OUTSTANDING_AUTHOR_INFORMATION.txt)
- [Stage 1 data and accounting corrections](DISCREPANCY_RESOLUTION.md)

The paper is a polished publication candidate, not submission-ready. The exact Kaggle dataset identity and reuse terms, the original HalfTrend source/version, author declarations, and confirmation of public access to the exact research revision remain outstanding.

## What “amplitude 3” means

The reference configuration is **amplitude = 3, channel deviation = 2**. Amplitude is HalfTrend’s lookback in completed 15-minute bars. Channel deviation is a separate channel-scaling setting. Available records do not establish that amplitude 3 was chosen before the historical sample was inspected; comparisons across amplitudes 2–5 are descriptive sensitivity analyses, not independent validation.

The primary results use **start-labeled minutes**, based on the author’s reported personal comparison with TradingView. An end-grouped candle construction is retained as a robustness check. The two groupings produce different candles and exclusions; the end grouping is not presented as the verified timestamp convention.

The January 2022–July 2025 period is called the **previously examined historical holdout** throughout the paper. It was examined previously, so it is not a fresh, untouched, independent out-of-sample test. Earlier-period and holdout portfolios reset to starting capital; full-history runs carry capital and open positions across the split.

## Findings at a glance

### Index-based futures proxy

This is a fully funded, spot-index-based proxy using fractional normalized units. It is **not actual futures trading**: historical futures fills, contract rolls, basis, funding, exchange lots, and margin were not modeled or verified. The primary run starts with INR 500,000 and charges 5 basis points per side on underlying notional. Its headline returns below are total returns after fees, not annual returns.

| Previously examined holdout | Net total return | Maximum drawdown |
| --- | ---: | ---: |
| Start-grouped HalfTrend reference configuration | 33.16% | 12.61% |
| NIFTY 50 price-index buy-and-hold | 38.56% | 17.12% |

The proxy had a lower historical drawdown and a lower total return than buy-and-hold. Exposure is not matched, so this is not evidence of superiority at equal risk. The end grouping earned 7.98% with no slippage; with two adverse index points per fill it returned **−0.39%**.

Separate start-grouping stresses remained positive: two adverse index points per fill reduced the holdout return to **22.87%**, while one additional included-bar execution delay produced **25.23%**. These are separate tests, not a combined stress. The start-grouping result was positive under each of those stresses; the end-grouping result shows that the conclusion is sensitive to candle construction.

### SIMULATED call calendar spread

The option study buys a longer-dated call and sells a nearer-dated call at the same strike. Prices and Greeks are **SIMULATED** with Black–Scholes assumptions; they are not observed option premiums or implied volatilities. The primary fee assumption is 3 basis points per side on each option leg’s premium value.

| Previously examined holdout | Net total return | Maximum drawdown |
| --- | ---: | ---: |
| Entry-only theta matching | 7.48% | 1.54% |
| Daily theta checks | 7.31% | 1.54% |

Entry-only matching returned 7.48% after INR 5,791.11 in modeled fees. Daily checks returned 7.31%. Under 25 basis points of adverse premium slippage per fill, entry-only return was **−2.64%**. The spread had much lower directional exposure than the index proxy, so its lower drawdown is not a matched-exposure comparison. The results are historical model outcomes, not evidence that theta matching creates alpha or that actual option trading would be profitable.

## Charts

The curves below show saved account values after modeled costs. Full-history and previously examined holdout runs are separate where stated; the figures use the saved research outputs.

**Index-based futures proxy**

[![Futures-proxy equity curves](docs/images/futures_proxy_equity.png)](docs/images/futures_proxy_equity.png)

**SIMULATED call calendars**

[![Simulated calendar equity curves](docs/images/simulated_calendar_equity.png)](docs/images/simulated_calendar_equity.png)

## Data and calculation notes

- The research used a local Kaggle-derived `NIFTY_50_minute.csv`. The raw file is not included here; its exact Kaggle URL, version, acquisition date, and reuse rights have not been confirmed.
- Conflicting duplicate timestamp rows, incomplete regular-session bars, and evening observations are excluded. Regular 09:15–15:30 sessions contain 25 complete 15-minute bars. Zero volume is treated as unavailable information.
- The start-grouping run retained 64,951 bars; the end grouping retained 62,349 because the alternate grouping changes which bars are complete. The author’s TradingView timestamp check has not been independently replicated.
- Futures-proxy fees are charged on underlying notional; option fees and slippage are charged on option premium. Index-point slippage and premium-basis-point slippage are distinct assumptions.
- Annual growth uses elapsed calendar time. Sharpe and Sortino use daily marked-to-market equity changes and 252 sessions per year. Stage 2 uses a 0% annual risk-free comparison rate; Stage 3 reports ratios against a 6% annual comparison rate as well as a zero-rate comparison. The 6% Black–Scholes pricing rate does not mean idle cash earns interest.
- The implemented Sortino denominator is the sample standard deviation of negative daily excess returns. It is not the more common root-mean-square downside deviation; the paper and supplement state this convention.
- Maximum-drawdown figures are shown as positive magnitudes in tables. Underwater charts show the same losses as negative values.

## Research reports and saved results

- [Stage 2 proxy report](results/stage2_futures_proxy_20261007_completed/REPORT.md)
- [Stage 3 SIMULATED calendar report](results/stage3_SIMULATED_calendars_20261007_completed/REPORT.md)
- [Complete run tables and research audit supplement](paper/publication_candidate/Supplementary_Results.pdf)

The stage reports and saved results contain the complete scenario tables, annual figures, trade/account records, assumptions, and historical verification evidence. Previously recorded test counts were 85 for Stage 1, 103 for Stage 2, and 129 for Stage 3; those counts describe earlier stage runs and were not rerun for the manuscript revision. Computational cross-checks are not external replication.

## Reproducing the saved research

The commands below run the research and therefore require the local CSV and project dependencies. They write to new output directories; use your own data path.

```powershell
python -m src.futures_proxy --data "C:/path/to/NIFTY_50_minute.csv" --output results/stage2_futures_proxy_repeat
python -m src.simulated_calendars --data "C:/path/to/NIFTY_50_minute.csv" --output results/stage3_simulated_calendars_repeat
```

To rebuild the paper from the already saved result artifacts, use new output directory names. This rebuilds document figures and files; it does not run those strategy commands:

```powershell
python -X utf8 paper/build_review_draft.py --output paper/publication_candidate_rebuild
python -X utf8 paper/export_review_documents.py paper/publication_candidate_rebuild
```

The author-information checklist in the publication-candidate folder lists the remaining items needed before submission. Actual futures execution, observed option premiums, market volatility term structure, liquidity, exchange expiries/lots, broker margin, data rights, and independent replication remain unverified.
