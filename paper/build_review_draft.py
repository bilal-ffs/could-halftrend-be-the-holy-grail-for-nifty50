"""Assemble the publication-candidate manuscript from saved results only."""

import argparse
import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

REPO = Path(__file__).resolve().parents[1]
S2 = REPO / "results/stage2_futures_proxy_20261007_completed"
S3 = REPO / "results/stage3_SIMULATED_calendars_20261007_completed"
SOURCE_FILES = {}
CHART_CHECKS = []
BLUE, ORANGE, GREEN = "#176b87", "#d16b18", "#66813b"
PURPLE = "#76528f"
PERIODS = ["IS", "OOS", "FULL"]
MODES = ["entry", "daily", "equal_control"]
PERIOD_LABELS = {
    "IS": "Earlier period",
    "OOS": "Previously examined holdout",
    "FULL": "Full sample",
}
FUTURES_CASE_LABELS = {
    "gross": "No transaction costs",
    "net": "5 bps per side; zero slippage",
    "buy_hold_net": "Price-index buy-and-hold",
    "slip_1": "1 adverse index point per fill",
    "slip_2": "2 adverse index points per fill",
    "delay_2": "One additional included bar of delay",
}
CASE_NAMES = {
    "primary": "Primary",
    "fee_2": "2 bps fees",
    "slip_10": "10 bps slippage",
    "slip_25": "25 bps slippage",
    "vol_1_0": "Volatility x1.0",
    "vol_1_5": "Volatility x1.5",
    "near_0_9": "Near volatility x0.9",
    "near_1_1": "Near volatility x1.1",
    "combined_flat": "Combined flat",
    "combined_steep": "Combined steep",
}
CASE_LABELS = {
    "primary": "Primary volatility; 3 bps fees; no slippage",
    "fee_2": "2 bps premium fees per side",
    "slip_10": "10 bps adverse premium slippage per fill",
    "slip_25": "25 bps adverse premium slippage per fill",
    "vol_1_0": "Volatility multiplier 1.0",
    "vol_1_5": "Volatility multiplier 1.5",
    "near_0_9": "Near-term volatility 0.9 × long-term volatility",
    "near_1_1": "Near-term volatility 1.1 × long-term volatility",
    "combined_flat": "Combined flat-term scenario; 25 bps slippage",
    "combined_steep": "Combined steep-term scenario; 25 bps slippage",
}
MODE_NAMES = {
    "entry": "Entry-only",
    "daily": "Daily checks",
    "equal_control": "Equal-unit control",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def track(path):
    path = Path(path)
    SOURCE_FILES[str(path.relative_to(REPO))] = digest(path)
    return path


def load_json(path):
    return json.loads(track(path).read_text(encoding="utf-8"))


def load_csv(path, **kwargs):
    return pd.read_csv(track(path), **kwargs)


def pct(value):
    return "Unavailable" if pd.isna(value) else f"{100 * value:.2f}%"


def num(value, places=2):
    return "Unavailable" if pd.isna(value) else f"{value:,.{places}f}"


def curve(path, output):
    file = path / "equity.csv"
    if not file.exists():
        file = path / "equity.csv.gz"
    frame = load_csv(file)
    metrics = load_json(path / "metrics.json")
    marks = pd.to_datetime(frame.mark_time).dt.tz_convert("Asia/Kolkata")
    full = pd.Series(frame.equity.to_numpy(), index=pd.DatetimeIndex(marks))
    full.index = full.index.tz_localize(None)
    daily = full.groupby(full.index.normalize()).tail(1)
    initial = pd.Series(
        [500000.0],
        index=[
            pd.Timestamp(metrics["start_time"])
            .tz_convert("Asia/Kolkata")
            .tz_localize(None)
        ],
    )
    daily = pd.concat([initial, daily])
    assert abs(full.iloc[-1] - metrics["final_equity"]) < 1e-6
    dd = full / full.cummax().clip(lower=500000) - 1
    assert abs(dd.min() - metrics["max_drawdown"]) < 1e-10
    dd = pd.concat([initial * 0, dd])
    name = "_".join(path.relative_to(REPO / "results").parts)
    daily.to_csv(
        output / "supplements" / f"{name}_session_equity.csv",
        header=["equity_INR"],
        index_label="mark_time_Asia_Kolkata",
    )
    CHART_CHECKS.append(
        {
            "path": str(path.relative_to(REPO)),
            "final_equity": float(full.iloc[-1]),
            "max_drawdown": float(dd.min()),
            "passed": True,
        }
    )
    return daily, dd


def finish_figure(fig, output, name):
    fig.savefig(
        output / "figures" / f"{name}.png",
        dpi=260,
        bbox_inches="tight",
        facecolor="white",
    )
    fig.savefig(output / "figures" / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def axis_time(ax, period):
    ax.xaxis.set_major_locator(mdates.YearLocator(2 if period == "FULL" else 1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(alpha=0.18)


def figures(output, futures, options, cases):
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 10.5,
            "svg.fonttype": "none",
        }
    )
    for kind in ["futures", "options"]:
        for drawdown in [False, True]:
            fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), constrained_layout=True)
            for ax, period in zip(axes, ["FULL", "OOS"]):
                if kind == "futures":
                    paths = [
                        (
                            S2 / "start/a3" / period / "net",
                            "HalfTrend proxy",
                            BLUE,
                            "-",
                        ),
                        (
                            S2 / "start/a3" / period / "buy_hold_net",
                            "Buy-and-hold",
                            GREEN,
                            "--",
                        ),
                    ]
                else:
                    paths = [
                        (
                            S3 / "start/primary" / mode / period,
                            MODE_NAMES[mode],
                            color,
                            style,
                        )
                        for mode, color, style in zip(
                            MODES, [BLUE, ORANGE, GREEN], ["-", "--", ":"]
                        )
                    ]
                for path, label, color, style in paths:
                    equity, dd = curve(path, output)
                    values = dd if drawdown else equity / 100000
                    ax.plot(
                        values.index,
                        values.values,
                        label=label,
                        color=color,
                        linestyle=style,
                        linewidth=1.4,
                        marker=None,
                    )
                ax.set_title(
                    "Full history: 2015-2025"
                    if period == "FULL"
                    else "Historical holdout: 2022-2025"
                )
                if drawdown:
                    ax.yaxis.set_major_formatter(PercentFormatter(1))
                    ax.set_ylabel("Underwater return (negative)")
                else:
                    ax.set_ylabel("Account value (INR lakh)")
                    ax.axhline(5, color="#777777", lw=0.6)
                axis_time(ax, period)
                ax.legend(loc="lower left" if drawdown else "upper left")
            number = (1 if kind == "futures" else 6) + int(drawdown)
            finish_figure(
                fig,
                output,
                f"figure_{number:02d}_{kind}_{'drawdown' if drawdown else 'equity'}",
            )
    annual = load_csv(S2 / "annual_net_performance.csv")
    selected = annual[
        (annual.interpretation == "start")
        & (annual.amplitude == 3)
        & (annual.period == "FULL")
    ]
    oa = load_csv(S3 / "start/primary/entry/FULL/annual_net.csv")
    years = list(oa.year)
    fig, ax = plt.subplots(figsize=(11.5, 4.2), constrained_layout=True)
    for offset, vals, label, color in [
        (
            -0.25,
            selected[selected.scenario == "net"]
            .set_index("year")
            .loc[years, "total_return"],
            "HalfTrend futures proxy",
            BLUE,
        ),
        (
            0,
            selected[selected.scenario == "buy_hold_net"]
            .set_index("year")
            .loc[years, "total_return"],
            "Buy-and-hold",
            GREEN,
        ),
        (0.25, oa.total_return, "SIMULATED entry-only calendar", ORANGE),
    ]:
        ax.bar(
            np.arange(len(years)) + offset, vals, width=0.24, label=label, color=color
        )
    ax.set_xticks(
        np.arange(len(years)),
        [str(y) + "*" if y in [2015, 2025] else str(y) for y in years],
    )
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Net calendar-year return")
    ax.axhline(0, color="#777777", lw=0.8)
    ax.grid(axis="y", alpha=0.18)
    ax.legend(loc="upper left", ncol=2)
    finish_figure(fig, output, "figure_10_annual_returns")
    fig, ax = plt.subplots(figsize=(11, 4), constrained_layout=True)
    labels = [
        "No fees",
        "5 bps fees",
        "+1 point slip",
        "+2 points slip",
        "Extra-bar delay",
    ]
    for offset, interp, color, hatch in [
        (-0.18, "start", BLUE, ""),
        (0.18, "end", ORANGE, "///"),
    ]:
        vals = []
        for case in ["gross", "net", "slip_1", "slip_2", "delay_2"]:
            row = futures[
                (futures.interpretation == interp)
                & (futures.amplitude == 3)
                & (futures.period == "OOS")
                & (futures.scenario == case)
            ].iloc[0]
            vals.append(row.total_return)
        ax.bar(
            np.arange(5) + offset,
            vals,
            width=0.35,
            color=color,
            hatch=hatch,
            label=(
                "Start: primary" if interp == "start" else "End: grouping sensitivity"
            ),
        )
    ax.set_xticks(np.arange(5), labels)
    ax.set_ylabel("Previously examined holdout total return")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.axhline(0, color="#777777", lw=0.8)
    ax.legend()
    ax.grid(axis="y", alpha=0.18)
    finish_figure(fig, output, "figure_03_futures_execution_sensitivity")
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    for offset, interp, color, hatch in [
        (-0.18, "start", BLUE, ""),
        (0.18, "end", ORANGE, "///"),
    ]:
        d = futures[
            (futures.interpretation == interp)
            & (futures.period == "OOS")
            & (futures.scenario == "net")
        ].set_index("amplitude")
        ax.bar(
            np.arange(4) + offset,
            d.loc[[2, 3, 4, 5], "total_return"],
            width=0.35,
            color=color,
            hatch=hatch,
            label=(
                "Start: primary" if interp == "start" else "End: grouping sensitivity"
            ),
        )
    ax.set_xticks(np.arange(4), ["2", "3 (reference)", "4", "5"])
    ax.set_xlabel("HalfTrend lookback amplitude (completed 15-minute bars)")
    ax.set_ylabel("Previously examined holdout net total return")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.axhline(0, color="#777777", lw=0.8)
    ax.grid(axis="y", alpha=0.18)
    ax.legend()
    finish_figure(fig, output, "figure_04_amplitude_sensitivity")
    fig, axes = plt.subplots(
        1, 2, figsize=(12.5, 6.0), constrained_layout=True, sharey=True
    )
    names = [c[0] for c in cases]
    for ax, interp in zip(axes, ["start", "end"]):
        for offset, mode, color in [(-0.18, "entry", BLUE), (0.18, "daily", ORANGE)]:
            d = options[
                (options.interpretation == interp)
                & (options.period == "OOS")
                & (options["mode"] == mode)
            ].set_index("case")
            ax.barh(
                np.arange(10) + offset,
                d.loc[names, "total_return"],
                height=0.35,
                color=color,
                label=MODE_NAMES[mode],
            )
        ax.set_yticks(np.arange(10), [CASE_NAMES[x] for x in names])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.set_xlabel("SIMULATED historical OOS net return")
        ax.set_title(
            "Start: primary" if interp == "start" else "End: grouping sensitivity"
        )
        ax.axvline(0, color="#777777", lw=0.8)
        ax.grid(axis="x", alpha=0.18)
        ax.legend(loc="lower right")
    finish_figure(fig, output, "figure_09_option_sensitivity")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), constrained_layout=True)
    for mode, color, style in zip(MODES, [BLUE, ORANGE, GREEN], ["-", "--", ":"]):
        g = load_csv(S3 / "start/primary" / mode / "OOS/greek_history.csv.gz")
        residual = np.sort(g.loc[g.long_quantity > 0, "residual_theta"].abs().values)
        axes[0].plot(
            residual,
            np.arange(1, len(residual) + 1) / len(residual),
            color=color,
            linestyle=style,
            label=MODE_NAMES[mode],
        )
    axes[0].axvline(0.1, color="#777777", linestyle="--", lw=0.8)
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_xlabel("Absolute net theta / initial absolute long-leg theta")
    axes[0].set_ylabel("Fraction of active 15-minute marks at or below x")
    axes[0].set_title("Theta drift: SIMULATED primary OOS")
    axes[0].legend(loc="lower right")
    for offset, mode, color in zip([-0.24, 0, 0.24], MODES, [BLUE, ORANGE, GREEN]):
        d = options[
            (options.interpretation == "start")
            & (options.case == "primary")
            & (options.period == "OOS")
            & (options["mode"] == mode)
        ].iloc[0]
        values = [
            d.mean_net_delta_exposure_fraction,
            d.mean_collateral_fraction,
            d.mean_gross_underlying_exposure_fraction,
        ]
        axes[1].bar(
            np.arange(3) + offset,
            values,
            width=0.23,
            color=color,
            label=MODE_NAMES[mode],
        )
    axes[1].set_xticks(
        np.arange(3),
        [
            "Directional\nexposure",
            "Reserved\ncollateral",
            "Gross underlying-\nequivalent exposure",
        ],
    )
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_ylabel("Mean fraction of portfolio equity, all marks")
    axes[1].set_title("Matching changes exposure as well as theta")
    axes[1].legend(loc="upper left")
    for ax in axes:
        ax.grid(alpha=0.18)
    finish_figure(fig, output, "figure_08_theta_and_exposure")
    fig, ax = plt.subplots(figsize=(10.5, 3.7), constrained_layout=True)
    for offset, interp, color in [(-0.18, "start", BLUE), (0.18, "end", ORANGE)]:
        d = futures[
            (futures.interpretation == interp)
            & (futures.amplitude == 3)
            & (futures.scenario == "net")
        ].set_index("period")
        ax.bar(
            np.arange(3) + offset,
            d.loc[PERIODS, "fraction_of_closed_net"],
            width=0.35,
            color=color,
            label=(
                "Start: primary" if interp == "start" else "End: grouping sensitivity"
            ),
        )
    ax.set_xticks(
        np.arange(3), ["Earlier period", "Historical holdout", "Full history"]
    )
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Five best trades / aggregate closed net P&L")
    ax.legend()
    ax.grid(axis="y", alpha=0.18)
    finish_figure(fig, output, "figure_05_trade_concentration")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for interp, color, style in [
        ("start", BLUE, "-"),
        ("end", ORANGE, "--"),
    ]:
        for ax, path in [
            (axes[0], S2 / interp / "a3/OOS/net"),
            (axes[1], S3 / interp / "primary/entry/OOS"),
        ]:
            equity, _ = curve(path, output)
            ax.plot(
                equity.index,
                equity / 100000,
                color=color,
                linestyle=style,
                label=(
                    "Start: primary"
                    if interp == "start"
                    else "End: grouping sensitivity"
                ),
            )
    for ax, title in zip(
        axes, ["Index-based futures proxy", "SIMULATED entry-only calendars"]
    ):
        ax.set_title(title)
        ax.set_ylabel("Account value (INR lakh)")
        axis_time(ax, "OOS")
        ax.legend()
    finish_figure(fig, output, "figure_11_grouping_sensitivity")


