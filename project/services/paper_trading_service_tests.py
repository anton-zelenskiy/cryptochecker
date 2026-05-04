from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from project.core import config
from project.services import paper_trading_service as pts


class FakeUserTrackedAssetRepository:
    def __init__(self, markets: list[tuple[str, str]]) -> None:
        self._markets = markets

    async def list_distinct_enabled_markets(self) -> list[tuple[str, str]]:
        return self._markets


class FakeScreenerSnapshotRepository:
    def __init__(self, snap: object | None) -> None:
        self._snap = snap

    async def get_latest_for_market(self, *, base_asset: str, quote_asset: str) -> object | None:
        return self._snap


class FakePaperTradeRepository:
    def __init__(self, initial_open: object | None = None) -> None:
        self.active_position = initial_open
        self.closed: list[dict] = []
        self.open_calls: list[dict] = []

    async def get_latest_open_trade_for_market(
        self,
        *,
        base_asset: str,
        quote_asset: str,
    ) -> object | None:
        return self.active_position

    async def close_trade(
        self,
        trade_id: int,
        *,
        exit_time_utc: dt.datetime,
        exit_price: float,
        pnl_pct: float,
        exit_reason: str | None = None,
    ) -> None:
        self.closed.append(
            {
                "id": trade_id,
                "exit_time_utc": exit_time_utc,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
            }
        )
        if self.active_position is not None and int(getattr(self.active_position, "id")) == trade_id:
            self.active_position = None

    async def open_trade(self, **kwargs: object) -> SimpleNamespace:
        oid = len(self.open_calls) + 1
        self.open_calls.append(dict(kwargs))
        o = SimpleNamespace(id=oid, **kwargs)
        self.active_position = o
        return o


class FakeCandleRepository:
    def __init__(self, candles: list[object]) -> None:
        self._candles = candles

    async def list_from_open_time_asc(self, **kwargs: object) -> list[object]:
        return list(self._candles)


def _minimal_features_dict(
    *,
    base: str = "BTC",
    quote: str = "USDT",
    price: float = 100.0,
    atr_14: float = 5.0,
) -> dict:
    return {
        "source": "kucoin",
        "base_asset": base,
        "quote_asset": quote,
        "asof_time_utc": "2026-05-02T12:00:00+00:00",
        "current_price": price,
        "current_price_time_utc": "2026-05-02T12:00:00+00:00",
        "current_price_timeframe": "5m",
        "per_tf_indicators": {
            "1h": {
                "timeframe": "1h",
                "rsi_14": 50.0,
                "atr_14": atr_14,
            }
        },
        "per_tf_trend": {},
    }


def _snap(
    *,
    features: dict,
    final_decision: str = "LONG",
    final_confidence: float = 0.9,
    computed_at: dt.datetime | None = None,
    sid: int = 1,
) -> SimpleNamespace:
    now = dt.datetime.now(dt.timezone.utc)
    return SimpleNamespace(
        id=sid,
        source="kucoin",
        features=features,
        final_decision=final_decision,
        final_confidence=final_confidence,
        computed_at=computed_at or now,
        asof_time_utc=dt.datetime(2026, 5, 2, 12, 0, tzinfo=dt.timezone.utc),
    )


@pytest.fixture
def patch_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pts,
        "UserTrackedAssetRepository",
        lambda: FakeUserTrackedAssetRepository([("BTC", "USDT")]),
    )


@pytest.mark.asyncio
async def test_tick_skips_when_disabled(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", False)
    paper = FakePaperTradeRepository()
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(_snap(features=_minimal_features_dict())),
        paper_repo=paper,
        candles_repo=FakeCandleRepository([]),
    )
    await svc.paper_trading_tick()
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_skips_stale_snapshot(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_MAX_SNAPSHOT_AGE_MINUTES", 5)
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    paper = FakePaperTradeRepository()
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(
            _snap(features=_minimal_features_dict(), computed_at=old)
        ),
        paper_repo=paper,
        candles_repo=FakeCandleRepository([]),
    )
    await svc.paper_trading_tick()
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_skips_wait_decision(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    paper = FakePaperTradeRepository()
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(
            _snap(features=_minimal_features_dict(), final_decision="WAIT")
        ),
        paper_repo=paper,
        candles_repo=FakeCandleRepository([]),
    )
    await svc.paper_trading_tick()
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_skips_low_confidence(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_MIN_CONFIDENCE", 0.65)
    paper = FakePaperTradeRepository()
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(
            _snap(features=_minimal_features_dict(), final_decision="LONG", final_confidence=0.2)
        ),
        paper_repo=paper,
        candles_repo=FakeCandleRepository([]),
    )
    await svc.paper_trading_tick()
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_opens_long_with_sl_tp(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_MIN_CONFIDENCE", 0.5)
    paper = FakePaperTradeRepository()
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(_snap(features=_minimal_features_dict())),
        paper_repo=paper,
        candles_repo=FakeCandleRepository([]),
    )
    await svc.paper_trading_tick()
    assert len(paper.open_calls) == 1
    oc = paper.open_calls[0]
    assert oc["side"] == "LONG"
    assert oc["stop_loss"] is not None
    assert oc["take_profit"] is not None
    assert oc["screener_snapshot_id"] == 1


