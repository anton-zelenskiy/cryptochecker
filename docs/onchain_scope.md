# On-chain holders scope (free tier)

Goal: flag tokens where supply is concentrated (e.g. 90% held by top 10–20 wallets).

## Why this is best-effort on free tiers

- Holder concentration is **on-chain**, chain-specific, and usually requires an indexed dataset.
- Most explorer APIs expose holder lists as **paid** endpoints or severely rate-limit them.
- Many top coins are **CEX-listed symbols** without a single canonical contract across chains.

## MVP behavior

- If we can resolve a stable free endpoint for a token's primary chain+contract, we compute concentration.
- Otherwise we return `holders_concentration = null` and mark it as `unknown` (does not block screening).

## Candidate free sources (unstable / chain-specific)

- **Blockscout** instances (some chains): may expose token holder endpoints (not standardized across deployments).
- **Public chain RPC + indexing**: possible but not realistic for a small free project without an indexer.

## Output model (recommended)

- `holders_total`: int | null
- `top_n_share_pct`: float | null (for N=10/20)
- `holders_risk_flag`: bool | null
- `holders_source`: str | null
- `holders_last_updated`: timestamp | null

