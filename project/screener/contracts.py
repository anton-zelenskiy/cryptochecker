from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FEATURE_VERSION = "1"

TrendBias = Literal["bull", "bear", "neutral"]


class PerTimeframeIndicators(BaseModel):
    timeframe: str
    rsi_14: float | None = None
    ema_20: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr_14: float | None = None
    adx_14: float | None = None
    bb_upper: float | None = None
    bb_mid: float | None = None
    bb_lower: float | None = None
    mfi_14: float | None = None
    obv: float | None = None
    stochrsi_k: float | None = None
    stochrsi_d: float | None = None


class VolumeRegimeFeature(BaseModel):
    avg_daily_volume_quote: float | None = None
    latest_daily_volume_quote: float | None = None
    volume_ratio_vs_avg: float | None = None
    volume_zscore: float | None = None
    is_sharp_spike: bool = False
    lookback_days: int = 14
    note: str | None = None


class TrendSwingFeature(BaseModel):
    timeframe: str
    bias: TrendBias = "neutral"
    higher_lows: bool | None = None
    lower_highs: bool | None = None
    ema20_above_ema50: bool | None = None
    close_above_ema200: bool | None = None
    log_close_slope_20: float | None = None


class FvgNearbyFeature(BaseModel):
    timeframe: str
    direction: Literal["bull", "bear"] | None = None
    zone_low: float | None = None
    zone_high: float | None = None
    distance_pct_to_mid: float | None = None
    is_unfilled: bool = False


class FundamentalsFeature(BaseModel):
    coingecko_id: str | None = None
    market_cap_usd: float | None = None
    fdv_usd: float | None = None
    total_volume_24h_usd: float | None = None
    tvl_usd: float | None = None
    mcap_to_tvl: float | None = None
    fdv_to_tvl: float | None = None
    flag_overpriced: bool = False
    flag_undervalued_tvl: bool = False
    tvl_unavailable: bool = True


class MicrostructureFeature(BaseModel):
    large_buy_cluster_recent: bool = False
    support_wall_recent: bool = False


class ScreenerFeaturesV1(BaseModel):
    version: str = Field(default=FEATURE_VERSION)
    source: str
    base_asset: str
    quote_asset: str
    asof_time_utc: str
    current_price: float | None = None
    current_price_time_utc: str | None = None
    current_price_timeframe: str | None = None
    per_tf_indicators: dict[str, PerTimeframeIndicators] = Field(default_factory=dict)
    per_tf_trend: dict[str, TrendSwingFeature] = Field(default_factory=dict)
    volume: VolumeRegimeFeature | None = None
    higher_tf_bias: TrendBias = "neutral"
    lower_tf_bias: TrendBias = "neutral"
    fvg: FvgNearbyFeature | None = None
    fundamentals: FundamentalsFeature | None = None
    microstructure: MicrostructureFeature | None = None


DecisionSide = Literal["LONG", "SHORT", "WAIT"]


class ScreenerDecisionPayload(BaseModel):
    decision: DecisionSide = "WAIT"
    confidence: float = 0.0
    long_score: float = 0.0
    short_score: float = 0.0
    risk_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class ScreenerLlmRecheckResult(BaseModel):
    verdict: Literal["accept", "downgrade_to_wait", "flip"] = "accept"
    confidence_adjust: float = Field(default=0.0, ge=-0.35, le=0.35)
    rationale: str = ""
    telegram_summary_ru: str = ""


class ScreenerFinalPayload(BaseModel):
    deterministic: ScreenerDecisionPayload
    llm: ScreenerLlmRecheckResult | None = None
    final_decision: DecisionSide = "WAIT"
    final_confidence: float = 0.0
