from __future__ import annotations

from project.screener.indicators_bundle import compute_indicator_bundle_row


def test_compute_indicator_bundle_row_basic() -> None:
    n = 250
    close = [100.0 + (i % 7) * 0.1 for i in range(n)]
    high = [c + 0.2 for c in close]
    low = [c - 0.2 for c in close]
    vol = [1e5 + i * 10 for i in range(n)]
    row = compute_indicator_bundle_row(high=high, low=low, close=close, volume=vol)
    assert "rsi_14" in row
    assert row["rsi_14"] is not None
    assert row.get("ema_20") is not None


def test_compute_indicator_bundle_short_history() -> None:
    row = compute_indicator_bundle_row(
        high=[1.0] * 10,
        low=[0.9] * 10,
        close=[1.0] * 10,
        volume=[1.0] * 10,
    )
    assert row == {}
