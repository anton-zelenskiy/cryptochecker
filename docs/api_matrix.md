# API matrix (free-tier) + caching/fallback

This project intentionally uses **free** public APIs only. Because free tiers are rate-limited and sometimes flaky, the runtime must:

- cache aggressively (Redis),
- deduplicate requests,
- use exponential backoff + jitter on 429/5xx,
- support **fallback providers** behind a common adapter interface,
- persist canonical time-series (candles) in TimescaleDB to avoid re-fetching.

## Providers

### 1) Exchange market data (primary OHLCV + trades + order book)

These provide the core market microstructure and OHLCV for indicators.

| Data | KuCoin | Bybit | Notes |
|------|--------|-------|------|
| **Candles OHLCV** | REST klines | REST klines | Primary for indicators + volume logic. Prefer exchange candles over aggregators. |
| **Trades stream** | WS public trades | WS public trades | Used for `LargeBuyCluster` detection (large prints + clustering). |
| **Order book (L2)** | WS L2 | WS L2 | Used for liquidity walls + bid/ask imbalance. |

**Normalized outputs (adapter DTOs):**

- `NormalizedCandle`: `source`, `base_asset`, `quote_asset`, `timeframe`, `open_time_utc`, `open`, `high`, `low`, `close`, `volume_base`, `volume_quote?`
- `NormalizedTrade`: `source`, `symbol`, `ts`, `price`, `qty`, `side?`, `trade_id`
- `OrderBookDelta` / `OrderBookSnapshot`: `bids[]`, `asks[]` with price/size

**Rate limiting strategy (free tiers):**

- client-side token bucket per provider + per endpoint family (REST vs WS reconnect),
- backoff on `429` with increasing delays,
- optional round-robin between KuCoin/Bybit for candles if one throttles.

### 2) Aggregated market context (catalog + mcap + FDV)

| Data | CoinGecko | Fallback | Notes |
|------|-----------|----------|------|
| **Top catalog** (top-300) | `/coins/markets` | Coinpaprika/CryptoCompare | In MVP: used as **catalog only**, not full tracking. |
| **Market cap / FDV** | `/coins/markets` | depends | Cached; used for valuation heuristics. |
| **Coin metadata** (id, platforms/contracts) | `/coins/{id}` | limited | Expensive for 300 ids; batch + cache in DB daily. |

**Stablecoins filtering (catalog):**

- primary: provider flag/category/tag if available,
- fallback: denylist by `symbol`/`id` (USDT, USDC, DAI, TUSD, FDUSD, USDP, PYUSD, USDE, FRAX, ...),
- result: `catalog_coins = top_300_non_stablecoins`.

### 3) Optional: TVL / DeFi context

| Data | DeFiLlama | Notes |
|------|-----------|------|
| **TVL** | public REST | Optional for `mcap/TVL` heuristics. |

### 4) Optional: On-chain holder concentration (best-effort)

Not guaranteed on free tiers for all chains/tokens. In MVP we treat it as **N/A** unless a stable free endpoint exists for the token's chain.

## Caching (Redis)

Redis is used for:

- response caches with TTLs,
- API quota bookkeeping,
- dedup keys for WS-derived events.

Suggested TTLs (tune later):

| Item | TTL |
|------|-----|
| catalog top-300 | 6–24h |
| coin metadata (contracts/platforms) | 24h |
| market cap / FDV | 15–60m |
| OHLCV fetch “tail” (last N candles) | 30–120s (if still used at runtime) |
| Gemini summaries | 1–10m per `(symbol,timeframe_set,ts_bucket)` |

## Fallback policy

1. Prefer **exchange candles** for any tracked symbol/timeframe.
2. If provider A throttles/errors, try provider B for the same market.
3. Never mix candles from different sources into the same series unless explicitly filling gaps (v2).

## Data persistence (TimescaleDB)

Candles are persisted as the canonical time-series to avoid re-fetching and to enable backtests/paper trading.

- hypertable key: `open_time_utc`
- unique constraint: `(source, base_asset, quote_asset, timeframe, open_time_utc)`

## LLM summary (Gemini, free tier)

Gemini is used only to generate a short **explanation** of our deterministic calculations:

- summary of indicator states,
- explanation of `LONG/SHORT/WAIT` decision,
- includes `confidence` + top factors.

Guardrails:

- best-effort (fallback to deterministic text),
- strict budget + caching,
- never send secrets or PII.

