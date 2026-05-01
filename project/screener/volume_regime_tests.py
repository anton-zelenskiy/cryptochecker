from __future__ import annotations

import datetime as dt

from project.screener.volume_regime import CandleOHLCV, compute_volume_regime


def _day(t: int, vol: float) -> CandleOHLCV:
    return CandleOHLCV(
        open_time_utc=dt.datetime(2026, 1, t, tzinfo=dt.timezone.utc),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.0,
        volume_quote=vol,
        volume_base=None,
    )


def test_compute_volume_regime_spike() -> None:
    days = [_day(i, 1e6) for i in range(1, 20)]
    days.append(_day(20, 5e6))
    feat = compute_volume_regime(days, lookback_days=14)
    assert feat.volume_ratio_vs_avg is not None
    assert feat.volume_ratio_vs_avg >= 2.0
    assert feat.is_sharp_spike is True


def test_compute_volume_regime_empty() -> None:
    feat = compute_volume_regime([], lookback_days=14)
    assert feat.note == "no_candles"
