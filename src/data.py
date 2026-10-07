"""Explicit timestamp, duplicate, volume and session policies for minute CSVs."""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.validation import local_index, numeric_columns

REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}
AUDIT_DIR = Path("verification/data_audit")


def load_minute_data(path, *, duplicate_policy="reject", audit_dir=AUDIT_DIR):
    """Parse DD-MM-YYYY HH:MM as Asia/Kolkata, auditing every duplicate group.

    Conflicts are rejected by default. Explicit 'exclude', 'first', and 'last'
    policies warn and record affected source rows. Exact duplicate observations
    are collapsed with an audit record; input CSVs are never rewritten.
    All-zero volume becomes NaN (unavailable), not zero trading activity.
    """
    if duplicate_policy not in {"reject", "exclude", "first", "last"}:
        raise ValueError("duplicate_policy must be reject, exclude, first or last.")
    raw = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(raw)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    raw["source_row"] = np.arange(len(raw)) + 2  # header is physical CSV row 1
    raw["date"] = pd.to_datetime(raw["date"], format="%d-%m-%Y %H:%M", errors="raise")
    raw["date"] = raw["date"].dt.tz_localize("Asia/Kolkata")
    if raw["date"].isna().any():
        raise ValueError("Missing timestamps are not allowed.")
    values = ["open", "high", "low", "close", "volume"]
    numeric_columns(raw, values)
    numeric_columns(raw, values[:4], positive=True)
    if (raw.volume < 0).any():
        raise ValueError("Volume must be nonnegative.")
    if (raw.high < raw[["open", "low", "close"]].max(axis=1)).any() or (
        raw.low > raw[["open", "high", "close"]].min(axis=1)
    ).any():
        raise ValueError("Inconsistent OHLC bounds.")
    raw = raw.sort_values("date", kind="stable")
    duplicate = raw.date.duplicated(keep=False)
    groups = raw.loc[duplicate].groupby("date")[values].nunique()
    conflicts = groups.index[(groups > 1).any(axis=1)]
    conflicting = raw.date.isin(conflicts)
    duplicates = raw.loc[duplicate].copy()
    duplicates["conflicting"] = duplicates.date.isin(conflicts)
    duplicates["policy"] = duplicate_policy
    remove = pd.Series(False, index=raw.index)
    if duplicate_policy == "exclude":
        remove |= conflicting
    elif duplicate_policy in {"first", "last"}:
        remove |= conflicting & raw.date.duplicated(keep=duplicate_policy)
    remove |= ~conflicting & raw.date.duplicated(keep="first")
    duplicates["action"] = np.where(
        remove.loc[duplicates.index], "excluded", "retained"
    )
    if duplicate_policy == "reject":
        duplicates.loc[duplicates.conflicting, "action"] = "rejected_unresolved"
    metadata = {
        "source": str(Path(path).resolve()),
        "duplicate_policy": duplicate_policy,
        "source_rows": len(raw),
        "duplicate_rows": int(duplicate.sum()),
        "conflicting_groups": len(conflicts),
        "conflicting_rows": int(conflicting.sum()),
        "excluded_rows": int(remove.sum()),
        "volume_available": bool((raw.volume != 0).any()),
        "timezone": "Asia/Kolkata",
        "timestamp_format": "%d-%m-%Y %H:%M",
    }
    if len(duplicates):
        if audit_dir is None:
            raise ValueError("audit_dir is required to record duplicate decisions.")
        out = Path(audit_dir)
        out.mkdir(parents=True, exist_ok=True)
        duplicates.to_csv(out / "duplicate_observations.csv", index=False)
        duplicates.loc[duplicates.conflicting].to_csv(
            out / "conflicting_duplicates.csv", index=False
        )
        (out / "loading_policy.json").write_text(json.dumps(metadata, indent=2))
        if len(conflicts) and duplicate_policy == "reject":
            raise ValueError(
                f"{len(conflicts)} conflicting duplicate timestamp groups; "
                f"see {out / 'conflicting_duplicates.csv'}."
            )
        warnings.warn(
            f"Duplicate observations audited under policy {duplicate_policy}: "
            f"{metadata['excluded_rows']} source rows excluded; see {out}.",
            UserWarning,
            stacklevel=2,
        )
    data = raw.loc[~remove].set_index("date")[values].copy()
    if not metadata["volume_available"]:
        data["volume"] = np.nan
    data.attrs["data_audit"] = metadata
    return data


