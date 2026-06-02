from __future__ import annotations

from project.screener.contracts import (
    FundamentalsFeature,
    LiquidityLevelsFeature,
    LiquidityStructureComputed,
    MicrostructureFeature,
    PerTimeframeIndicators,
    TrendSwingFeature,
    VolumeRegimeFeature,
)
from project.screener.scoring import apply_llm_adjustment, score_screener


def test_score_screener_long_bias() -> None:
    higher = {
        "4h": TrendSwingFeature(timeframe="4h", bias="bull"),
        "1d": TrendSwingFeature(timeframe="1d", bias="bull"),
    }
    lower = {
        "15m": TrendSwingFeature(timeframe="15m", bias="bull"),
        "1h": TrendSwingFeature(timeframe="1h", bias="bull"),
    }
    ind = {
        "1h": PerTimeframeIndicators(timeframe="1h", rsi_14=28.0, macd_hist=0.1, adx_14=30.0),
    }
    vol = VolumeRegimeFeature(is_sharp_spike=True, volume_ratio_vs_avg=3.0)
    out = score_screener(
        higher_tf_trends=higher,
        lower_tf_trends=lower,
        indicators_by_tf=ind,
        volume=vol,
        fundamentals=None,
        microstructure=None,
        fvg_aligns_long=True,
        fvg_aligns_short=False,
    )
    assert out.decision == "LONG"
    assert out.confidence > 0.4


def test_score_screener_overpriced_gate() -> None:
    higher = {"4h": TrendSwingFeature(timeframe="4h", bias="bull")}
    lower = {"1h": TrendSwingFeature(timeframe="1h", bias="bull")}
    ind = {"1h": PerTimeframeIndicators(timeframe="1h", rsi_14=40.0)}
    fund = FundamentalsFeature(flag_overpriced=True, tvl_unavailable=False)
    out = score_screener(
        higher_tf_trends=higher,
        lower_tf_trends=lower,
        indicators_by_tf=ind,
        volume=None,
        fundamentals=fund,
        microstructure=MicrostructureFeature(),
        fvg_aligns_long=False,
        fvg_aligns_short=False,
    )
    assert out.decision in ("WAIT", "LONG", "SHORT")


def test_apply_llm_downgrade() -> None:
    d, c = apply_llm_adjustment("LONG", 0.8, "downgrade_to_wait", -0.1)
    assert d == "WAIT"


def test_apply_llm_flip() -> None:
    d, c = apply_llm_adjustment("LONG", 0.7, "flip", 0.0)
    assert d == "SHORT"


def test_apply_llm_flip_wait() -> None:
    d, c = apply_llm_adjustment("WAIT", 0.5, "flip", 0.0)
    assert d == "WAIT"
    assert c <= 0.35


def test_score_screener_liquidity_sweep_setup_down() -> None:
    higher = {"4h": TrendSwingFeature(timeframe="4h", bias="bear")}
    lower = {"1h": TrendSwingFeature(timeframe="1h", bias="neutral")}
    ind = {"1h": PerTimeframeIndicators(timeframe="1h", rsi_14=55.0)}
    liquidity = LiquidityLevelsFeature(
        structure=LiquidityStructureComputed(
            pattern="sweep_setup_down",
            liquidity_line_low=0.97,
        ),
    )
    out = score_screener(
        higher_tf_trends=higher,
        lower_tf_trends=lower,
        indicators_by_tf=ind,
        volume=None,
        fundamentals=None,
        microstructure=None,
        fvg_aligns_long=False,
        fvg_aligns_short=False,
        liquidity=liquidity,
        current_price=1.0,
    )
    assert "liquidity_sweep_setup_down" in out.reasons
    assert out.short_score > 0


def test_score_screener_liquidity_sweep_setup_up() -> None:
    higher = {"4h": TrendSwingFeature(timeframe="4h", bias="bull")}
    lower = {"1h": TrendSwingFeature(timeframe="1h", bias="neutral")}
    ind = {"1h": PerTimeframeIndicators(timeframe="1h", rsi_14=45.0)}
    liquidity = LiquidityLevelsFeature(
        structure=LiquidityStructureComputed(
            pattern="sweep_setup_up",
            liquidity_line_high=1.03,
        ),
    )
    out = score_screener(
        higher_tf_trends=higher,
        lower_tf_trends=lower,
        indicators_by_tf=ind,
        volume=None,
        fundamentals=None,
        microstructure=None,
        fvg_aligns_long=False,
        fvg_aligns_short=False,
        liquidity=liquidity,
        current_price=1.0,
    )
    assert "liquidity_sweep_setup_up" in out.reasons
    assert out.long_score > 0
