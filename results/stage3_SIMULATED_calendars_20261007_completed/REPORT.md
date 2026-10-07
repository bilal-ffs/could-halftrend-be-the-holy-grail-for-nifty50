# Stage 3: SIMULATED bullish call calendar spread

All premiums, Greeks and option results are **SIMULATED** on the actual local
NIFTY_50_minute.csv path. No observed option prices or standalone long calls.
This strategy is approximately theta-neutral under the model at construction;
it is not permanently theta-neutral or risk-free.

## Primary results, predeclared amplitude 3 / volatility 1.2 / 3 bps / zero slippage

| interpretation | period | mode | total_return | cagr | sharpe_ratio | max_drawdown | expectancy | signal_count | spread_count | rolls | adjustments | fees |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| end | FULL | daily | 13.89% | 1.24% | -2.501 | -2.52% | 59.301 | 1171 | 1171 | 0 | 13 | 17,878.930 |
| end | IS | daily | 10.06% | 1.38% | -2.397 | -2.52% | 65.232 | 771 | 771 | 0 | 6 | 11,610.488 |
| end | OOS | daily | 3.96% | 1.10% | -2.652 | -2.11% | 49.535 | 400 | 400 | 0 | 7 | 5,693.819 |
| end | FULL | entry | 14.00% | 1.25% | -2.493 | -2.54% | 59.792 | 1171 | 1171 | 0 | 0 | 17,864.447 |
| end | IS | entry | 10.04% | 1.38% | -2.396 | -2.54% | 65.129 | 771 | 771 | 0 | 0 | 11,603.811 |
| end | OOS | entry | 4.05% | 1.13% | -2.635 | -2.11% | 50.615 | 400 | 400 | 0 | 0 | 5,689.416 |
| end | FULL | equal_control | 2.37% | 0.22% | -8.982 | -2.02% | 10.125 | 1169 | 1169 | 0 | 0 | 18,218.585 |
| end | IS | equal_control | 1.07% | 0.15% | -9.078 | -2.02% | 6.957 | 771 | 771 | 0 | 0 | 12,232.996 |
| end | OOS | equal_control | 1.28% | 0.36% | -8.785 | -0.71% | 16.132 | 398 | 398 | 0 | 0 | 5,923.870 |
| start | FULL | daily | 21.15% | 1.84% | -2.239 | -2.59% | 88.720 | 1192 | 1192 | 0 | 11 | 18,843.647 |
| start | IS | daily | 12.99% | 1.76% | -2.253 | -2.59% | 82.025 | 792 | 792 | 0 | 4 | 12,236.916 |
| start | OOS | daily | 7.31% | 2.02% | -2.171 | -1.54% | 91.422 | 400 | 400 | 0 | 6 | 5,790.566 |
| start | FULL | entry | 21.06% | 1.83% | -2.238 | -2.59% | 88.343 | 1192 | 1192 | 0 | 0 | 18,828.057 |
| start | IS | entry | 13.08% | 1.77% | -2.245 | -2.59% | 82.566 | 792 | 792 | 0 | 0 | 12,229.863 |
| start | OOS | entry | 7.48% | 2.06% | -2.140 | -1.54% | 93.465 | 400 | 400 | 0 | 0 | 5,791.115 |
| start | FULL | equal_control | 2.58% | 0.24% | -9.010 | -1.42% | 10.810 | 1192 | 1192 | 0 | 0 | 18,570.843 |
| start | IS | equal_control | 1.18% | 0.17% | -9.307 | -1.42% | 7.442 | 792 | 792 | 0 | 0 | 12,534.225 |
| start | OOS | equal_control | 1.40% | 0.39% | -8.436 | -0.59% | 17.506 | 400 | 400 | 0 | 0 | 5,973.214 |

### Additional risk and signal-level statistics

