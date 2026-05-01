from __future__ import annotations

from dataclasses import dataclass

from project.screener.contracts import DecisionSide, FvgNearbyFeature, ScreenerFeaturesV1


SL_ATR_MULT_DEFAULT = 1.5
TP_R_MULT_DEFAULT = 2.0
SNAP_MAX_PCT_DEFAULT = 0.04
SNAP_MAX_RISK_MULT_DEFAULT = 2.0


@dataclass(frozen=True, slots=True)
class TpSlSuggestion:
    entry: float
    stop_loss: float
    take_profit: float
    risk_r: float
    atr_used: float
    atr_timeframe: str
    method: str  # "atr_baseline" | "atr_plus_fvg_snap"


def select_atr(features: ScreenerFeaturesV1) -> tuple[float | None, str | None]:
    for tf in ("1h", "15m"):
        block = features.per_tf_indicators.get(tf)
        if block and block.atr_14 is not None:
            try:
                atr = float(block.atr_14)
            except Exception:
                continue
            if atr > 0:
                return atr, tf
    return None, None


def _baseline_levels(*, decision: DecisionSide, entry: float, atr: float, sl_atr_mult: float) -> tuple[float, float]:
    risk = max(1e-12, sl_atr_mult * atr)
    if decision == "LONG":
        return entry - risk, risk
    if decision == "SHORT":
        return entry + risk, risk
    raise ValueError("baseline levels require LONG/SHORT")


def suggest_trade_levels(
    *,
    decision: DecisionSide,
    entry: float,
    atr: float,
    atr_timeframe: str,
    fvg: FvgNearbyFeature | None,
    sl_atr_mult: float = SL_ATR_MULT_DEFAULT,
    tp_r_mult: float = TP_R_MULT_DEFAULT,
    snap_max_pct: float = SNAP_MAX_PCT_DEFAULT,
    snap_max_risk_mult: float = SNAP_MAX_RISK_MULT_DEFAULT,
) -> TpSlSuggestion:
    if decision not in ("LONG", "SHORT"):
        raise ValueError("TP/SL suggestions only for LONG/SHORT")
    if entry <= 0:
        raise ValueError("entry must be > 0")
    if atr <= 0:
        raise ValueError("atr must be > 0")
    if sl_atr_mult <= 0 or tp_r_mult <= 0:
        raise ValueError("multipliers must be > 0")

    baseline_sl, baseline_risk = _baseline_levels(decision=decision, entry=entry, atr=atr, sl_atr_mult=sl_atr_mult)
    sl = baseline_sl
    method = "atr_baseline"

    if fvg and fvg.direction and fvg.zone_low is not None and fvg.zone_high is not None:
        if decision == "LONG" and fvg.direction == "bull":
            candidate = float(fvg.zone_low)
            if 0 < candidate < entry:
                candidate_risk = entry - candidate
                pct = candidate_risk / entry
                if pct <= snap_max_pct or candidate_risk <= baseline_risk * snap_max_risk_mult:
                    sl = candidate
                    method = "atr_plus_fvg_snap"
        elif decision == "SHORT" and fvg.direction == "bear":
            candidate = float(fvg.zone_high)
            if candidate > entry:
                candidate_risk = candidate - entry
                pct = candidate_risk / entry
                if pct <= snap_max_pct or candidate_risk <= baseline_risk * snap_max_risk_mult:
                    sl = candidate
                    method = "atr_plus_fvg_snap"

    risk = abs(entry - sl)
    tp = entry + tp_r_mult * risk if decision == "LONG" else entry - tp_r_mult * risk

    return TpSlSuggestion(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        risk_r=tp_r_mult,
        atr_used=atr,
        atr_timeframe=atr_timeframe,
        method=method,
    )

