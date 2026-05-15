from __future__ import annotations

import pytest

from project.screener.contracts import ScreenerFeaturesV1, TrendBias
from project.screener.signal_horizon import infer_signal_horizon


def _fx(
    *,
    higher: TrendBias = "neutral",
    lower: TrendBias = "neutral",
) -> ScreenerFeaturesV1:
    return ScreenerFeaturesV1(
        source="kucoin",
        base_asset="BTC",
        quote_asset="USDT",
        asof_time_utc="2026-05-02T12:00:00+00:00",
        higher_tf_bias=higher,
        lower_tf_bias=lower,
    )


@pytest.mark.parametrize(
    ("decision", "h", "l", "want"),
    [
        ("LONG", "bull", "bull", "swing"),
        ("LONG", "bull", "neutral", "swing"),
        ("LONG", "neutral", "bull", "intraday"),
        ("LONG", "bear", "bull", "scalp"),
        ("LONG", "neutral", "neutral", "intraday"),
        ("SHORT", "bear", "bear", "swing"),
        ("SHORT", "neutral", "bear", "intraday"),
        ("SHORT", "bull", "bear", "scalp"),
    ],
)
def test_infer_signal_horizon(decision: str, h: TrendBias, l: TrendBias, want: str) -> None:
    assert infer_signal_horizon(decision=decision, features=_fx(higher=h, lower=l)) == want


def test_wait_maps_to_intraday() -> None:
    assert infer_signal_horizon(decision="WAIT", features=_fx(higher="bull", lower="bull")) == "intraday"
