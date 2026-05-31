from __future__ import annotations

import datetime as dt

import structlog
from aiogram import Bot
from pydantic import BaseModel, ConfigDict

from project.marketdata.timeframes import TREND_PULLBACK_CONFIGS, TrendPullbackConfig, normalize_timeframe
from project.models.candles import Candle
from project.repositories.candles import CandleRepository
from project.models.indicators import IndicatorSnapshot
from project.repositories.indicators import IndicatorSnapshotRepository
from project.repositories.screener_snapshots import ScreenerSnapshotRepository
from project.repositories.users import UserSettingsRepository, UserTrackedAssetRepository
from project.repositories.volatility_events import VolatilityEventRepository
from project.screener.indicator_format import format_screener_context_suffix
from project.services.screener_service import fallback_decision_from_indicator_snapshot
from project.web.bot import get_bot


logger = structlog.get_logger(__name__)


class BigMoveMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    pct_change: float
    range_pct: float


class VolumeSpikeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    latest_volume_quote: float
    baseline_median_quote: float
    volume_ratio: float
    pct_above_median: float


VOLUME_SPIKE_LOOKBACK_DAYS = 7
VOLUME_SPIKE_BASELINE_TIMEFRAME = "1h"
VOLUME_SPIKE_MIN_QUOTE_USD = 100_000.0
VOLUME_SPIKE_MIN_BASELINE_SAMPLES = 10


def volume_spike_baseline_candle_count(
    *,
    timeframe_seconds: int,
    lookback_days: int = VOLUME_SPIKE_LOOKBACK_DAYS,
) -> int:
    return lookback_days * 86_400 // timeframe_seconds


def floor_time(ts: dt.datetime, *, seconds: int) -> dt.datetime:
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % seconds)
    return dt.datetime.fromtimestamp(floored, tz=dt.timezone.utc)


def compute_big_move_metrics(
    *, prev_close: float, latest_close: float, latest_high: float, latest_low: float
) -> BigMoveMetrics:
    if prev_close <= 0:
        raise ValueError("prev_close must be > 0")
    pct_change = (latest_close - prev_close) / prev_close * 100.0
    range_pct = (latest_high - latest_low) / prev_close * 100.0
    return BigMoveMetrics(pct_change=float(pct_change), range_pct=float(range_pct))


def passes_big_move_gate(
    metrics: BigMoveMetrics,
    *,
    threshold_pct: float,
    range_multiplier: float = 1.25,
) -> bool:
    return abs(metrics.pct_change) >= threshold_pct or metrics.range_pct >= (threshold_pct * range_multiplier)


def candle_volume_quote(c: Candle) -> float | None:
    if c.volume_quote is not None and c.volume_quote > 0:
        return float(c.volume_quote)
    if c.volume_base is not None and c.volume_base > 0 and c.close > 0:
        return float(c.volume_base) * float(c.close)
    return None


def median_positive(values: list[float]) -> float | None:
    pos = sorted(v for v in values if v > 0)
    if not pos:
        return None
    mid = len(pos) // 2
    if len(pos) % 2:
        return pos[mid]
    return (pos[mid - 1] + pos[mid]) / 2.0


def compute_volume_spike_metrics(
    *,
    latest_candle: Candle,
    baseline_candles_chrono: list[Candle],
    baseline_periods_per_spike: float,
    min_baseline_samples: int = VOLUME_SPIKE_MIN_BASELINE_SAMPLES,
) -> VolumeSpikeMetrics | None:
    latest_vol = candle_volume_quote(latest_candle)
    if latest_vol is None:
        return None
    if baseline_periods_per_spike <= 0:
        return None

    baseline_vols = [v for c in baseline_candles_chrono if (v := candle_volume_quote(c)) is not None]
    if len(baseline_vols) < min_baseline_samples:
        return None

    median_baseline = median_positive(baseline_vols)
    if median_baseline is None or median_baseline <= 0:
        return None

    median_per_spike = median_baseline / baseline_periods_per_spike
    ratio = latest_vol / median_per_spike
    pct_above = (ratio - 1.0) * 100.0
    return VolumeSpikeMetrics(
        latest_volume_quote=float(latest_vol),
        baseline_median_quote=float(median_per_spike),
        volume_ratio=float(ratio),
        pct_above_median=float(pct_above),
    )


