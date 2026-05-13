from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class FvgDetected(BaseModel):
    model_config = ConfigDict(frozen=True)

    direction: str
    zone_low: float
    zone_high: float
    middle_open_time_utc: dt.datetime


def detect_fvgs(
    opens: list[dt.datetime],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> list[FvgDetected]:
    out: list[FvgDetected] = []
    n = len(highs)
    if n < 3:
        return out
    for i in range(1, n - 1):
        h_prev, l_prev = highs[i - 1], lows[i - 1]
        h_next, l_next = highs[i + 1], lows[i + 1]
        mid_t = opens[i]

        if h_prev < l_next:
            z_low, z_high = float(h_prev), float(l_next)
            if z_low < z_high:
                out.append(FvgDetected(direction="bull", zone_low=z_low, zone_high=z_high, middle_open_time_utc=mid_t))

        if l_prev > h_next:
            z_low, z_high = float(h_next), float(l_prev)
            if z_low < z_high:
                out.append(FvgDetected(direction="bear", zone_low=z_low, zone_high=z_high, middle_open_time_utc=mid_t))

    return out


def nearest_unfilled_fvg(
    fvgs: list[FvgDetected],
    last_close: float,
    *,
    mitigated_before: set[tuple[str, float, float, dt.datetime]] | None = None,
) -> FvgDetected | None:
    mitigated_before = mitigated_before or set()
    candidates: list[FvgDetected] = []
    for f in fvgs:
        key = (f.direction, f.zone_low, f.zone_high, f.middle_open_time_utc)
        if key in mitigated_before:
            continue
        if f.direction == "bull":
            filled = last_close <= f.zone_low
        else:
            filled = last_close >= f.zone_high
        if not filled:
            candidates.append(f)
    if not candidates:
        return None
    return candidates[-1]


def distance_pct_to_zone_mid(last_close: float, zone_low: float, zone_high: float) -> float:
    mid = (zone_low + zone_high) / 2.0
    if last_close <= 0:
        return 0.0
    return abs(last_close - mid) / last_close * 100.0
