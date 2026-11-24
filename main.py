"""Pump.fun paper-sprint bot: birth-snipe with a tight flip.

Own design, written from the protocol schema and the vendor shim alone.

Entry: buy a coin at the first batch where it can take a 0.02 SOL order
(real quote reserves >= 2 SOL, so the 1% size cap allows it), provided the
coin was first seen no more than 600 slots ago and its price has not
already run more than 30% above its first-seen price. There is no momentum
filter: the bet is buying near the floor before the opening pump, not
after it. One buy per coin ever; at most 5 open positions; fixed size.

Exit: sell the whole position when the price reaches +30% of the entry
price, falls to -20%, or the position is older than 900 slots. No
scale-out, no trailing stop, no re-entry.

All price comparisons use exact integer cross-multiplication on the
bonding-curve reserves, never floats. Every decision is a pure function of
the harness state (curves, positions, pending orders, slot): no clock, no
environment, no randomness, so the two graded executions agree.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bot

BUY_LAMPORTS = 20_000_000          # 0.02 SOL per coin, above the 0.01 SOL round-trip bar
TAKE_PROFIT_NUM = 130              # sell at +30% of entry price
STOP_LOSS_NUM = 80                 # sell at -20% of entry price
MAX_HOLD_SLOTS = 900               # sell whatever is left after 900 slots
MAX_AGE_AT_ENTRY_SLOTS = 600       # only coins first seen within the last 600 slots
MAX_ENTRY_RUNUP_NUM = 130          # skip if price already >30% above first sight
SLIPPAGE_BPS = 500                 # 5% slippage allowance on every order

_first_slot = {}    # mint -> slot the curve was first seen
_first_price = {}   # mint -> (virtual_quote_reserves, virtual_token_reserves) at first sight
_entry_slot = {}    # mint -> slot the position first appeared in the account
_traded = set()     # mints this bot has ever bought (never buy the same coin twice)


def _ratio_at_least(a_vq, a_vt, b_vq, b_vt, num, den=100):
    """True when (a_vq / a_vt) >= (num / den) * (b_vq / b_vt), exactly."""
    return a_vq * b_vt * den >= num * b_vq * a_vt


def _ratio_at_most(a_vq, a_vt, b_vq, b_vt, num, den=100):
    """True when (a_vq / a_vt) <= (num / den) * (b_vq / b_vt), exactly."""
    return a_vq * b_vt * den <= num * b_vq * a_vt


def on_batch(state, batch):
    slot = state.slot
    orders = []

    for mint, curve in state.curves.items():
        if mint not in _first_slot:
            _first_slot[mint] = slot
            _first_price[mint] = (
                curve.virtual_quote_reserves,
                curve.virtual_token_reserves,
            )

    for mint in state.positions:
        if mint not in _entry_slot:
            _entry_slot[mint] = slot

    # Exits first: take profit, stop loss, or time exit on every open position.
    pending_sell = {
        p.order["mint"] for p in state.pending.values() if p.order["side"] == "sell"
    }
    for mint, holding in list(state.positions.items()):
        if mint in pending_sell:
            continue
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            continue
        tokens = holding.token_amount
        cost = holding.cost_lamports
        cur_vq = curve.virtual_quote_reserves
        cur_vt = curve.virtual_token_reserves
        take_profit = _ratio_at_least(cur_vq, cur_vt, cost, tokens, TAKE_PROFIT_NUM)
        stop_loss = _ratio_at_most(cur_vq, cur_vt, cost, tokens, STOP_LOSS_NUM)
        too_old = slot - _entry_slot.get(mint, slot) > MAX_HOLD_SLOTS
        if take_profit or stop_loss or too_old:
            orders.append(
                {
                    "side": "sell",
                    "mint": mint,
                    "token_amount": tokens,
                    "max_slippage_bps": SLIPPAGE_BPS,
                }
            )

    # Entries: earliest buyable moment on fresh coins, never a chase.
    room = state.hello["caps"]["max_open_positions"] - state.committed_position_count()
    if room > 0:
        free = state.free_cash_lamports()
        tx = state.tx_fee_lamports()
        for mint, curve in state.curves.items():
            if room <= 0:
                break
            if mint in state.positions or mint in _traded or curve.complete:
                continue
            if slot - _first_slot.get(mint, slot) > MAX_AGE_AT_ENTRY_SLOTS:
                continue
            if state.max_buy_lamports(mint) < BUY_LAMPORTS:
                continue
            first_vq, first_vt = _first_price[mint]
            if not _ratio_at_most(
                curve.virtual_quote_reserves,
                curve.virtual_token_reserves,
                first_vq,
                first_vt,
                MAX_ENTRY_RUNUP_NUM,
            ):
                continue
            if free < BUY_LAMPORTS + tx:
                break
            orders.append(
                {
                    "side": "buy",
                    "mint": mint,
                    "quote_lamports": BUY_LAMPORTS,
                    "max_slippage_bps": SLIPPAGE_BPS,
                }
            )
            _traded.add(mint)
            free -= BUY_LAMPORTS + tx
            room -= 1

    return orders


def on_done(state, done):
    cash = state.cash
    held = len(state.positions)
    print(
        f"[bot] done after {state.seq} batches: cash {cash} lamports, "
        f"{held} positions left, {len(_traded)} coins traded",
        file=sys.stderr,
    )


makefun_bot.run(on_batch, on_done=on_done)
