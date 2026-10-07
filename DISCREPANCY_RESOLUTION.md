# Discrepancy-resolution report

Scope: audited corrections only. No full research results regenerated, no
parameter optimization or new strategies, and no commit or push. No AGENTS.md
was found in the repository or its Documents parent. Existing user edits were
backed up before correction; unrelated result artifacts were preserved.

| Audited issue | Correction |
| --- | --- |
| Ambiguous CSV date parsing | Explicit DD-MM-YYYY HH:MM parsing and Asia/Kolkata timezone |
| Four conflicting timestamp groups | Default rejection; exported eight source rows; explicit exclude/first/last policies with warnings and decision records |
| Partial/evening sessions and all-zero volume | Explicit session classification, default exclusion of incomplete/evening bars, zero volume marked unavailable |
| Incorrect bar-count annualization | 25 complete regular 15-minute bars; CAGR from elapsed calendar time, ratios from daily equity at 252 sessions/year |
| Inconsistent Calmar and initial drawdown | Calmar uses the same calendar CAGR; starting capital is the initial high-water mark |
| Different OOS indicator initialization | One causal full-history calculation, then fixed IS/OOS slicing; shared capital and flat reset; exact zero-cost equivalence assertion |
| Additive ledger versus multiplicative equity | Preserve original fee-reserved sizing and fixed trade quantity; one cash/fill/actual-notional fee model retaining residual cash |
| Weak fee reconciliation | Independently check the actual costed ledger and final cash/positions from fills; include open P&L and entry fee without deducting closed fees twice |
| Nonfinite costs/equity and bad inputs | Validate finite costs, positive capital/prices/quantities, bar chronology, boolean signals and indicator parameters; explicit insolvency errors |
| Tautological OOS check and undiscoverable tests | Discoverable pytest suite, independent numeric expectations, prefix/future-data perturbations of values/signals/fills, local Ruff/Black configuration |

## Verification

- 85 pytest cases pass, covering parsing and duplicate policies, complete/partial
  sessions, label modes, fees/sizing, open positions, calendar CAGR, daily ratios,
  first-period losses, zero-cost OOS equivalence, invalid inputs and causality.
- Ruff check and Black check pass. Final command output is saved separately under
  `verification/discrepancy_fix/checks/`.
- Real-data verification is bounded to the first 1000 retained bars, at 5 bps per
  side on underlying notional, with initial capital 100,000.
- Independent final-equity reconciliation: 98,491.96221329046 actual and expected;
  difference 0.0. This sample has 16 completed trades and no final open position;
  synthetic tests also independently verify open-position accounting.
- Real-data prefix/future perturbation at cutoff 500 passed, covering 14 historical
  fills. Synthetic tests cover ATR warm-up and post-warm-up indicator state, every
  derived indicator column, signals, fills and historical equity.
- All 31 pre-existing result files retain their original SHA-256 hashes. The raw
  CSV hash is also unchanged. No checks require market downloads.

## Data decisions and ambiguity

The raw CSV has 975,321 rows. Verification explicitly selects conflict exclusion:
8 rows from four timestamp groups are removed (June 29, August 10 twice, and
August 13, 2015). Both source records and the physical CSV row numbers are in
[the conflict CSV](verification/discrepancy_fix/data_audit/exclude/conflicting_duplicates.csv).
The default-rejection audit is saved separately, so neither policy overwrites
its evidence.

After duplicate exclusions, 974,701 observations are regular-clock minutes and
612 are evening minutes. Verification excludes **40 incomplete regular bars**
(containing 436 retained minutes) and **41 evening bars** (612 minutes, including
one incomplete evening bar). It retains **64,951 complete regular bars**. All bar
classifications and exclusion flags are exported; no original data or result file
is rewritten. Existing complete bars on a partial day are retained; missing
intervals are not fabricated.

Kaggle provenance was supplied by the user, but no dataset page or producer
metadata establishing label semantics was available. Normal coverage of 375
observations from 09:15 through 15:29 supports minute **start** labels. Verification
selects that convention explicitly; producer semantics remain unresolved rather
than falsely claimed verified. The resampler requires an explicit start/end
choice and tests both. Session labels use local-clock windows, not an exchange
holiday/special-session calendar; evening and unusual partial sessions still need
calendar/source confirmation. All-zero volume means unavailable information,
not proof of no trading.

## Intentional behavior changes

- Valid timestamps are timezone-aware; duplicates can no longer be silently
  counted or resolved. Default regular-only, complete-bar evaluation excludes
  evening/partial data formerly included by unconditional resampling.
- CAGR is calendar-based, Sharpe/Sortino are daily, and Calmar is internally
  consistent. Previously reported summaries are historical and unchanged.
- Costed equity changes by retaining real residual cash and using actual-notional
  fees. Entry quantity remains `cash*(1-rate)/entry_open`, fixed until exit; this
  is explicitly **not** a silent switch to a different sizing rule.
- Trade statistics now use actual cash net P&L. Per-unit price changes remain in
  pnl_points; the legacy points wrapper remains available.
- Undefined metrics are NaN in Python and null in JSON with reasons. Insolvency
  is an error, not an undefined metric. Costs have no arbitrary cap: positive
  entry quantity imposes the retained sizing formula's mathematical limit.
- Risk-free conversion is annual_rate/252; Sortino preserves QuantTools' sample
  deviation of negative excess returns. See README for complete conventions.
- 5 bps underlying-notional costs are the verification baseline. 2/3 bps option
  premium costs remain reserved for later work; no options/futures stage exists.

Detailed policy and reconciliation evidence is in
[real_data_verification.json](verification/discrepancy_fix/real_data_verification.json).
Backups of pre-existing modified cost source/diagnostics and original result hashes
are under `verification/discrepancy_fix/`. Full research runners were not executed.