def resample_to_15m(
    df,
    *,
    minute_label,
    include_evening=False,
    partial_bar_policy="exclude",
    audit_dir=None,
):
    """Anchor local start-labeled intervals to 09:15, left-closed/right-open.

    minute_label must explicitly be 'start' or 'end'. End labels are shifted
    back one minute BEFORE classification. Default: regular sessions only and
    complete 15-minute bars only. Evening (17:00-21:00) inclusion and partial-bar
    inclusion are explicit. Other out-of-session observations remain excluded.
    No missing prices are manufactured, and no exchange holiday calendar is inferred.
    Returned index labels bar starts; bar_end is the actual mark/signal timestamp.
    """
    if minute_label not in {"start", "end"}:
        raise ValueError("minute_label must explicitly be start or end.")
    if partial_bar_policy not in {"exclude", "include"}:
        raise ValueError("partial_bar_policy must be exclude or include.")
    if not isinstance(include_evening, bool):
        raise TypeError("include_evening must be bool.")
    data = df.copy()
    data.index = local_index(data.index)
    numeric_columns(data, ["open", "high", "low", "close"], positive=True)
    if "volume" not in data:
        raise ValueError("Missing required column: volume")
    numeric_columns(data.loc[data.volume.notna()], ["volume"])
    if (data.volume.dropna() < 0).any():
        raise ValueError("Volume must be nonnegative when available.")
    if not (data.volume.dropna() != 0).any():
        data["volume"] = np.nan
    if (data.high < data[["open", "low", "close"]].max(axis=1)).any() or (
        data.low > data[["open", "high", "close"]].min(axis=1)
    ).any():
        raise ValueError("Inconsistent OHLC bounds.")
    if data.index.empty:
        raise ValueError("Minute observations cannot be empty.")
    if (
        (data.index.second != 0).any()
        or (data.index.microsecond != 0).any()
        or (data.index.nanosecond != 0).any()
    ):
        raise ValueError("Minute timestamps must be on exact minute boundaries.")
    if minute_label == "end":
        data.index -= pd.Timedelta(minutes=1)
    clock = data.index.hour * 60 + data.index.minute
    regular = (clock >= 555) & (clock < 930)
    evening = (clock >= 1020) & (clock < 1260)
    classification = np.where(
        regular, "regular", np.where(evening, "evening", "outside")
    )
    # Aggregate first so excluded evening and incomplete bars can still be audited.
    grouper = data.resample(
        "15min", origin="start_day", offset="9h15min", closed="left", label="left"
    )
    bars = grouper.agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    bars["volume"] = grouper.volume.sum(min_count=1)
    bars["minute_count"] = grouper.size()
    bars = bars.loc[bars.minute_count > 0].copy()
    bclock = bars.index.hour * 60 + bars.index.minute
    bars["session"] = np.where(
        (bclock >= 555) & (bclock < 930),
        "regular",
        np.where((bclock >= 1020) & (bclock < 1260), "evening", "outside"),
    )
    bars["complete"] = bars.minute_count == 15
    allowed = (bars.session == "regular") | (
        include_evening & (bars.session == "evening")
    )
    if partial_bar_policy == "exclude":
        allowed &= bars.complete
    bars["included"] = allowed
    # For partial bars, do not pretend the final observed close is 15 minutes later.
    last = pd.Series(data.index + pd.Timedelta(minutes=1), index=data.index)
    first = pd.Series(data.index, index=data.index)
    bars["bar_open"] = (
        first.resample("15min", origin="start_day", offset="9h15min")
        .min()
        .reindex(bars.index)
    )
    bars["bar_end"] = (
        last.resample("15min", origin="start_day", offset="9h15min")
        .max()
        .reindex(bars.index)
    )
    metadata = {
        "minute_label": minute_label,
        "include_evening": include_evening,
        "partial_bar_policy": partial_bar_policy,
        "timezone": "Asia/Kolkata",
        "regular_minutes": int((classification == "regular").sum()),
        "evening_minutes": int((classification == "evening").sum()),
        "outside_minutes": int((classification == "outside").sum()),
        "partial_bars": int((~bars.complete).sum()),
        "excluded_bars": int((~allowed).sum()),
        "included_bars": int(allowed.sum()),
        "volume_available": bool(data.volume.notna().any()),
    }
    if audit_dir is not None:
        out = Path(audit_dir)
        out.mkdir(parents=True, exist_ok=True)
        bars.to_csv(out / "bar_classification.csv")
        bars.loc[~bars.complete].to_csv(out / "partial_bars.csv")
        (out / "session_policy.json").write_text(json.dumps(metadata, indent=2))
    result = bars.loc[allowed].drop(columns="included")
    result.attrs["session_audit"] = metadata
    result.attrs["data_audit"] = df.attrs.get("data_audit", {})
    return result
