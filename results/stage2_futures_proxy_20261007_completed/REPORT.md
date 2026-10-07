# Stage 2: index-based futures proxy

INCONCLUSIVE: timestamp interpretation changes a directional conclusion.

Benchmark: NIFTY 50 price-index buy-and-hold, excluding dividends. The input
was obtained from Kaggle; producer timestamp semantics are still unconfirmed.

## Primary gross/net and benchmark comparison

| interpretation | period | scenario | total_return | cagr | max_drawdown | expectancy | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| start | IS | gross | 282.30% | 21.13% | -16.29% | 1,762.198 | 801 |
| start | IS | net | 71.61% | 8.03% | -18.28% | 446.995 | 801 |
| start | IS | buy_hold_gross | 115.05% | 11.57% | -38.82% | undefined | 0 |
| start | IS | buy_hold_net | 114.95% | 11.56% | -38.82% | undefined | 0 |
| start | OOS | gross | 98.66% | 21.41% | -9.14% | 1,233.215 | 400 |
| start | OOS | net | 33.16% | 8.43% | -12.61% | 414.549 | 400 |
| start | OOS | buy_hold_gross | 38.62% | 9.67% | -17.12% | undefined | 0 |
| start | OOS | buy_hold_net | 38.56% | 9.66% | -17.12% | undefined | 0 |
| start | FULL | gross | 659.47% | 21.21% | -16.29% | 2,745.524 | 1201 |
| start | FULL | net | 128.52% | 8.16% | -18.28% | 535.057 | 1201 |
| start | FULL | buy_hold_gross | 199.71% | 10.97% | -38.82% | undefined | 0 |
| start | FULL | buy_hold_net | 199.56% | 10.97% | -38.82% | undefined | 0 |
| end | IS | gross | 205.64% | 17.32% | -17.62% | 1,318.174 | 780 |
| end | IS | net | 40.10% | 4.94% | -20.70% | 257.083 | 780 |
| end | IS | buy_hold_gross | 114.84% | 11.55% | -38.97% | undefined | 0 |
| end | IS | buy_hold_net | 114.73% | 11.54% | -38.97% | undefined | 0 |
| end | OOS | gross | 61.09% | 14.43% | -9.43% | 763.594 | 400 |
| end | OOS | net | 7.98% | 2.19% | -15.76% | 99.752 | 400 |
| end | OOS | buy_hold_gross | 38.62% | 9.67% | -17.13% | undefined | 0 |
| end | OOS | buy_hold_net | 38.55% | 9.65% | -17.13% | undefined | 0 |
| end | FULL | gross | 392.34% | 16.32% | -17.62% | 1,662.458 | 1180 |
| end | FULL | net | 51.29% | 4.01% | -20.70% | 217.312 | 1180 |
| end | FULL | buy_hold_gross | 199.56% | 10.97% | -38.97% | undefined | 0 |
| end | FULL | buy_hold_net | 199.41% | 10.96% | -38.97% | undefined | 0 |

## OOS execution robustness (historical holdout)

| interpretation | period | scenario | total_return | cagr | max_drawdown | expectancy | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| start | OOS | net | 33.16% | 8.43% | -12.61% | 414.549 | 400 |
| start | OOS | slip_1 | 27.91% | 7.21% | -13.94% | 348.925 | 400 |
| start | OOS | slip_2 | 22.87% | 5.99% | -15.25% | 285.888 | 400 |
| start | OOS | delay_2 | 25.23% | 6.56% | -13.61% | 315.328 | 400 |
| end | OOS | net | 7.98% | 2.19% | -15.76% | 99.752 | 400 |
| end | OOS | slip_1 | 3.71% | 1.04% | -17.03% | 46.379 | 400 |
| end | OOS | slip_2 | -0.39% | -0.11% | -18.39% | -4.884 | 400 |
| end | OOS | delay_2 | 13.63% | 3.68% | -14.84% | 170.435 | 400 |

1. Amplitude 3 net expectancy at 5 bps each side: see all IS/OOS/FULL values above;
the verdict emphasizes OOS.
2. Buy-and-hold return/drawdown: both comparisons above use identical included bars,
capital and calendar boundaries within each interpretation. Sign-based comparisons
within each interpretation: start: lower return, lower maximum drawdown; end: lower return, lower maximum drawdown.
3. Stability: INCONCLUSIVE: timestamp interpretation changes a directional conclusion. Both interpretations are reported, never selected by
profitability. Slippage and delay scenarios are evaluated independently, not combined.
Amplitudes 2-5 are sensitivity only; no parameter was selected.
4. Actual futures remain unverified: spot-index data do not establish futures fills,
basis, funding, contract rolls, exchange lots, historical margins, liquidity or
executable returns. No options stage is implemented.

## Primary net risk metrics

