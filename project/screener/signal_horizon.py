from __future__ import annotations

from project.screener.contracts import ScreenerFeaturesV1, TrendBias


def _bias_aligns_side(*, decision: str, bias: TrendBias) -> bool:
    if bias == "neutral":
        return False
    if decision == "LONG":
        return bias == "bull"
    if decision == "SHORT":
        return bias == "bear"
    return False


def _bias_fights_side(*, decision: str, bias: TrendBias) -> bool:
    if bias == "neutral":
        return False
    if decision == "LONG":
        return bias == "bear"
    if decision == "SHORT":
        return bias == "bull"
    return False


def infer_signal_horizon(*, decision: str, features: ScreenerFeaturesV1) -> str:
    """Classify intended holding style from HTF/LTF bias vs side (not candle TF of last price)."""
    if decision not in ("LONG", "SHORT"):
        return "intraday"

    hb = features.higher_tf_bias
    lb = features.lower_tf_bias
    h_ok = _bias_aligns_side(decision=decision, bias=hb)
    h_against = _bias_fights_side(decision=decision, bias=hb)
    l_ok = _bias_aligns_side(decision=decision, bias=lb)

    if h_ok:
        return "swing"
    if l_ok and not h_against:
        return "intraday"
    if l_ok and h_against:
        return "scalp"
    return "intraday"


def signal_horizon_label_ru(horizon: str) -> str:
    return {
        "swing": "свинг (старшие ТФ)",
        "intraday": "внутри дня",
        "scalp": "краткосрок / контртренд",
    }.get(horizon, horizon)
