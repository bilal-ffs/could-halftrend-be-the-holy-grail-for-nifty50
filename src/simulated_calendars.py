"""Stage 3 SIMULATED bullish call-calendar research CLI. Never standalone calls."""

import argparse
import json
from pathlib import Path

import pandas as pd

from src.backtest import run_backtest
from src.calendar_spread import reconcile_calendar, simulate_calendar
from src.data import load_minute_data, resample_to_15m
from src.futures_proxy import digest, markdown_table, save_environment, write_json
from src.halftrend import calculate_halftrend
from src.option_model import causal_volatility
from src.portfolio import equity_to_returns
from src.research import IS_END, IS_START, OOS_END, OOS_START, split_is_oos

LABEL = "SIMULATED bullish call calendar spread"
CASES = [
    ("primary", 3, 0, 1.2, 1.0),
    ("fee_2", 2, 0, 1.2, 1.0),
    ("slip_10", 3, 10, 1.2, 1.0),
    ("slip_25", 3, 25, 1.2, 1.0),
    ("vol_1_0", 3, 0, 1.0, 1.0),
    ("vol_1_5", 3, 0, 1.5, 1.0),
    ("near_0_9", 3, 0, 1.2, 0.9),
    ("near_1_1", 3, 0, 1.2, 1.1),
    ("combined_flat", 3, 25, 1.0, 0.9),
    ("combined_steep", 3, 25, 1.5, 1.1),
]


def metrics(bars, result):
    equity = result.marks.equity
    pnl = result.signals.net_pnl.astype(float)
    returns = equity_to_returns(equity, initial_capital=result.initial_capital)
    backtest = run_backtest(
        bars,
        equity,
        returns,
        pnl,
        initial_capital=result.initial_capital,
        risk_free_rate=0.06,
    )
    out = backtest.summary()
    reasons = dict(backtest.undefined_metrics)
    backtest.risk_free_rate = 0
    out["sharpe_zero_rf"] = backtest.sharpe_ratio()
    out["sortino_zero_rf"] = backtest.sortino_ratio()
    events = result.events
    entries = events.loc[events.action == "entry"] if len(events) else pd.DataFrame()
    active = result.marks.long_quantity > 0
    theta = result.marks.loc[active, "residual_theta"]
    adjustment = result.fills.loc[result.fills.reason == "theta_adjustment"]
    out.update(
        total_return=float(equity.iloc[-1] / result.initial_capital - 1),
        final_equity=float(equity.iloc[-1]),
        signal_count=len(result.signals),
        spread_count=len(entries),
        rolls=int((events.action == "roll").sum()) if len(events) else 0,
        adjustments=int(result.signals.adjustments.sum())
        + (0 if result.open_signal is None else result.open_signal["adjustments"]),
        adjustment_units=int(adjustment.quantity.sum()),
        adjustment_premium_turnover=float(adjustment.premium_notional.sum()),
        fees=float(result.fills.fee.astype(float).sum()),
        slippage_cost=float(
            (
                result.fills.quantity
                * (result.fills.fill_price - result.fills.model_price).abs()
            ).sum()
        ),
        skipped_entries=(
            int((events.action == "entry_skipped").sum()) if len(events) else 0
        ),
        gap_expiry_crossings=(
            int(
                (
                    (events.action == "roll") & (events.reason == "expiry_crossing_gap")
                ).sum()
            )
            if len(events)
            else 0
        ),
        late_buffer_gaps=(
            int(
                ((events.action == "roll") & (events.reason == "late_buffer_gap")).sum()
            )
            if len(events)
            else 0
        ),
        open_pnl=0.0 if result.open_signal is None else result.open_signal["net_pnl"],
        mean_abs_residual_theta=None if theta.empty else float(theta.abs().mean()),
        fraction_marks_within_10pct=(
            None if theta.empty else float(theta.abs().le(0.10).mean())
        ),
        max_abs_residual_theta=None if theta.empty else float(theta.abs().max()),
        nonpositive_delta_marks=int((result.marks.loc[active, "delta"] <= 0).sum()),
        mean_net_delta_exposure_fraction=float(
            (result.marks.net_delta_exposure / equity).mean()
        ),
        mean_gross_underlying_exposure_fraction=float(
            (result.marks.gross_underlying_exposure / equity).mean()
        ),
        mean_collateral_fraction=float((result.marks.collateral / equity).mean()),
        mean_entry_long_premium_fraction=(
            None
            if entries.empty
            else float(
                (entries.long_premium_with_fees / entries.pre_entry_equity).mean()
            )
        ),
        mean_entry_abs_residual=(
            None if entries.empty else float(entries.residual_theta.abs().mean())
        ),
        start_time=result.start_time,
        end_time=result.end_time,
        undefined_metrics=reasons,
    )
    return out


