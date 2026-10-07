"""Reproducible Stage 2 index-based futures proxy; no exchange contract model."""

import argparse
import hashlib
import json
import sys
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

from src.accounting import reconcile_portfolio, simulate_portfolio
from src.backtest import run_backtest
from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend
from src.portfolio import equity_to_returns
from src.research import IS_END, IS_START, OOS_END, OOS_START, split_is_oos

LABEL = "index-based futures proxy"
CAPITAL = 500_000.0


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def write_json(path, value):
    path.write_text(
        json.dumps(clean(value), indent=2, allow_nan=False), encoding="utf-8"
    )


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_environment(output):
    versions = {}
    for package in [
        "pandas",
        "numpy",
        "quant-research-tools",
        "pytest",
        "ruff",
        "black",
    ]:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "distribution metadata unavailable"
    files = list(Path("src").glob("*.py")) + [Path("pyproject.toml")]
    write_json(
        output / "environment.json",
        dict(
            python=sys.version,
            package_versions=versions,
            source_sha256={str(p): digest(p) for p in files},
        ),
    )


def summarize(bars, result):
    returns = equity_to_returns(result.equity, initial_capital=result.initial_capital)
    backtest = run_backtest(
        bars,
        result.equity,
        returns,
        result.trades.net_pnl,
        initial_capital=result.initial_capital,
    )
    metrics = backtest.summary()
    position = result.open_position
    metrics.update(
        total_return=float(result.equity.iloc[-1] / result.initial_capital - 1),
        final_equity=float(result.equity.iloc[-1]),
        trade_count=len(result.trades),
        exposure_observed_bars=float(result.positions.mean()),
        total_fees=float(result.fills.fee.sum()),
        closed_net_pnl=float(result.trades.net_pnl.sum()),
        open_gross_pnl=0.0 if position is None else position["gross_pnl"],
        open_net_pnl=(
            0.0 if position is None else position["gross_pnl"] - position["entry_cost"]
        ),
        start_time=result.start_time,
        end_time=result.end_time,
        undefined_metrics=backtest.undefined_metrics,
    )
    buys = result.fills.loc[result.fills.side == "buy", "time"].tolist()
    exits = result.fills.loc[result.fills.side == "sell", "time"].tolist()
    if len(buys) > len(exits):
        exits.append(result.end_time)
    metrics["exposure_calendar_fraction"] = (
        sum((exit - entry).total_seconds() for entry, exit in zip(buys, exits))
        / (result.end_time - result.start_time).total_seconds()
    )
    return metrics


def annual_performance(result):
    rows = []
    previous = result.initial_capital
    marks = pd.Series(result.equity.to_numpy(), index=result.mark_times)
    for year, values in marks.groupby(marks.index.year):
        rows.append(
            dict(
                year=int(year),
                starting_equity=previous,
                ending_equity=float(values.iloc[-1]),
                total_return=float(values.iloc[-1] / previous - 1),
                first_mark=values.index[0],
                last_mark=values.index[-1],
            )
        )
        previous = float(values.iloc[-1])
    return pd.DataFrame(rows)


def concentration(result):
    top = result.trades.nlargest(5, "net_pnl").copy()
    pnl = float(top.net_pnl.sum())
    all_net = float(result.trades.net_pnl.sum())
    positives = float(result.trades.loc[result.trades.net_pnl > 0, "net_pnl"].sum())
    return top, dict(
        top_five_net_pnl=pnl,
        closed_net_pnl=all_net,
        fraction_of_closed_net=None if all_net == 0 else pnl / all_net,
        fraction_of_positive_pnl=None if positives == 0 else pnl / positives,
        analysis="Descriptive only; no trades removed or equity/sizing recomputed.",
    )


