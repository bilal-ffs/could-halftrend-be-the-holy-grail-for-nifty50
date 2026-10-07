"""One fixed-quantity, cash-and-position model for all research accounting.

Legacy fee-reserved sizing is preserved: q = cash * (1-rate) / entry_open.
The omitted residual cash (cash * rate**2) is now retained, not erased.
Both fees use actual quantity * fill price * rate. Optional adverse slippage
and execution delay default to zero points and the next observed bar.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype

from src.validation import finite_scalar, local_index, numeric_columns, validate_index

INITIAL_CAPITAL = 100_000.0
BASE_COST_BPS = 5.0
TRADE_COLUMNS = [
    "trade",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "quantity",
    "pnl_points",
    "gross_pnl",
    "entry_notional",
    "exit_notional",
    "entry_cost",
    "exit_cost",
    "total_cost",
    "net_pnl",
]
FILL_COLUMNS = ["time", "signal_time", "side", "price", "quantity", "notional", "fee"]


class InsolvencyError(ValueError):
    """The accounting model encountered nonfinite or nonpositive equity."""


@dataclass
class PortfolioResult:
    equity: pd.Series
    positions: pd.Series
    quantities: pd.Series
    cash: pd.Series
    trades: pd.DataFrame
    fills: pd.DataFrame
    open_position: dict | None
    initial_capital: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    mark_times: pd.DatetimeIndex
    cost_bps: float


def simulate_portfolio(
    df,
    *,
    initial_capital=INITIAL_CAPITAL,
    cost_bps=0.0,
    slippage_points=0.0,
    execution_delay=1,
    enter_first_bar=False,
):
    """Execute completed signals after execution_delay observed bars, starting flat.

    Quantity is fixed for the lifetime of each trade. No boundary position or
    pending order is imported into a fresh evaluation. Open trades are marked,
    not force-closed or charged an invented exit fee at the end.
    """
    capital = finite_scalar(initial_capital, "initial_capital", positive=True)
    rate = finite_scalar(cost_bps, "cost_bps", nonnegative=True) / 10000
    slippage = finite_scalar(slippage_points, "slippage_points", nonnegative=True)
    if (
        isinstance(execution_delay, bool)
        or not isinstance(execution_delay, (int, np.integer))
        or execution_delay < 1
    ):
        raise ValueError("execution_delay must be a positive integer.")
    if not isinstance(enter_first_bar, bool):
        raise ValueError("enter_first_bar must be boolean.")
    validate_index(df.index)
    if df.empty:
        raise ValueError("Evaluation bars cannot be empty.")
    numeric_columns(df, ["open", "close"], positive=True)
    for column in ["buy_signal", "sell_signal"]:
        if column not in df or not is_bool_dtype(df[column]) or df[column].isna().any():
            raise ValueError(f"{column} must contain nonmissing booleans.")
    if (df.buy_signal & df.sell_signal).any():
        raise ValueError("Simultaneous buy and sell signals are ambiguous.")
    opens = df.open.to_numpy(dtype=float)
    closes = df.close.to_numpy(dtype=float)
    buys = df.buy_signal.to_numpy(dtype=bool)
    sells = df.sell_signal.to_numpy(dtype=bool)
    # Synthetic callers may supply only bar-start index labels; intervals are 15m.
    starts = (
        local_index(pd.DatetimeIndex(df.bar_open))
        if "bar_open" in df
        else local_index(df.index)
    )
    ends = (
        local_index(pd.DatetimeIndex(df.bar_end))
        if "bar_end" in df
        else starts + pd.Timedelta(minutes=15)
    )
    if (ends <= starts).any() or (starts[1:] < ends[:-1]).any():
        raise ValueError("Bar intervals must be positive and nonoverlapping.")
    cash = capital
    quantity = 0.0
    active = None
    trades, fills = [], []
    equities, cash_values, quantities, positions = [], [], [], []
    for i in range(len(df)):
        signal_i = i - execution_delay
        initial_entry = i == 0 and enter_first_bar
        if (initial_entry or (signal_i >= 0 and buys[signal_i])) and quantity == 0:
            entry_price = opens[i] + slippage
            finite_scalar(entry_price, "entry fill price", positive=True)
            # This formula is the existing sizing rule, not a new cash/(1+rate) rule.
            if 1 - rate <= 0:
                raise ValueError(
                    "Positive entry quantity requires 1-fee_rate>0 "
                    "under legacy fee-reserved sizing."
                )
            quantity = cash * (1 - rate) / entry_price
            finite_scalar(quantity, "entry quantity", positive=True)
            notional = quantity * entry_price
            fee = notional * rate
            finite_scalar(notional, "entry notional", positive=True)
            finite_scalar(fee, "entry fee", nonnegative=True)
            cash -= notional + fee
            # Only roundoff-sized cash deficits can be zeroed.
            if cash < -capital * 1e-12:
                raise InsolvencyError("Entry purchase and fee exceed available cash.")
            cash = max(0.0, cash)
            active = dict(
                entry_time=starts[i],
                entry_price=entry_price,
                quantity=quantity,
                entry_notional=notional,
                entry_cost=fee,
            )
            fills.append(
                dict(
                    time=starts[i],
                    signal_time=starts[i] if initial_entry else ends[signal_i],
                    side="buy",
                    price=entry_price,
                    quantity=quantity,
                    notional=notional,
                    fee=fee,
                )
            )
        elif signal_i >= 0 and sells[signal_i] and quantity > 0:
            exit_price = opens[i] - slippage
            finite_scalar(exit_price, "exit fill price", positive=True)
            notional = quantity * exit_price
            fee = notional * rate
            finite_scalar(notional, "exit notional", positive=True)
            finite_scalar(fee, "exit fee", nonnegative=True)
            cash += notional - fee
            gross = quantity * (exit_price - active["entry_price"])
            total_cost = active["entry_cost"] + fee
            trades.append(
                dict(
                    trade=len(trades) + 1,
                    **active,
                    exit_time=starts[i],
                    exit_price=exit_price,
                    pnl_points=exit_price - active["entry_price"],
                    gross_pnl=gross,
                    exit_notional=notional,
                    exit_cost=fee,
                    total_cost=total_cost,
                    net_pnl=gross - total_cost,
                )
            )
            fills.append(
                dict(
                    time=starts[i],
                    signal_time=ends[signal_i],
                    side="sell",
                    price=exit_price,
                    quantity=quantity,
                    notional=notional,
                    fee=fee,
                )
            )
            active = None
            quantity = 0.0
        with np.errstate(over="ignore", invalid="ignore"):
            marked = cash + quantity * closes[i]
        if not np.isfinite(marked) or marked <= 0 or not np.isfinite(cash):
            raise InsolvencyError(f"Insolvent/nonfinite equity at {ends[i]}.")
        equities.append(marked)
        cash_values.append(cash)
        quantities.append(quantity)
        positions.append(float(quantity > 0))
    open_position = (
        None
        if active is None
        else dict(
            **active,
            mark_price=closes[-1],
            mark_time=ends[-1],
            gross_pnl=quantity * (closes[-1] - active["entry_price"]),
        )
    )

    def series(values, name):
        return pd.Series(values, index=df.index, name=name, dtype=float)

    trade_frame = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    fill_frame = pd.DataFrame(fills, columns=FILL_COLUMNS)
    # Stable schemas ensure empty prefixes compare to empty historical fill slices.
    for column in set(TRADE_COLUMNS) - {"entry_time", "exit_time", "trade"}:
        trade_frame[column] = trade_frame[column].astype(float)
    trade_frame["trade"] = trade_frame["trade"].astype("int64")
    for column in ["entry_time", "exit_time"]:
        trade_frame[column] = pd.Series(
            pd.DatetimeIndex(trade_frame[column], tz="Asia/Kolkata"),
            index=trade_frame.index,
        ).astype(pd.DatetimeTZDtype(unit="ns", tz="Asia/Kolkata"))
    for column in ["quantity", "price", "notional", "fee"]:
        fill_frame[column] = fill_frame[column].astype(float)
    for column in ["time", "signal_time"]:
        fill_frame[column] = pd.Series(
            pd.DatetimeIndex(fill_frame[column], tz="Asia/Kolkata"),
            index=fill_frame.index,
        ).astype(pd.DatetimeTZDtype(unit="ns", tz="Asia/Kolkata"))
    fill_frame["side"] = fill_frame["side"].astype("str")
    return PortfolioResult(
        equity=series(equities, "equity"),
        positions=series(positions, "position"),
        quantities=series(quantities, "quantity"),
        cash=series(cash_values, "cash"),
        trades=trade_frame,
        fills=fill_frame,
        open_position=open_position,
        initial_capital=capital,
        start_time=starts[0],
        end_time=ends[-1],
        mark_times=ends,
        cost_bps=float(cost_bps),
    )


def reconcile_portfolio(result, *, atol=1e-7):
    """Independent ledger/fill arithmetic, not repetition of a compounding formula.

    Closed net P&L already includes BOTH fees. Deduct only an open trade's entry
    fee separately; its mark is gross unrealized P&L, not a hypothetical sale.
    """
    finite_scalar(atol, "atol", nonnegative=True)
    ledger = result.trades
    if len(ledger):
        numeric_columns(
            ledger, ["quantity", "entry_price", "exit_price"], positive=True
        )
        expected_gross = ledger.quantity * (ledger.exit_price - ledger.entry_price)
        expected_entry = ledger.quantity * ledger.entry_price * result.cost_bps / 10000
        expected_exit = ledger.quantity * ledger.exit_price * result.cost_bps / 10000
        for actual, expected in [
            (ledger.gross_pnl, expected_gross),
            (ledger.entry_cost, expected_entry),
            (ledger.exit_cost, expected_exit),
            (ledger.total_cost, expected_entry + expected_exit),
            (ledger.net_pnl, expected_gross - expected_entry - expected_exit),
        ]:
            np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=atol)
    closed_net = float(ledger.net_pnl.sum())
    closed_fees = float(ledger.total_cost.sum())
    open_gross = open_entry_fee = 0.0
    if result.open_position is not None:
        position = result.open_position
        open_gross = position["quantity"] * (
            position["mark_price"] - position["entry_price"]
        )
        open_entry_fee = position["entry_cost"]
    expected = result.initial_capital + closed_net + open_gross - open_entry_fee
    final = float(result.equity.iloc[-1])
    # A second identity reconstructs cash directly from recorded fill notionals/fees.
    fills = result.fills
    buy = fills.loc[fills.side == "buy"]
    sell = fills.loc[fills.side == "sell"]
    fill_cash = (
        result.initial_capital
        - float(buy.notional.sum())
        + float(sell.notional.sum())
        - float(fills.fee.sum())
    )
    q = float(buy.quantity.sum()) - float(sell.quantity.sum())
    mark = 0 if result.open_position is None else result.open_position["mark_price"]
    np.testing.assert_allclose(result.cash.iloc[-1], fill_cash, rtol=1e-10, atol=atol)
    np.testing.assert_allclose(result.quantities.iloc[-1], q, rtol=1e-10, atol=atol)
    np.testing.assert_allclose(final, fill_cash + q * mark, rtol=1e-10, atol=atol)
    np.testing.assert_allclose(final, expected, rtol=1e-10, atol=atol)
    np.testing.assert_allclose(
        fills.fee.sum(), closed_fees + open_entry_fee, rtol=1e-10, atol=atol
    )
    return dict(
        initial_capital=result.initial_capital,
        closed_net_pnl=closed_net,
        closed_fees_included_in_net=closed_fees,
        open_gross_pnl=open_gross,
        open_entry_fee=open_entry_fee,
        expected_final_equity=expected,
        actual_final_equity=final,
        difference=final - expected,
    )