def export(path, bars, result, config):
    path.mkdir(parents=True)
    write_json(path / "configuration.json", config)
    proof = reconcile_calendar(result, config["fee_bps"], config["slippage_bps"])
    write_json(path / "reconciliation.json", proof)
    write_json(path / "open_signal.json", result.open_signal)
    summary = {**config, **metrics(bars, result)}
    write_json(path / "metrics.json", summary)
    result.fills.assign(label="SIMULATED").to_csv(
        path / "leg_ledger.csv.gz", index=False
    )
    result.signals.assign(label="SIMULATED").to_csv(
        path / "signal_ledger.csv.gz", index=False
    )
    result.events.assign(label="SIMULATED").to_csv(path / "events.csv.gz", index=False)
    equity_cols = [
        "mark_time",
        "spot",
        "cash",
        "collateral",
        "free_cash",
        "long_value",
        "short_liability",
        "equity",
        "signal",
        "spread",
        "long_quantity",
        "short_quantity",
        "strike",
        "long_expiry",
        "short_expiry",
        "long_price",
        "short_price",
        "long_sigma",
        "short_sigma",
    ]
    result.marks[equity_cols].assign(label="SIMULATED").to_csv(
        path / "equity.csv.gz", index_label="bar_start"
    )
    result.marks.drop(
        columns=["cash", "collateral", "free_cash", "long_value", "short_liability"]
    ).assign(label="SIMULATED").to_csv(
        path / "greek_history.csv.gz", index_label="bar_start"
    )
    marks = pd.Series(
        result.marks.equity.to_numpy(), index=pd.DatetimeIndex(result.marks.mark_time)
    )
    previous = result.initial_capital
    annual = []
    for year, values in marks.groupby(marks.index.year):
        annual.append(
            dict(
                label="SIMULATED",
                year=int(year),
                start_equity=previous,
                end_equity=float(values.iloc[-1]),
                total_return=float(values.iloc[-1] / previous - 1),
                first_mark=values.index[0],
                last_mark=values.index[-1],
            )
        )
        previous = float(values.iloc[-1])
    pd.DataFrame(annual).to_csv(path / "annual_net.csv", index=False)
    return summary


def prepare(bars):
    full = calculate_halftrend(bars, amplitude=3, channel_deviation=2)
    full["causal_sigma"] = causal_volatility(bars)
    return full


def verify_causality(bars, full, cutoff):
    prefix = prepare(bars.iloc[:cutoff])
    derived = [c for c in full if c not in bars]
    pd.testing.assert_frame_equal(full.iloc[:cutoff][derived], prefix[derived])
    altered = bars.copy()
    altered.loc[altered.index[cutoff:], ["open", "high", "low", "close"]] *= 1.1
    future = prepare(altered)
    pd.testing.assert_frame_equal(
        full.iloc[:cutoff][derived], future.iloc[:cutoff][derived]
    )
    checks = []
    for management, matching in [
        ("entry", "theta"),
        ("daily", "theta"),
        ("entry", "equal"),
    ]:
        kwargs = dict(management=management, matching=matching, slippage_bps=25)
        before = simulate_calendar(full, **kwargs)
        after = simulate_calendar(future, **kwargs)
        partial = simulate_calendar(prefix, **kwargs)
        boundary = partial.end_time
        old_fills = before.fills.loc[before.fills.time < boundary].reset_index(
            drop=True
        )
        pd.testing.assert_frame_equal(
            old_fills,
            after.fills.loc[after.fills.time < boundary].reset_index(drop=True),
        )
        pd.testing.assert_frame_equal(old_fills, partial.fills.reset_index(drop=True))
        pd.testing.assert_frame_equal(
            before.marks.iloc[:cutoff], after.marks.iloc[:cutoff]
        )
        pd.testing.assert_frame_equal(before.marks.iloc[:cutoff], partial.marks)
        checks.append(
            dict(
                management=management,
                matching=matching,
                past_fills=len(old_fills),
                passed=True,
            )
        )
    return dict(cutoff=cutoff, indicator_and_volatility_causal=True, checks=checks)


