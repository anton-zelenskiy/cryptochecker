"""Analyze SL exits; simulate new TPSL policy on historical trades.

Run: POSTGRES_HOST=localhost uv run python -m project.paper_trading.sl_postmortem_analysis
"""
from __future__ import annotations

import asyncio
import datetime as dt
from collections import Counter

from sqlalchemy import select

from project.core.config import settings
from project.core.db_session import sessionmanager
from project.models.paper_trading import PaperTrade
from project.paper_trading.exit import evaluate_exit
from project.repositories.candles import CandleRepository
from project.screener.risk import suggest_trade_levels, tpsl_kwargs_from_settings


EXIT_TF = settings.PAPER_TRADING_EXIT_SCAN_TIMEFRAME
FORWARD_WINDOWS_H = (4, 24, 72)


def _sl_dist_pct(*, entry: float, sl: float) -> float:
    if entry <= 0:
        return 0.0
    return abs(entry - sl) / entry * 100.0


def _tp_reached_after_exit(*, side: str, tp: float, candles_after_exit: list) -> bool:
    for c in candles_after_exit:
        if side == "LONG" and float(c.high) >= tp:
            return True
        if side == "SHORT" and float(c.low) <= tp:
            return True
    return False


def _simulate_exit(*, side: str, sl: float, tp: float, candles_from_entry: list) -> str:
    class T:
        pass

    t = T()
    t.side = side
    t.stop_loss = sl
    t.take_profit = tp
    hit = evaluate_exit(t, candles_from_entry)
    if hit is None:
        return "open"
    return hit[0]


async def main() -> None:
    print(
        "=== Current TPSL settings ===\n"
        f"  SL_ATR_MULT={settings.SCREENER_TPSL_SL_ATR_MULT} "
        f"SWING={settings.SCREENER_TPSL_SL_ATR_MULT_SWING}\n"
        f"  FVG_SNAP_ENABLED={settings.SCREENER_TPSL_FVG_SNAP_ENABLED} "
        f"FVG_SNAP_MIN_RISK_ATR={settings.SCREENER_TPSL_FVG_SNAP_MIN_RISK_ATR_MULT}\n"
    )

    async with sessionmanager.session() as session:
        res = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.exit_time_utc.is_not(None))
            .order_by(PaperTrade.entry_time_utc.asc())
        )
        all_closed = list(res.scalars().all())

    wins = [t for t in all_closed if (t.pnl_pct or 0) > 0]
    losses = [t for t in all_closed if (t.pnl_pct or 0) < 0 and t.exit_reason == "sl_hit"]

    print(
        f"=== Closed trades: {len(all_closed)} | wins: {len(wins)} | sl_hit losses: {len(losses)} ===\n"
    )
    if wins:
        win_sl = [_sl_dist_pct(entry=float(t.entry_price), sl=float(t.stop_loss)) for t in wins if t.stop_loss]
        print(f"Wins SL dist %: avg={sum(win_sl) / len(win_sl):.3f} (n={len(win_sl)})")
    if losses:
        loss_sl = [_sl_dist_pct(entry=float(t.entry_price), sl=float(t.stop_loss)) for t in losses if t.stop_loss]
        print(f"Losses SL dist % (actual at entry): avg={sum(loss_sl) / len(loss_sl):.3f}")
        print(f"Loss tpsl_method: {dict(Counter(t.tpsl_method for t in losses))}\n")

    repo = CandleRepository()
    tp_after: dict[int, dict[int, bool]] = {h: {} for h in FORWARD_WINDOWS_H}
    new_policy: list[str] = []
    old_policy: list[str] = []
    missing = 0

    for t in losses:
        candles = await repo.list_from_open_time_asc(
            source=t.source,
            base_asset=t.base_asset,
            quote_asset=t.quote_asset,
            timeframe=EXIT_TF,
            open_time_from_utc=t.entry_time_utc,
            limit=2000,
        )
        if not candles:
            missing += 1
            continue

        exit_t = t.exit_time_utc
        after = [c for c in candles if c.open_time_utc >= exit_t]
        for h in FORWARD_WINDOWS_H:
            window = [c for c in after if c.open_time_utc <= exit_t + dt.timedelta(hours=h)]
            tp_after[h][t.id] = _tp_reached_after_exit(
                side=t.side,
                tp=float(t.take_profit),
                candles_after_exit=window,
            )

        old_policy.append(
            _simulate_exit(
                side=t.side,
                sl=float(t.stop_loss),
                tp=float(t.take_profit),
                candles_from_entry=candles,
            )
        )

        if t.atr_used and t.atr_used > 0:
            try:
                sug = suggest_trade_levels(
                    decision=t.side,  # type: ignore[arg-type]
                    entry=float(t.entry_price),
                    atr=float(t.atr_used),
                    atr_timeframe=t.atr_timeframe or "1h",
                    fvg=None,
                    **tpsl_kwargs_from_settings(signal_horizon=t.signal_horizon),
                )
            except Exception:
                new_policy.append("error")
                continue
            new_policy.append(
                _simulate_exit(
                    side=t.side,
                    sl=sug.stop_loss,
                    tp=sug.take_profit,
                    candles_from_entry=candles,
                )
            )

    print("--- Historical: original SL/TP on path ---")
    print(f"  sl_hit first: {old_policy.count('sl_hit')}/{len(old_policy)}")
    print(f"  tp_hit first: {old_policy.count('tp_hit')}/{len(old_policy)}")

    print("\n--- Counterfactual: NEW policy on same candles ---")
    print(f"  (fvg=None, settings sl/swing + fvg_snap={settings.SCREENER_TPSL_FVG_SNAP_ENABLED})")
    print(f"  sl_hit first: {new_policy.count('sl_hit')}/{len(new_policy)}")
    print(f"  tp_hit first: {new_policy.count('tp_hit')}/{len(new_policy)}")
    print(f"  still open:   {new_policy.count('open')}/{len(new_policy)}")

    print("\n--- After actual SL exit: would original TP be touched? ---")
    for h in FORWARD_WINDOWS_H:
        n = len(tp_after[h])
        hits = sum(1 for v in tp_after[h].values() if v)
        if n:
            print(f"  within {h}h: {hits}/{n} ({100 * hits / n:.1f}%)")

    if missing:
        print(f"\n  skipped {missing} trades (no {EXIT_TF} candles)")

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
