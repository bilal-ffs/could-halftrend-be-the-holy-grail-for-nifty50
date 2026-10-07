"""Audit and correct pending Stage 3 output for the BOTH-entry-fee budget.

Prior-stage directories are never changed. Recomputed paths replace only this
new Stage 3 output, with complete originals retained under verification/.
"""

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from src.calendar_spread import simulate_calendar
from src.data import load_minute_data, resample_to_15m
from src.futures_proxy import digest, write_json
from src.research import split_is_oos
from src.simulated_calendars import export, prepare, report


def budget_violations(path):
    fills = pd.read_csv(path / "leg_ledger.csv.gz")
    before = 500000 + fills.cash_flow.cumsum().shift(1, fill_value=0)
    entries = (fills.leg == "long") & (fills.side == "buy")
    budget_cost = fills.premium_notional + fills.fee + fills.fee.shift(-1)
    excess = budget_cost - 0.05 * before
    return fills.loc[entries & (excess > 1e-7), ["time", "signal", "spread"]].assign(
        excess_currency=excess.loc[entries & (excess > 1e-7)]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    config = json.loads((output / "configuration.json").read_text())
    assert config["label"] == "SIMULATED" and (output / "sensitivity.csv").exists()
    paths = sorted(output.glob("*/*/*/*/configuration.json"))
    affected = []
    for item in paths:
        violations = budget_violations(item.parent)
        if len(violations):
            affected.append((item.parent, violations))
    root = Path("verification/stage3_budget_correction").resolve()
    root.mkdir(parents=True, exist_ok=True)
    minute = load_minute_data(
        config["data_path"], duplicate_policy="exclude", audit_dir=root / "data_audit"
    )
    windows = {}
    proof = []
    for path, violations in affected:
        params = json.loads((path / "configuration.json").read_text())
        label = params["interpretation"]
        if label not in windows:
            full = prepare(resample_to_15m(minute, minute_label=label))
            is_data, oos_data = split_is_oos(full)
            windows[label] = dict(IS=is_data, OOS=oos_data, FULL=full)
        relative = path.relative_to(output)
        assert path.is_relative_to(output)
        backup = root / "original" / relative
        backup.mkdir(parents=True, exist_ok=False)
        old_hashes = {}
        for f in path.iterdir():
            if f.is_file():
                shutil.copyfile(f, backup / f.name)
                old_hashes[f.name] = digest(f)
        kwargs = {
            k: params[k]
            for k in [
                "fee_bps",
                "slippage_bps",
                "vol_multiplier",
                "near_multiplier",
                "management",
                "matching",
            ]
        }
        bars = windows[label][params["period"]]
        result = simulate_calendar(bars, **kwargs)
        repaired = root / "recomputed" / relative
        export(repaired, bars, result, params)
        for f in repaired.iterdir():
            target = path / f.name
            assert target.resolve().is_relative_to(output)
            shutil.copyfile(f, target)
        assert budget_violations(path).empty
        proof.append(
            dict(
                path=str(relative),
                preliminary_excess=violations.to_dict("records"),
                original_sha256=old_hashes,
                backup=str(backup),
                corrected=True,
            )
        )
        print(f"SIMULATED corrected both-entry-fee budget: {relative}", flush=True)
    summaries = [json.loads((p.parent / "metrics.json").read_text()) for p in paths]
    table = pd.DataFrame(summaries)
    table.drop(columns=["undefined_metrics"]).to_csv(
        output / "sensitivity.csv", index=False
    )
    report(output, table, pd.read_csv(output / "stage2_comparison.csv"))
    config["entry_budget"] = (
        "long premium PLUS BOTH entry fees <=5% pre-entry equity; "
        "no short receipt credit"
    )
    config["delta_policy"] = (
        "positive at entry/adjustment; report intraday drift; no risk exits"
    )
    write_json(output / "configuration.json", config)
    write_json(
        output / "budget_correction.json",
        dict(
            label="SIMULATED",
            affected_paths=len(proof),
            corrections=proof,
            prior_stages_untouched=True,
        ),
    )
    assert all(budget_violations(p.parent).empty for p in paths)
    print(
        f"SIMULATED finalized {len(paths)} runs; "
        f"corrected {len(proof)} affected paths.",
        flush=True,
    )


if __name__ == "__main__":
    main()
