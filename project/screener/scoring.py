from __future__ import annotations

from project.core.config import settings
from project.screener.contracts import (
    FundamentalsFeature,
    LiquidityLevelsFeature,
    MicrostructureFeature,
    PerTimeframeIndicators,
    ScreenerDecisionPayload,
    TrendBias,
    TrendSwingFeature,
    VolumeRegimeFeature,
)
from project.screener.indicator_format import format_indicator_value
from project.screener.trend_structure import aggregate_bias


def _bias_score(b: TrendBias) -> float:
    return {"bull": 1.0, "bear": -1.0, "neutral": 0.0}[b]


def _near_liquidity_line(*, price: float, line: float) -> bool:
    if price <= 0 or line <= 0:
        return False
    gap_pct = abs(price - line) / price
    return gap_pct <= float(settings.LIQUIDITY_SWEEP_NEAR_PCT) + 1e-9


def score_screener(
    *,
    higher_tf_trends: dict[str, TrendSwingFeature],
    lower_tf_trends: dict[str, TrendSwingFeature],
    indicators_by_tf: dict[str, PerTimeframeIndicators],
    volume: VolumeRegimeFeature | None,
    fundamentals: FundamentalsFeature | None,
    microstructure: MicrostructureFeature | None,
    fvg_aligns_long: bool | None,
    fvg_aligns_short: bool | None,
    liquidity: LiquidityLevelsFeature | None = None,
    current_price: float | None = None,
) -> ScreenerDecisionPayload:
    reasons: list[str] = []

    higher_bias = aggregate_bias([t.bias for t in higher_tf_trends.values()])
    lower_bias = aggregate_bias([t.bias for t in lower_tf_trends.values()])
    reasons.append(f"higher_tf_bias={higher_bias}")
    reasons.append(f"lower_tf_bias={lower_bias}")

    long_score = 0.0
    short_score = 0.0
    risk_score = 0.0

    long_score += 1.8 * max(0.0, _bias_score(higher_bias))
    short_score += 1.8 * max(0.0, -_bias_score(higher_bias))
    long_score += 1.2 * max(0.0, _bias_score(lower_bias))
    short_score += 1.2 * max(0.0, -_bias_score(lower_bias))

    ref_tf = "1h" if "1h" in indicators_by_tf else next(iter(indicators_by_tf), None)
    ind = indicators_by_tf.get(ref_tf) if ref_tf else None
    if ind:
        if ind.rsi_14 is not None:
            if ind.rsi_14 <= 32:
                long_score += 0.8
                reasons.append(f"rsi_oversold_{ref_tf}={format_indicator_value(ind.rsi_14)}")
            elif ind.rsi_14 >= 68:
                short_score += 0.8
                reasons.append(f"rsi_overbought_{ref_tf}={format_indicator_value(ind.rsi_14)}")
        if ind.macd_hist is not None:
            if ind.macd_hist > 0:
                long_score += 0.35
            elif ind.macd_hist < 0:
                short_score += 0.35
        if ind.adx_14 is not None and ind.adx_14 > 22:
            reasons.append(f"adx_trending={format_indicator_value(ind.adx_14)}")
            long_score *= 1.05 if higher_bias == "bull" else 1.0
            short_score *= 1.05 if higher_bias == "bear" else 1.0

    if volume and volume.is_sharp_spike:
        long_score += 0.5
        short_score += 0.5
        reasons.append("volume_spike")

    if fvg_aligns_long:
        long_score += 0.45
        reasons.append("fvg_bull_near")
    if fvg_aligns_short:
        short_score += 0.45
        reasons.append("fvg_bear_near")

    if microstructure:
        if microstructure.large_buy_cluster_recent:
            long_score += 0.35
            reasons.append("large_buy_cluster")
        if microstructure.support_wall_recent:
            long_score += 0.25
            reasons.append("support_wall")

    if fundamentals:
        if fundamentals.flag_overpriced:
            risk_score += 1.5
            long_score *= 0.55
            reasons.append("fundamentals_overpriced")
        if fundamentals.flag_undervalued_tvl:
            long_score += 0.4
            reasons.append("fundamentals_tvl_value")

    if liquidity and liquidity.structure:
        struct = liquidity.structure
        price = current_price
        deriv = liquidity.derivatives

        if struct.pattern == "sweep_setup_down" and price and struct.liquidity_line_low:
            if _near_liquidity_line(price=price, line=struct.liquidity_line_low):
                short_score += 0.4
                risk_score += 0.35
                reasons.append("liquidity_sweep_setup_down")
                if higher_bias == "bear":
                    short_score += 0.25
                if deriv and deriv.funding_crowded_long and deriv.oi_rising:
                    risk_score += 0.4
                    long_score *= 0.85
                    reasons.append("funding_crowded_long")

        if struct.pattern == "sweep_setup_up" and price and struct.liquidity_line_high:
            if _near_liquidity_line(price=price, line=struct.liquidity_line_high):
                long_score += 0.4
                risk_score += 0.35
                reasons.append("liquidity_sweep_setup_up")
                if higher_bias == "bull":
                    long_score += 0.25
                if deriv and deriv.funding_crowded_short and deriv.oi_rising:
                    risk_score += 0.4
                    short_score *= 0.85
                    reasons.append("funding_crowded_short")

    margin = long_score - short_score
    if risk_score >= 1.2 and margin < 1.0:
        return ScreenerDecisionPayload(
            decision="WAIT",
            confidence=min(0.85, 0.35 + risk_score * 0.1),
            long_score=long_score,
            short_score=short_score,
            risk_score=risk_score,
            reasons=reasons + ["risk_gate_wait"],
        )

    if margin > 1.15:
        conf = min(0.92, 0.45 + min(0.45, margin / 8.0))
        return ScreenerDecisionPayload(
            decision="LONG",
            confidence=conf,
            long_score=long_score,
            short_score=short_score,
            risk_score=risk_score,
            reasons=reasons,
        )
    if margin < -1.15:
        conf = min(0.92, 0.45 + min(0.45, (-margin) / 8.0))
        return ScreenerDecisionPayload(
            decision="SHORT",
            confidence=conf,
            long_score=long_score,
            short_score=short_score,
            risk_score=risk_score,
            reasons=reasons,
        )

    return ScreenerDecisionPayload(
        decision="WAIT",
        confidence=0.25,
        long_score=long_score,
        short_score=short_score,
        risk_score=risk_score,
        reasons=reasons + ["scores_balanced"],
    )


def apply_llm_adjustment(
    decision: str,
    confidence: float,
    verdict: str,
    adjust: float,
) -> tuple[str, float]:
    d = decision
    c = max(0.0, min(1.0, confidence + adjust))
    if verdict == "downgrade_to_wait":
        return "WAIT", min(c, 0.4)
    if verdict == "flip":
        if d == "LONG":
            return "SHORT", c
        if d == "SHORT":
            return "LONG", c
        return "WAIT", min(c, 0.35)
    return d, c