| interpretation | period | mode | sortino_ratio | calmar_ratio | sharpe_zero_rf | drawdown_duration | profit_factor | win_rate | open_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| end | FULL | daily | -3.919 | 0.493 | 0.677 | 10050 | 1.208 | 39.20% | 0.000 |
| end | IS | daily | -3.657 | 0.548 | 0.742 | 8192 | 1.227 | 39.43% | 0.000 |
| end | OOS | daily | -4.372 | 0.522 | 0.618 | 9858 | 1.193 | 38.75% | 0.000 |
| end | FULL | entry | -3.912 | 0.492 | 0.681 | 10026 | 1.209 | 39.20% | 0.000 |
| end | IS | entry | -3.660 | 0.541 | 0.740 | 8201 | 1.227 | 39.43% | 0.000 |
| end | OOS | entry | -4.353 | 0.534 | 0.630 | 9858 | 1.197 | 38.75% | 0.000 |
| end | FULL | equal_control | -12.513 | 0.110 | 0.356 | 31385 | 1.127 | 43.28% | 0.000 |
| end | IS | equal_control | -11.865 | 0.076 | 0.245 | 10382 | 1.082 | 43.71% | 0.000 |
| end | OOS | equal_control | -14.298 | 0.512 | 0.575 | 12892 | 1.229 | 42.46% | 0.000 |
| start | FULL | daily | -3.429 | 0.708 | 1.018 | 6981 | 1.320 | 40.60% | 0.000 |
| start | IS | daily | -3.304 | 0.679 | 0.967 | 6981 | 1.301 | 40.40% | 0.000 |
| start | OOS | daily | -3.738 | 1.311 | 1.122 | 4781 | 1.360 | 41.00% | 0.000 |
| start | FULL | entry | -3.428 | 0.705 | 1.012 | 6981 | 1.318 | 40.60% | 0.000 |
| start | IS | entry | -3.296 | 0.683 | 0.972 | 6981 | 1.303 | 40.40% | 0.000 |
| start | OOS | entry | -3.696 | 1.340 | 1.143 | 4781 | 1.368 | 41.00% | 0.000 |
| start | FULL | equal_control | -12.482 | 0.170 | 0.389 | 25575 | 1.141 | 44.88% | 0.000 |
| start | IS | equal_control | -12.100 | 0.118 | 0.277 | 12256 | 1.093 | 45.33% | 0.000 |
| start | OOS | equal_control | -13.434 | 0.667 | 0.606 | 5675 | 1.250 | 44.00% | 0.000 |

Drawdown duration counts included 15-minute observations, not calendar days.
Win rate and expectancy use completed signal groups; terminal open P&L is separate.

Calendar units are integer normalized units (INR 1 per premium/index point per unit),
not exchange lots. Every spread has both legs. Equal control is a conventional
same-strike, equal-unit 60/30-day calendar, not an unhedged call.

## Theta/exposure diagnostics, primary OOS

| interpretation | mode | mean_entry_abs_residual | mean_abs_residual_theta | fraction_marks_within_10pct | mean_net_delta_exposure_fraction | mean_collateral_fraction | nonpositive_delta_marks | open_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| end | daily | 0.16% | 1.19% | 98.79% | 7.76% | 42.84% | 0 | 0.000 |
| end | entry | 0.16% | 1.33% | 97.87% | 7.84% | 42.77% | 0 | 0.000 |
| end | equal_control | 29.94% | 29.80% | 1.54% | 0.14% | 52.67% | 3972 | 0.000 |
| start | daily | 0.16% | 1.21% | 98.82% | 7.64% | 42.31% | 0 | 0.000 |
| start | entry | 0.16% | 1.33% | 97.88% | 7.72% | 42.35% | 0 | 0.000 |
| start | equal_control | 29.82% | 29.44% | 1.56% | 0.10% | 52.43% | 4356 | 0.000 |

