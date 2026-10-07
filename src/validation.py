"""Shared finite numeric and chronology checks for this research model."""

from numbers import Real

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_complex_dtype, is_numeric_dtype


def finite_scalar(value, name, *, positive=False, nonnegative=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number.")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive.")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be nonnegative.")
    return float(value)


def numeric_columns(df, columns, *, positive=False):
    for column in columns:
        if column not in df:
            raise ValueError(f"Missing required column: {column}")
        if (
            not is_numeric_dtype(df[column])
            or is_bool_dtype(df[column])
            or is_complex_dtype(df[column])
        ):
            raise TypeError(f"{column} must be real numeric values.")
        values = df[column].to_numpy(dtype=float)
        if np.iscomplexobj(df[column].to_numpy()) or not np.isfinite(values).all():
            raise ValueError(f"{column} must be finite real values.")
        if positive and (values <= 0).any():
            raise ValueError(f"{column} must be positive.")


def validate_index(index):
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("A DatetimeIndex is required.")
    if index.hasnans or not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("Timestamps must be valid, unique and chronologically sorted.")


def local_index(index):
    validate_index(index)
    return (
        index.tz_localize("Asia/Kolkata")
        if index.tz is None
        else index.tz_convert("Asia/Kolkata")
    )
