from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from project.core.config import settings
from project.screener.contracts import DecisionSide, FvgNearbyFeature, ScreenerFeaturesV1


SL_ATR_MULT_DEFAULT = 1.5
TP_R_MULT_DEFAULT = 3.0
SNAP_MAX_PCT_DEFAULT = 0.04
SNAP_MAX_RISK_MULT_DEFAULT = 2.0


class TpSlSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

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


def sl_atr_mult_for_horizon(signal_horizon: str | None) -> float:
    if signal_horizon == "swing":
        return float(settings.SCREENER_TPSL_SL_ATR_MULT_SWING)
    return float(settings.SCREENER_TPSL_SL_ATR_MULT)


def tpsl_kwargs_from_settings(*, signal_horizon: str | None = None) -> dict[str, float | bool]:
    return {
        "sl_atr_mult": sl_atr_mult_for_horizon(signal_horizon),
        "fvg_snap_enabled": bool(settings.SCREENER_TPSL_FVG_SNAP_ENABLED),
        "fvg_snap_min_risk_atr_mult": float(settings.SCREENER_TPSL_FVG_SNAP_MIN_RISK_ATR_MULT),
        "min_stop_atr_mult": float(settings.SCREENER_TPSL_MIN_STOP_ATR_MULT),
        "min_stop_pct": float(settings.SCREENER_TPSL_MIN_STOP_PCT),
        "roundtrip_fee_frac": float(settings.SCREENER_TPSL_ROUNDTRIP_FEE_FRAC),
        "roundtrip_slip_frac": float(settings.SCREENER_TPSL_ROUNDTRIP_SLIP_FRAC),
    }


def _baseline_levels(*, decision: DecisionSide, entry: float, atr: float, sl_atr_mult: float) -> tuple[float, float]:
    risk = max(1e-12, sl_atr_mult * atr)
    if decision == "LONG":
        return entry - risk, risk
    if decision == "SHORT":
        return entry + risk, risk
    raise ValueError("baseline levels require LONG/SHORT")


def _enforce_min_risk_and_friction(
    *,
    decision: DecisionSide,
    entry: float,
    sl: float,
    tp_r_mult: float,
    min_stop_atr_mult: float,
    min_stop_pct: float,
    roundtrip_fee_frac: float,
    roundtrip_slip_frac: float,
    atr: float,
) -> tuple[float, float, str]:
    risk_raw = abs(entry - sl)
    min_floor = 0.0
    if min_stop_atr_mult > 0 and atr > 0:
        min_floor = max(min_floor, min_stop_atr_mult * atr)
    if min_stop_pct > 0 and entry > 0:
        min_floor = max(min_floor, min_stop_pct * entry)
    friction = 0.0
    if entry > 0:
        friction = entry * max(0.0, roundtrip_fee_frac + roundtrip_slip_frac)
    risk_adj = max(risk_raw, min_floor) + friction
    if decision == "LONG":
        sl_adj = entry - risk_adj
        tp_adj = entry + tp_r_mult * risk_adj
    else:
        sl_adj = entry + risk_adj
        tp_adj = entry - tp_r_mult * risk_adj
    tol = max(1e-12, 1e-9 * entry, 1e-9 * max(risk_raw, risk_adj, 1.0))
    suffix = "_adj" if risk_adj > risk_raw + tol else ""
    return sl_adj, tp_adj, suffix


def suggest_trade_levels(
    *,
    decision: DecisionSide,
    entry: float,
    atr: float,
    atr_timeframe: str,
    fvg: FvgNearbyFeature | None,
    sl_atr_mult: float = SL_ATR_MULT_DEFAULT,
    tp_r_mult: float = TP_R_MULT_DEFAULT,
    fvg_snap_enabled: bool = True,
    fvg_snap_min_risk_atr_mult: float = 0.0,
    snap_max_pct: float = SNAP_MAX_PCT_DEFAULT,
    snap_max_risk_mult: float = SNAP_MAX_RISK_MULT_DEFAULT,
    min_stop_atr_mult: float = 0.0,
    min_stop_pct: float = 0.0,
    roundtrip_fee_frac: float = 0.0,
    roundtrip_slip_frac: float = 0.0,
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

    if fvg_snap_enabled and fvg and fvg.direction and fvg.zone_low is not None and fvg.zone_high is not None:
        if decision == "LONG" and fvg.direction == "bull":
            candidate = float(fvg.zone_low)
            if 0 < candidate < entry:
                candidate_risk = entry - candidate
                pct = candidate_risk / entry
                if pct <= snap_max_pct or candidate_risk <= baseline_risk * snap_max_risk_mult:
                    if fvg_snap_min_risk_atr_mult <= 0 or candidate_risk >= fvg_snap_min_risk_atr_mult * atr:
                        sl = candidate
                        method = "atr_plus_fvg_snap"
        elif decision == "SHORT" and fvg.direction == "bear":
            candidate = float(fvg.zone_high)
            if candidate > entry:
                candidate_risk = candidate - entry
                pct = candidate_risk / entry
                if pct <= snap_max_pct or candidate_risk <= baseline_risk * snap_max_risk_mult:
                    if fvg_snap_min_risk_atr_mult <= 0 or candidate_risk >= fvg_snap_min_risk_atr_mult * atr:
                        sl = candidate
                        method = "atr_plus_fvg_snap"

    sl, tp, suffix = _enforce_min_risk_and_friction(
        decision=decision,
        entry=entry,
        sl=sl,
        tp_r_mult=tp_r_mult,
        min_stop_atr_mult=min_stop_atr_mult,
        min_stop_pct=min_stop_pct,
        roundtrip_fee_frac=roundtrip_fee_frac,
        roundtrip_slip_frac=roundtrip_slip_frac,
        atr=atr,
    )
    if suffix:
        method = f"{method}{suffix}"

    return TpSlSuggestion(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        risk_r=tp_r_mult,
        atr_used=atr,
        atr_timeframe=atr_timeframe,
        method=method,
    )

