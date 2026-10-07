import json

import numpy as np
import pandas as pd
import pytest

from src.data import load_minute_data, resample_to_15m


def csv_data(tmp_path, dates, **changes):
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 101.0,
            "volume": 0.0,
        }
    )
    for column, values in changes.items():
        frame[column] = values
    path = tmp_path / "minutes.csv"
    frame.to_csv(path, index=False)
    return path


def test_explicit_day_month_year_and_unavailable_volume(tmp_path):
    path = csv_data(tmp_path, ["09-01-2015 09:15", "13-01-2015 09:15"])
    loaded = load_minute_data(path)
    assert loaded.index[0] == pd.Timestamp("2015-01-09 09:15", tz="Asia/Kolkata")
    assert loaded.index[1].day == 13
    assert loaded.volume.isna().all()
    assert not loaded.attrs["data_audit"]["volume_available"]


def test_rejects_conflicts_and_exports_source_rows(tmp_path):
    path = csv_data(tmp_path, ["29-06-2015 11:54"] * 2, open=[100, 100.5])
    audit = tmp_path / "audit"
    with pytest.raises(ValueError, match="conflicting"):
        load_minute_data(path, audit_dir=audit)
    exported = pd.read_csv(audit / "conflicting_duplicates.csv")
    assert exported.source_row.tolist() == [2, 3]
    assert exported.open.tolist() == [100, 100.5]
    assert exported.policy.tolist() == ["reject"] * 2
    assert exported.action.tolist() == ["rejected_unresolved"] * 2


@pytest.mark.parametrize(
    "policy,expected,removed",
    [
        ("exclude", [102.0], 2),
        ("first", [100.0, 102.0], 1),
        ("last", [100.5, 102.0], 1),
    ],
)
def test_explicit_conflict_policies_record_decisions(
    tmp_path, policy, expected, removed
):
    path = csv_data(
        tmp_path,
        ["29-06-2015 11:54"] * 2 + ["29-06-2015 11:55"],
        open=[100, 100.5, 102],
    )
    audit = tmp_path / "audit"
    with pytest.warns(UserWarning, match=policy):
        loaded = load_minute_data(path, duplicate_policy=policy, audit_dir=audit)
    assert loaded.open.tolist() == expected
    metadata = json.loads((audit / "loading_policy.json").read_text())
    assert metadata["duplicate_policy"] == policy
    assert metadata["excluded_rows"] == removed
    assert metadata["conflicting_rows"] == 2
    assert not loaded.index.has_duplicates


def test_exact_duplicates_are_also_audited(tmp_path):
    path = csv_data(tmp_path, ["09-01-2015 09:15"] * 2)
    with pytest.warns(UserWarning):
        loaded = load_minute_data(path, audit_dir=tmp_path / "audit")
    assert len(loaded) == 1
    assert loaded.attrs["data_audit"]["excluded_rows"] == 1


def test_conflicts_cannot_be_silently_resolved_without_audit(tmp_path):
    path = csv_data(tmp_path, ["09-01-2015 09:15"] * 2, open=[100, 100.5])
    with pytest.raises(ValueError, match="audit_dir"):
        load_minute_data(path, duplicate_policy="first", audit_dir=None)


@pytest.mark.parametrize("dates", [["2015-01-09 09:15"], ["32-01-2015 09:15"], [None]])
def test_invalid_date_format_or_missing_timestamp(tmp_path, dates):
    with pytest.raises(ValueError):
        load_minute_data(csv_data(tmp_path, dates))


@pytest.mark.parametrize(
    "column,value",
    [
        ("open", 0),
        ("close", np.inf),
        ("high", 99),
        ("low", 102),
        ("volume", -1),
        ("close", np.nan),
    ],
)
def test_invalid_raw_observations(tmp_path, column, value):
    path = csv_data(tmp_path, ["09-01-2015 09:15"], **{column: [value]})
    with pytest.raises(ValueError):
        load_minute_data(path)