Residual theta is currency per calendar day divided by the INITIAL long-leg absolute
theta of that spread. Its denominator resets only on a new spread/roll. Net delta,
gamma and vega are long units times long Greek minus short units times short Greek.
Positive net delta is enforced at construction and adjustment, per the user's
clarification; intraday drift is recorded without extra rebalancing or risk exits.
The equal-unit CONTROL can also become negatively exposed between checks and is
not a permanently bullish benchmark.
Vega is currency per 1 percentage point parallel change in each leg's modeled vol;
gamma is delta change per index point; delta exposure is net delta times spot.
Target zero theta, achieved entry/adjustment theta and turnover are in events and
leg ledgers; drift and individual/net Greeks are marked every included bar.

## Matching Stage 2 reference paths, same observations and INR 500,000

| interpretation | period | benchmark | total_return | cagr | max_drawdown | sharpe_ratio | mean_net_delta_exposure_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| start | IS | net | 71.61% | 8.03% | -18.28% | 0.215 | 53.95% |
| start | IS | buy_hold_net | 114.95% | 11.56% | -38.82% | 0.385 | 100.00% |
| start | OOS | net | 33.16% | 8.43% | -12.61% | 0.277 | 54.45% |
| start | OOS | buy_hold_net | 38.56% | 9.66% | -17.12% | 0.313 | 100.00% |
| start | FULL | net | 128.52% | 8.16% | -18.28% | 0.232 | 54.12% |
| start | FULL | buy_hold_net | 199.56% | 10.97% | -38.82% | 0.366 | 100.00% |
| end | IS | net | 40.10% | 4.94% | -20.70% | -0.021 | 54.04% |
| end | IS | buy_hold_net | 114.73% | 11.54% | -38.97% | 0.380 | 100.00% |
| end | OOS | net | 7.98% | 2.19% | -15.76% | -0.326 | 54.93% |
| end | OOS | buy_hold_net | 38.55% | 9.65% | -17.13% | 0.311 | 100.00% |
| end | FULL | net | 51.29% | 4.01% | -20.70% | -0.108 | 54.34% |
| end | FULL | buy_hold_net | 199.41% | 10.96% | -38.97% | 0.362 | 100.00% |

Main Sharpe/Sortino here use annual 6% risk-free rate divided by 252, consistent
with repository ratio conventions. Stage 2 risk ratios above were recomputed at
6% without changing its equity/results. Zero-RF risk ratios are also exported for
comparison with the original Stage 2 summaries. Pricing discounts use continuous
6% and dividend yield 1%; idle cash actually earns zero. Sortino retains sample
std of negative daily excess returns; undefined ratios are null with reasons.
CAGR uses actual first included open to final included close and 365.25 days/year;
pricing/Greek decay uses ACT/365. Drawdown includes starting equity and
15-minute bar-end marks; duration counts included observations.

## Evidence-based verdict, historical OOS

| interpretation | case | matching_return_minus_equal | matching_drawdown_improvement | matching_sharpe_improvement | rebalance_return_minus_entry | rebalance_drawdown_improvement | rebalance_sharpe_improvement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| end | primary | 0.028 | -0.014 | 0.055 | -0.001 | 0.000 | -0.012 |
| start | primary | 0.061 | -0.009 | 0.537 | -0.002 | 0.000 | -0.021 |

Theta-matched entry-only calendars jointly improve return AND absolute drawdown
over equal-unit calendars in 8/20 paired OOS cases. Daily
rebalancing jointly improves both over entry-only in 3/20
cases. This is not robust dominance unless every predeclared case improves both;
Entry matching improves ZERO-RF Sharpe in 16/20
cases; daily management improves return in 12/20
and ZERO-RF Sharpe in 12/20. These distinguish
risk-adjusted improvement from strict return/drawdown dominance. Main 6%-RF
ratios remain in the tables; zero-RF ratios show portfolio return per variability.
Neither ratio is selected by results.
In the primary OOS scenarios, matching increases return and zero-RF Sharpe over
the equal-unit calendar in both interpretations, while increasing drawdown.
Daily rebalancing reduces primary OOS returns and zero-RF Sharpe in both
interpretations without improving maximum drawdown. The sensitivity counts
above do not support a universal improvement from either intervention.
Primary calendar CAGR is below the 6% risk-free comparison rate, so its main
Sharpe/Sortino are negative despite positive net returns. Most equity remains
cash or collateral earning zero. This differs from pricing at continuous 6%.
The comparison changes integer allocation, collateral and net delta as well as
theta; it cannot establish that theta matching alone creates an executable edge.
The OOS period is a previously examined historical holdout, not untouched testing.