| interpretation | period | total_return | cagr | sharpe_ratio | sortino_ratio | calmar_ratio | max_drawdown | drawdown_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| start | IS | 71.61% | 8.03% | 0.704 | 0.937 | 0.439 | -18.28% | 16319 |
| start | OOS | 33.16% | 8.43% | 0.892 | 1.381 | 0.669 | -12.61% | 10264 |
| start | FULL | 128.52% | 8.16% | 0.755 | 1.036 | 0.446 | -18.28% | 16319 |
| end | IS | 40.10% | 4.94% | 0.452 | 0.607 | 0.239 | -20.70% | 14216 |
| end | OOS | 7.98% | 2.19% | 0.269 | 0.387 | 0.139 | -15.76% | 13141 |
| end | FULL | 51.29% | 4.01% | 0.397 | 0.541 | 0.193 | -20.70% | 15877 |

Drawdown duration is consecutive included observations; expectancy is INR per
completed trade with this path's changing entry equity, not points or a fixed stake.

## Primary net trade/accounting metrics

| interpretation | period | profit_factor | win_rate | expectancy | trade_count | exposure_observed_bars | total_fees | open_gross_pnl | open_net_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| start | IS | 1.229 | 41.70% | 446.995 | 801 | 53.95% | 467,807.237 | 0.000 | 0.000 |
| start | OOS | 1.254 | 40.00% | 414.549 | 400 | 54.45% | 224,248.570 | 0.000 | 0.000 |
| start | FULL | 1.239 | 41.13% | 535.057 | 1201 | 54.12% | 852,637.049 | 0.000 | 0.000 |
| end | IS | 1.138 | 40.77% | 257.083 | 780 | 54.04% | 404,623.615 | 0.000 | 0.000 |
| end | OOS | 1.063 | 37.50% | 99.752 | 400 | 54.93% | 197,014.714 | 0.000 | 0.000 |
| end | FULL | 1.109 | 39.66% | 217.312 | 1180 | 54.34% | 680,651.077 | 0.000 | 0.000 |

The benchmark remains open. Per-run open-position files contain actual quantity,
mark, gross P&L and entry fee; no hypothetical exit is booked.
Exposure here counts included bars; calendar exposure is also exported in metrics.

## Annual full-period primary net returns (partial 2015/2025)

| year | start | end |
| --- | --- | --- |
| 2015 | -1.19% | -7.47% |
| 2016 | 2.48% | 8.95% |
| 2017 | -0.80% | -2.20% |
| 2018 | 6.50% | 0.76% |
| 2019 | 11.97% | 2.14% |
| 2020 | 31.44% | 19.19% |
| 2021 | 7.65% | 14.52% |
| 2022 | 4.61% | -4.05% |
| 2023 | 14.47% | 6.86% |
| 2024 | 5.18% | 4.27% |
| 2025 | 7.07% | 2.18% |

All IS/OOS annual rows, stresses and sensitivities are in annual_net_performance.csv.

## Amplitude sensitivity, OOS only (no selection)

| interpretation | amplitude | total_return | max_drawdown | expectancy | trade_count |
| --- | --- | --- | --- | --- | --- |
| start | 3 | 33.16% | -12.61% | 414.549 | 400 |
| start | 2 | 4.54% | -19.19% | 42.755 | 531 |
| start | 4 | 19.49% | -17.89% | 285.831 | 341 |
| start | 5 | 2.72% | -19.74% | 44.231 | 307 |
| end | 3 | 7.98% | -15.76% | 99.752 | 400 |
| end | 2 | -10.82% | -21.25% | -102.224 | 529 |
| end | 4 | 2.61% | -21.85% | 38.336 | 341 |
| end | 5 | -2.85% | -24.19% | -47.625 | 299 |

IS/full-period sensitivities are in sensitivity.csv. Amplitude 3 remains primary.

## Five-best-completed-trade concentration, primary net

| interpretation | period | top_five_net_pnl | fraction_of_closed_net | fraction_of_positive_pnl |
| --- | --- | --- | --- | --- |
| start | IS | 215,163.887 | 60.09% | 11.18% |
| start | OOS | 112,519.615 | 67.86% | 13.73% |
| start | FULL | 229,801.887 | 35.76% | 6.90% |
| end | IS | 176,135.650 | 87.84% | 10.63% |
| end | OOS | 97,973.809 | 245.54% | 14.54% |
| end | FULL | 181,307.517 | 70.71% | 6.97% |

All five selected completed trades and their dates/quantity/net P&L are exported in
each run's five_best_completed_trades.csv. This is descriptive concentration:
subsequent equity/sizing is untouched and no exclusion experiment is performed.

## Conventions and limitations