class Manuscript:
    def __init__(self, output):
        self.output = output
        self.parts = []
        self.table_count = 0

    def p(self, text, cls=""):
        self.parts.append(f'<p class="{cls}">{html.escape(str(text))}</p>')

    def heading(self, text, level=1):
        self.parts.append(f"<h{level}>{html.escape(text)}</h{level}>")

    def page(self):
        self.parts.append('<p class="pagebreak">&nbsp;</p>')

    def table(self, title, headers, rows, note=""):
        self.table_count += 1
        self.p(f"Table {self.table_count}. {title}", "caption")
        self.parts.append(
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
            + "</tr></thead><tbody>"
        )
        for row in rows:
            self.parts.append(
                "<tr>"
                + "".join(f"<td>{html.escape(str(v))}</td>" for v in row)
                + "</tr>"
            )
        self.parts.append("</tbody></table>")
        if note:
            self.p(note, "note")

    def figure(self, number, name, caption):
        file = self.output / "figures" / (name + ".png")
        self.parts.append(
            f'<p class="figure"><img src="{file.resolve().as_uri()}" width="640"></p>'
        )
        self.p(f"Figure {number}. {caption}", "caption")

    def save(self):
        css = """
        @page {size:A4; margin:0.75in;}
        body {font-family:'Times New Roman';
        font-size:11pt;line-height:115%;color:#202020;}
        p {margin:0 0 7pt 0;text-align:justify;}
        h1 {font-size:16pt;color:#173b55;margin:16pt 0 8pt;page-break-after:avoid;}
        h2 {font-size:12pt;color:#173b55;margin:12pt 0 6pt;page-break-after:avoid;}
        .title
        {font-size:24pt;font-weight:bold;text-align:center;color:#173b55;margin-top:40pt;}
        .subtitle {font-size:15pt;text-align:center;margin:18pt 0;}
        .center {text-align:center;margin:12pt 0;}
        .review {font-size:10pt;color:#924500;border-top:1px solid
        #aaaaaa;padding-top:10pt;}
        .pagebreak {page-break-before:always;margin:0;font-size:1pt;}
        .caption {font-size:9.5pt;text-align:left;margin:7pt 0;page-break-after:avoid;}
        .note {font-size:9pt;text-align:left;margin:6pt 0 12pt;}
        .equation {text-align:center;font-family:'Cambria Math';margin:8pt 0;}
        .figure {text-align:center;page-break-inside:avoid;margin:10pt 0 0;}
        table {border-collapse:collapse;width:100%;font-size:9pt;margin-bottom:8pt;}
        td,th {border:0.5pt solid #b7c4ce;padding:4pt;vertical-align:top;}
        th {background:#173b55;color:white;font-weight:bold;}
        tr {page-break-inside:avoid;} thead {display:table-header-group;}
        a {color:#176b87;} .reference {text-align:left;font-size:10pt;}
        """
        body = "\n".join(self.parts)
        appendix_at = body.index("<h1>Appendix A. Complete Stage 2 run summary</h1>")
        main_body = body[:appendix_at]
        trailing_break = '<p class="pagebreak">&nbsp;</p>'
        if main_body.endswith(trailing_break):
            main_body = main_body[: -len(trailing_break)]
        main = main_body
        supplement = (
            "<h1>Supplementary results and research audit</h1>"
            "<p class=\"\">Supplement to <i>HalfTrend on NIFTY 50: Transaction Costs, "
            "Execution Sensitivity, and Simulated Call Calendar Spreads</i>. "
            "All values summarize the completed saved runs; this document does not "
            "contain newly computed research results.</p>"
            + body[appendix_at:]
        )

        def document(title, contents):
            return (
                '<!DOCTYPE html><html><head><meta charset="utf-8"><title>'
                + html.escape(title)
                + f"</title><style>{css}</style></head><body>"
                + contents
                + "</body></html>"
            )

        (self.output / "HalfTrend_NIFTY50_Publication_Candidate.html").write_text(
            document(
                "HalfTrend on NIFTY 50 - Publication Candidate", main
            ),
            encoding="utf-8",
        )
        (self.output / "Supplementary_Results.html").write_text(
            document("Supplementary results and research audit", supplement),
            encoding="utf-8",
        )


def row_of(frame, **kwargs):
    chosen = frame
    for key, value in kwargs.items():
        chosen = chosen[chosen[key] == value]
    assert len(chosen) == 1, kwargs
    return chosen.iloc[0]