def minutes(start="2024-01-02 09:15", periods=375):
    index = pd.date_range(start, periods=periods, freq="min", tz="Asia/Kolkata")
    return pd.DataFrame(
        {"open": 100.0, "high": 105.0, "low": 95.0, "close": 101.0, "volume": np.nan},
        index=index,
    )


def test_normal_session_has_25_complete_anchored_bars():
    result = resample_to_15m(minutes(), minute_label="start")
    assert len(result) == 25
    assert result.index[0] == pd.Timestamp("2024-01-02 09:15", tz="Asia/Kolkata")
    assert result.index[-1].strftime("%H:%M") == "15:15"
    assert result.bar_end.iloc[-1].strftime("%H:%M") == "15:30"
    assert result.complete.all()
    assert result.minute_count.tolist() == [15] * 25
    assert result.volume.isna().all()


def test_end_labels_are_shifted_before_session_classification():
    starts = minutes()
    ends = starts.copy()
    ends.index += pd.Timedelta(minutes=1)
    pd.testing.assert_frame_equal(
        resample_to_15m(starts, minute_label="start"),
        resample_to_15m(ends, minute_label="end"),
    )


def test_minute_label_must_be_explicit():
    with pytest.raises(TypeError):
        resample_to_15m(minutes())
    with pytest.raises(ValueError, match="minute_label"):
        resample_to_15m(minutes(), minute_label="infer")


def test_partial_bar_exclusion_and_explicit_inclusion(tmp_path):
    data = minutes(periods=30).drop(pd.Timestamp("2024-01-02 09:15", tz="Asia/Kolkata"))
    excluded = resample_to_15m(data, minute_label="start", audit_dir=tmp_path)
    assert len(excluded) == 1
    included = resample_to_15m(data, minute_label="start", partial_bar_policy="include")
    assert len(included) == 2
    assert included.minute_count.tolist() == [14, 15]
    assert included.bar_open.iloc[0].strftime("%H:%M") == "09:16"
    assert not included.complete.iloc[0]
    assert len(pd.read_csv(tmp_path / "partial_bars.csv")) == 1


def test_evening_and_outside_sessions_have_explicit_policies(tmp_path):
    data = pd.concat(
        [
            minutes(periods=15),
            minutes("2024-01-02 15:30", 1),
            minutes("2024-01-02 18:00", 15),
        ]
    )
    regular = resample_to_15m(data, minute_label="start", audit_dir=tmp_path)
    assert len(regular) == 1
    assert regular.attrs["session_audit"]["evening_minutes"] == 15
    assert regular.attrs["session_audit"]["outside_minutes"] == 1
    included = resample_to_15m(data, minute_label="start", include_evening=True)
    assert included.session.tolist() == ["regular", "evening"]


def test_session_open_and_close_are_not_extra_regular_bars():
    data = minutes("2024-01-02 09:14", 377)
    bars = resample_to_15m(data, minute_label="start")
    assert len(bars) == 25
    assert bars.attrs["session_audit"]["outside_minutes"] == 2


def test_resampling_rejects_duplicate_and_unordered_minutes():
    with pytest.raises(ValueError, match="unique"):
        resample_to_15m(pd.concat([minutes(periods=1)] * 2), minute_label="start")
    with pytest.raises(ValueError, match="sorted"):
        resample_to_15m(minutes(periods=2).iloc[::-1], minute_label="start")


def test_resampling_also_marks_all_zero_volume_as_unavailable():
    data = minutes(periods=15)
    data["volume"] = 0.0
    bars = resample_to_15m(data, minute_label="start")
    assert bars.volume.isna().all()
    assert not bars.attrs["session_audit"]["volume_available"]


def test_partial_bar_end_is_last_observed_interval_end():
    data = minutes(periods=7)
    bars = resample_to_15m(data, minute_label="start", partial_bar_policy="include")
    assert bars.bar_end.iloc[0].strftime("%H:%M") == "09:22"


def test_wrong_duplicate_policy_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate_policy"):
        load_minute_data(
            csv_data(tmp_path, ["09-01-2015 09:15"]), duplicate_policy="silent"
        )
