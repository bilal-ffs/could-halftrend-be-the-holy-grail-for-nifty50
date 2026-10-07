"""SIMULATED European calls: Black-Scholes-Merton, calendar-day theta."""

from functools import lru_cache
from math import erfc, exp, log, pi, sqrt
from typing import NamedTuple

import numpy as np
import pandas as pd

from src.validation import finite_scalar, local_index

YEAR_SECONDS = 365 * 86400


class Call(NamedTuple):
    price: float
    delta: float
    gamma: float
    vega: float  # currency per 1 percentage point of this leg's volatility
    theta: float  # currency per CALENDAR day, passage-of-time derivative


@lru_cache(maxsize=100_000)
def _call(spot, strike, years, sigma, rate=0.06, dividend=0.01):
    """Validated research callers use this cached scalar kernel."""
    if years <= 0:
        delta = 1.0 if spot > strike else 0.0 if spot < strike else 0.5
        return Call(max(spot - strike, 0.0), delta, 0.0, 0.0, 0.0)
    root = sqrt(years)
    d1 = (log(spot / strike) + (rate - dividend + sigma * sigma / 2) * years) / (
        sigma * root
    )
    d2 = d1 - sigma * root
    n1, n2 = 0.5 * erfc(-d1 / sqrt(2)), 0.5 * erfc(-d2 / sqrt(2))
    phi = exp(-d1 * d1 / 2) / sqrt(2 * pi)
    sq = spot * exp(-dividend * years)
    kr = strike * exp(-rate * years)
    price = max(sq * n1 - kr * n2, 0.0)
    theta = (-sq * phi * sigma / (2 * root) - rate * kr * n2 + dividend * sq * n1) / 365
    return Call(
        price,
        exp(-dividend * years) * n1,
        exp(-dividend * years) * phi / (spot * sigma * root),
        sq * phi * root / 100,
        theta,
    )


def call(spot, strike, years, sigma, *, rate=0.06, dividend=0.01):
    """Continuous annual rates; ACT/365 time; intrinsic settlement for T<=0.

    At expiry ATM delta is conventionally 0.5, other expired Greeks are zero.
    Expired contracts cannot be opened as calendar spreads.
    """
    spot = finite_scalar(spot, "spot", positive=True)
    strike = finite_scalar(strike, "strike", positive=True)
    years = finite_scalar(years, "years")
    sigma = finite_scalar(sigma, "sigma", positive=True)
    rate = finite_scalar(rate, "rate")
    dividend = finite_scalar(dividend, "dividend")
    return _call(spot, strike, years, sigma, rate, dividend)


def expiry(time, days):
    """Synthetic expiry: entry local date + target days, next weekday 15:30.

    This is NOT a historical NIFTY exchange expiry or holiday calendar.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("Maturity days must be a positive integer.")
    day = pd.Timestamp(time).normalize() + pd.Timedelta(days=days)
    while day.weekday() >= 5:
        day += pd.Timedelta(days=1)
    return day + pd.Timedelta(hours=15, minutes=30)


def causal_volatility(bars, sessions=21):
    """Sample std of 21 daily log returns * sqrt(252), next session only.

    Included daily close marks only: no fabricated holiday/missing-session prices.
    A return across a gap is one observed session return. Zero/undefined estimates
    are not floored; entries skip unavailable estimates.
    """
    if isinstance(sessions, bool) or not isinstance(sessions, int) or sessions < 2:
        raise ValueError("sessions must be an integer >=2.")
    index = local_index(bars.index)
    daily = bars.close.groupby(index.normalize()).last()
    returns = np.log(daily / daily.shift(1))
    estimates = returns.rolling(sessions, min_periods=sessions).std(ddof=1) * np.sqrt(
        252
    )
    available = estimates.shift(1)
    values = available.reindex(index.normalize()).to_numpy()
    return pd.Series(values, index=bars.index, name="causal_sigma")


def integer_spread(
    long,
    short,
    strike,
    equity,
    cash,
    *,
    fee_rate,
    slippage_rate,
    matching="theta",
    premium_limit=0.05,
):
    """Globally closest feasible integer ratio, then largest long quantity.

    Both legs must have >=1 unit. No long-only fallback or short-receipt budget
    bypass. Cash after ALL entry flows must cover q_short*strike.
    """
    for name, value in [("strike", strike), ("equity", equity), ("cash", cash)]:
        finite_scalar(value, name, positive=True)
    finite_scalar(premium_limit, "premium_limit", positive=True)
    if premium_limit > 1:
        raise ValueError("premium_limit cannot exceed equity.")
    finite_scalar(fee_rate, "fee_rate", nonnegative=True)
    finite_scalar(slippage_rate, "slippage_rate", nonnegative=True)
    if slippage_rate >= 1:
        raise ValueError("Sell fill requires slippage_rate<1.")
    if matching not in {"theta", "equal"}:
        raise ValueError("matching must be theta or equal.")
    if long.theta >= 0 or short.theta >= 0 or short.price <= 0 or long.price <= 0:
        return None, "nonnegative_or_undefined_leg_theta_or_premium"
    target = abs(long.theta) / abs(short.theta) if matching == "theta" else 1.0
    buy = long.price * (1 + slippage_rate)
    sell = short.price * (1 - slippage_rate)
    maximum = int(premium_limit * equity / (buy * (1 + fee_rate)))
    best = None
    for qlong in range(1, maximum + 1):
        if matching == "equal":
            candidates = [qlong]
        else:
            # Solve feasible integer interval before rounding: collateral and
            # positive delta bound the short quantity; never search only a
            # financially infeasible rounded hedge.
            lower, upper = 1, qlong
            if fee_rate > 0:
                entry_room = premium_limit * equity - qlong * buy * (1 + fee_rate)
                upper = min(
                    upper, int(np.floor((entry_room + 1e-8) / (sell * fee_rate)))
                )
            if short.delta > 0:
                upper = min(upper, int(np.ceil(qlong * long.delta / short.delta)) - 1)
            base_cash = cash - qlong * buy * (1 + fee_rate)
            per_short = strike - sell * (1 - fee_rate)
            if per_short > 0:
                upper = min(upper, int(np.floor((base_cash + 1e-8) / per_short)))
            elif per_short < 0:
                lower = max(lower, int(np.ceil(base_cash / per_short)))
            elif base_cash < 0:
                continue
            if upper < lower:
                continue
            ideal = qlong * target
            candidates = {
                max(lower, min(upper, int(np.floor(ideal)))),
                max(lower, min(upper, int(np.ceil(ideal)))),
            }
        for qshort in candidates:
            budget_cost = qlong * buy * (1 + fee_rate) + qshort * sell * fee_rate
            if budget_cost > premium_limit * equity + 1e-8:
                continue
            if qlong * long.delta - qshort * short.delta <= 0:
                continue
            after = cash - qlong * buy * (1 + fee_rate) + qshort * sell * (1 - fee_rate)
            if after + 1e-8 < qshort * strike:
                continue
            score = (abs(qshort / qlong - target), -qlong, qshort)
            if best is None or score < best[0]:
                best = score, qlong, qshort
    if best is None:
        return (
            None,
            "no_integer_hedge_with_positive_delta_premium_budget_and_collateral",
        )
    return (best[1], best[2], target), None