def passes_volume_spike_gate(
    metrics: VolumeSpikeMetrics,
    *,
    min_multiplier: float,
    min_quote_usd: float = VOLUME_SPIKE_MIN_QUOTE_USD,
) -> bool:
    if metrics.latest_volume_quote < min_quote_usd:
        return False
    return metrics.volume_ratio >= min_multiplier


def _candle_direction(c: Candle) -> int | None:
    if c.close > c.open:
        return 1
    if c.close < c.open:
        return -1
    return None


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def _majority_min_count(*, window: int, ratio: float) -> int:
    if ratio <= 0:
        return 0
    if ratio >= 1:
        return window
    # Avoid importing math; keep deterministic integer ceil.
    scaled = int(ratio * window * 1000)
    return _ceil_div(scaled, 1000)


def _window_net_pct(candles_chrono: list[Candle]) -> float:
    first_open = float(candles_chrono[0].open)
    last_close = float(candles_chrono[-1].close)
    if first_open <= 0:
        return 0.0
    return (last_close - first_open) / first_open * 100.0


def _qualifies_pullback_window(
    candles_chrono: list[Candle],
    *,
    cfg: TrendPullbackConfig,
    direction: int,
) -> tuple[bool, dict]:
    w = candles_chrono[-cfg.window_candles :]
    dirs = [_candle_direction(c) for c in w]
    green_count = sum(1 for d in dirs if d == 1)
    red_count = sum(1 for d in dirs if d == -1)
    doji_count = sum(1 for d in dirs if d is None)

    tail = dirs[-cfg.continuation_candles :]
    if len(tail) < cfg.continuation_candles or any(d is None for d in tail):
        return False, {}
    if not all(d == direction for d in tail):
        return False, {}

    window = int(cfg.window_candles)
    min_majority = _majority_min_count(window=window, ratio=float(cfg.majority_ratio))
    net_pct = _window_net_pct(w)

    if direction == 1:
        if green_count < max(int(cfg.min_impulse_green), min_majority):
            return False, {}
        if red_count > int(cfg.max_pullback_red):
            return False, {}
        if net_pct < float(cfg.min_net_pct_abs):
            return False, {}
    else:
        if red_count < max(int(cfg.min_impulse_red), min_majority):
            return False, {}
        if green_count > int(cfg.max_pullback_green):
            return False, {}
        if net_pct > -float(cfg.min_net_pct_abs):
            return False, {}

    payload = {
        "timeframe": cfg.timeframe,
        "window_candles": int(cfg.window_candles),
        "continuation_candles": int(cfg.continuation_candles),
        "majority_ratio": float(cfg.majority_ratio),
        "min_net_pct_abs": float(cfg.min_net_pct_abs),
        "green_count": int(green_count),
        "red_count": int(red_count),
        "doji_count": int(doji_count),
        "net_pct": float(net_pct),
    }
    return True, payload


def detect_trend_with_pullback(
    candles_chrono: list[Candle],
    *,
    cfg: TrendPullbackConfig,
) -> tuple[str, dict] | None:
    if len(candles_chrono) < int(cfg.window_candles):
        return None

    # Bullish
    ok, payload = _qualifies_pullback_window(candles_chrono, cfg=cfg, direction=1)
    if ok:
        # Transition-only: avoid alerting every candle while trend remains qualified.
        prev_ok, _prev_payload = (False, {})
        if len(candles_chrono) - 1 >= int(cfg.window_candles):
            prev_ok, _prev_payload = _qualifies_pullback_window(candles_chrono[:-1], cfg=cfg, direction=1)
        if not prev_ok:
            return "green", payload
        return None

    # Bearish
    ok, payload = _qualifies_pullback_window(candles_chrono, cfg=cfg, direction=-1)
    if ok:
        prev_ok, _prev_payload = (False, {})
        if len(candles_chrono) - 1 >= int(cfg.window_candles):
            prev_ok, _prev_payload = _qualifies_pullback_window(candles_chrono[:-1], cfg=cfg, direction=-1)
        if not prev_ok:
            return "red", payload
        return None

    return None


