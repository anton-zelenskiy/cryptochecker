from __future__ import annotations

from dataclasses import dataclass

from project.models.indicators import IndicatorSnapshot


@dataclass(frozen=True, slots=True)
class ScreenerDecision:
    decision: str  # LONG/SHORT/WAIT
    confidence: float
    rsi_14: float | None = None


def decide_from_indicator_snapshot(snap: IndicatorSnapshot | None) -> ScreenerDecision:
    if snap is None or snap.rsi_14 is None:
        return ScreenerDecision(decision="WAIT", confidence=0.0, rsi_14=None)

    rsi = float(snap.rsi_14)
    if rsi <= 30:
        return ScreenerDecision(decision="LONG", confidence=min(1.0, (30 - rsi) / 30 + 0.5), rsi_14=rsi)
    if rsi >= 70:
        return ScreenerDecision(decision="SHORT", confidence=min(1.0, (rsi - 70) / 30 + 0.5), rsi_14=rsi)

    return ScreenerDecision(decision="WAIT", confidence=0.2, rsi_14=rsi)

