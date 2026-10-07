"""Independent reconstruction of exported Stage 2 cash, fills and every mark."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.futures_proxy import digest, write_json


def check_run(path, audit):
    metrics = json.loads((path / "metrics.json").read_text())
    curve = pd.read_csv(path / "equity.csv", index_col="bar_start")
    curve.index = pd.to_datetime(curve.index)
    fills = pd.read_csv(path / "fills.csv")
    fills["time"] = pd.to_datetime(fills.time)
    fills["signal_time"] = pd.to_datetime(fills.signal_time)
    rate = metrics["cost_bps"] / 10000
    cash = 500_000.0
    quantity = 0.0
    balances, units = [], []
    assert fills.time.is_unique
    for fill in fills.itertuples():
        i = curve.index.get_indexer([fill.time])[0]
        assert i >= 0
        side = 1 if fill.side == "buy" else -1
        expected_price = (
            audit.loc[fill.time, "open"] + side * metrics["slippage_points"]
        )
        np.testing.assert_allclose(fill.price, expected_price, rtol=1e-12)
        notional = fill.price * fill.quantity
        fee = notional * rate
        np.testing.assert_allclose(fill.notional, notional, rtol=1e-12)
        np.testing.assert_allclose(fill.fee, fee, rtol=1e-12)
        if side == 1:
            assert quantity == 0
            expected_q = cash * (1 - rate) / expected_price
            np.testing.assert_allclose(fill.quantity, expected_q, rtol=1e-10)
            assert notional + fee <= cash + 1e-7
            cash -= notional + fee
            quantity = fill.quantity
        else:
            np.testing.assert_allclose(fill.quantity, quantity, rtol=1e-12)
            cash += notional - fee
            quantity = 0.0
        if not metrics["scenario"].startswith("buy_hold"):
            origin = i - metrics["execution_delay"]
            assert origin >= 0
            expected_signal = pd.Timestamp(audit.loc[curve.index[origin], "bar_end"])
            assert fill.signal_time == expected_signal
        else:
            assert i == 0 and side == 1
        assert cash >= -1e-7
        balances.append(cash)
        units.append(quantity)
    cash_path = pd.Series(balances, index=pd.DatetimeIndex(fills.time), dtype=float)
    q_path = pd.Series(units, index=pd.DatetimeIndex(fills.time), dtype=float)
    cash_path = cash_path.reindex(curve.index).ffill().fillna(500_000)
    q_path = q_path.reindex(curve.index).ffill().fillna(0)
    marked = (
        cash_path.to_numpy()
        + q_path.to_numpy() * audit.loc[curve.index, "close"].to_numpy()
    )
    np.testing.assert_allclose(curve.equity, marked, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(curve.cash, cash_path, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(curve.quantity, q_path, rtol=1e-10, atol=1e-7)
    ledger = pd.read_csv(
        path / "trades.csv",
        dtype={
            "quantity": float,
            "entry_price": float,
            "exit_price": float,
            "net_pnl": float,
        },
    )
    entry_fee = ledger.quantity * ledger.entry_price * rate
    exit_fee = ledger.quantity * ledger.exit_price * rate
    net = (
        ledger.quantity * (ledger.exit_price - ledger.entry_price)
        - entry_fee
        - exit_fee
    )
    np.testing.assert_allclose(ledger.net_pnl, net, rtol=1e-10, atol=1e-7)
    opened = json.loads((path / "open_position.json").read_text())
    open_pnl = (
        0
        if opened is None
        else opened["quantity"] * (opened["mark_price"] - opened["entry_price"])
        - opened["quantity"] * opened["entry_price"] * rate
    )
    expected_final = 500_000 + float(net.sum()) + open_pnl
    np.testing.assert_allclose(curve.equity.iloc[-1], expected_final, rtol=1e-10)
    return dict(path=str(path), bars=len(curve), fills=len(fills), passed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    checks = []
    for label in ["start", "end"]:
        audit = pd.read_csv(
            output / label / "data_audit" / "bar_classification.csv", index_col=0
        )
        audit.index = pd.to_datetime(audit.index)
        for metrics in sorted((output / label).rglob("metrics.json")):
            checks.append(check_run(metrics.parent, audit))
    config = json.loads((output / "configuration.json").read_text())
    assert digest(Path(config["data_path"])) == config["data_sha256"]
    manifest = json.loads((output / "original_results_sha256.json").read_text())
    assert all(digest(Path(p)) == expected for p, expected in manifest.items())
    assert len(checks) == 60
    write_json(
        output / "independent_export_verification.json",
        dict(
            runs=checks,
            all_marks_reconstructed=True,
            raw_data_unchanged=True,
            original_results_unchanged=True,
        ),
    )
    print(f"Verified all exported marks/fills/ledgers for {len(checks)} runs.")


if __name__ == "__main__":
    main()
