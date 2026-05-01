from __future__ import annotations

import datetime as dt

from project.screener.fvg_detect import detect_fvgs, distance_pct_to_zone_mid


def test_detect_bullish_fvg() -> None:
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    times = [t0 + dt.timedelta(hours=i) for i in range(3)]
    highs = [10.0, 10.5, 12.0]
    lows = [9.0, 9.2, 11.0]
    closes = [9.5, 10.0, 11.5]
    fvgs = detect_fvgs(times, highs, lows, closes)
    assert any(f.direction == "bull" for f in fvgs)


def test_distance_pct() -> None:
    d = distance_pct_to_zone_mid(100.0, 99.0, 101.0)
    assert abs(d - 0.0) < 1e-6
