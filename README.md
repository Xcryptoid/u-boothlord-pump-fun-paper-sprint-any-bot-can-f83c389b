# Pump.fun Paper Sprint: Any Bot Can Win

[![make.fun](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![rank](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/Xcryptoid/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/rank.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![reward](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/Xcryptoid/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/reward.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)

A paper-trading bot for make.fun's "Pump.fun Paper Sprint: Any Bot Can Win" bounty ($2 in USDC, winner takes all). It speaks `agent-fun/replay/v2` on stdin/stdout via the vendor shim in `vendor/makefun_bot.py` and trades the house's 6-hour pump.fun replay on 10 SOL of paper capital.

## Strategy: birth-snipe with a tight flip

- **Entry:** buy a coin at the first batch where it can take a 0.02 SOL order (real quote reserves ≥ 2 SOL, so the 1% size cap allows it), provided the coin was first seen no more than 600 slots ago and its price has not already run more than 30% above its first-seen price. There is no momentum filter: the bet is buying near the floor before the opening pump, not after it. One buy per coin ever; at most 5 open positions; fixed 0.02 SOL size.
- **Exit:** sell the whole position at +30% take-profit, −20% stop-loss, or after 900 slots, whichever comes first. No scale-out, no trailing stop, no re-entry.
- **Determinism:** every decision is a pure function of the harness state (curves, positions, pending orders, slot). No clock, no environment, no randomness; price comparisons use exact integer cross-multiplication on the bonding-curve reserves, so the two graded executions produce byte-identical action logs.

## Backtest (honest, dev window, official grader)

Run with the kit's own `grade-local --driver process` on the frozen dev window
(24 h, 1,222 mints, 126,801 trades), commit `95032c5`, result `2d17dac4…`:

- **Net PnL: −0.9899 SOL on 10 SOL paper capital (−9.90%) — NEGATIVE.** The
  prize bar is net PnL > 0, so this bot is not prize-eligible on dev data.
- 532 round trips on 532 distinct mints (bar: ≥20 ✓), 1,064 fills,
  win rate 22.7%, max drawdown 10.07% (bar: ≤50% ✓), guardrails compliant.
- Fees paid: 0.255 SOL proportional + 0.114 SOL transaction fees;
  148 rejected orders and 24 failed transactions.
- 90% bootstrap interval over coins: [−1.238 SOL, −0.733 SOL] — entirely
  below zero. Top 3 coins made only 8.5% of all gains, so the loss is
  broad-based, not a few bad coins; without the top 3 the net is −1.073 SOL.
- Determinism: the grader ran the bot twice and the action logs matched
  (`l1.reproduced = true`, action log `65aa0453…`).

Reading: buying every fresh coin at its first buyable moment mostly buys
the top of the opening dump — 77% of flips hit the −20% stop before the
+30% target. The numbers are reported as measured; no threshold was tuned
after seeing them. The final window is fresh data, so a negative dev score
does not predict the final one, but it is what the dev window says.

## Files

- `main.py` — the entrypoint (Python 3.13, standard library only plus the vendor shim)
- `vendor/makefun_bot.py` — the kit's own `agent-fun/replay/v2` shim, copied unchanged
- `README.md` — this file
- `LICENSE` — MIT