def verify_causal(bars, full, amplitude, cutoff):
    columns = [c for c in full if c not in bars]
    prefix = calculate_halftrend(
        bars.iloc[:cutoff], amplitude=amplitude, channel_deviation=2
    )
    pd.testing.assert_frame_equal(prefix[columns], full.iloc[:cutoff][columns])
    altered = bars.copy()
    altered.loc[altered.index[cutoff:], ["open", "high", "low", "close"]] *= 1.5
    future = calculate_halftrend(altered, amplitude=amplitude, channel_deviation=2)
    pd.testing.assert_frame_equal(
        full.iloc[:cutoff][columns], future.iloc[:cutoff][columns]
    )
    checks = []
    for slip, delay in [(0, 1), (1, 1), (2, 1), (0, 2)]:
        kwargs = dict(
            initial_capital=CAPITAL,
            cost_bps=5,
            slippage_points=slip,
            execution_delay=delay,
        )
        original = simulate_portfolio(full, **kwargs)
        changed = simulate_portfolio(future, **kwargs)
        partial = simulate_portfolio(prefix, **kwargs)
        boundary = partial.end_time
        prior = original.fills.loc[original.fills.time < boundary].reset_index(
            drop=True
        )
        pd.testing.assert_frame_equal(
            prior,
            changed.fills.loc[changed.fills.time < boundary].reset_index(drop=True),
        )
        pd.testing.assert_frame_equal(prior, partial.fills.reset_index(drop=True))
        pd.testing.assert_series_equal(
            original.equity.iloc[:cutoff], changed.equity.iloc[:cutoff]
        )
        pd.testing.assert_series_equal(original.equity.iloc[:cutoff], partial.equity)
        checks.append(
            dict(
                slippage_points=slip,
                execution_delay=delay,
                historical_fills=len(prior),
                passed=True,
            )
        )
    return dict(
        amplitude=amplitude,
        cutoff=cutoff,
        indicator_prefix_passed=True,
        future_perturbation_passed=True,
        fills_and_equity=checks,
    )


def export_run(path, bars, result, metadata):
    path.mkdir(parents=True)
    reconciliation = reconcile_portfolio(result)
    metrics = summarize(bars, result)
    write_json(path / "metrics.json", dict(**metadata, **metrics))
    write_json(path / "reconciliation.json", reconciliation)
    write_json(path / "open_position.json", result.open_position)
    result.trades.to_csv(path / "trades.csv", index=False)
    result.fills.to_csv(path / "fills.csv", index=False)
    pd.DataFrame(
        dict(
            equity=result.equity,
            cash=result.cash,
            quantity=result.quantities,
            position=result.positions,
            mark_time=result.mark_times,
        )
    ).to_csv(path / "equity.csv", index_label="bar_start")
    annual_performance(result).to_csv(path / "annual_performance.csv", index=False)
    top, stats = concentration(result)
    top.to_csv(path / "five_best_completed_trades.csv", index=False)
    write_json(path / "concentration.json", stats)
    return {
        **metadata,
        **metrics,
        **{k: v for k, v in stats.items() if k != "analysis"},
    }


def timestamp_differences(output, indicators, primary):
    cols = ["open", "high", "low", "close", "buy_signal", "sell_signal"]
    left, right = indicators["start"][cols].align(indicators["end"][cols], join="outer")
    differences = (left.ne(right) & ~(left.isna() & right.isna())).any(axis=1)
    pd.concat(
        {"start": left.loc[differences], "end": right.loc[differences]}, axis=1
    ).to_csv(output / "bar_signal_differences.csv")
    signals = ["buy_signal", "sell_signal"]
    signal_changed = (
        left[signals].ne(right[signals])
        & ~(left[signals].isna() & right[signals].isna())
    ).any(axis=1)
    pd.concat(
        {
            "start": left.loc[signal_changed, signals],
            "end": right.loc[signal_changed, signals],
        },
        axis=1,
    ).to_csv(output / "signal_differences.csv")
    counts = {}
    for period in ["IS", "OOS", "FULL"]:
        a, b = primary["start", period].fills, primary["end", period].fills
        merged = a.merge(
            b,
            on=["signal_time", "side"],
            how="outer",
            suffixes=("_start", "_end"),
            indicator=True,
        )
        merged.to_csv(output / f"fill_comparison_{period}.csv", index=False)
        changed = merged._merge.ne("both")
        for column in ["time", "price", "quantity", "notional", "fee"]:
            changed |= merged[f"{column}_start"].ne(merged[f"{column}_end"])
        merged.loc[changed].to_csv(
            output / f"fill_differences_{period}.csv", index=False
        )
        counts[period] = merged._merge.value_counts().to_dict()
    write_json(
        output / "timestamp_comparison_counts.json",
        dict(
            changed_or_missing_bars=int(differences.sum()),
            changed_or_missing_signal_bars=int(signal_changed.sum()),
            fills_by_signal=counts,
        ),
    )