## Construction, execution and capital

- Indicator calculated once on full history for each timestamp interpretation,
  amplitude 3/channel deviation 2. Fixed IS 2015-01-09 to 2022-01-08, historical OOS
  2022-01-09 to 2025-07-25; both restart flat at INR 500,000, discarding pre-boundary
  pending signals. Full period carries positions. End positions stay marked open.
- Bullish entry at next included open, same strike EXACTLY the preceding completed
  close (synthetic continuous strike, no assumed exchange strike grid). Strike
  stays frozen through the spread; a roll selects a fresh preceding-close strike.
- Expiry: local entry date + 60/30 calendar days, advance weekend dates to Monday,
  synthetic 15:30 Asia/Kolkata; no historical holidays/weekly-expiry changes used.
  Roll at 09:15 on the weekday on/before short-expiry-minus-five-calendar-days,
  closing both legs and reopening only if previous completed bar is bullish.
  Missing bars execute at the next available open. Late buffers and expiry-gap
  crossings are explicit events; expired legs use intrinsic at that observed
  open, NOT an invented historical settlement price. Every leg pays costs.
- 21 observed-session daily log returns, sample std * sqrt(252), estimated from
  included last daily closes and available only from the following session.
  Calendar-time decay includes nights/weekends. No filled missing sessions or IV
  floor. Undefined/zero vol prevents entry; no long-call fallback. Model vol is
  held constant within each session and updated causally at the next open.
- Integer sizing globally minimizes hedge-ratio error, with larger long quantity
  breaking ties. Both units >=1, long>=short, net delta positive at entry and
  adjustment, gross long premium PLUS BOTH entry fees <=5% of pre-entry equity. Short
  receipts never increase that budget. Cash after flows >=short units*strike.
  Reserved collateral stays inside cash and equity, unavailable for additional
  positions, not historical exchange/broker margin. One spread at a time.
- Entry-only has no interim adjustments. Daily checks preceding session's final
  marks, triggers at absolute residual >10% initial long theta, chooses closest
  feasible integer short target using those marks, and fills at next session
  open. Long units remain fixed until roll. Current-open Greeks/cash validate
  feasibility, but do not determine the preceding-mark theta target. Drift may
  differ immediately after overnight gaps/new volatility. Skips are explicit.
- Fees 2/3 bps EACH SIDE of each actual leg premium; adverse premium slippage
  0/10/25 bps increases buy fills and decreases sells. All adjustments/rolls pay
  both, kept separate in ledgers. No interest, dividends credited, or funding.
- Premium/collateral-limited calendars have different changing net delta and gross
  underlying exposure from fully collateralized Stage 2 proxies/buy-and-hold.
  Smaller raw drawdown alone is not proof of a better risk-adjusted strategy.

## Sensitivity, verification and limitations

Ten cases are predeclared: primary; each fee/slippage/vol/term alternative one at
a time; two combined stress corners. Both interpretations and management modes,
plus the equal-calendar control, run all cases across IS/OOS/full. This is not a
full factorial or optimization; untested interactions remain a limitation.
See sensitivity.csv, paired_oos_comparisons.csv, coverage.json and configuration.json.

OOS ranges across all predeclared scenarios (not selected headline cases):

