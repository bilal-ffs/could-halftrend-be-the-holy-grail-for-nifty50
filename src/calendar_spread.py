"""SIMULATED bullish call calendars with integer units and explicit liabilities."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype

from src.accounting import InsolvencyError
from src.option_model import YEAR_SECONDS, _call, expiry, integer_spread
from src.validation import finite_scalar, local_index, numeric_columns

CAPITAL = 500_000.0


@dataclass
class CalendarResult:
    marks: pd.DataFrame
    fills: pd.DataFrame
    signals: pd.DataFrame
    events: pd.DataFrame
    initial_capital: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    open_signal: dict | None


def simulate_calendar(
    bars,
    *,
    initial_capital=CAPITAL,
    fee_bps=3,
    slippage_bps=0,
    vol_multiplier=1.2,
    near_multiplier=1.0,
    management="entry",
    matching="theta",
    threshold=0.10,
):
    """One spread at a time; decision data never come from the execution candle.

    Missing-session crossings settle expired legs at first available open's
    intrinsic value (explicit modeled fallback, not observed expiry settlement).
    Fees/slippage apply to every fill, including these synthetic settlements.
    """
    cash = finite_scalar(initial_capital, "initial_capital", positive=True)
    fee = finite_scalar(fee_bps, "fee_bps", nonnegative=True) / 10000
    slip = finite_scalar(slippage_bps, "slippage_bps", nonnegative=True) / 10000
    vm = finite_scalar(vol_multiplier, "vol_multiplier", positive=True)
    nm = finite_scalar(near_multiplier, "near_multiplier", positive=True)
    finite_scalar(threshold, "threshold", positive=True)
    if slip >= 1:
        raise ValueError("Adverse sell fill requires slippage_bps<10000.")
    if management not in {"entry", "daily"} or matching not in {"theta", "equal"}:
        raise ValueError("Invalid management or matching mode.")
    if bars.empty:
        raise ValueError("Evaluation bars cannot be empty.")
    numeric_columns(bars, ["open", "close"], positive=True)
    for c in ["buy_signal", "sell_signal"]:
        if not is_bool_dtype(bars[c]) or bars[c].isna().any():
            raise ValueError("Signals must be nonmissing booleans.")
    if (bars.buy_signal & bars.sell_signal).any():
        raise ValueError("Simultaneous signals are ambiguous.")
    starts = local_index(
        pd.DatetimeIndex(bars.bar_open) if "bar_open" in bars else bars.index
    )
    ends = (
        local_index(pd.DatetimeIndex(bars.bar_end))
        if "bar_end" in bars
        else starts + pd.Timedelta(minutes=15)
    )
    if (ends <= starts).any() or (starts[1:] < ends[:-1]).any():
        raise ValueError("Bar intervals must be positive and nonoverlapping.")
    for c in ["causal_sigma", "trend"]:
        if c not in bars:
            raise ValueError(f"Missing column {c}.")
    if np.isinf(bars.causal_sigma.to_numpy(dtype=float)).any():
        raise ValueError("Causal volatility cannot be infinite.")
    if not bars.trend.isin([0, 1]).all():
        raise ValueError("Trend must be 0 or 1.")
    opens, closes = bars.open.to_numpy(), bars.close.to_numpy()
    buys, sells = bars.buy_signal.to_numpy(), bars.sell_signal.to_numpy()
    trends = bars.trend.to_numpy()
    sigmas = bars.causal_sigma.to_numpy(dtype=float) * vm
    for c in ["causal_sigma", "trend"]:
        if c not in bars:
            raise ValueError(f"Missing column {c}.")
    active = group = previous = None
    fills, events, marks, closed = [], [], [], []
    signal_number = spread_number = 0
    start_ns, end_ns = starts.as_unit("ns").asi8, ends.as_unit("ns").asi8

    def price_pair(spot, time_ns, sigma, position):
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("Active spread has unavailable/zero causal volatility.")
        long_t = (position["long_expiry"].value - time_ns) / (YEAR_SECONDS * 1e9)
        short_t = (position["short_expiry"].value - time_ns) / (YEAR_SECONDS * 1e9)
        return (
            _call(float(spot), position["strike"], long_t, float(sigma)),
            _call(float(spot), position["strike"], short_t, float(sigma * nm)),
        )

    def fill(leg, side, quantity, model, time, decision, reason, position):
        nonlocal cash
        if quantity < 1 or int(quantity) != quantity:
            raise ValueError("Option fill quantity must be a positive integer.")
        price = model.price * (1 + slip if side == "buy" else 1 - slip)
        notional = quantity * price
        cost = notional * fee
        flow = (-notional if side == "buy" else notional) - cost
        cash += flow
        group["cash_flow"] += flow
        group["fees"] += cost
        group["slippage_cost"] += quantity * abs(price - model.price)
        fills.append(
            dict(
                time=time,
                decision_time=decision,
                signal=group["signal"],
                spread=position["spread"],
                leg=leg,
                side=side,
                quantity=int(quantity),
                strike=position["strike"],
                expiry=position[f"{leg}_expiry"],
                model_price=model.price,
                fill_price=price,
                premium_notional=notional,
                fee=cost,
                cash_flow=flow,
                reason=reason,
                model_delta=model.delta,
                model_theta=model.theta,
                model_gamma=model.gamma,
                model_vega=model.vega,
            )
        )

    def finish(time, reason):
        nonlocal group
        closed.append(
            dict(
                signal=group["signal"],
                entry_time=group["entry_time"],
                exit_time=time,
                net_pnl=group["cash_flow"],
                fees=group["fees"],
                slippage_cost=group["slippage_cost"],
                spreads=group["spreads"],
                rolls=group["rolls"],
                adjustments=group["adjustments"],
                exit_reason=reason,
            )
        )
        group = None

    def close_position(i, reason):
        nonlocal active
        long, short = price_pair(opens[i], start_ns[i], sigmas[i], active)
        fill(
            "long",
            "sell",
            active["long_quantity"],
            long,
            starts[i],
            ends[i - 1] if i else starts[i],
            reason,
            active,
        )
        fill(
            "short",
            "buy",
            active["short_quantity"],
            short,
            starts[i],
            ends[i - 1] if i else starts[i],
            reason,
            active,
        )
        active = None

    def enter(i, reason):
        nonlocal active, spread_number
        if i == 0 or not np.isfinite(sigmas[i]) or sigmas[i] <= 0:
            events.append(
                dict(
                    time=starts[i],
                    signal=group["signal"],
                    action="entry_skipped",
                    reason="volatility_warmup_or_zero",
                )
            )
            return False
        position = dict(
            strike=float(closes[i - 1]),
            long_expiry=expiry(starts[i], 60),
            short_expiry=expiry(starts[i], 30),
        )
        roll_day = position["short_expiry"].normalize() - pd.Timedelta(days=5)
        while roll_day.weekday() >= 5:
            roll_day -= pd.Timedelta(days=1)
        position["roll_time"] = roll_day + pd.Timedelta(hours=9, minutes=15)
        long, short = price_pair(opens[i], start_ns[i], sigmas[i], position)
        sizing, why = integer_spread(
            long,
            short,
            position["strike"],
            cash,
            cash,
            fee_rate=fee,
            slippage_rate=slip,
            matching=matching,
        )
        if sizing is None:
            events.append(
                dict(
                    time=starts[i],
                    signal=group["signal"],
                    action="entry_skipped",
                    reason=why,
                )
            )
            return False
        qlong, qshort, target = sizing
        spread_number += 1
        position.update(
            spread=spread_number,
            long_quantity=qlong,
            short_quantity=qshort,
            initial_long_theta=qlong * abs(long.theta),
            target_ratio=target,
            entry_theta=qlong * long.theta - qshort * short.theta,
            entry_long_cost=qlong * long.price * (1 + slip) * (1 + fee),
            entry_equity=cash,
            entry_time=starts[i],
        )
        before = cash
        fill("long", "buy", qlong, long, starts[i], ends[i - 1], reason, position)
        fill("short", "sell", qshort, short, starts[i], ends[i - 1], reason, position)
        position["entry_debit"] = before - cash
        position["entry_premium_and_fees"] = (
            position["entry_long_cost"] + qshort * short.price * (1 - slip) * fee
        )
        assert position["entry_premium_and_fees"] <= 0.05 * before + 1e-7
        assert cash + 1e-7 >= qshort * position["strike"]
        assert qlong * long.delta - qshort * short.delta > 0
        group["spreads"] += 1
        events.append(
            dict(
                time=starts[i],
                decision_time=ends[i - 1],
                signal=group["signal"],
                spread=spread_number,
                action="entry",
                reason=reason,
                target_ratio=target,
                achieved_ratio=qshort / qlong,
                theta=position["entry_theta"],
                residual_theta=position["entry_theta"] / position["initial_long_theta"],
                delta=qlong * long.delta - qshort * short.delta,
                long_quantity=qlong,
                short_quantity=qshort,
                debit=position["entry_debit"],
                collateral=qshort * position["strike"],
                initial_long_theta=position["initial_long_theta"],
                long_premium_with_fees=position["entry_long_cost"],
                entry_premium_and_fees=position["entry_premium_and_fees"],
                pre_entry_equity=before,
            )
        )
        active = position
        return True

    for i in range(len(bars)):
        new_session = i > 0 and starts[i].date() != starts[i - 1].date()
        acted = False
        if active is not None and i and sells[i - 1]:
            close_position(i, "bearish_exit")
            finish(starts[i], "bearish_exit")
            acted = True
        elif active is not None and starts[i] >= active["roll_time"]:
            crossed = starts[i] >= active["short_expiry"]
            late = starts[i] > active["short_expiry"] - pd.Timedelta(days=5)
            reason = (
                "expiry_crossing_gap"
                if crossed
                else "late_buffer_gap" if late else "five_day_roll"
            )
            group["rolls"] += 1
            events.append(
                dict(
                    time=starts[i], signal=group["signal"], action="roll", reason=reason
                )
            )
            close_position(i, reason)
            if i and trends[i - 1] == 0 and enter(i, "roll_entry"):
                pass
            else:
                finish(starts[i], "roll_no_reentry")
            acted = True
        if active is not None and management == "daily" and new_session and not acted:
            qlong = active["long_quantity"]
            denom = active["initial_long_theta"]
            drift = abs(previous["theta"]) / denom
            if drift > threshold:
                long, short = price_pair(opens[i], start_ns[i], sigmas[i], active)
                candidates = []
                for q in range(1, qlong + 1):
                    change = q - active["short_quantity"]
                    adj_price = short.price * (1 - slip if change > 0 else 1 + slip)
                    flow = change * adj_price - abs(change) * adj_price * fee
                    after = cash + flow
                    if (
                        qlong * long.delta - q * short.delta > 0
                        and after + 1e-7 >= q * active["strike"]
                    ):
                        target_error = (
                            abs(
                                qlong * previous["long_theta"]
                                - q * previous["short_theta"]
                            )
                            / denom
                        )
                        candidates.append((target_error, abs(change), q))
                if not candidates:
                    events.append(
                        dict(
                            time=starts[i],
                            decision_time=ends[i - 1],
                            signal=group["signal"],
                            action="adjustment_skipped",
                            reason="no_positive_delta_collateral_feasible_integer_short",
                        )
                    )
                else:
                    q = min(candidates)[2]
                    change = q - active["short_quantity"]
                    events.append(
                        dict(
                            time=starts[i],
                            decision_time=ends[i - 1],
                            signal=group["signal"],
                            spread=active["spread"],
                            action="theta_check",
                            prior_residual=previous["theta"] / denom,
                            target_short=q,
                            turnover=abs(change),
                            prior_long_theta=previous["long_theta"],
                            prior_short_theta=previous["short_theta"],
                            target_theta=0.0,
                            achieved_theta=qlong * long.theta - q * short.theta,
                            achieved_residual=(qlong * long.theta - q * short.theta)
                            / denom,
                            delta=qlong * long.delta - q * short.delta,
                        )
                    )
                    if change:
                        fill(
                            "short",
                            "sell" if change > 0 else "buy",
                            abs(change),
                            short,
                            starts[i],
                            ends[i - 1],
                            "theta_adjustment",
                            active,
                        )
                        active["short_quantity"] = q
                        group["adjustments"] += 1
        if i and buys[i - 1] and active is None and group is None and not acted:
            signal_number += 1
            group = dict(
                signal=signal_number,
                entry_time=starts[i],
                cash_flow=0.0,
                fees=0.0,
                slippage_cost=0.0,
                spreads=0,
                rolls=0,
                adjustments=0,
            )
            if not enter(i, "bullish_entry"):
                group = None
        row = dict(
            bar_start=bars.index[i],
            mark_time=ends[i],
            spot=float(closes[i]),
            cash=cash,
            collateral=0.0,
            free_cash=cash,
            long_value=0.0,
            short_liability=0.0,
            equity=cash,
            signal=0 if group is None else group["signal"],
            spread=0,
            long_quantity=0,
            short_quantity=0,
            strike=np.nan,
            long_expiry=pd.NaT,
            short_expiry=pd.NaT,
            long_sigma=sigmas[i],
            short_sigma=sigmas[i] * nm,
            long_price=0.0,
            short_price=0.0,
            long_theta=0.0,
            short_theta=0.0,
            long_delta=0.0,
            short_delta=0.0,
            long_gamma=0.0,
            short_gamma=0.0,
            long_vega=0.0,
            short_vega=0.0,
            theta=0.0,
            delta=0.0,
            gamma=0.0,
            vega=0.0,
            initial_long_theta=0.0,
            residual_theta=0.0,
            target_ratio=np.nan,
            achieved_ratio=np.nan,
            gross_underlying_exposure=0.0,
            net_delta_exposure=0.0,
            entry_debit=0.0,
        )
        if active is not None:
            long, short = price_pair(closes[i], end_ns[i], sigmas[i], active)
            qlong, qshort = active["long_quantity"], active["short_quantity"]
            row.update(
                spread=active["spread"],
                long_quantity=qlong,
                short_quantity=qshort,
                strike=active["strike"],
                long_expiry=active["long_expiry"],
                short_expiry=active["short_expiry"],
                long_price=long.price,
                short_price=short.price,
                long_value=qlong * long.price,
                short_liability=qshort * short.price,
                collateral=qshort * active["strike"],
                free_cash=cash - qshort * active["strike"],
                theta=qlong * long.theta - qshort * short.theta,
                delta=qlong * long.delta - qshort * short.delta,
                gamma=qlong * long.gamma - qshort * short.gamma,
                vega=qlong * long.vega - qshort * short.vega,
                initial_long_theta=active["initial_long_theta"],
                target_ratio=active["target_ratio"],
                achieved_ratio=qshort / qlong,
                entry_debit=active["entry_debit"],
                gross_underlying_exposure=(qlong + qshort) * closes[i],
                long_theta=long.theta,
                short_theta=short.theta,
                long_delta=long.delta,
                short_delta=short.delta,
                long_gamma=long.gamma,
                short_gamma=short.gamma,
                long_vega=long.vega,
                short_vega=short.vega,
            )
            row["equity"] = cash + row["long_value"] - row["short_liability"]
            row["net_delta_exposure"] = row["delta"] * closes[i]
            row["residual_theta"] = row["theta"] / active["initial_long_theta"]
            assert 1 <= qshort <= qlong
            assert row["free_cash"] >= -1e-7
        if not np.isfinite(row["equity"]) or row["equity"] <= 0:
            raise InsolvencyError(f"SIMULATED calendar insolvency at {ends[i]}")
        marks.append(row)
        previous = row
    frame = pd.DataFrame(marks).set_index("bar_start")
    fill_columns = [
        "time",
        "decision_time",
        "signal",
        "spread",
        "leg",
        "side",
        "quantity",
        "strike",
        "expiry",
        "model_price",
        "fill_price",
        "premium_notional",
        "fee",
        "cash_flow",
        "reason",
        "model_delta",
        "model_theta",
        "model_gamma",
        "model_vega",
    ]
    signal_columns = [
        "signal",
        "entry_time",
        "exit_time",
        "net_pnl",
        "fees",
        "slippage_cost",
        "spreads",
        "rolls",
        "adjustments",
        "exit_reason",
    ]
    event_frame = pd.DataFrame(events)
    opened = (
        None
        if group is None
        else dict(
            **group,
            net_pnl=group["cash_flow"]
            + frame.long_value.iloc[-1]
            - frame.short_liability.iloc[-1],
        )
    )
    fill_frame = pd.DataFrame(fills, columns=fill_columns)
    for c in ["time", "decision_time", "expiry"]:
        fill_frame[c] = pd.Series(
            pd.DatetimeIndex(fill_frame[c], tz="Asia/Kolkata")
        ).astype(pd.DatetimeTZDtype(unit="ns", tz="Asia/Kolkata"))
    for c in ["signal", "spread", "quantity"]:
        fill_frame[c] = fill_frame[c].astype("int64")
    for c in [
        "strike",
        "model_price",
        "fill_price",
        "premium_notional",
        "fee",
        "cash_flow",
        "model_delta",
        "model_theta",
        "model_gamma",
        "model_vega",
    ]:
        fill_frame[c] = fill_frame[c].astype(float)
    for c in ["leg", "side", "reason"]:
        fill_frame[c] = fill_frame[c].astype("str")
    return CalendarResult(
        frame,
        fill_frame,
        pd.DataFrame(closed, columns=signal_columns),
        event_frame,
        float(initial_capital),
        starts[0],
        ends[-1],
        opened,
    )


def reconcile_calendar(result, fee_bps, slippage_bps):
    """Independent cash-flow reconstruction from modeled premiums and leg fills.

    Reserved collateral is INSIDE cash: never an extra asset or equity deduction.
    """
    fills, marks = result.fills, result.marks
    if fills.empty:
        cash_path = pd.Series(result.initial_capital, index=marks.index)
    else:
        signs = np.where(fills.side == "buy", -1.0, 1.0)
        model = fills.model_price.to_numpy(dtype=float)
        actual = model * (1 - signs * slippage_bps / 10000)
        notionals = actual * fills.quantity.to_numpy(dtype=float)
        fees = notionals * fee_bps / 10000
        flows = signs * notionals - fees
        np.testing.assert_allclose(fills.fill_price.astype(float), actual, rtol=1e-12)
        np.testing.assert_allclose(fills.fee.astype(float), fees, rtol=1e-12)
        np.testing.assert_allclose(fills.cash_flow.astype(float), flows, rtol=1e-12)
        times = pd.DatetimeIndex(fills.time)
        changes = pd.Series(flows, index=times).groupby(level=0).sum()
        cash_path = (
            result.initial_capital + changes.reindex(marks.index, fill_value=0).cumsum()
        )
        grouped = pd.Series(flows, index=fills.signal.to_numpy()).groupby(level=0).sum()
        for trade in result.signals.itertuples():
            np.testing.assert_allclose(
                trade.net_pnl, grouped.loc[trade.signal], atol=1e-7
            )
    for leg in ["long", "short"]:
        selected = fills.loc[fills.leg == leg]
        if selected.empty:
            held = pd.Series(0.0, index=marks.index)
        else:
            direction = np.where(
                selected.side == ("buy" if leg == "long" else "sell"), 1.0, -1.0
            )
            deltas = (
                pd.Series(
                    selected.quantity.to_numpy(dtype=float) * direction,
                    index=pd.DatetimeIndex(selected.time),
                )
                .groupby(level=0)
                .sum()
            )
            held = deltas.reindex(marks.index, fill_value=0).cumsum()
        np.testing.assert_allclose(marks[f"{leg}_quantity"], held, atol=1e-10)
    if len(fills):
        assert fills.quantity.ge(1).all()
        assert (fills.quantity % 1 == 0).all()
        flows_before = result.initial_capital + fills.cash_flow.astype(
            float
        ).cumsum().shift(1, fill_value=0)
        entries = (fills.leg == "long") & (fills.side == "buy")
        for i in fills.index[entries]:
            partner = fills.iloc[i + 1]
            assert partner.leg == "short" and partner.side == "sell"
            assert partner.time == fills.loc[i, "time"]
            cost = fills.loc[i, "premium_notional"] + fills.loc[i, "fee"] + partner.fee
            assert cost <= 0.05 * flows_before.loc[i] + 1e-7
    active = marks.long_quantity > 0
    assert marks.loc[active, "short_quantity"].ge(1).all()
    assert (marks.short_quantity <= marks.long_quantity).all()
    long_value = marks.long_quantity * marks.long_price
    short_value = marks.short_quantity * marks.short_price
    expected = cash_path + long_value - short_value
    np.testing.assert_allclose(marks.cash, cash_path, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(marks.equity, expected, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(
        marks.collateral, marks.short_quantity * marks.strike.fillna(0), rtol=1e-12
    )
    np.testing.assert_allclose(
        marks.free_cash, marks.cash - marks.collateral, atol=1e-7
    )
    closed = float(result.signals.net_pnl.astype(float).sum())
    opened = 0.0 if result.open_signal is None else result.open_signal["net_pnl"]
    np.testing.assert_allclose(
        marks.equity.iloc[-1], result.initial_capital + closed + opened, atol=1e-7
    )
    return dict(
        passed=True,
        reconstructed_marks=len(marks),
        final_equity=float(expected.iloc[-1]),
        closed_signal_pnl=closed,
        open_signal_pnl=opened,
        collateral_counted_once=True,
    )
