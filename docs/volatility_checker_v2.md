# Volatility Checker v2 (big moves) + Screener integration

Goal: keep a **volatility checker** in the new stack, but make it **signal-driven** (react only to meaningful moves) and **integrated with the screener** (same data, same scoring, same notification path).

This doc is a living TODO list. Items marked **[x]** are already implemented in the codebase.

## Principles

- **React only to big market movements**
  - avoid spammy “every N minutes” price pings
  - trigger on statistically meaningful moves (range expansion, volume spikes, gap moves)
- **Single source of truth**: use stored candles/trades from PostgreSQL/TimescaleDB whenever possible
- **Best-effort** on free tiers: aggressive caching + provider fallback + backoff
- **Integrate with screener**: volatility events become inputs into the same `LONG/SHORT/WAIT` decision and summary pipeline

## What we have now (inventory)

- **Tracked universe** comes from `user_tracked_assets` (per Telegram user).
- **Candles** are ingested periodically into `candles` (Timescale hypertable).
- **Catalog** is refreshed into `catalog_coins` and stablecoins are filtered.
- **Microstructure slice** exists as a first step: WS **trades-only** into `market_trades`.

## Volatility Checker v2: detection (proposal)

Volatility checker becomes an **event detector** that emits `VolatilityEvent` rows and/or pushes notifications.

Suggested initial triggers (v1 of v2):

- **Range expansion (5m / 15m)**
  - compute \(abs(return)\), candle range \(high-low\), and compare to recent baseline (rolling median/ATR proxy)
  - trigger when move exceeds threshold, e.g. \(abs(return) > max(min_pct, k * median_abs_return)\)
- **Volume spike**
  - use `volume_quote` (USDT turnover) when available
  - trigger when \(volume > k * rolling_median(volume)\)
- **Trade prints (WS)**
  - trigger on large prints: \(notional\_quote = price * qty\) above threshold
  - later: cluster large prints within 5–20s window

Noise controls:

- per-market cooldown (e.g. 10–30 minutes)
- dedup by `(market, event_type, ts_bucket)`
- “only if new high/low” within window

## Screener integration (proposal)

When volatility triggers:

- **pull latest screener snapshot** (indicators + valuation + microstructure hints) from DB
- produce:
  - a deterministic reasoned summary (baseline)
  - optional Gemini summary (best-effort)
- send a single notification with:
  - event type + magnitude
  - decision `LONG/SHORT/WAIT` + confidence
  - key reasons

## TODO list (full list, with implemented steps marked)

### Foundation / platform

- [x] FastAPI app + aiogram webhooks (new stack)
- [x] PostgreSQL models for users/settings/tracked assets
- [x] Celery beat + worker wiring

### Catalog + metadata

- [x] Catalog refresh (top-300 non-stablecoins)
- [x] Market rank adapter with fallback when CoinGecko returns 429 (CoinGecko → CoinPaprika)
- [ ] Normalize catalog IDs across providers (fallback catalog rows are not CoinGecko IDs)

### Market data

- [x] Candle ingest task for tracked assets → `candles` (Timescale hypertable)
- [x] Exchange candle providers via `httpx` (KuCoin + Bybit)
- [ ] Provider-level rate limiting + jittered backoff (shared middleware/decorator)
- [ ] Smarter ingest windows per timeframe (avoid refetching the same 3h window each minute)

### Microstructure (WS)

- [x] Trades-only slice: Bybit WS public trades → `market_trades` (bounded periodic collector)
- [ ] Large print thresholding (store only above notional threshold or persist clusters only)
- [ ] Cluster logic (5–20s) → `trade_clusters` (recommended)
- [ ] Order book (L2): snapshot + delta ingest
- [ ] Support wall detection (appear/pulled/eaten) + persistence

### Volatility checker v2 (this doc)

- [ ] Add `volatility_events` table (event_type, magnitude, timeframe, detected_at, cooldown_key, payload)
- [ ] Implement “big move” detector using DB candles (5m/15m/1h)
- [ ] Add event dedup + cooldown (Redis + DB uniqueness)
- [ ] Integrate with screener snapshot + decision pipeline
- [ ] Notification pipeline: send Telegram message only on events (no periodic spam)
- [ ] Per-user preferences:
  - [ ] enable/disable
  - [ ] thresholds (min pct, volume spike multiplier, large print notional)
  - [ ] quiet hours / rate limit per user

### API / TWA

- [x] `verify_telegram_init_data` for TWA requests
- [ ] TWA endpoints for volatility events feed (history + last event per tracked market)

### Observability / ops

- [ ] Structured logs around provider failures and rate limits (429, timeouts)
- [ ] Metrics: event counts, provider 429 counts, ingest lag