- Every output is an **index-based futures proxy**. Fractional normalized index units
are permitted; no lot rounding or leverage. Entry quantity is
available_cash*(1-fee_rate)/adverse_entry_fill, fixed until exit. This preserves
corrected legacy fee-reserved sizing and leaves available_cash*fee_rate**2 idle
residual cash. Entry notional plus entry fee never exceeds cash. Idle cash earns zero.
- Capital INR 500,000 per run. Gross is zero fees/slippage; net is 5 bps each side of
actual fill notional. Slippage adds 1/2 points to buys and subtracts from sells,
separately from fees. Primary is zero points. Delay 1 executes completed-bar signals
at next available included open; delay 2 at the following included open, including
across gaps. Only signals inside each evaluation are used.
- Fixed IS 2015-01-09 to 2022-01-08; OOS 2022-01-09 to 2025-07-25. IS/OOS start flat and
discard pre-boundary signals; full-period carries state/positions across that
boundary. Indicator state always comes from full history. OOS has been examined
previously and is a historical holdout, not untouched validation.
- Buy-and-hold buys at the first included open with the same fractional sizing and
cost rate, holds fixed quantity, and retains its terminal open position. Gross/net
benchmarks do not charge a fictitious exit fee; strategy open positions likewise
remain marked at the final close. Open gross and net-of-entry-fee P&L are separate
from completed trades.
- Calendar CAGR uses actual first included open to last included bar end (365.25
days/year). Sharpe/Sortino use daily last-mark equity returns, initial capital
included, 252 sessions/year, annual risk-free rate zero. Sortino preserves sample
standard deviation of negative excess returns. Undefined metrics are null with
reasons. Drawdown includes starting capital; duration is consecutive included
15-minute observations underwater. Exposure is both fraction of included bars long and
calendar holding fraction (includes overnight/weekend holding).
- Annual performance uses last observed annual mark against previous year-end (initial
capital for first year); first/last years are partial, with timestamps exported. It is
not annualized calendar CAGR.
- Top-five trade concentration is descriptive, ranked by realized net cash P&L
separately per run. Ratios against signed aggregate closed P&L may exceed one or be
negative. No exclusion/backtest or altered subsequent sizing is performed.
- Conflicting duplicate groups excluded; incomplete regular and evening bars excluded.
Volume unavailable. Start/end minute semantics remain producer-unconfirmed. End labels
shift minutes back one minute before 09:15-anchored resampling; this loses some
first/last bars and changes OHLC and signals. No missing candles fabricated or
profitability-based timestamp choice. Different coverage is exported; benchmarks match
each interpretation exactly. Clock classification lacks an exchange calendar.

Coverage: {
  "start": {
    "minute_label": "start",
    "include_evening": false,
    "partial_bar_policy": "exclude",
    "timezone": "Asia/Kolkata",
    "regular_minutes": 974701,
    "evening_minutes": 612,
    "outside_minutes": 0,
    "partial_bars": 41,
    "excluded_bars": 81,
    "included_bars": 64951,
    "volume_available": false,
    "retained_bars": 64951,
    "first": "2015-01-09 09:15:00+05:30",
    "last": "2025-07-25 15:15:00+05:30"
  },
  "end": {
    "minute_label": "end",
    "include_evening": false,
    "partial_bar_policy": "exclude",
    "timezone": "Asia/Kolkata",
    "regular_minutes": 972101,
    "evening_minutes": 612,
    "outside_minutes": 2600,
    "partial_bars": 5265,
    "excluded_bars": 5295,
    "included_bars": 62349,
    "volume_available": false,
    "retained_bars": 62349,
    "first": "2015-01-09 09:15:00+05:30",
    "last": "2025-07-25 15:00:00+05:30"
  }
}

Every exported run is reconciled independently from completed net P&L plus open gross
P&L minus open entry fee, and from cash/fills. Zero-cost equivalence against corrected
baseline and causal prefix/future perturbations are asserted. See verification.json
and checks/. Raw CSV and pre-existing result hashes are verified unchanged.
Configuration, data hash, exclusions, signals, fills, ledgers, annual metrics,
concentrations and sensitivity are saved here. No commit or push.

Reproduce in a **new** directory:

`python -m src.futures_proxy --data
"C:/Users/beqmd/Documents/QuantResearch/data/NIFTY_50_minute.csv" --output
results/stage2_futures_proxy_repeat`


## Final verification

- 103 pytest tests passed; Ruff, Black and git diff --check passed. Logs and
  exit codes are saved in checks/. No checks were blocked.
- All 60 runs reconcile independently; the exported-artifact checker also
  reconstructs every equity mark from audited closing prices, actual fills,
  fixed quantity, cash and fees, including collateral and fill-delay checks.
- Zero-cost baseline equivalence and prefix/future perturbations passed for
  both timestamp interpretations and all sensitivity amplitudes.
- Raw CSV and all 31 original result files retain their hashes. No commit/push.
- The first incomplete export attempt is separately marked; these are the
  completed results. Annual/report rendering reused saved reconciled outputs
  without repeating simulations or changing configurations.

Independent artifact audit command:

`python -m tests.verify_futures_proxy_outputs results/stage2_futures_proxy_20261007_completed`