@pytest.mark.asyncio
async def test_tick_closes_on_tp(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    entry_t = dt.datetime(2026, 5, 2, 10, 0, tzinfo=dt.timezone.utc)
    hit_t = dt.datetime(2026, 5, 2, 10, 5, tzinfo=dt.timezone.utc)
    open_trade = SimpleNamespace(
        id=99,
        source="kucoin",
        base_asset="BTC",
        quote_asset="USDT",
        side="LONG",
        entry_price=100.0,
        entry_time_utc=entry_t,
        stop_loss=90.0,
        take_profit=110.0,
    )
    paper = FakePaperTradeRepository(initial_open=open_trade)
    candles = [SimpleNamespace(open_time_utc=hit_t, low=95.0, high=115.0)]
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(_snap(features=_minimal_features_dict())),
        paper_repo=paper,
        candles_repo=FakeCandleRepository(candles),
    )
    await svc.paper_trading_tick()
    assert len(paper.closed) == 1
    assert paper.closed[0]["exit_reason"] == "tp_hit"
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_flip_closes_long(monkeypatch: pytest.MonkeyPatch, patch_users: None) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_FLIP_MIN_CONFIDENCE", 0.65)
    entry_t = dt.datetime(2026, 5, 2, 10, 0, tzinfo=dt.timezone.utc)
    open_trade = SimpleNamespace(
        id=7,
        source="kucoin",
        base_asset="BTC",
        quote_asset="USDT",
        side="LONG",
        entry_price=100.0,
        entry_time_utc=entry_t,
        stop_loss=90.0,
        take_profit=200.0,
    )
    paper = FakePaperTradeRepository(initial_open=open_trade)
    candles = [SimpleNamespace(open_time_utc=hit_t, low=95.0, high=105.0) for hit_t in [entry_t]]
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(
            _snap(
                features=_minimal_features_dict(price=102.0),
                final_decision="SHORT",
                final_confidence=0.8,
            )
        ),
        paper_repo=paper,
        candles_repo=FakeCandleRepository(candles),
    )
    await svc.paper_trading_tick()
    assert len(paper.closed) == 1
    assert paper.closed[0]["exit_reason"] == "flip"
    assert paper.open_calls == []


@pytest.mark.asyncio
async def test_tick_does_not_open_new_trade_same_tick_after_close(
    monkeypatch: pytest.MonkeyPatch,
    patch_users: None,
) -> None:
    monkeypatch.setattr(config.settings, "PAPER_TRADING_ENABLED", True)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_MIN_CONFIDENCE", 0.5)
    monkeypatch.setattr(config.settings, "PAPER_TRADING_FLIP_MIN_CONFIDENCE", 0.65)
    entry_t = dt.datetime(2026, 5, 2, 10, 0, tzinfo=dt.timezone.utc)
    open_trade = SimpleNamespace(
        id=7,
        source="kucoin",
        base_asset="BTC",
        quote_asset="USDT",
        side="LONG",
        entry_price=100.0,
        entry_time_utc=entry_t,
        stop_loss=90.0,
        take_profit=200.0,
    )
    paper = FakePaperTradeRepository(initial_open=open_trade)
    candles = [SimpleNamespace(open_time_utc=entry_t, low=95.0, high=105.0)]
    svc = pts.PaperTradingService(
        snapshot_repo=FakeScreenerSnapshotRepository(
            _snap(
                features=_minimal_features_dict(price=102.0),
                final_decision="SHORT",
                final_confidence=0.8,
            )
        ),
        paper_repo=paper,
        candles_repo=FakeCandleRepository(candles),
    )
    await svc.paper_trading_tick()
    assert paper.open_calls == []