def benchmark_comparison(stage2, output, windows, interpretation):
    rows = []
    for period, bars in windows.items():
        for scenario in ["net", "buy_hold_net"]:
            path = stage2 / interpretation / "a3" / period / scenario
            original = json.loads((path / "metrics.json").read_text())
            curve = pd.read_csv(path / "equity.csv", index_col="bar_start")
            curve.index = pd.to_datetime(curve.index).tz_convert("Asia/Kolkata")
            # Confirm matching observations before comparing paired evaluations.
            assert curve.index.equals(bars.index)
            trades = pd.read_csv(path / "trades.csv")
            pnl = trades.net_pnl.astype(float)
            equity = curve.equity
            backtest = run_backtest(
                bars,
                equity,
                equity_to_returns(equity, initial_capital=500000),
                pnl,
                initial_capital=500000,
                risk_free_rate=0.06,
            )
            row = dict(
                label="SIMULATED comparison to Stage 2 proxy",
                interpretation=interpretation,
                period=period,
                benchmark=scenario,
                total_return=original["total_return"],
                cagr=original["cagr"],
                max_drawdown=original["max_drawdown"],
                sharpe_ratio=backtest.sharpe_ratio(),
                sortino_ratio=backtest.sortino_ratio(),
                original_stage2_sharpe_zero_rf=original["sharpe_ratio"],
                mean_net_delta_exposure_fraction=float(
                    (curve.quantity * bars.close / equity).mean()
                ),
            )
            rows.append(row)
    return rows