def build_text(output, futures, options, config2, config3, stage1, revision):
    d = Manuscript(output)
    d.p(
        "HalfTrend on NIFTY 50: Transaction Costs, Execution Sensitivity, "
        "and Simulated Call Calendar Spreads",
        "title",
    )
    d.p(
        "A historical evaluation of a long-only signal and modeled call calendars",
        "subtitle",
    )
    d.p("Mohd Bilal", "center")
    d.p("Independent Researcher | MSc Data Science, CU ’28", "center")
    d.p("Working paper · 7 October 2026", "center")
    d.heading("Abstract")
    d.p(
        "This study evaluates a long-only HalfTrend rule on NIFTY 50 minute "
        "observations from January 2015 to July 2025. The reference "
        "configuration is amplitude 3 (the lookback in completed 15-minute "
        "bars) and channel deviation 2. The primary data convention is "
        "start-labeled minutes, based on the author’s reported TradingView "
        "check. A fully funded index-based futures proxy uses INR 500,000 and "
        "5 bps per side on underlying notional. In the previously examined "
        "2022–2025 historical holdout, it returns 33.16% net with 12.61% "
        "maximum drawdown, compared with 38.56% and 17.12% for price-index "
        "buy-and-hold. Separate proxy stresses return 22.87% with two adverse "
        "index points per fill and 25.23% with one additional included-bar "
        "delay. End grouping with two-point slippage returns −0.39%. A separate "
        "SIMULATED Black–Scholes call-calendar study, using approximately "
        "60/30-day maturities and entry-only model-theta matching, returns "
        "7.48% with 1.54% maximum drawdown after 3 bps per-side premium fees "
        "and zero slippage; daily checks return 7.31%. At 25 bps adverse "
        "premium slippage, the entry-only return is −2.64%. These historical "
        "outcomes do not establish statistical evidence of alpha or executable "
        "derivative performance. Option prices and Greeks are modeled, and "
        "theta matching also changes directional exposure."
    )
    d.p(
        "AI-use disclosure: OpenAI Codex assisted with coding, analysis checks, "
        "figure preparation and drafting. The author is responsible for the "
        "final manuscript.",
        "note",
    )
    d.p(
        "Keywords: NIFTY 50; HalfTrend; technical trading; transaction costs; causal "
        "backtesting; futures proxy; simulated call calendars; theta matching.",
        "note",
    )
    d.heading("1. Introduction and research questions")
    d.p(
        "This paper evaluates a long-only HalfTrend rule on NIFTY 50. It asks how "
        "historical return and drawdown compare with a price-index benchmark, how "
        "sensitive results are to trading assumptions, and what a separate "
        "option-pricing model implies for a call calendar. It studies one index and "
        "one historical path; results do not generalize automatically to other "
        "markets or establish statistical evidence of alpha."
    )
    d.p(
        "The paper evaluates a fully funded index-based futures proxy against a "
        "price-index benchmark, then examines a separate SIMULATED bullish call "
        "calendar using the same underlying signal. It focuses on transaction costs, "
        "execution sensitivity and dependence on option-model assumptions."
    )
    d.p(
        "Amplitude 3 is the reference configuration used in this study. The available "
        "records do not establish that it was selected before inspection of the "
        "historical sample; the comparisons across amplitudes 2–5 are descriptive "
        "sensitivity analyses. An archived Stage 3 report calls amplitude 3 "
        "predeclared, while the Stage 2 report says no parameter was selected; no "
        "dated selection record resolves that conflict. Amplitude is the HalfTrend "
        "lookback, measured in completed 15-minute bars. Channel deviation is a "
        "separate parameter that scales the channel. The reference parameter "
        "configuration is distinct from the primary timestamp convention. Amplitudes "
        "2–5 do not provide "
        "independent validation. The primary start-labeled timestamp convention is "
        "a separate data choice, based on the author’s reported TradingView check."
    )
    d.p(
        "The questions are: (i) what did the reference configuration produce "
        "under the specified costs and fills; "
        "(ii) how do return and marked-to-market risk compare with buy-and-hold; "
        "(iii) how sensitive are findings to fill assumptions and candle grouping; "
        "and (iv) does approximately matching model theta improve the modeled calendar "
        "tradeoff, and does daily rebalancing add value? Positive "
        "historical profitability "
        "is distinguished from statistical significance and practical executability."
    )
    d.heading("2. Related literature")
    d.p(
        "Brock, Lakonishok and LeBaron (1992) evaluate moving-average and "
        "trading-range "
        "rules using historical Dow Jones data and bootstrap comparisons. Their study "
        "motivates explicit technical-rule testing, but does not "
        "establish that HalfTrend "
        "works on NIFTY 50. Sullivan, Timmermann and White (1999) examine "
        "selection bias "
        "when many technical rules are considered. This motivates disclosure of the "
        "previously examined holdout and the distinction between sensitivity analysis "
        "and independent experiments. The cases here are not independent statistical "
        "replications, and no multiple-testing-adjusted superiority test is claimed."
    )
    d.p(
        "Black and Scholes (1973) provide a theoretical option-valuation foundation. "
        "The dividend-yield European-call expressions summarized by Back, Liu and "
        "Loewenstein (n.d., Chapter 9) are used for scenario pricing and Greeks. "
        "Theory does not make these marks observed market premiums. Politis and Romano "
        "(1994) develop resampling for weakly dependent observations, "
        "relevant to future "
        "uncertainty analysis; no such bootstrap estimates were computed "
        "in these stages."
    )
    d.p(
        "The operational definition is the supplied Pine-style state logic and its "
        "Python implementation. The exact original indicator publication and version "
        "have not been identified, so no specific source attribution is claimed. This "
        "is a selective literature review, not a claim of priority."
    )
    d.heading("3. Data, provenance and research chronology")
    d.p(
        "The local input is NIFTY_50_minute.csv, obtained from Kaggle according to the "
        "author. Its 975,321 rows are parsed explicitly as day-month-year hour:minute "
        "and localized to Asia/Kolkata. The exact Kaggle page, uploader, version, "
        "download date and usage rights are unknown. Independent identification "
        "and permitted reuse therefore cannot be established. A local-file hash "
        "does not verify the dataset’s origin or license."
    )
    d.p(
        "The author reports personally comparing observations with TradingView and "
        "confirming start-labeled minutes. This check has not been independently "
        "replicated. End grouping shifts the observed minutes before bar aggregation "
        "and is reported as an alternative grouping sensitivity, not a second data "
        "source."
    )
    d.table(
        "Data coverage and exclusions",
        ["Item", "Primary start labels", "End grouping test"],
        [
            ["Raw source rows", "975,321", "Same raw input"],
            ["Conflicting duplicate groups / rows", "4 / 8 excluded", "Same exclusion"],
            ["Included complete regular bars", "64,951", "62,349"],
            ["Evening minutes excluded", "612", "612"],
            ["Outside regular/evening minute windows", "0", "2,600"],
            ["Regular incomplete bars excluded", "40", "5,264"],
            ["Volume", "Unavailable (all zero)", "Unavailable (all zero)"],
        ],
        "The loader rejects conflicts by default. Research runs "
        "explicitly select whole-group "
        "exclusion. Alternative grouping changes coverage as well as OHLC values.",
    )
    d.p(
        "The four conflicting timestamp groups are 29 June 2015 11:54, 10 August "
        "2015 09:36 and 10:54, and 13 August 2015 09:23. Audits retain the eight "
        "original rows and policy decisions. Regular hours are 09:15-15:30. Fifteen-"
        "minute candles are anchored at 09:15 and a normal session has 25 complete "
        "candles. Evening observations and incomplete regular candles are excluded; "
        "complete candles on otherwise partial days remain. Missing prices or "
        "sessions are not filled. All-zero volume is unavailable information, not "
        "evidence of no trading. Classification uses clock windows without an "
        "independently verified historical exchange calendar."
    )
    d.p(
        "Fixed earlier-period boundaries are 9 January 2015-8 January 2022; fixed "
        "historical holdout boundaries are 9 January 2022-25 July 2025. Actual "
        "included opens and closing marks determine elapsed time. For the primary "
        "holdout they are 10 January 2022 09:15 and 25 July 2025 15:30. Earlier/"
        "holdout portfolios restart flat, discard pending pre-boundary signals and "
        "retain indicator history. Full-history portfolios carry positions and "
        "equity across the split; full-history returns are not obtained by adding "
        "the two reset-window returns. The holdout was examined previously and is "
        "not a fresh or independent out-of-sample test. Archived documentation "
        "conflicts on whether amplitude 3 was predeclared; no dated record establishes "
        "when that reference setting was chosen."
    )
    d.heading("4. Signal, accounting and metric methods")
    d.heading("4.1. HalfTrend and next-bar execution", 2)
    d.p(
        "The reference configuration (amplitude = 3, channel deviation = 2) uses "
        "an amplitude lookback of three completed 15-minute bars. The indicator uses "
        "rolling high/low extrema and simple averages over that lookback, a 100-bar "
        "Wilder average true range, and stateful trend transitions. A bullish "
        "transition requires the low average above the maintained minimum high "
        "and the completed close above the preceding high; the bearish transition "
        "uses the corresponding high average, maximum low and preceding low. "
        "Signals are gated by the implemented ATR warmup. Channel deviation is a "
        "distinct parameter that scales the displayed channel; it is not the "
        "amplitude lookback or a separately optimized entry filter. Start-labeled "
        "minutes define the primary data convention and are not a strategy parameter."
    )
    d.p(
        "For each timestamp grouping, the production indicator is computed once "
        "over full causal history, then sliced for evaluation. Decisions use the "
        "last completed candle; purchases and exits fill at the next available "
        "included open, potentially after a data gap. No current candle’s future "
        "close/high/low determines that fill. Prefix and future-price perturbation "
        "checks compare earlier indicator values, signals, fills and equity. "
        "These checks establish implementation causality for tested cases, not "
        "the attainability of an idealized opening-price fill in live markets."
    )
    d.heading("4.2. Capital, fees and portfolio marks", 2)
    d.p(
        "The index proxy preserves the existing fee-reserved fractional sizing. At an "
        "entry, Q = cash x (1 - f) / purchase fill, where f is the per-side fee "
        "rate. Quantity remains fixed through the trade. Entry notional plus "
        "entry fees consumes cash x (1 - f²), retaining cash x f² rather than "
        "silently deleting it or switching sizing. Fees equal actual quantity "
        "times each leg’s actual fill price times f. One cash-and-position model "
        "generates both the ledger and equity; closed net P&L already includes "
        "entry and exit fees. Final equity is reconciled against closed net P&L, "
        "open gross P&L and the open entry fee, and separately reconstructed "
        "from fills. Invalid or insolvent equity raises explicitly."
    )
    d.heading("4.3. Performance conventions", 2)
    d.p(
        "Initial capital is timestamped at the first evaluated observed open; "
        "terminal equity is marked at the final included interval end. Calendar "
        "CAGR uses elapsed seconds divided by 365.25 days per year. Sharpe and "
        "Sortino use daily last-mark account returns, include the first change "
        "from capital, and annualize at 252 sessions per year. Missing dates "
        "are not inserted as zero returns. Annual risk-free rates are divided "
        "arithmetically by 252: 0% for proxy Sharpe/Sortino ratios and 6% for the "
        "main SIMULATED option ratios. Zero-rate option ratios and matched 6%-rate "
        "proxy comparisons are "
        "also provided. The 6% continuous pricing discount rate is a separate "
        "model input; idle cash earns zero in every run."
    )
    d.p(
        "Sharpe uses sample standard deviation. The repository’s Sortino variant "
        "uses sample standard deviation of negative excess daily observations, "
        "not root-mean-square downside deviation across all observations; this "
        "must be considered before comparing with external Sortino reports. "
        "Undefined ratios are null with reasons. Calmar divides calendar CAGR "
        "by absolute maximum drawdown. Drawdown uses starting capital and all "
        "included 15-minute marks; its duration is the longest consecutive "
        "underwater observation count, not elapsed calendar recovery time. "
        "Equity charts sample session-end values for readability, while drawdown "
        "plots retain all marked observations."
    )
    d.p(
        "Profit factor, win rate and expectancy refer to completed trades or "
        "completed option signal groups. Expectancy is actual INR per group "
        "with changing entry equity, not fixed-stake points. Open P&L is "
        "reported separately. Calendar-year returns compare annual last marks "
        "with the previous annual last mark; 2015 and 2025 are partial years. "
        "Fee totals are already deducted from equity. Gross-minus-net returns "
        "are not simply paid fees because later quantities and compounding differ."
    )
    d.heading("5. Index-based futures proxy")
    d.p(
        "The reference configuration (amplitude = 3, channel deviation = 2) is "
        "evaluated using the primary start-labeled timestamp convention. These are "
        "separate choices. Every Stage 2 result is an index-based futures proxy "
        "using spot-index "
        "observations, INR 500,000 starting capital, fractional normalized units "
        "and no leverage. Quantity follows the preserved sizing rule and is "
        "fixed within each trade. Gross means zero fees/slippage; primary net "
        "means 5 bps each side on actual underlying notional and zero slippage. "
        "This is not an actual-contract futures strategy. Basis, funding, "
        "historical lots, margin, rolls and executable quotes are not represented."
    )
    d.p(
        "Buy-and-hold purchases at the first included open using the same "
        "capital, fractional sizing and fee rate, holds fixed quantity and "
        "remains open at the final mark. There is no hypothetical exit fee. "
        "The comparison is to NIFTY’s price index, excluding dividends; it "
        "is not an observed ETF return or a total-return benchmark. Strategy "
        "and benchmark observations match within each grouping/window."
    )
    rows = []
    for period in PERIODS:
        for scenario, label in [
            ("gross", "Proxy gross"),
            ("net", "Proxy net"),
            ("buy_hold_net", "Buy-and-hold net"),
        ]:
            m = row_of(
                futures,
                interpretation="start",
                amplitude=3,
                period=period,
                scenario=scenario,
            )
            rows.append(
                [
                    PERIOD_LABELS[period],
                    label,
                    pct(m.total_return),
                    pct(m.cagr),
                    pct(abs(m.max_drawdown)),
                    num(m.final_equity, 0),
                ]
            )
    d.table(
        "Proxy returns and risk",
        ["Evaluation window", "Case", "Total return", "Calendar CAGR", "Maximum drawdown", "Final equity (INR)"],
        rows,
        "Earlier period and historical holdout reset to flat positions and INR "
        "500,000. The full sample carries positions across the boundary. Drawdown "
        "is shown as a positive peak-to-trough magnitude here; drawdown plots show "
        "negative underwater returns. The historical holdout was examined previously.",
    )
    rows = []
    for period in PERIODS:
        m = row_of(
            futures, interpretation="start", amplitude=3, period=period, scenario="net"
        )
        rows.append(
            [
                PERIOD_LABELS[period],
                int(m.trade_count),
                pct(m.win_rate),
                num(m.profit_factor, 3),
                num(m.expectancy),
                num(m.total_fees),
                pct(m.exposure_observed_bars),
            ]
        )
    d.table(
        "Proxy completed trades and costs",
        [
            "Evaluation window",
            "Trades",
            "Win rate",
            "Profit factor",
            "Expectancy INR",
            "Fees INR",
            "Exposure",
        ],
        rows,
        "Exposure is the fraction of included observations with a long position; "
        "calendar holding fractions are in the supplement. Primary "
        "terminal strategy P&L is closed.",
    )
    rows = []
    for period in PERIODS:
        m = row_of(
            futures, interpretation="start", amplitude=3, period=period, scenario="net"
        )
        rows.append(
            [
                PERIOD_LABELS[period],
                num(m.sharpe_ratio, 3),
                num(m.sortino_ratio, 3),
                num(m.calmar_ratio, 3),
                int(m.drawdown_duration),
            ]
        )
    d.table(
        "Proxy daily ratios and drawdown duration",
        ["Evaluation window", "Sharpe (0% annual RF)", "Sortino variant (0% annual RF)", "Calmar", "Duration (bars)"],
        rows,
        "Proxy risk ratios use a zero annual risk-free comparison rate; the Sortino "
        "variant uses the sample standard deviation of negative excess daily returns.",
    )
    d.p(
        "In the previously examined historical holdout, the primary start-labeled "
        "reference configuration ends at INR 665,819.57, a net profit of "
        "INR 165,819.57, after INR 224,248.57 of modeled fees across 400 trades. "
        "Its 33.16% return trails buy-and-hold’s 38.56%, while its 12.61% maximum "
        "drawdown is smaller than 17.12%. Average closed-trade net P&L is INR "
        "414.55. This is positive historical net profitability under the stated "
        "configuration and proxy assumptions, not statistical evidence of alpha. "
        "The proxy’s drawdown is lower and its total return is also lower than the "
        "price-index benchmark; exposure is not matched."
    )
    d.figure(
        1,
        "figure_01_futures_equity",
        "Primary start-labeled index-based futures proxy and "
        "price-index buy-and-hold after fees. Session-end account values; "
        "both start with "
        "INR 5 lakh. Full and holdout panels are separate runs.",
    )
    d.figure(
        2,
        "figure_02_futures_drawdown",
        "Primary proxy and buy-and-hold drawdowns after fees, "
        "calculated at every included 15-minute mark with starting "
        "capital as the initial peak.",
    )
    d.heading("5.1. Execution, amplitude and concentration sensitivity", 2)
    rows = []
    for scenario, label in [
        ("net", "Reference: 5 bps/side, no slippage"),
        ("slip_1", "+1 point per fill"),
        ("slip_2", "+2 points per fill"),
        ("delay_2", "One extra bar delay"),
    ]:
        m = row_of(
            futures,
            interpretation="start",
            amplitude=3,
            period="OOS",
            scenario=scenario,
        )
        rows.append(
            [label, pct(m.total_return), pct(abs(m.max_drawdown)), num(m.expectancy)]
        )
    d.table(
        "Reference-configuration proxy: start grouping, historical holdout",
        ["Case", "Net return", "Maximum drawdown", "Expectancy (INR/trade)"],
        rows,
        "Slippage increases purchase fills and decreases sales. All rows "
        "use 5 bps per side on underlying notional; the reference case uses zero "
        "slippage. Drawdown is a positive magnitude in this table and negative in "
        "the underwater plots. Slippage and delay are separate stresses, not a "
        "combined case.",
    )
    d.p(
        "Two adverse index points per fill reduce primary holdout return to "
        "22.87%; one extra included bar of delay gives 25.23%. These separately "
        "tested results apply to the start-grouping holdout only. Amplitudes 2–5 "
        "are descriptive sensitivities around the reference setting. The five best "
        "completed primary holdout trades total INR 112,519.62, or 67.86% of "
        "aggregate closed net P&L and 13.73% of positive P&L. This is descriptive "
        "concentration: those trades are not removed and subsequent sizing is "
        "not recomputed. Concentration ratios can exceed 100% if other trades "
        "lose money in aggregate, as in the end-grouping sensitivity case."
    )
    d.figure(
        3,
        "figure_03_futures_execution_sensitivity",
        "Total return in the previously examined historical holdout under separately "
        "tested fee, slippage and delay assumptions. Start grouping is the reported "
        "primary convention; hatched bars show alternative end grouping. No-fee and "
        "fee-paying runs have different subsequent sizing.",
    )
    d.figure(
        4,
        "figure_04_amplitude_sensitivity",
        "Amplitude 3 is retained as the reference configuration. These comparisons "
        "describe parameter sensitivity and do not constitute independent validation.",
    )
    d.figure(
        5,
        "figure_05_trade_concentration",
        "Share of aggregate closed net P&L attributable "
        "to the five best completed proxy trades. Ratios above 100% "
        "indicate aggregate losses "
        "in the other trades; this is not a trade-exclusion experiment.",
    )
    d.heading("6. SIMULATED bullish call calendars")
    d.heading("6.1. Pricing, synthetic maturities and causal volatility", 2)
    d.p(
        "On a bullish signal, the calendar buys a longer-dated European call "
        "and sells a nearer-dated call at the same strike. The strike is "
        "exactly the preceding completed underlying close, not an assumed "
        "exchange strike grid. Both legs execute at the next included open. "
        "The strike remains frozen while that spread is active. Synthetic "
        "expiries are the entry local date plus 60 and 30 calendar days, "
        "weekend dates advanced to Monday at 15:30 Asia/Kolkata. No historical "
        "weekly/monthly exchange expiry or holiday calendar is claimed."
    )
    d.p(
        "The model uses continuous annual r = 6% and dividend yield q = 1%. "
        "With tau measured by actual seconds / (365 x 86,400), each European "
        "call is valued using dividend-yield Black-Scholes:"
    )
    d.p("C = S e^(−qτ) N(d₁) − K e^(−rτ) N(d₂)", "equation")
    d.p(
        "d₁ = [ln(S/K) + (r − q + σ²/2)τ] / (σ√τ);  d₂ = d₁ − σ√τ",
        "equation",
    )
    d.p(
        "Sigma is the sample standard deviation of 21 observed-session daily "
        "log returns times sqrt(252), available only from the following "
        "session. Primary sigma is 1.2 times that estimate for both maturities. "
        "Multipliers 1.0 and 1.5 and near-leg relative multipliers 0.9 and 1.1 "
        "are sensitivity assumptions, not observed IV. Volatility updates "
        "causally at session opens and remains fixed within that session. "
        "Calendar-time decay and overnight gaps are included. Undefined or "
        "zero estimates prevent entry; no artificial volatility floor or "
        "standalone-call substitute is used. The 21-return estimate requires "
        "22 prior observed closes. Initial evaluated warmup remains cash."
    )
    d.heading("6.2. Theta matching, Greek units and capital", 2)
    d.p(
        "At execution the target short/long quantity ratio is "
        "abs(theta_long)/abs(theta_short). Integer normalized units are "
        "chosen to minimize absolute ratio error globally over feasible "
        "pairs, with larger long quantity breaking ties. Both quantities "
        "are at least one, long quantity is at least short quantity, and "
        "net model delta is positive at construction. These are INR 1 per "
        "premium/index point research units, not actual exchange lots."
    )
    d.p(
        "Gross long-leg purchase premium PLUS BOTH entry fees must be at "
        "most 5% of pre-entry equity. Short premium receipts cannot enlarge "
        "that budget. Cash after both fills must cover reserved collateral "
        "equal to short units times strike. This conservative research "
        "collateral is not historical exchange margin. One spread is active "
        "at a time. Infeasible or unaffordable constructions are skipped "
        "with reasons. There is no unhedged long-call fallback."
    )
    d.p(
        "Theta is currency per calendar day for the passage of time, and net "
        "theta is long units times long theta minus short units times short "
        "theta. Residual theta divides this quantity by initial long units "
        "times absolute long theta for that spread; the denominator resets "
        "at a new spread or roll, not daily. Delta exposure is net delta "
        "times underlying price. Gamma is delta change per index point; "
        "vega is currency per one volatility percentage point. Net Greeks "
        "are signed leg sums. Model theta matching does not remove gamma, "
        "vega, jump, model or execution risks."
    )
    d.heading("6.3. Management, rolls, costs and liabilities", 2)
    d.p(
        "The primary version matches theta only at entry and makes no "
        "interim adjustment. Daily management checks the preceding completed "
        "session’s final marks once per session. If absolute residual "
        "theta exceeds 10% of initial absolute long theta, it chooses the "
        "closest feasible integer short target using those marks and fills "
        "at the next observed session open. The long quantity stays fixed "
        "until a roll. Current-open Greeks and cash validate positive delta "
        "and collateral feasibility, but do not replace the preceding-mark "
        "theta target. Positive delta is enforced at entry and adjustment; "
        "intraday drift is reported without adding risk exits."
    )
    d.p(
        "Both legs close on a bearish completed-bar signal. A roll is "
        "scheduled at 09:15 on the weekday on or before short-expiry minus "
        "five calendar days. If still bullish, a new spread opens at that "
        "open and pays all leg costs. Missing sessions use the next "
        "available open; late-buffer and expiry-crossing gaps are explicit "
        "events. An expired leg uses intrinsic at that observed open, not "
        "a reconstructed historical settlement price. No historical run "
        "actually reached a roll or expiry crossing; synthetic tests "
        "verify those mechanisms."
    )
    d.p(
        "Primary fees are 3 bps each side of each leg’s actual premium "
        "notional; 2 bps is the fee sensitivity. Adverse premium slippage "
        "of 0, 10 and 25 bps raises buy fills and lowers sell fills. Fees "
        "and slippage apply to every entry, exit, roll and adjustment "
        "separately. They are research assumptions, not calibrated "
        "all-inclusive brokerage, tax or observed bid/ask schedules. Short "
        "receipts increase cash while short market values create liabilities:"
    )
    d.p(
        "Equity = cash + long quantity x long call value - short quantity "
        "x short call value",
        "equation",
    )
    d.p(
        "Reserved collateral remains part of cash and equity, but is "
        "unavailable for added exposure; it is never added twice. Completed "
        "signal groups combine both legs, rolls and adjustments using net "
        "signed cash flows. Open group P&L includes its remaining net "
        "option value and is separate from completed-trade expectancy. "
        "Terminal positions remain marked, without invented closing fees."
    )
    d.heading("6.4. Primary modeled results", 2)
    rows = []
    for period in PERIODS:
        for mode in MODES:
            m = row_of(
                options,
                interpretation="start",
                case="primary",
                period=period,
                mode=mode,
            )
            rows.append(
                [
                    PERIOD_LABELS[period],
                    MODE_NAMES[mode],
                    pct(m.total_return),
                    pct(m.cagr),
                    pct(abs(m.max_drawdown)),
                    num(m.sharpe_ratio, 3),
                    num(m.sharpe_zero_rf, 3),
                ]
            )
    d.table(
        "SIMULATED reference calendar results",
        [
            "Evaluation window",
            "Management",
            "Net total return",
            "Calendar CAGR",
            "Maximum drawdown",
            "Sharpe (6% annual RF)",
            "Sharpe (0% annual RF)",
        ],
        rows,
        "Fees 3 bps per side on option premium, zero premium slippage, volatility x1.2 and flat "
        "relative maturity "
        "volatility. The 6% continuous pricing rate is not cash interest; idle cash "
        "earns zero. Sharpe rates are annual comparison rates. Equal-unit calendars "
        "are a control, not standalone long calls. Drawdown table values are positive "
        "magnitudes; drawdown plots show negative underwater returns.",
    )
    rows = []
    for mode in MODES:
        m = row_of(
            options, interpretation="start", case="primary", period="OOS", mode=mode
        )
        rows.append(
            [
                MODE_NAMES[mode],
                int(m.signal_count),
                pct(m.win_rate),
                num(m.expectancy),
                num(m.fees),
                int(m.adjustments),
                num(m.open_pnl),
            ]
        )
    d.table(
        "SIMULATED holdout signal groups and fees",
        [
            "Management",
            "Closed groups",
            "Win rate",
            "Expectancy (INR/group)",
            "Fees (INR)",
            "Adjustments",
            "Open P&L (INR)",
        ],
        rows,
    )
    rows = []
    for mode in MODES:
        m = row_of(
            options, interpretation="start", case="primary", period="OOS", mode=mode
        )
        rows.append(
            [
                MODE_NAMES[mode],
                pct(m.mean_entry_abs_residual),
                pct(m.mean_abs_residual_theta),
                pct(m.fraction_marks_within_10pct),
                pct(m.mean_net_delta_exposure_fraction),
                pct(m.mean_collateral_fraction),
            ]
        )
    theta_summary = "; ".join(
        f"{r[0]}: entry residual {r[1]}, mean absolute drift {r[2]}, "
        f"active marks within 10% {r[3]}, mean delta exposure {r[4]}, "
        f"mean reserved collateral {r[5]}"
        for r in rows
    )
    d.p(
        "Table 8. SIMULATED holdout theta and allocation. All theta percentages "
        "are normalized by initial long-leg absolute theta; drift uses active "
        "marks, while exposure and collateral fractions average all evaluated "
        "marks. "
        + theta_summary
        + "."
    )
    d.p(
        "Under the reference configuration and primary start-labeled convention, "
        "SIMULATED entry-only calendars return 7.48% in the previously examined "
        "historical holdout "
        "and finish at INR 537,386.17 after INR 5,791.11 fees, with 1.54% "
        "drawdown. Daily checks return 7.31%, with six adjustments and the "
        "same maximum drawdown. Their Sharpe ratios using a 6% annual risk-free "
        "comparison rate are negative because returns are low relative "
        "to that opportunity-cost assumption. Pricing at continuous 6% "
        "does not credit interest to idle cash or collateral."
    )
    d.p(
        "Entry matching exceeds equal-unit calendar return (1.40%) and "
        "zero-rate Sharpe in the primary holdout, but has larger drawdown "
        "(1.54% versus 0.59%). It also raises mean net directional exposure "
        "from about 0.10% to 7.72% of portfolio equity. The comparator "
        "therefore does not isolate theta matching. The equal-unit "
        "control can drift to negative net delta; this is reported rather "
        "than presented as a permanently bullish or equal-risk benchmark."
    )
    d.figure(
        6,
        "figure_06_options_equity",
        "SIMULATED primary calendar account values after fees. "
        "Entry matching, daily checks and the equal-unit calendar control. Different "
        "allocation and exposure prohibit attributing the whole difference to theta.",
    )
    d.figure(
        7,
        "figure_07_options_drawdown",
        "SIMULATED primary calendar drawdowns at every "
        "included marked observation. Smaller risk than the futures proxy "
        "partly reflects "
        "lower directional exposure; figures use different vertical scales.",
    )
    d.figure(
        8,
        "figure_08_theta_and_exposure",
        "SIMULATED primary holdout theta drift and "
        "allocation. Left: empirical distribution over active 15-minute marks, not a "
        "sampling confidence interval. Right: mean fractions over all evaluated marks; "
        "gross exposure is (long units + short units) times spot divided by equity.",
    )
    d.heading("6.5. Modeled fee, fill and volatility sensitivity", 2)
    rows = [[CASE_LABELS[c[0]], c[1], c[2], c[3], c[4]] for c in config3["cases"]]
    d.table(
        "SIMULATED scenario definitions",
        [
            "Case",
            "Fee bps/side",
            "Slip bps/fill",
            "Long vol multiplier",
            "Near/long vol",
        ],
        rows,
        "One-factor alternatives plus two combined corners, not a full factorial. "
        "Combined flat: 3/25/1.0/0.9; combined steep: 3/25/1.5/1.1. "
        "Both management modes and the equal-unit control run all cases "
        "in all windows.",
    )
    rows = []
    for case in CASE_NAMES:
        a = row_of(
            options, interpretation="start", case=case, period="OOS", mode="entry"
        )
        b = row_of(
            options, interpretation="start", case=case, period="OOS", mode="daily"
        )
        rows.append(
            [
                CASE_LABELS[case],
                pct(a.total_return),
                pct(b.total_return),
                pct(abs(a.max_drawdown)),
                pct(abs(b.max_drawdown)),
            ]
        )
    d.table(
        "SIMULATED primary-grouping holdout sensitivity",
        ["Scenario assumptions", "Entry return", "Daily return", "Entry maximum drawdown", "Daily maximum drawdown"],
        rows,
    )
    d.p(
        "The primary grouping’s entry-only holdout returns range from about "
        "-5.50% to 13.36% over the stated scenarios. At 25 bps premium "
        "slippage with otherwise primary pricing, return is -2.64%; daily "
        "management is -2.52%. Near-leg volatility x0.9 gives 2.14% entry "
        "return and x1.1 gives 13.36%. These are conditional model outcomes "
        "on one historical path, not observed implied-volatility estimates or "
        "probabilistic forecasts. The reference scenario is retained as the headline, "
        "not the highest-return sensitivity case."
    )
    d.p(
        "Across ten cases and two groupings, entry matching increases "
        "zero-rate Sharpe in 16 of 20 paired holdout comparisons. It "
        "improves both raw return and absolute drawdown in only 8 of 20. "
        "Daily checks improve both in 3 of 20 and improve return in 12 "
        "of 20. These descriptive counts are not significance tests and "
        "the paired cases are not independent. Primary daily management "
        "does not improve return, zero-rate Sharpe or maximum drawdown. "
        "Some stressed daily cases drift to nonpositive delta between "
        "checks, consistent with the stated construction/adjustment policy."
    )
    d.figure(
        9,
        "figure_09_option_sensitivity",
        "SIMULATED holdout net returns under all ten saved scenarios. "
        "Primary start grouping and end "
        "grouping sensitivity "
        "are shown separately. These bars are not confidence intervals.",
    )
    d.heading("7. Comparison and annual outcomes")
    d.p(
        "The proxy and SIMULATED option analyses start with INR 500,000 and use matching "
        "included observations within each grouping/window. The primary "
        "holdout proxy is invested at approximately full account notional "
        "when long and is long for 54.45% of included marks; buy-and-hold "
        "is continuously exposed. The entry-only calendar’s mean net "
        "delta exposure is about 7.72% of equity, with 42.35% reserved "
        "cash collateral. Lower raw calendar drawdown does not establish "
        "better performance at equal risk. Common 6%-rate comparison "
        "ratios are supplied separately; original Stage 2 ratios use 0%."
    )
    rows = []
    for label, m, fee_key in [
        (
            "Futures proxy net",
            row_of(
                futures,
                interpretation="start",
                amplitude=3,
                period="OOS",
                scenario="net",
            ),
            "total_fees",
        ),
        (
            "Buy-and-hold net",
            row_of(
                futures,
                interpretation="start",
                amplitude=3,
                period="OOS",
                scenario="buy_hold_net",
            ),
            "total_fees",
        ),
        (
            "SIMULATED calendar entry",
            row_of(
                options,
                interpretation="start",
                case="primary",
                period="OOS",
                mode="entry",
            ),
            "fees",
        ),
        (
            "SIMULATED calendar daily",
            row_of(
                options,
                interpretation="start",
                case="primary",
                period="OOS",
                mode="daily",
            ),
            "fees",
        ),
    ]:
        rows.append(
            [
                label,
                pct(m.total_return),
                pct(m.cagr),
                pct(abs(m.max_drawdown)),
                num(m[fee_key]),
            ]
        )
    d.table(
        "Primary historical holdout comparison",
        ["Implementation", "Net return", "CAGR", "Maximum drawdown", "Fees INR"],
        rows,
        "These are unequal exposures and different fee bases. "
        "Buy-and-hold remains open "
        "and pays only its recorded entry fee. No imaginary terminal exit is charged.",
    )
    a2 = load_csv(S2 / "annual_net_performance.csv")
    a2 = a2[
        (a2.interpretation == "start") & (a2.amplitude == 3) & (a2.period == "FULL")
    ]
    a3 = load_csv(S3 / "start/primary/entry/FULL/annual_net.csv")
    rows = []
    for _, m in a3.iterrows():
        rows.append(
            [
                str(int(m.year)) + (" (partial)" if m.year in [2015, 2025] else ""),
                pct(row_of(a2, year=m.year, scenario="net").total_return),
                pct(row_of(a2, year=m.year, scenario="buy_hold_net").total_return),
                pct(m.total_return),
            ]
        )
    d.table(
        "Primary full-history annual net returns",
        ["Year", "Futures proxy", "Buy-and-hold", "SIMULATED entry calendar"],
        rows,
    )
    d.figure(
        10,
        "figure_10_annual_returns",
        "Primary full-history calendar-year net returns. "
        "Asterisks mark partial 2015/2025. Strategies have unequal exposure; these are "
        "annual realized account changes, not independently reset annual backtests.",
    )
    d.heading("8. Capital efficiency: an untested futures implementation")
    d.p(
        "Actual futures can give exposure with less upfront cash than "
        "fully funded exposure of the same notional size. That may make "
        "a profitable signal more capital-efficient, but it also "
        "increases losses relative to the total account. NSE requires "
        "upfront SPAN/extreme-loss margins and settlement obligations; "
        "requirements are not a fixed percentage guaranteed over history "
        "(NSE, n.d.-a). The corrected research has not modeled them."
    )
    d.table(
        "Illustrative capital-efficiency example; NOT a tested result",
        ["Assumption or arithmetic", "Value"],
        [
            ["Assumed contract exposure", "INR 2,000,000 (20 lakh)"],
            ["Assumed initial margin", "INR 200,000 (2 lakh)"],
            ["Assumed additional buffer", "INR 400,000 (4 lakh)"],
            ["Total committed capital / exposure ratio", "INR 600,000 / 3.33x"],
            [
                "Illustrative 1% adverse move, before costs",
                "INR 20,000 loss; 3.33% of total capital",
            ],
        ],
        "User-supplied illustrative amounts, not current verified "
        "contract/margin quotes. "
        "They are not used in any performance table or equity curve.",
    )
    d.p(
        "A buffer of INR 400,000 is not established as sufficient. A proper "
        "leveraged study would need actual contract prices, changing lot "
        "sizes, daily mark-to-market cash settlement, margin calls, rolls, "
        "funding and liquidation rules. Returns must use all committed "
        "capital, including the buffer. One cannot multiply the reported "
        "33.16% by a leverage factor and present it as a tested outcome: "
        "The index proxy uses varying fractional units and reinvested equity, "
        "not a fixed historical futures lot. Buy-and-hold through ETF "
        "units also does not require one full futures-equivalent lot "
        "(NSE, n.d.-b). This is a potential application, not validation "
        "of a margin-backed implementation."
    )
    d.heading("9. Grouping sensitivity and uncertainty")
    d.p(
        "The end-grouping test shifts minute observations back one minute "
        "before 09:15-anchored grouping. It changes candles, excluded "
        "incomplete bars and signals; it is not just a harmless relabeling. "
        "Its zero-slippage holdout proxy returns 7.98% with 15.76% maximum "
        "drawdown, while two adverse index points per fill give -0.39%. Its "
        "SIMULATED entry calendar "
        "returns 4.05% versus the start grouping’s 7.48%. These results "
        "document aggregation sensitivity. Start labels remain the author-reported "
        "primary convention; they are not independently verified data provenance. "
        "Unlike that end-grouping stress, the start-grouping holdout has positive "
        "returns in each separately tested slippage and delay scenario."
    )
    d.figure(
        11,
        "figure_11_grouping_sensitivity",
        "Historical holdout grouping sensitivity, "
        "net of modeled fees. Start is the author-reported primary grouping; end is an "
        "alternative aggregation stress, not an independent sample.",
    )
    d.p(
        "Recorded implementation cross-checks and the research correction history "
        "are summarized in Supplement A. They are computational checks completed "
        "during the original research stages, not external replication or newly run "
        "tests."
    )
    d.p(
        "No confidence intervals, p-values, dependence-aware bootstrap "
        "or selection-adjusted performance tests were calculated here. "
        "All conclusions are descriptive and conditional on the one "
        "historical path and stated assumptions. Hypothesis tests of "
        "superiority would need additional analysis; dependence-aware "
        "resampling could help quantify uncertainty, but would not "
        "create an untouched holdout or validate real option prices. "
        "Saved run counts are scenario combinations, not independent samples."
    )
    d.heading("10. Limitations")
    limitations = [
        "Data provenance: the exact Kaggle source/version and rights "
        "remain unresolved. "
        "Personal TradingView verification establishes the chosen "
        "convention as reported "
        "by the author, not a full independent audit of every historical candle.",
        "Single instrument and parameter history: only NIFTY 50 is studied. The "
        "previously examined holdout is not independent validation. The archived "
        "records conflict on when amplitude 3 was chosen, and the amplitude 2–5 "
        "comparisons are descriptive rather than independent validation.",
        "Execution: next-open spot proxies and modeled premium fills exclude real "
        "order-book spread, liquidity, latency, basis, changing taxes/fees and rolls. "
        "The stress assumptions were not calibrated to historical executable quotes.",
        "Model dependence: realized-volatility scenarios, synthetic "
        "maturities/strikes, "
        "flat or simple term multipliers and fixed rates do not reproduce market IV "
        "surfaces or actual expiry calendars. Greeks are model "
        "derivatives, not protection "
        "from overnight gaps or pricing error.",
        "Unequal risk: theta matching also changes size, net delta and collateral. "
        "Cross-stage raw drawdown comparisons and equal-unit controls cannot establish "
        "a pure theta effect or superiority at matched exposure.",
        "Capital: the proxy is unleveraged, option collateral is conservative research "
        "collateral, and idle cash earns zero. Historical exchange/broker margins and "
        "cash-buffer sufficiency have not been tested.",
        "Uncertainty and unobserved mechanisms: no sampling intervals or new untouched "
        "test exist. Historical trades do not demonstrate rolls/expiry crossings; "
        "those are synthetic-verification mechanisms only.",
    ]
    for i, text in enumerate(limitations, 1):
        d.p(f"{i}. {text}")
    d.heading("11. Conclusion")
    d.p(
        "For the reference configuration (amplitude = 3, channel deviation = 2), "
        "the primary start-labeled, long-only, fully funded index-based futures proxy "
        "has a 33.16% net total return in the previously examined holdout, after 5 bps "
        "per side on underlying notional, zero slippage and next-available-open fills. "
        "Its maximum drawdown is 12.61%, below buy-and-hold's 17.12%, while its total "
        "return is below the benchmark's 38.56%; exposure is not matched. The same "
        "start-grouping proxy returns 22.87% with two adverse index points per fill and "
        "25.23% with one additional included-bar delay. These are separate stresses. "
        "End grouping with two-point slippage instead returns -0.39%, so the finding "
        "does not extend across groupings. Amplitudes 2-5 are descriptive sensitivity "
        "comparisons; the records do not establish that amplitude 3 was chosen before "
        "historical inspection."
    )
    d.p(
        "The SIMULATED entry-only call calendar has a 7.48% holdout total return and "
        "1.54% maximum drawdown under its stated Black-Scholes, volatility, premium-fee "
        "and zero-slippage assumptions. Daily checks return 7.31%; 25 bps adverse "
        "premium slippage changes the entry-only return to -2.64%. Theta matching also "
        "changes directional exposure, so its effect is not isolated. These results "
        "are historical outcomes, not statistical evidence of alpha, matched-exposure "
        "superiority, observed option-premium performance or actual futures returns."
    )
    d.heading("Declarations and research availability")
    d.p(
        "Author: Mohd Bilal, Independent researcher. The author supplied MSc Data "
        "Science, CU 28; the full institution name and degree status have not been "
        "confirmed."
    )
    d.p(
        "Funding and competing-interest information was not supplied by the author; "
        "no declaration of absence is made."
    )
    d.p(
        "AI-use disclosure: OpenAI Codex assisted with coding, analysis checks, "
        "figure preparation and drafting. The author is responsible for the final "
        "manuscript."
    )
    d.p(
        "The manuscript describes saved research artifacts in the accompanying "
        "workspace. Public availability of the current repository revision has not "
        "been confirmed. The raw data are not included. Data source identity and "
        "rights, indicator attribution, and public access to the code and outputs "
        "remain unresolved; full external reproducibility cannot be claimed. "
        "Complete run tables, formulas and reconciliation details are provided in "
        "the accompanying Supplementary Results PDF."
    )
    d.page()
    d.heading("References")
    references = [
        (
            "Back, K., Liu, H., and Loewenstein, M. (n.d.). Pricing and Hedging "
            "Derivative Securities, Chapter 9: The Black-Scholes Formula. "
            "Online draft textbook. "
            "Accessed 7 October 2026.",
            "https://book.derivative-securities.org/Chapter_BlackScholes.html",
        ),
        (
            "Black, F., and Scholes, M. (1973). The pricing of options and corporate "
            "liabilities. Journal of Political Economy, 81(3), 637-654.",
            "https://doi.org/10.1086/260062",
        ),
        (
            "Brock, W., Lakonishok, J., and LeBaron, B. (1992). Simple "
            "technical trading "
            "rules and the stochastic properties of stock returns. Journal of Finance, "
            "47(5), 1731-1764.",
            "https://doi.org/10.1111/j.1540-6261.1992.tb04681.x",
        ),
        (
            "Politis, D. N., and Romano, J. P. (1994). The stationary "
            "bootstrap. Journal "
            "of the American Statistical Association, 89(428), 1303-1313.",
            "https://doi.org/10.1080/01621459.1994.10476870",
        ),
        (
            "Sullivan, R., Timmermann, A., and White, H. (1999). "
            "Data-snooping, technical "
            "trading rule performance, and the bootstrap. Journal of Finance, 54(5), "
            "1647-1691.",
            "https://doi.org/10.1111/0022-1082.00163",
        ),
        (
            "National Stock Exchange of India (n.d.-a). Equity Derivatives: Margins. "
            "Accessed 7 October 2026.",
            "https://www.nseindia.com/static/products-services/equity-derivati"
            "ves-margins",
        ),
        (
            "National Stock Exchange of India (n.d.-b). Structure of ETF. "
            "Accessed 7 October 2026.",
            "https://www.nseindia.com/static/products-services/etfs-structure",
        ),
    ]
    for text, url in references:
        d.p(text, "reference")
        d.parts.append(
            f'<p class="reference"><a href="{html.escape(url)}">'
            f"{html.escape(url)}</a></p>"
        )
    d.page()
    d.heading("Appendix A. Complete Stage 2 run summary")
    d.p(
        "The following 60 rows cover all saved Stage 2 runs. Start is the "
        "author-reported primary grouping; end is the alternative candle grouping. "
        "Buy-and-hold amplitude is N/A: its inherited run identifier does not imply "
        "that HalfTrend is applied to the benchmark. Fees and slippage/delay follow "
        "Section 5. The companion futures_all_runs.csv includes every saved metric, "
        "including risk ratios, fees, exposure and open P&L. Values are descriptive."
    )
    rows = []
    for _, m in futures.sort_values(
        ["interpretation", "amplitude", "period", "scenario"]
    ).iterrows():
        rows.append(
            [
                "S" if m.interpretation == "start" else "E",
                "N/A" if m.scenario == "buy_hold_net" else int(m.amplitude),
                PERIOD_LABELS[m.period],
                FUTURES_CASE_LABELS.get(m.scenario, str(m.scenario)),
                pct(m.total_return),
                pct(abs(m.max_drawdown)),
                num(m.total_fees, 2),
            ]
        )
    d.table(
        "All index-based futures proxy runs",
        ["Grouping", "Amplitude", "Evaluation window", "Run assumptions", "Total return", "Maximum drawdown", "Fees (INR)"],
        rows,
    )
    d.heading("Appendix B. Complete SIMULATED Stage 3 run summary")
    d.p(
        "The following 180 rows cover all ten modeled cases, three management/control "
        "modes, three evaluation windows and two groupings. The equal-unit control "
        "always contains both calls. Full metric "
        "precision, Greek diagnostics, fee/slippage totals, adjustment turnover "
        "and open P&L are in options_all_runs.csv. Case definitions are in Table "
        "The scenario definitions and run_label_mapping.csv; no scenario is selected as a headline based "
        "on its return. Positive drawdown magnitudes in these tables correspond to "
        "negative underwater values in plots."
    )
    for interp in ["start", "end"]:
        for period in PERIODS:
            rows = []
            for case in CASE_NAMES:
                for mode in MODES:
                    m = row_of(
                        options,
                        interpretation=interp,
                        case=case,
                        period=period,
                        mode=mode,
                    )
                    rows.append(
                        [
                            CASE_LABELS[case],
                            {
                                "entry": "Entry",
                                "daily": "Daily",
                                "equal_control": "Equal",
                            }[mode],
                            pct(m.total_return),
                            pct(abs(m.max_drawdown)),
                            num(m.fees, 2),
                            int(m.adjustments),
                        ]
                    )
            d.table(
                f"SIMULATED {interp} grouping / {PERIOD_LABELS[period]}",
                ["Scenario assumptions", "Mode", "Total return", "Maximum drawdown", "Fees (INR)", "Adjustments"],
                rows,
            )
    d.page()
    d.heading("Appendix C. Formulas, reconciliation and implementation details")
    d.p(
        "Simple return: rₜ = Eₜ / Eₜ₋₁ − 1; total return = E_T / E₀ − 1. "
        "Calendar CAGR = (E_T/E₀)^(1/elapsed calendar years) − 1. Daily returns use "
        "the final included account mark each session, with initial capital "
        "E₀ for the first denominator. Drawdown Dₜ = Eₜ/max(E₀, max prior E) − 1. "
        "CAGR uses 365.25 days/year; option maturity uses 365 days/year."
    )
    d.p(
        "Sharpe = √252 × mean(xₜ)/s(xₜ), where xₜ = daily return − annual RF/252 "
        "and s is sample standard deviation. The implemented Sortino is √252 × "
        "mean(xₜ)/s(xₜ | xₜ < 0), with the denominator the sample standard "
        "deviation of negative excess observations (not root-mean-square downside). "
        "Calmar = CAGR/|maximum "
        "drawdown). Profit factor = total positive completed net P&L / absolute "
        "total negative completed net P&L. Expectancy = mean completed net P&L."
    )
    d.p(
        "With φ the standard normal density, call Greeks are Δ = e^(−qτ)N(d₁), "
        "Γ = e^(−qτ)φ(d₁)/(Sσ√τ), and Vega per 1 volatility percentage point = "
        "S e^(−qτ)φ(d₁)√τ/100. Passage-of-time θ per calendar day is "
        "[−S e^(−qτ)φ(d₁)σ/(2√τ) − rK e^(−rτ)N(d₂) "
        "+ qS e^(−qτ)N(d₁)]/365. Expired calls use max(S−K, 0), delta "
        "1/0/0.5 for in/out/at-the-money and other expired Greeks zero. "
        "Expired contracts are not opened as new calendars."
    )
    d.p(
        "Proxy final equity = initial capital + closed net P&L + open gross "
        "P&L - open entry fee. Calendar final equity = initial capital + "
        "completed signal net P&L + open signal net P&L. Closed net P&L "
        "already includes its fees, so total fees must not be subtracted "
        "again. Separate fill reconstructions verify cumulative cash, "
        "fixed quantities, fee arithmetic and market values. Calendar "
        "reserved collateral is not another asset added to equity."
    )
    d.p(
        "Input validation rejects nonfinite/negative costs and nonpositive "
        "capital/prices/quantities. Proxy entry sizing requires fee rate "
        "below one for positive quantity; option adverse sell slippage "
        "requires slippage rate below one for positive premium fills. "
        "These are mathematical conditions, not arbitrary fee caps. "
        "Nonfinite or nonpositive equity triggers explicit insolvency."
    )
    d.heading("Appendix D. Reproducibility and evidence inventory")
    r = stage1["baseline_reconciliation"]
    d.p(
        "The stage test counts below are historical values recorded in the completed "
        "research artifacts. They were not rerun for this editorial revision.",
        "note",
    )
    d.table(
        "Previously recorded checks and bounded accounting result",
        ["Research stage", "Previously recorded tests", "Saved scope or result"],
        [
            [
                "Loader/accounting corrections",
                "85 passed",
                "1,000 retained bars; 16 closed trades; ending equity "
                + num(r["actual_final_equity"])
                + " INR; reconciliation difference 0 INR",
            ],
            [
                "Index-based futures proxy",
                "103 passed",
                "60 runs; saved-curve and zero-cost checks",
            ],
            [
                "SIMULATED call calendars",
                "129 passed",
                "180 runs; independent saved-artifact pricing and reconciliation",
            ],
            [
                "Formatting tools",
                "Ruff and Black passed (recorded)",
                "Historical recorded completion checks",
            ],
        ],
    )
    d.p(
        "The Stage 1 bounded sample recorded net P&L of "
        + num(r["closed_net_pnl"])
        + " INR and fees already included in net P&L of "
        + num(r["closed_fees_included_in_net"])
        + " INR. This was an accounting check, not a strategy-wide result."
    )
    budget_correction = load_json(S3 / "budget_correction.json")
    d.p(
        "The saved Stage 3 correction record documents an earlier premium-budget "
        "calculation that omitted the short leg’s entry fee. It reports "
        + str(budget_correction["affected_paths"])
        + " affected saved paths, which were recomputed for the completed results. "
        "Only completed corrected outputs are used in this paper. This correction "
        "history is reproduced from the saved record and was not rerun here."
    )
    d.p("Raw input file SHA-256: " + config2["data_sha256"], "note")
    d.p(
        "Run from the repository root after installing the saved environment’s "
        "dependencies. The data path is local and must be replaced on another "
        "machine. Research commands require NEW output directories. The "
        "current assembly only reads saved results; it does not execute "
        "these research commands."
    )
    for command in [
        'python -m src.futures_proxy --data "PATH/NIFTY_50_minute.csv" '
        "--output results/stage2_repeat",
        "python -m src.simulated_calendars --data "
        '"PATH/NIFTY_50_minute.csv" --output results/stage3_repeat',
        "python -m tests.verify_futures_proxy_outputs "
        "results/stage2_futures_proxy_20261007_completed",
        "python -m tests.verify_simulated_calendar_outputs "
        "results/stage3_SIMULATED_calendars_20261007_completed",
        "python -m pytest -q; python -m ruff check .; python -m black --check .",
    ]:
        d.p(command, "note")
    d.table(
        "Evidence and accompanying material",
        ["Material", "Location / meaning"],
        [
            [
                "Data/accounting audit",
                "DISCREPANCY_RESOLUTION.md; verification/discrepancy_fix/",
            ],
            [
                "Stage 2 completed research",
                "results/stage2_futures_proxy_20261007_completed/",
            ],
            [
                "Stage 3 completed SIMULATED research",
                "results/stage3_SIMULATED_calendars_20261007_completed/",
            ],
            [
                "Full saved metrics and readable case labels",
                "supplements/futures_all_runs.csv, options_all_runs.csv, run_label_mapping.csv",
            ],
            [
                "Annual outcomes and common-rate comparisons",
                "supplements/annual_* and stage2_comparison.csv",
            ],
            [
                "Pricing/causality/accounting evidence",
                "supplements/*verification*.json and completed-stage checks/",
            ],
            [
                "Plot sources / figure exports",
                "supplements/*session_equity.csv; figures/*.png and *.svg",
            ],
            [
                "Immutable source identification",
                "source_manifest.json; assembly_verification.json",
            ],
        ],
    )
    d.p(
        "Full leg, fill, signal and Greek histories remain in the listed "
        "completed research directories. Companion CSV tables summarize all "
        "240 completed runs; SVG files preserve vector versions of the figures."
    )
    d.save()
    return d.table_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "paper/HalfTrend_NIFTY50_Publication_Candidate",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(
            "Choose a new manuscript directory; no artifacts overwritten."
        )
    output.mkdir(parents=True)
    (output / "figures").mkdir()
    (output / "supplements").mkdir()
    config2 = load_json(S2 / "configuration.json")
    config3 = load_json(S3 / "configuration.json")
    stage1 = load_json(
        REPO / "verification/discrepancy_fix/real_data_verification.json"
    )
    primary = load_csv(S2 / "performance_comparison.csv")
    sensitivity = load_csv(S2 / "sensitivity.csv")
    futures = pd.concat([primary, sensitivity], ignore_index=True).drop_duplicates(
        ["interpretation", "period", "amplitude", "scenario"]
    )
    options = load_csv(S3 / "sensitivity.csv")
    assert len(futures) == 60 and len(options) == 180
    futures.to_csv(output / "supplements/futures_all_runs.csv", index=False)
    options.to_csv(output / "supplements/options_all_runs.csv", index=False)
    case_rows = [
        ["Stage 2 scenario", code, label] for code, label in FUTURES_CASE_LABELS.items()
    ] + [
        ["Stage 3 scenario", code, label] for code, label in CASE_LABELS.items()
    ]
    case_rows.extend([
        ["Timestamp grouping", "start", "Author-reported primary grouping"],
        ["Timestamp grouping", "end", "Alternative candle-aggregation sensitivity"],
    ])
    case_rows.extend(
        [["Evaluation period", code, label] for code, label in PERIOD_LABELS.items()]
    )
    pd.DataFrame(case_rows, columns=["category", "saved_code", "reader_label"]).to_csv(
        output / "supplements/run_label_mapping.csv", index=False
    )
    for file, new in [
        (S2 / "configuration.json", "stage2_configuration.json"),
        (S3 / "configuration.json", "stage3_configuration.json"),
        (S2 / "annual_net_performance.csv", "annual_futures_all_runs.csv"),
        (S3 / "stage2_comparison.csv", "stage2_common_rate_comparison.csv"),
        (S2 / "verification.json", "stage2_verification.json"),
        (
            S2 / "independent_export_verification.json",
            "stage2_independent_verification.json",
        ),
        (S3 / "verification.json", "stage3_verification.json"),
        (
            S3 / "independent_artifact_verification.json",
            "stage3_independent_verification.json",
        ),
        (S3 / "budget_correction.json", "stage3_budget_correction.json"),
        (S2 / "coverage.json", "stage2_coverage.json"),
        (S3 / "coverage.json", "stage3_coverage.json"),
        (S3 / "environment_final.json", "research_environment.json"),
    ]:
        shutil.copy2(track(file), output / "supplements" / new)
    track(Path(__file__))
    track(REPO / "paper/export_review_documents.py")
    track(REPO / "README.md")
    track(REPO / "DISCREPANCY_RESOLUTION.md")
    track(S2 / "REPORT.md")
    track(S3 / "REPORT.md")
    figures(output, futures, options, config3["cases"])
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    tables = build_text(output, futures, options, config2, config3, stage1, revision)
    assert all(
        digest(REPO / path) == checksum for path, checksum in SOURCE_FILES.items()
    )
    (output / "source_manifest.json").write_text(
        json.dumps(
            {
                "revision": revision,
                "data_sha256": config2["data_sha256"],
                "read_sources": SOURCE_FILES,
            },
            indent=2,
        )
    )
    (output / "assembly_verification.json").write_text(
        json.dumps(
            {
                "no_backtests_run": True,
                "prior_sources_unchanged": True,
                "no_backtests_or_research_tests_run": True,
                "stage2_rows": len(futures),
                "stage3_rows": len(options),
                "figure_count": 11,
                "table_count": tables,
                "chart_checks": CHART_CHECKS,
                "author": "Mohd Bilal",
                "data_url_missing": True,
            },
            indent=2,
        )
    )
    checklist = """Outstanding author-supplied information

1. Exact Kaggle dataset URL, uploader/version, acquisition date and reuse terms.
2. The full institution name represented by “CU” and confirmation of degree status.
3. Correspondence email, if one should be published.
4. Funding and competing-interest statements; no absence is presumed here.
5. Original HalfTrend publication/version and attribution terms.
6. Dates, symbols, matched observations and evidence for the author-reported
   TradingView timestamp check. It has not been independently replicated.
7. Confirm public availability and licensing of the exact code/results revision.
8. The historical holdout was previously examined. No confidence intervals,
   p-values or selection-adjusted inference are supplied.
9. Research conclusion: distinguish historical returns from statistical alpha;
   modeled option prices from observed premiums; and proxy futures from actual
   contracts, basis, rolls, liquidity and margin requirements.

Until these details and legal/data rights are resolved, this is a polished
publication candidate rather than a submission-ready paper.
"""
    (output / "OUTSTANDING_AUTHOR_INFORMATION.txt").write_text(checklist)
    (output / "EDITORIAL_CHANGE_LOG.txt").write_text(
        "Editorial changes\n\n"
        "- Applied the neutral requested title and removed promotional framing, "
        "reader-facing instructions and author placeholders.\n"
        "- Defined the reference configuration (amplitude = 3, channel deviation = 2); "
        "amplitude is a completed 15-minute-bar lookback. Separated it from the "
        "author-reported primary start-labeled data convention.\n"
        "- Disclosed conflicting archived claims about amplitude selection timing "
        "and used the requested conservative statement.\n"
        "- Clarified that the previously examined holdout is not independent validation; "
        "distinguished separate slippage/delay tests and index-point from premium-bps "
        "stress results.\n"
        "- Rewrote the discussion around the supplied return/drawdown findings and "
        "limits, retaining the distinction between proxy, SIMULATED prices, observed "
        "market data, and alpha evidence.\n"
        "- Redesigned charts, tables, headings, references and page furniture; moved "
        "complete run summaries and implementation/audit history to the supplement.\n"
        "- Preserved supplied metrics and results; no strategy code or data changed.\n"
    )
    print(
        f"Manuscript HTML, {tables} tables, 11 figures and "
        f"all 240 run summaries: {output}"
    )


if __name__ == "__main__":
    main()
