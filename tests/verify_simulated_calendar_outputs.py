"""Independent SIMULATED artifact audit: repricing, units, cash and liabilities."""

import argparse
import json
from math import erf, exp, log, pi, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from src.calendar_spread import CalendarResult, reconcile_calendar
from src.futures_proxy import digest, write_json


def independent_call(spot, strike, years, sigma):
    """Independent erf formulation, no model kernel/cache or stored prices."""
    if years <= 0:
        return (
            max(spot - strike, 0.0),
            1.0 if spot > strike else 0.0 if spot < strike else 0.5,
            0.0,
            0.0,
            0.0,
        )
    d1 = (log(spot / strike) + (0.06 - 0.01 + sigma**2 / 2) * years) / (
        sigma * sqrt(years)
    )
    d2 = d1 - sigma * sqrt(years)
    n1, n2 = (1 + erf(d1 / sqrt(2))) / 2, (1 + erf(d2 / sqrt(2))) / 2
    phi = exp(-d1 * d1 / 2) / sqrt(2 * pi)
    price = max(spot * exp(-0.01 * years) * n1 - strike * exp(-0.06 * years) * n2, 0.0)
    delta = exp(-0.01 * years) * n1
    gamma = exp(-0.01 * years) * phi / (spot * sigma * sqrt(years))
    vega = spot * exp(-0.01 * years) * phi * sqrt(years) / 100
    theta = (
        -spot * exp(-0.01 * years) * phi * sigma / (2 * sqrt(years))
        - 0.06 * strike * exp(-0.06 * years) * n2
        + 0.01 * spot * exp(-0.01 * years) * n1
    ) / 365
    return price, delta, gamma, vega, theta


def stamp(values):
    return pd.to_datetime(values).dt.tz_convert("Asia/Kolkata")


def audit_run(path, audit, inputs):
    config = json.loads((path / "configuration.json").read_text())
    marks = pd.read_csv(path / "equity.csv.gz", index_col="bar_start")
    marks.index = pd.to_datetime(marks.index).tz_convert("Asia/Kolkata")
    marks["mark_time"] = stamp(marks.mark_time)
    fills = pd.read_csv(path / "leg_ledger.csv.gz")
    signals = pd.read_csv(path / "signal_ledger.csv.gz")
    for c in ["time", "decision_time", "expiry"]:
        fills[c] = stamp(fills[c])
    opened = json.loads((path / "open_signal.json").read_text())
    result = CalendarResult(
        marks,
        fills,
        signals,
        pd.DataFrame(),
        500000,
        marks.index[0],
        marks.mark_time.iloc[-1],
        opened,
    )
    proof = reconcile_calendar(result, config["fee_bps"], config["slippage_bps"])
    np.testing.assert_allclose(marks.spot, audit.loc[marks.index, "close"], rtol=1e-12)
    active = marks.long_quantity > 0
    indices = np.flatnonzero(active)
    direct_values = {}
    direct_greeks = {}
    for leg in ["long", "short"]:
        spot = marks.spot.to_numpy()
        strikes = marks.strike.to_numpy()
        sigmas = marks[f"{leg}_sigma"].to_numpy()
        expiries = pd.DatetimeIndex(pd.to_datetime(marks.loc[active, f"{leg}_expiry"]))
        times = pd.DatetimeIndex(marks.loc[active, "mark_time"])
        years = (expiries.as_unit("ns").asi8 - times.as_unit("ns").asi8) / (
            365 * 86400 * 1e9
        )
        direct = np.array(
            [
                independent_call(spot[i], strikes[i], t, sigmas[i])
                for i, t in zip(indices, years)
            ]
        )
        values = np.zeros(len(marks))
        if len(indices):
            values[indices] = direct[:, 0]
        np.testing.assert_allclose(marks[f"{leg}_price"], values, rtol=1e-9, atol=1e-8)
        direct_values[leg] = values
        greek_values = np.zeros((len(marks), 5))
        if len(indices):
            greek_values[indices] = direct
        direct_greeks[leg] = greek_values
    equity = (
        marks.cash
        + marks.long_quantity * direct_values["long"]
        - marks.short_quantity * direct_values["short"]
    )
    np.testing.assert_allclose(marks.equity, equity, rtol=1e-10, atol=1e-7)
    for row in fills.itertuples():
        sigma = inputs.loc[row.time, "causal_sigma"] * config["vol_multiplier"]
        if row.leg == "short":
            sigma *= config["near_multiplier"]
        price = independent_call(
            audit.loc[row.time, "open"],
            row.strike,
            (row.expiry - row.time).total_seconds() / (365 * 86400),
            sigma,
        )
        np.testing.assert_allclose(
            [
                row.model_price,
                row.model_delta,
                row.model_gamma,
                row.model_vega,
                row.model_theta,
            ],
            price,
            rtol=1e-8,
            atol=1e-8,
        )
        assert row.decision_time <= row.time
    greek = pd.read_csv(path / "greek_history.csv.gz", index_col="bar_start")
    for leg in ["long", "short"]:
        for column, key in enumerate(["price", "delta", "gamma", "vega", "theta"]):
            np.testing.assert_allclose(
                greek[f"{leg}_{key}"],
                direct_greeks[leg][:, column],
                rtol=1e-8,
                atol=1e-8,
            )
    # Net Greek arithmetic is independent of portfolio/cash bookkeeping.
    for key in ["theta", "delta", "gamma", "vega"]:
        expected = (
            greek.long_quantity * greek[f"long_{key}"]
            - greek.short_quantity * greek[f"short_{key}"]
        )
        np.testing.assert_allclose(greek[key], expected, rtol=1e-9, atol=1e-8)
    expected_sigma = (
        inputs.loc[marks.index, "causal_sigma"].to_numpy() * config["vol_multiplier"]
    )
    np.testing.assert_allclose(
        marks.long_sigma, expected_sigma, equal_nan=True, rtol=1e-12
    )
    return dict(
        path=str(path), **proof, independent_repricing=True, fill_greeks_verified=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    checks = []
    for label in ["start", "end"]:
        audit = pd.read_csv(
            output / label / "data_audit" / "bar_classification.csv", index_col=0
        )
        audit.index = pd.to_datetime(audit.index).tz_convert("Asia/Kolkata")
        inputs = pd.read_csv(output / label / "causal_inputs.csv.gz", index_col=0)
        inputs.index = pd.to_datetime(inputs.index).tz_convert("Asia/Kolkata")
        for path in sorted((output / label).rglob("metrics.json")):
            checks.append(audit_run(path.parent, audit, inputs))
        print(
            f"SIMULATED independently repriced/reconciled {label} outputs", flush=True
        )
    config = json.loads((output / "configuration.json").read_text())
    assert digest(Path(config["data_path"])) == config["data_sha256"]
    old = json.loads((output / "prior_results_sha256.json").read_text())
    assert all(digest(Path(p)) == h for p, h in old.items())
    assert len(checks) == 180
    write_json(
        output / "independent_artifact_verification.json",
        dict(
            label="SIMULATED",
            runs=checks,
            independent_repricing=True,
            all_marks_reconstructed=True,
            raw_data_preserved=True,
            prior_results_preserved=len(old),
        ),
    )
    print(f"SIMULATED verified all {len(checks)} runs independently.", flush=True)


if __name__ == "__main__":
    main()