def report(output, table, benchmark):
    primary = table.loc[table.case == "primary"]
    cols = [
        "interpretation",
        "period",
        "mode",
        "total_return",
        "cagr",
        "sharpe_ratio",
        "max_drawdown",
        "expectancy",
        "signal_count",
        "spread_count",
        "rolls",
        "adjustments",
        "fees",
    ]
    oos = table.loc[table.period == "OOS"]
    paired = oos.pivot(
        index=["interpretation", "case"],
        columns="mode",
        values=["total_return", "sharpe_zero_rf", "max_drawdown"],
    )
    comparisons = []
    for (interpretation, case), row in paired.iterrows():
        comparisons.append(
            dict(
                interpretation=interpretation,
                case=case,
                matching_return_minus_equal=row["total_return", "entry"]
                - row["total_return", "equal_control"],
                matching_drawdown_improvement=abs(row["max_drawdown", "equal_control"])
                - abs(row["max_drawdown", "entry"]),
                matching_sharpe_improvement=row["sharpe_zero_rf", "entry"]
                - row["sharpe_zero_rf", "equal_control"],
                rebalance_return_minus_entry=row["total_return", "daily"]
                - row["total_return", "entry"],
                rebalance_drawdown_improvement=abs(row["max_drawdown", "entry"])
                - abs(row["max_drawdown", "daily"]),
                rebalance_sharpe_improvement=row["sharpe_zero_rf", "daily"]
                - row["sharpe_zero_rf", "entry"],
            )
        )
    comp = pd.DataFrame(comparisons)
    comp.to_csv(output / "paired_oos_comparisons.csv", index=False)
    theta_count = int(
        (
            (comp.matching_return_minus_equal > 0)
            & (comp.matching_drawdown_improvement > 0)
        ).sum()
    )
    rebal_count = int(
        (
            (comp.rebalance_return_minus_entry > 0)
            & (comp.rebalance_drawdown_improvement > 0)
        ).sum()
    )
    matching_sharpe_count = int((comp.matching_sharpe_improvement > 0).sum())
    rebalance_return_count = int((comp.rebalance_return_minus_entry > 0).sum())
    rebalance_sharpe_count = int((comp.rebalance_sharpe_improvement > 0).sum())
    baseline = comp.loc[comp.case == "primary"]
    write_json(
        output / "verdict.json",
        dict(
            label="SIMULATED",
            primary=baseline.to_dict("records"),
            paired_oos_cases=len(comp),
            matching_return_drawdown_dominance_cases=theta_count,
            daily_return_drawdown_dominance_cases=rebal_count,
            matching_robust_dominance=theta_count == len(comp),
            matching_zero_rf_sharpe_improvement_cases=matching_sharpe_count,
            daily_return_improvement_cases=rebalance_return_count,
            daily_zero_rf_sharpe_improvement_cases=rebalance_sharpe_count,
            daily_robust_dominance=rebal_count == len(comp),
        ),
    )
    table_text = markdown_table(primary, cols, ["total_return", "cagr", "max_drawdown"])
    bcols = [
        "interpretation",
        "period",
        "benchmark",
        "total_return",
        "cagr",
        "max_drawdown",
        "sharpe_ratio",
        "mean_net_delta_exposure_fraction",
    ]
    btext = markdown_table(
        benchmark,
        bcols,
        ["total_return", "cagr", "max_drawdown", "mean_net_delta_exposure_fraction"],
    )
    risk = primary.loc[primary.period == "OOS"]
    riskcols = [
        "interpretation",
        "mode",
        "mean_entry_abs_residual",
        "mean_abs_residual_theta",
        "fraction_marks_within_10pct",
        "mean_net_delta_exposure_fraction",
        "mean_collateral_fraction",
        "nonpositive_delta_marks",
        "open_pnl",
    ]
    rtext = markdown_table(
        risk,
        riskcols,
        [
            "mean_entry_abs_residual",
            "mean_abs_residual_theta",
            "fraction_marks_within_10pct",
            "mean_net_delta_exposure_fraction",
            "mean_collateral_fraction",
        ],
    )
    paired_text = markdown_table(baseline, list(baseline.columns))
    supplemental = markdown_table(
        primary,
        [
            "interpretation",
            "period",
            "mode",
            "sortino_ratio",
            "calmar_ratio",
            "sharpe_zero_rf",
            "drawdown_duration",
            "profit_factor",
            "win_rate",
            "open_pnl",
        ],
        ["win_rate"],
    )
    modeled = oos.loc[oos["mode"].isin(["entry", "daily"])]
    ranges = (
        modeled.groupby(["interpretation", "mode"])
        .agg(
            minimum_return=("total_return", "min"),
            maximum_return=("total_return", "max"),
            worst_drawdown=("max_drawdown", "min"),
            maximum_nonpositive_delta_marks=("nonpositive_delta_marks", "max"),
        )
        .reset_index()
    )
    ranges_text = markdown_table(
        ranges,
        list(ranges.columns),
        ["minimum_return", "maximum_return", "worst_drawdown"],
    )
    text = f"""# Stage 3: SIMULATED bullish call calendar spread

All premiums, Greeks and option results are **SIMULATED** on the actual local
NIFTY_50_minute.csv path. No observed option prices or standalone long calls.
This strategy is approximately theta-neutral under the model at construction;
it is not permanently theta-neutral or risk-free.

## Primary results, predeclared amplitude 3 / volatility 1.2 / 3 bps / zero slippage

{table_text}

### Additional risk and signal-level statistics

{supplemental}

Drawdown duration counts included 15-minute observations, not calendar days.
Win rate and expectancy use completed signal groups; terminal open P&L is separate.

Calendar units are integer normalized units (INR 1 per premium/index point per unit),
not exchange lots. Every spread has both legs. Equal control is a conventional
same-strike, equal-unit 60/30-day calendar, not an unhedged call.

## Theta/exposure diagnostics, primary OOS

{rtext}

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

{btext}

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

{paired_text}

Theta-matched entry-only calendars jointly improve return AND absolute drawdown
over equal-unit calendars in {theta_count}/{len(comp)} paired OOS cases. Daily
rebalancing jointly improves both over entry-only in {rebal_count}/{len(comp)}
cases. This is not robust dominance unless every predeclared case improves both;
Entry matching improves ZERO-RF Sharpe in {matching_sharpe_count}/{len(comp)}
cases; daily management improves return in {rebalance_return_count}/{len(comp)}
and ZERO-RF Sharpe in {rebalance_sharpe_count}/{len(comp)}. These distinguish
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
  amplitude 3/channel deviation 2. Fixed IS {IS_START} to {IS_END}, historical OOS
  {OOS_START} to {OOS_END}; both restart flat at INR 500,000, discarding pre-boundary
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

{ranges_text}

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
"""
    (output / "REPORT.md").write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=LABEL)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stage2",
        type=Path,
        default=Path("results/stage2_futures_proxy_20261007_completed"),
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output exists: choose a NEW directory.")
    preserved = {str(p): digest(p) for p in Path("results").rglob("*") if p.is_file()}
    raw_hash = digest(args.data)
    assert (
        json.loads((args.stage2 / "configuration.json").read_text())["data_sha256"]
        == raw_hash
    )
    args.output.mkdir(parents=True)
    save_environment(args.output)
    write_json(
        args.output / "configuration.json",
        dict(
            label="SIMULATED",
            data_path=args.data,
            data_sha256=raw_hash,
            initial_capital=500000,
            amplitude=3,
            channel_deviation=2,
            vol_sessions=21,
            pricing_risk_free_rate=0.06,
            dividend_yield=0.01,
            risk_ratio_annual_rf=0.06,
            idle_cash_rate=0,
            primary_case=CASES[0],
            cases=CASES,
            modes=["entry", "daily", "equal_control"],
            long_days=60,
            short_days=30,
            premium_budget=0.05,
            entry_budget="long premium PLUS BOTH entry fees; no short receipt credit",
            theta_threshold=0.10,
            collateral="short_quantity*strike reserved INSIDE cash",
            integer_units=True,
            delta_policy="positive_at_entry_and_adjustment_report_intraday_drift_no_risk_exits",
            synthetic_strike="preceding_completed_close",
            stage2_directory=args.stage2,
            fixed_boundaries=dict(
                IS_START=IS_START, IS_END=IS_END, OOS_START=OOS_START, OOS_END=OOS_END
            ),
        ),
    )
    write_json(args.output / "prior_results_sha256.json", preserved)
    minute = load_minute_data(
        args.data, duplicate_policy="exclude", audit_dir=args.output / "data_audit"
    )
    all_rows, coverage, causal, references = [], {}, {}, []
    for interpretation in ["start", "end"]:
        print(
            f"SIMULATED {interpretation}: resampling and causal preparation", flush=True
        )
        bars = resample_to_15m(
            minute,
            minute_label=interpretation,
            audit_dir=args.output / interpretation / "data_audit",
        )
        full = prepare(bars)
        full[["buy_signal", "sell_signal", "trend", "causal_sigma"]].assign(
            label="SIMULATED"
        ).to_csv(args.output / interpretation / "causal_inputs.csv.gz")
        is_data, oos_data = split_is_oos(full)
        windows = dict(IS=is_data, OOS=oos_data, FULL=full)
        coverage[interpretation] = dict(
            **bars.attrs["session_audit"],
            vol_warmup_bars=int(full.causal_sigma.isna().sum()),
        )
        print(
            f"SIMULATED {interpretation}: verifying prefix/future causality", flush=True
        )
        causal[interpretation] = verify_causality(bars, full, len(full) // 2)
        references.extend(
            benchmark_comparison(args.stage2, args.output, windows, interpretation)
        )
        for case, fee, slip, vm, nm in CASES:
            for mode in ["entry", "daily", "equal_control"]:
                print(f"SIMULATED {interpretation} {case} {mode}", flush=True)
                for period, window in windows.items():
                    kwargs = dict(
                        fee_bps=fee,
                        slippage_bps=slip,
                        vol_multiplier=vm,
                        near_multiplier=nm,
                        management="daily" if mode == "daily" else "entry",
                        matching="equal" if mode == "equal_control" else "theta",
                    )
                    result = simulate_calendar(window, **kwargs)
                    config = dict(
                        label="SIMULATED",
                        interpretation=interpretation,
                        period=period,
                        mode=mode,
                        case=case,
                        **kwargs,
                    )
                    all_rows.append(
                        export(
                            args.output / interpretation / case / mode / period,
                            window,
                            result,
                            config,
                        )
                    )
    table = pd.DataFrame(all_rows)
    table.drop(columns=["undefined_metrics"]).to_csv(
        args.output / "sensitivity.csv", index=False
    )
    bench = pd.DataFrame(references)
    bench.to_csv(args.output / "stage2_comparison.csv", index=False)
    write_json(
        args.output / "coverage.json",
        dict(loading=minute.attrs, interpretations=coverage),
    )
    assert digest(args.data) == raw_hash
    assert all(digest(Path(p)) == h for p, h in preserved.items())
    write_json(
        args.output / "verification.json",
        dict(
            label="SIMULATED",
            causality=causal,
            independently_reconciled_runs=len(all_rows),
            raw_data_preserved=True,
            prior_results_preserved=len(preserved),
        ),
    )
    report(args.output, table, bench)
    print(f"Completed {len(all_rows)} SIMULATED runs: {args.output}", flush=True)


if __name__ == "__main__":
    main()
