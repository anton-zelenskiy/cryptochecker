from __future__ import annotations


def decision_from_rsi(rsi_14: float) -> tuple[str, float]:
    """
    Very simple v1 rule:
    - RSI <= 30 -> LONG
    - RSI >= 70 -> SHORT
    - else WAIT

    Returns: (decision, confidence 0..1)
    """
    if rsi_14 <= 30:
        return "LONG", min(1.0, (30 - rsi_14) / 30 + 0.5)
    if rsi_14 >= 70:
        return "SHORT", min(1.0, (rsi_14 - 70) / 30 + 0.5)
    return "WAIT", 0.0