| interpretation | mode | minimum_return | maximum_return | worst_drawdown | maximum_nonpositive_delta_marks |
| --- | --- | --- | --- | --- | --- |
| end | daily | -7.45% | 8.22% | -7.67% | 27 |
| end | entry | -7.50% | 8.20% | -7.73% | 0 |
| start | daily | -5.45% | 13.40% | -6.02% | 35 |
| start | entry | -5.50% | 13.36% | -6.07% | 0 |

At 25 bps premium slippage both interpretations lose money in OOS. With near-leg
volatility 0.9, entry-only OOS return is positive for start labels but negative
for end labels. Thus profitability and the benefit of theta management do not
survive the assumed fill/term-structure sensitivities; the robust conclusion is
**inconclusive**, not an executable advantage. Some daily-managed scenarios drift
to nonpositive delta between checks; the table reports these without extra exits.
No historical run reached a roll or expiry crossing: those mechanics are tested
synthetically, not demonstrated by the observed HalfTrend holding periods.

Both timestamp interpretations remain producer-unconfirmed and are never selected
by profit. Conflicting duplicates, incomplete regular bars and evenings excluded;
zero volume unavailable. Full-history indicator/volatility warmup is preserved.

Every run independently reconstructs cash from leg fills and equity as cash plus
long value minus short liability: collateral is never counted twice. Signal-level
P&L includes both legs and all rolls/adjustments; open signal P&L is separate.
Prefix/future perturbations check indicators, daily volatility, fills and marks.
All results are compressed CSV/JSON under this new directory; previous outputs
and raw-data hashes are preserved. Checks and detailed reconciliation are saved.

Real premiums, volatility term structure, bid/ask spreads, liquidity, actual
expiries/settlements, strike grids, lots and broker margin remain unverified.
European Black-Scholes-Merton marks on historical spot and realized-vol scenarios
are not observed IV or evidence of executable option returns.
Formula reference: [dividend-yield Black-Scholes derivation](https://book.derivative-securities.org/Chapter_BlackScholes.html).

Reproduce into a NEW directory from repository root:

`python -m src.simulated_calendars
--data C:/Users/beqmd/Documents/QuantResearch/data/NIFTY_50_minute.csv
--output results/stage3_simulated_calendars_repeat`


## Completed verification

- Existing baseline: 103 tests passed before Stage 3. Final suite: **129 passed**.
- Ruff passed; Black passed with 36 files unchanged; `git diff --check` passed.
- All **180 saved runs** were independently repriced using a separate BSM formula
  and independently reconciled from leg cash flows, quantities, both entry fees,
  collateral, long values and short liabilities at every mark. Fill Greeks and
  marked Greek histories also matched independent calculations.
- Final-code real-data prefix and future-candle perturbation tests passed for both
  interpretations, including entry-only, daily and equal-unit calendars at 25 bps
  slippage. Earlier indicators, volatility, fills and marks remained unchanged.
- The raw CSV and all 650 previously hashed result artifacts are unchanged.
- A preliminary entry-budget edge case omitted the short leg's entry fee from the
  5% limit. The sizing rule now includes BOTH fees. All 37 affected paths were
  recomputed in full; preliminary files were preserved separately under
  `verification/stage3_budget_correction/original`. Final artifacts all pass the
  stricter budget check. Unaffected paths retained the same feasible optimum.
- An initial export attempt failed on fixed-offset versus named-timezone index
  comparison; this was corrected and regression-tested. The incomplete directory
  remains explicitly marked. A supplementary causality-check setup used a
  nonexistent audit column; it was corrected to `included` and rerun successfully.
  Its setup error is preserved in checks. No final check is blocked or failing.

See `verification.json`, `independent_artifact_verification.json`,
`budget_correction.json`, `environment_final.json` and `checks/` for evidence.
The initial environment snapshot is retained; final source and verification hashes
are saved separately. No prior-stage results were regenerated. No commit or push.

Recheck saved artifacts:

```powershell
python -m tests.verify_simulated_calendar_outputs results/stage3_SIMULATED_calendars_20261007_completed
python -m pytest -q
python -m ruff check .
python -m black --check .
```
