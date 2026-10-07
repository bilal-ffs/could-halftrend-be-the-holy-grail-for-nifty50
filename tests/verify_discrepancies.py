"""Bounded real-data verification; never writes or regenerates research results.

Run: python -m tests.verify_discrepancies
Full CSV processing here is DATA AUDITING, not a full backtest. Accounting and
causality verification use only the first 1000 retained regular-session bars.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.accounting import BASE_COST_BPS, reconcile_portfolio
from src.data import load_minute_data, resample_to_15m
from src.halftrend import calculate_halftrend
from src.research import evaluate_window
from src.run_research import DATA_PATH
from tests.check_oos_integrity import check_causality


def main():
    out = Path("verification/discrepancy_fix")
    audit = out / "data_audit"
    audit.mkdir(parents=True, exist_ok=True)
    hashes = json.loads((out / "original_results_sha256.json").read_text())
    for name, expected in hashes.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
    try:
        load_minute_data(DATA_PATH, audit_dir=audit / "rejected_default")
    except ValueError as error:
        if "4 conflicting duplicate" not in str(error):
            raise
        default_reject = str(error)
    else:
        raise AssertionError("Expected four conflicting groups in audited input.")
    minute = load_minute_data(
        DATA_PATH, duplicate_policy="exclude", audit_dir=audit / "exclude"
    )
    bars = resample_to_15m(minute, minute_label="start", audit_dir=audit / "exclude")
    per_day = minute.groupby(minute.index.normalize()).size()
    # Evidence is recorded without pretending dataset provenance proves labels.
    evidence = {
        "source": "Kaggle (user supplied); dataset URL not supplied",
        "normal_session_observation_count": 375,
        "normal_observed_range": "09:15 through 15:29",
        "sessions_with_375_retained_minutes": int((per_day == 375).sum()),
        "selected_minute_label": "start",
        "status": "coverage supports start labels; producer semantics unverified",
        "raw_sha256": hashlib.sha256(Path(DATA_PATH).read_bytes()).hexdigest(),
    }
    (audit / "timestamp_evidence.json").write_text(json.dumps(evidence, indent=2))
    sample = bars.iloc[:1000].copy()
    halftrend = calculate_halftrend(sample)
    backtest, result = evaluate_window(halftrend, cost_bps=BASE_COST_BPS)
    baseline = reconcile_portfolio(result)
    sample_output = out / "baseline_5bps_sample"
    sample_output.mkdir(exist_ok=True)
    result.trades.to_csv(sample_output / "trades.csv", index=False)
    result.fills.to_csv(sample_output / "fills.csv", index=False)
    pd.concat([result.equity, result.cash, result.quantities], axis=1).to_csv(
        sample_output / "accounting.csv"
    )
    (sample_output / "summary.json").write_text(backtest.to_json())
    report = {
        "scope": "first 1000 retained bars only; no full research results regenerated",
        "default_conflicting_duplicate_rejection": default_reject,
        "data_policy": minute.attrs["data_audit"],
        "session_policy": bars.attrs["session_audit"],
        "timestamp_evidence": evidence,
        "baseline_cost_bps_per_side": BASE_COST_BPS,
        "cost_basis": "underlying notional",
        "slippage": "none simulated",
        "sample_start_capital_time": str(result.start_time),
        "sample_end_equity_time": str(result.end_time),
        "baseline_reconciliation": baseline,
        "causality": check_causality(sample, 500),
        "undefined_metrics": backtest.undefined_metrics,
    }
    for name, expected in hashes.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
    assert {str(path) for path in Path("results").glob("*") if path.is_file()} == set(
        hashes
    )
    report["existing_results_unchanged"] = len(hashes)
    (out / "real_data_verification.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