def detect_trend_streak_formation(candles_chrono: list[Candle], *, min_streak: int = 3) -> str | None:
    if len(candles_chrono) < min_streak:
        return None
    tail = candles_chrono[-min_streak:]
    dirs_ = [_candle_direction(c) for c in tail]
    if any(d is None for d in dirs_):
        return None
    head = dirs_[0]
    if not all(d == head for d in dirs_):
        return None
    if len(candles_chrono) == min_streak:
        return "green" if head == 1 else "red"
    prev = _candle_direction(candles_chrono[-(min_streak + 1)])
    if prev == head:
        return None
    return "green" if head == 1 else "red"


def _streak_window_metrics(candles_chrono: list[Candle], *, tail_n: int) -> BigMoveMetrics:
    w = candles_chrono[-tail_n:]
    first_open = float(w[0].open)
    last_close = float(w[-1].close)
    hi = max(float(c.high) for c in w)
    lo = min(float(c.low) for c in w)
    return compute_big_move_metrics(
        prev_close=first_open, latest_close=last_close, latest_high=hi, latest_low=lo
    )


INDICATOR_CONTEXT_TF_ORDER = ("1h", "15m", "4h", "5m")


def _core_indicators_from_screener_features(
    features: dict | None,
) -> tuple[float | None, float | None, float | None]:
    if not isinstance(features, dict):
        return (None, None, None)
    per = features.get("per_tf_indicators")
    if not isinstance(per, dict):
        return (None, None, None)
    for k in INDICATOR_CONTEXT_TF_ORDER:
        block = per.get(k)
        if not isinstance(block, dict) or block.get("rsi_14") is None:
            continue
        rsi = float(block["rsi_14"])
        mh = block.get("macd_hist")
        adx = block.get("adx_14")
        return (
            rsi,
            float(mh) if mh is not None else None,
            float(adx) if adx is not None else None,
        )
    return (None, None, None)


def _core_indicators_from_indicator_snapshot(
    snap: IndicatorSnapshot | None,
) -> tuple[float | None, float | None, float | None]:
    if snap is None or snap.rsi_14 is None:
        return (None, None, None)
    return (
        float(snap.rsi_14),
        float(snap.macd_hist) if snap.macd_hist is not None else None,
        float(snap.adx_14) if snap.adx_14 is not None else None,
    )


def _format_volume_quote(vol: float) -> str:
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.2f}M"
    if vol >= 1_000:
        return f"{vol / 1_000:.1f}K"
    return f"{vol:.0f}"


async def _resolve_market_screener_context(
    *,
    now: dt.datetime,
    base_asset: str,
    quote_asset: str,
    preferred_source: str,
    sources_try: list[str],
    screener_repo: ScreenerSnapshotRepository,
    indicator_repo: IndicatorSnapshotRepository,
) -> tuple[str, float, float | None, float | None, float | None]:
    scr = await screener_repo.get_latest_for_market(base_asset=base_asset, quote_asset=quote_asset)
    if scr and (now - scr.computed_at).total_seconds() < 45 * 60:
        rsi, macd, adx = _core_indicators_from_screener_features(scr.features)
        return scr.final_decision, float(scr.final_confidence), rsi, macd, adx

    snap = await _resolve_indicator_snapshot_for_context(
        indicator_repo,
        base_asset=base_asset,
        quote_asset=quote_asset,
        preferred_source=preferred_source,
        sources_try=sources_try,
    )
    decision_str, decision_conf, rsi = fallback_decision_from_indicator_snapshot(snap)
    _, macd, adx = _core_indicators_from_indicator_snapshot(snap)
    return decision_str, decision_conf, rsi, macd, adx