def markdown_table(frame, columns, percentages=()):
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        cells = []
        for key in columns:
            value = row[key]
            if pd.isna(value):
                cells.append("undefined")
            elif key in {"year", "amplitude", "trade_count", "drawdown_duration"}:
                cells.append(str(int(value)))
            elif key in percentages:
                cells.append(f"{value:.2%}")
            elif isinstance(value, (float, np.floating)):
                cells.append(f"{value:,.3f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def annual_net_table(output, table):
    frames = []
    for _, row in table.loc[table.cost_bps == 5].iterrows():
        path = (
            output
            / row.interpretation
            / f"a{row.amplitude}"
            / row.period
            / row.scenario
            / "annual_performance.csv"
        )
        annual = pd.read_csv(path)
        for key in ["interpretation", "amplitude", "period", "scenario"]:
            annual[key] = row[key]
        annual["label"] = LABEL
        frames.append(annual)
    result = pd.concat(frames, ignore_index=True)
    result.to_csv(output / "annual_net_performance.csv", index=False)
    return (
        result.loc[
            (result.amplitude == 3)
            & (result.period == "FULL")
            & (result.scenario == "net")
        ]
        .pivot(index="year", columns="interpretation", values="total_return")
        .reset_index()
    )


def build_report(output, table, coverage):
    primary = table.loc[
        (table.amplitude == 3)
        & (table.scenario.isin(["gross", "net", "buy_hold_gross", "buy_hold_net"]))
    ]
    columns = [
        "interpretation",
        "period",
        "scenario",
        "total_return",
        "cagr",
        "max_drawdown",
        "expectancy",
        "trade_count",
    ]
    oos = table.loc[
        (table.period == "OOS")
        & (table.scenario.isin(["net", "slip_1", "slip_2", "delay_2"]))
        & (table.amplitude == 3)
    ]
    positive = bool((oos.expectancy > 0).all())
    base = oos.loc[oos.scenario == "net"]
    interpretation_sign_changed = (
        base.expectancy.gt(0).nunique() > 1 or base.total_return.gt(0).nunique() > 1
    )
    comparisons = []
    for label in ["start", "end"]:
        strategy = primary.loc[
            (primary.interpretation == label)
            & (primary.period == "OOS")
            & (primary.scenario == "net")
        ].iloc[0]
        benchmark = primary.loc[
            (primary.interpretation == label)
            & (primary.period == "OOS")
            & (primary.scenario == "buy_hold_net")
        ].iloc[0]
        comparisons.append(
            (
                bool(strategy.total_return > benchmark.total_return),
                bool(abs(strategy.max_drawdown) < abs(benchmark.max_drawdown)),
            )
        )
    comparison_text = "; ".join(
        f"{label}: {'higher' if higher else 'lower'} return, "
        f"{'lower' if lower_dd else 'higher'} maximum drawdown"
        for label, (higher, lower_dd) in zip(["start", "end"], comparisons)
    )
    interpretation_sign_changed |= len(set(comparisons)) > 1
    # Material direction means a sign reversal in return/expectancy, or a
    # strategy-versus-benchmark return/drawdown ranking reversal. Check all
    # periods and specified execution stresses, without selecting a winner.
    directional_checks = []
    stress = table.loc[
        (table.amplitude == 3)
        & table.scenario.isin(["net", "slip_1", "slip_2", "delay_2"])
    ]
    for (period, scenario), group in stress.groupby(["period", "scenario"]):
        changed = (
            group.expectancy.gt(0).nunique() > 1
            or group.total_return.gt(0).nunique() > 1
        )
        rankings = []
        for _, row in group.iterrows():
            bh = primary.loc[
                (primary.interpretation == row.interpretation)
                & (primary.period == period)
                & (primary.scenario == "buy_hold_net")
            ].iloc[0]
            rankings.append(
                (
                    row.total_return > bh.total_return,
                    abs(row.max_drawdown) < abs(bh.max_drawdown),
                )
            )
        changed |= len(set(rankings)) > 1
        interpretation_sign_changed |= changed
        directional_checks.append(
            dict(
                period=period,
                scenario=scenario,
                timestamp_direction_changed=bool(changed),
            )
        )
    verdict = (
        "INCONCLUSIVE: timestamp interpretation changes " "a directional conclusion."
        if interpretation_sign_changed
        else (
            "Positive OOS expectancy survives all specified execution stresses."
            if positive
            else "Positive OOS expectancy fails at least one execution stress."
        )
    )
    annual = annual_net_table(output, table)
    net = primary.loc[primary.scenario == "net"]
    risk_columns = [
        "interpretation",
        "period",
        "total_return",
        "cagr",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "drawdown_duration",
    ]
    trade_columns = [
        "interpretation",
        "period",
        "profit_factor",
        "win_rate",
        "expectancy",
        "trade_count",
        "exposure_observed_bars",
        "total_fees",
        "open_gross_pnl",
        "open_net_pnl",
    ]
    top_columns = [
        "interpretation",
        "period",
        "top_five_net_pnl",
        "fraction_of_closed_net",
        "fraction_of_positive_pnl",
    ]
    sensitivity = table.loc[(table.period == "OOS") & (table.scenario == "net")]
    sensitivity_columns = [
        "interpretation",
        "amplitude",
        "total_return",
        "max_drawdown",
        "expectancy",
        "trade_count",
    ]
    risk_table = markdown_table(
        net, risk_columns, ["total_return", "cagr", "max_drawdown"]
    )
    trade_table = markdown_table(
        net, trade_columns, ["win_rate", "exposure_observed_bars"]
    )
    concentration_table = markdown_table(
        net, top_columns, ["fraction_of_closed_net", "fraction_of_positive_pnl"]
    )
    annual_table = markdown_table(annual, ["year", "start", "end"], ["start", "end"])
    sensitivity_table = markdown_table(
        sensitivity, sensitivity_columns, ["total_return", "max_drawdown"]
    )
    text = f"""# Stage 2: {LABEL}

{verdict}

Benchmark: NIFTY 50 price-index buy-and-hold, excluding dividends. The input
was obtained from Kaggle; producer timestamp semantics are still unconfirmed.

## Primary gross/net and benchmark comparison

{markdown_table(primary, columns, ["total_return", "cagr", "max_drawdown"])}

## OOS execution robustness (historical holdout)

{markdown_table(oos, columns, ["total_return", "cagr", "max_drawdown"])}

1. Amplitude 3 net expectancy at 5 bps each side: see all IS/OOS/FULL values above;
the verdict emphasizes OOS.
2. Buy-and-hold return/drawdown: both comparisons above use identical included bars,
capital and calendar boundaries within each interpretation. Sign-based comparisons
within each interpretation: {comparison_text}.
3. Stability: {verdict} Both interpretations are reported, never selected by
profitability. Slippage and delay scenarios are evaluated independently, not combined.
Amplitudes 2-5 are sensitivity only; no parameter was selected.
4. Actual futures remain unverified: spot-index data do not establish futures fills,
basis, funding, contract rolls, exchange lots, historical margins, liquidity or
executable returns. No options stage is implemented.

## Primary net risk metrics

{risk_table}

Drawdown duration is consecutive included observations; expectancy is INR per
completed trade with this path's changing entry equity, not points or a fixed stake.

## Primary net trade/accounting metrics

{trade_table}

The benchmark remains open. Per-run open-position files contain actual quantity,
mark, gross P&L and entry fee; no hypothetical exit is booked.
Exposure here counts included bars; calendar exposure is also exported in metrics.

## Annual full-period primary net returns (partial 2015/2025)

{annual_table}

All IS/OOS annual rows, stresses and sensitivities are in annual_net_performance.csv.

## Amplitude sensitivity, OOS only (no selection)

{sensitivity_table}

IS/full-period sensitivities are in sensitivity.csv. Amplitude 3 remains primary.

## Five-best-completed-trade concentration, primary net

{concentration_table}

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
- Fixed IS {IS_START} to {IS_END}; OOS {OOS_START} to {OOS_END}. IS/OOS start flat and
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

Coverage: {json.dumps(clean(coverage), indent=2)}

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
"""
    (output / "REPORT.md").write_text(text, encoding="utf-8")
    write_json(
        output / "verdict.json",
        dict(
            verdict=verdict,
            timestamp_direction_changed=bool(interpretation_sign_changed),
            all_oos_stress_expectancies_positive=positive,
            directional_checks=directional_checks,
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=LABEL)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output directory already exists; choose a new directory.")
    existing = {str(p): digest(p) for p in Path("results").rglob("*") if p.is_file()}
    raw_hash = digest(args.data)
    args.output.mkdir(parents=True)
    save_environment(args.output)
    write_json(
        args.output / "configuration.json",
        dict(
            label=LABEL,
            initial_capital=CAPITAL,
            amplitude=3,
            channel_deviation=2,
            sensitivity_amplitudes=[2, 3, 4, 5],
            transaction_cost_bps_each_side=5,
            primary_slippage_points=0,
            stress_slippage_points=[1, 2],
            execution_delay_bars=[1, 2],
            fractional_units=True,
            idle_cash_rate=0,
            risk_free_rate=0,
            interpretations=["start", "end"],
            duplicates="exclude",
            partial_bars="exclude",
            evening=False,
            data_path=args.data,
            data_sha256=raw_hash,
            fixed_boundaries=dict(
                IS_START=IS_START, IS_END=IS_END, OOS_START=OOS_START, OOS_END=OOS_END
            ),
        ),
    )
    write_json(args.output / "original_results_sha256.json", existing)
    minute = load_minute_data(
        args.data, duplicate_policy="exclude", audit_dir=args.output / "data_audit"
    )
    rows, coverage, indicators, primary, verifications = [], {}, {}, {}, []
    for label in ["start", "end"]:
        print(f"Resampling {label} interpretation", flush=True)
        bars = resample_to_15m(
            minute, minute_label=label, audit_dir=args.output / label / "data_audit"
        )
        coverage[label] = dict(
            bars.attrs.get("session_audit", {}),
            retained_bars=len(bars),
            first=bars.index[0],
            last=bars.index[-1],
        )
        for amplitude in [3, 2, 4, 5]:
            print(f"Evaluating {label}, amplitude {amplitude}", flush=True)
            full = calculate_halftrend(bars, amplitude=amplitude, channel_deviation=2)
            is_data, oos_data = split_is_oos(full)
            if amplitude == 3:
                indicators[label] = full
                full[["buy_signal", "sell_signal"]].to_csv(
                    args.output / label / "signals.csv"
                )
            # One full production indicator calculation per configuration; additional
            # prefix/perturbation calculations are verification-only.
            verifications.append(
                dict(
                    interpretation=label,
                    **verify_causal(bars, full, amplitude, len(bars) // 2),
                )
            )
            for period, window in [("IS", is_data), ("OOS", oos_data), ("FULL", full)]:
                scenarios = (
                    [("net", 5, 0, 1)]
                    if amplitude != 3
                    else [
                        ("gross", 0, 0, 1),
                        ("net", 5, 0, 1),
                        ("slip_1", 5, 1, 1),
                        ("slip_2", 5, 2, 1),
                        ("delay_2", 5, 0, 2),
                        ("buy_hold_gross", 0, 0, 1),
                        ("buy_hold_net", 5, 0, 1),
                    ]
                )
                for scenario, fee, slip, delay in scenarios:
                    evaluation = window
                    if scenario.startswith("buy_hold"):
                        evaluation = window.copy()
                        evaluation["buy_signal"] = False
                        evaluation["sell_signal"] = False
                    result = simulate_portfolio(
                        evaluation,
                        initial_capital=CAPITAL,
                        cost_bps=fee,
                        slippage_points=slip,
                        execution_delay=delay,
                        enter_first_bar=scenario.startswith("buy_hold"),
                    )
                    metadata = dict(
                        label=LABEL,
                        interpretation=label,
                        period=period,
                        amplitude=amplitude,
                        scenario=scenario,
                        cost_bps=fee,
                        slippage_points=slip,
                        execution_delay=delay,
                    )
                    rows.append(
                        export_run(
                            args.output / label / f"a{amplitude}" / period / scenario,
                            evaluation,
                            result,
                            metadata,
                        )
                    )
                    if amplitude == 3 and scenario == "net":
                        primary[label, period] = result
                    if amplitude == 3 and scenario == "gross":
                        from src.research import evaluate_window

                        _, baseline = evaluate_window(
                            window, initial_capital=CAPITAL, cost_bps=0
                        )
                        pd.testing.assert_series_equal(result.equity, baseline.equity)
                        pd.testing.assert_frame_equal(result.trades, baseline.trades)
                        pd.testing.assert_frame_equal(result.fills, baseline.fills)
    timestamp_differences(args.output, indicators, primary)
    table = pd.DataFrame(rows)
    table.drop(columns=["undefined_metrics"]).to_csv(
        args.output / "performance_comparison.csv", index=False
    )
    table.loc[table.scenario.isin(["net", "slip_1", "slip_2", "delay_2"])].drop(
        columns=["undefined_metrics"]
    ).to_csv(args.output / "sensitivity.csv", index=False)
    write_json(
        args.output / "coverage.json",
        dict(loading=minute.attrs, interpretations=coverage),
    )
    assert digest(args.data) == raw_hash, "Raw data changed"
    assert all(
        Path(p).exists() and digest(Path(p)) == h for p, h in existing.items()
    ), "Existing results changed"
    write_json(
        args.output / "verification.json",
        dict(
            causality=verifications,
            zero_cost_equivalence=True,
            all_run_reconciliations=True,
            run_count=len(rows),
            preserved_existing_results=len(existing),
            raw_data_unchanged=True,
        ),
    )
    build_report(args.output, table, coverage)
    print(f"Saved {len(rows)} runs to {args.output}", flush=True)


if __name__ == "__main__":
    main()