async def _resolve_indicator_snapshot_for_context(
    indicator_repo: IndicatorSnapshotRepository,
    *,
    base_asset: str,
    quote_asset: str,
    preferred_source: str,
    sources_try: list[str],
) -> IndicatorSnapshot | None:
    """Indicators are computed on 15m+ TFs during screener runs, not on 5m."""
    sources: list[str] = []
    for src in (preferred_source, *sources_try):
        if src and src not in sources:
            sources.append(src)
    for src in sources:
        for tf in INDICATOR_CONTEXT_TF_ORDER:
            snap = await indicator_repo.get_latest(
                source=src,
                base_asset=base_asset,
                quote_asset=quote_asset,
                timeframe=tf,
            )
            if snap is not None and snap.rsi_14 is not None:
                return snap
    return None


class VolatilityService:
    async def run_all_volatility_checks(
        self,
        *,
        source_preference: list[str] | None = None,
        big_move_min_gate_pct: float = 2.0,
        volume_spike_min_multiplier: float = 3.0,
    ) -> None:
        bot = get_bot()
        try:
            await self.detect_and_notify_big_moves(
                timeframe="5m",
                source_preference=source_preference,
                min_gate_pct=big_move_min_gate_pct,
                volume_spike_min_multiplier=volume_spike_min_multiplier,
                bot=bot,
            )
            await self.detect_and_notify_trend_pullbacks(
                source_preference=source_preference,
                bot=bot,
            )
        finally:
            await bot.session.close()

    async def detect_and_notify_big_moves(
        self,
        *,
        timeframe: str = "5m",
        source_preference: list[str] | None = None,
        min_gate_pct: float = 2.0,
        volume_spike_min_multiplier: float = 3.0,
        bot: Bot | None = None,
    ) -> None:
        tf_seconds = normalize_timeframe(timeframe).seconds
        baseline_tf = VOLUME_SPIKE_BASELINE_TIMEFRAME
        baseline_tf_seconds = normalize_timeframe(baseline_tf).seconds
        volume_baseline_candles = volume_spike_baseline_candle_count(timeframe_seconds=baseline_tf_seconds)
        baseline_periods_per_spike = baseline_tf_seconds / tf_seconds

        now = dt.datetime.now(dt.timezone.utc)
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()

        if not markets:
            return

        sources = source_preference or ["kucoin", "bybit"]
        indicator_repo = IndicatorSnapshotRepository()
        screener_repo = ScreenerSnapshotRepository()
        candle_repo = CandleRepository()
        event_repo = VolatilityEventRepository()
        settings_repo = UserSettingsRepository()
        own_bot = bot is None
        bot = bot or get_bot()

        try:
            for base, quote in markets:
                chrono, source_used = await self._get_latest_n_candles_chrono_with_fallback(
                    base=base,
                    quote=quote,
                    timeframe=timeframe,
                    sources=sources,
                    candle_repo=candle_repo,
                    n=2,
                    min_needed=2,
                )
                if len(chrono) < 2 or not source_used:
                    continue

                sources_for_baseline = [source_used] + [s for s in sources if s != source_used]
                chrono_baseline, _ = await self._get_latest_n_candles_chrono_with_fallback(
                    base=base,
                    quote=quote,
                    timeframe=baseline_tf,
                    sources=sources_for_baseline,
                    candle_repo=candle_repo,
                    n=volume_baseline_candles + 1,
                    min_needed=VOLUME_SPIKE_MIN_BASELINE_SAMPLES + 1,
                )
                baseline_slice = (
                    chrono_baseline[-(volume_baseline_candles + 1) : -1]
                    if len(chrono_baseline) >= volume_baseline_candles + 1
                    else []
                )

                latest = chrono[-1]
                prev = chrono[-2]
                bucket = floor_time(latest.open_time_utc, seconds=tf_seconds)

                price_metrics: BigMoveMetrics | None = None
                price_passes_global = False
                try:
                    price_metrics = compute_big_move_metrics(
                        prev_close=float(prev.close),
                        latest_close=float(latest.close),
                        latest_high=float(latest.high),
                        latest_low=float(latest.low),
                    )
                    price_passes_global = passes_big_move_gate(price_metrics, threshold_pct=min_gate_pct)
                except Exception:
                    price_metrics = None

                volume_metrics = compute_volume_spike_metrics(
                    latest_candle=latest,
                    baseline_candles_chrono=baseline_slice,
                    baseline_periods_per_spike=baseline_periods_per_spike,
                )
                volume_passes_global = volume_metrics is not None and passes_volume_spike_gate(
                    volume_metrics, min_multiplier=volume_spike_min_multiplier
                )

                if not price_passes_global and not volume_passes_global:
                    continue

                price_inserted = False
                if price_passes_global and price_metrics is not None:
                    price_inserted = await self._insert_event_if_new(
                        source=source_used,
                        base=base,
                        quote=quote,
                        timeframe=timeframe,
                        bucket=bucket,
                        metrics=price_metrics,
                        latest=latest,
                        prev=prev,
                        detected_at=now,
                        repo=event_repo,
                    )

                volume_inserted = False
                if volume_passes_global and volume_metrics is not None:
                    volume_inserted = await self._insert_volume_spike_event_if_new(
                        source=source_used,
                        base=base,
                        quote=quote,
                        timeframe=timeframe,
                        bucket=bucket,
                        metrics=volume_metrics,
                        latest=latest,
                        detected_at=now,
                        repo=event_repo,
                    )

                if not price_inserted and not volume_inserted:
                    continue

                subscribers = await settings_repo.list_market_subscribers(base_asset=base, quote_asset=quote)
                if not subscribers:
                    continue

                decision_str, decision_conf, rsi_for_msg, macd_for_msg, adx_for_msg = await _resolve_market_screener_context(
                    now=now,
                    base_asset=base,
                    quote_asset=quote,
                    preferred_source=source_used,
                    sources_try=sources,
                    screener_repo=screener_repo,
                    indicator_repo=indicator_repo,
                )
                context_suffix = format_screener_context_suffix(
                    decision_str=decision_str,
                    decision_conf=decision_conf,
                    rsi=rsi_for_msg,
                    macd=macd_for_msg,
                    adx=adx_for_msg,
                )

                for telegram_id, threshold in subscribers:
                    lines: list[str] = []
                    if price_inserted and price_metrics is not None and passes_big_move_gate(
                        price_metrics, threshold_pct=threshold
                    ):
                        direction = "UP" if price_metrics.pct_change >= 0 else "DOWN"
                        lines.append(
                            f"Big move: {base}/{quote} {direction} {price_metrics.pct_change:.2f}% "
                            f"(range {price_metrics.range_pct:.2f}%)"
                        )
                    if (
                        volume_inserted
                        and volume_metrics is not None
                        and passes_volume_spike_gate(volume_metrics, min_multiplier=volume_spike_min_multiplier)
                    ):
                        lines.append(
                            f"Volume spike: {base}/{quote} {volume_metrics.volume_ratio:.1f}x median "
                            f"({_format_volume_quote(volume_metrics.latest_volume_quote)} USDT vs "
                            f"{_format_volume_quote(volume_metrics.baseline_median_quote)} median, "
                            f"+{volume_metrics.pct_above_median:.0f}%)"
                        )
                    if not lines:
                        continue
                    text = "\n".join(lines) + f"\n{context_suffix}"
                    try:
                        await bot.send_message(chat_id=telegram_id, text=text)
                    except Exception as e:
                        logger.warning(
                            "telegram send failed",
                            telegram_id=telegram_id,
                            market=f"{base}/{quote}",
                            error=str(e),
                        )
        finally:
            if own_bot:
                await bot.session.close()

    async def detect_and_notify_trend_pullbacks(
        self,
        *,
        source_preference: list[str] | None = None,
        bot: Bot | None = None,
    ) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        markets = await UserTrackedAssetRepository().list_distinct_enabled_markets()
        if not markets:
            return

        sources = source_preference or ["kucoin", "bybit"]
        indicator_repo = IndicatorSnapshotRepository()
        screener_repo = ScreenerSnapshotRepository()
        candle_repo = CandleRepository()
        event_repo = VolatilityEventRepository()
        settings_repo = UserSettingsRepository()
        own_bot = bot is None
        bot = bot or get_bot()

        try:
            for base, quote in markets:
                for timeframe, cfg in TREND_PULLBACK_CONFIGS.items():
                    fetch_n = int(cfg.window_candles) + 2
                    chrono, source_used = await self._get_latest_n_candles_chrono_with_fallback(
                        base=base,
                        quote=quote,
                        timeframe=timeframe,
                        sources=sources,
                        candle_repo=candle_repo,
                        n=fetch_n,
                        min_needed=int(cfg.window_candles),
                    )
                    if len(chrono) < int(cfg.window_candles):
                        continue

                    detected = detect_trend_with_pullback(chrono, cfg=cfg)
                    if detected is None:
                        continue
                    direction, payload = detected

                    latest = chrono[-1]
                    bucket = latest.open_time_utc
                    event_type = "trend_pullback_bull" if direction == "green" else "trend_pullback_bear"
                    window_metrics = _streak_window_metrics(chrono, tail_n=int(cfg.window_candles))

                    inserted = await self._insert_trend_event_if_new(
                        source=source_used,
                        base=base,
                        quote=quote,
                        timeframe=timeframe,
                        event_type=event_type,
                        bucket=bucket,
                        metrics=window_metrics,
                        latest=latest,
                        detected_at=now,
                        repo=event_repo,
                        payload_extra={
                            **payload,
                            "direction": direction,
                            "candle_open_times_utc": [
                                c.open_time_utc.isoformat() for c in chrono[-int(cfg.window_candles) :]
                            ],
                        },
                    )
                    if not inserted:
                        continue

                    subscribers = await settings_repo.list_market_subscribers(base_asset=base, quote_asset=quote)
                    if not subscribers:
                        continue

                    scr = await screener_repo.get_latest_for_market(base_asset=base, quote_asset=quote)
                    rsi_for_msg: float | None = None
                    macd_for_msg: float | None = None
                    adx_for_msg: float | None = None
                    if scr and (now - scr.computed_at).total_seconds() < 45 * 60:
                        decision_str = scr.final_decision
                        decision_conf = float(scr.final_confidence)
                        rsi_for_msg, macd_for_msg, adx_for_msg = _core_indicators_from_screener_features(scr.features)
                    else:
                        snap = await _resolve_indicator_snapshot_for_context(
                            indicator_repo,
                            base_asset=base,
                            quote_asset=quote,
                            preferred_source=source_used,
                            sources_try=sources,
                        )
                        decision_str, decision_conf, rsi_for_msg = fallback_decision_from_indicator_snapshot(snap)
                        _, macd_for_msg, adx_for_msg = _core_indicators_from_indicator_snapshot(snap)

                    dir_label = "UP" if direction == "green" else "DOWN"
                    text = (
                        f"Trend ({timeframe}): {base}/{quote} pullback-tolerant {dir_label} "
                        f"(~{window_metrics.pct_change:+.2f}% over window)\n"
                        + format_screener_context_suffix(
                            decision_str=decision_str,
                            decision_conf=decision_conf,
                            rsi=rsi_for_msg,
                            macd=macd_for_msg,
                            adx=adx_for_msg,
                        )
                    )

                    for telegram_id, _threshold in subscribers:
                        try:
                            await bot.send_message(chat_id=telegram_id, text=text)
                        except Exception as e:
                            logger.warning(
                                "telegram send failed (trend pullback)",
                                telegram_id=telegram_id,
                                market=f"{base}/{quote}",
                                timeframe=timeframe,
                                error=str(e),
                            )
        finally:
            if own_bot:
                await bot.session.close()

    async def _get_latest_n_candles_chrono_with_fallback(
        self,
        *,
        base: str,
        quote: str,
        timeframe: str,
        sources: list[str],
        candle_repo: CandleRepository,
        n: int,
        min_needed: int | None = None,
    ) -> tuple[list[Candle], str]:
        need = min_needed if min_needed is not None else n
        for src in sources:
            raw = await candle_repo.list_latest_n(
                source=src,
                base_asset=base,
                quote_asset=quote,
                timeframe=timeframe,
                limit=n,
            )
            if len(raw) >= need:
                return list(reversed(raw)), src
        return [], ""

    async def _get_latest_two_candles_with_fallback(
        self,
        *,
        base: str,
        quote: str,
        timeframe: str,
        sources: list[str],
        candle_repo: CandleRepository,
    ) -> tuple[Candle | None, Candle | None, str]:
        for src in sources:
            latest, prev = await self._get_latest_two_candles(
                source=src,
                base=base,
                quote=quote,
                timeframe=timeframe,
                candle_repo=candle_repo,
            )
            if latest is not None and prev is not None:
                return latest, prev, src
        return None, None, ""

    async def _get_latest_two_candles(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        candle_repo: CandleRepository,
    ) -> tuple[Candle | None, Candle | None]:
        return await candle_repo.get_latest_two(source=source, base_asset=base, quote_asset=quote, timeframe=timeframe)

    async def _insert_event_if_new(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        bucket: dt.datetime,
        metrics,
        latest: Candle,
        prev: Candle,
        detected_at: dt.datetime,
        repo: VolatilityEventRepository,
    ) -> bool:
        row = {
            "source": source,
            "base_asset": base,
            "quote_asset": quote,
            "timeframe": timeframe,
            "event_type": "big_move",
            "bucket_time_utc": bucket,
            "pct_change": float(metrics.pct_change),
            "range_pct": float(metrics.range_pct),
            "volume_quote": float(latest.volume_quote) if latest.volume_quote is not None else None,
            "detected_at": detected_at,
            "payload": {
                "latest_open_time_utc": latest.open_time_utc.isoformat(),
                "latest_close": float(latest.close),
                "prev_close": float(prev.close),
            },
        }
        return await repo.insert_if_new(row, conflict_constraint="uq_volatility_event_dedup")

    async def _insert_volume_spike_event_if_new(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        bucket: dt.datetime,
        metrics: VolumeSpikeMetrics,
        latest: Candle,
        detected_at: dt.datetime,
        repo: VolatilityEventRepository,
    ) -> bool:
        row = {
            "source": source,
            "base_asset": base,
            "quote_asset": quote,
            "timeframe": timeframe,
            "event_type": "volume_spike",
            "bucket_time_utc": bucket,
            "pct_change": float(metrics.pct_above_median),
            "range_pct": float(metrics.volume_ratio),
            "volume_quote": float(metrics.latest_volume_quote),
            "detected_at": detected_at,
            "payload": {
                "latest_open_time_utc": latest.open_time_utc.isoformat(),
                "baseline_median_quote": float(metrics.baseline_median_quote),
                "volume_ratio": float(metrics.volume_ratio),
                "lookback_days": VOLUME_SPIKE_LOOKBACK_DAYS,
                "baseline_timeframe": VOLUME_SPIKE_BASELINE_TIMEFRAME,
            },
        }
        return await repo.insert_if_new(row, conflict_constraint="uq_volatility_event_dedup")

    async def _insert_trend_event_if_new(
        self,
        *,
        source: str,
        base: str,
        quote: str,
        timeframe: str,
        event_type: str,
        bucket: dt.datetime,
        metrics: BigMoveMetrics,
        latest: Candle,
        detected_at: dt.datetime,
        repo: VolatilityEventRepository,
        payload_extra: dict,
    ) -> bool:
        row = {
            "source": source,
            "base_asset": base,
            "quote_asset": quote,
            "timeframe": timeframe,
            "event_type": event_type,
            "bucket_time_utc": bucket,
            "pct_change": float(metrics.pct_change),
            "range_pct": float(metrics.range_pct),
            "volume_quote": float(latest.volume_quote) if latest.volume_quote is not None else None,
            "detected_at": detected_at,
            "payload": payload_extra,
        }
        return await repo.insert_if_new(row, conflict_constraint="uq_volatility_event_dedup")

