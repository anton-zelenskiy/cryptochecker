from __future__ import annotations


def coin_ids_from_stablecoin_tag_payload(payload: object) -> frozenset[str]:
    if not isinstance(payload, dict):
        return frozenset()
    coins = payload.get("coins")
    if not isinstance(coins, list):
        return frozenset()
    return frozenset(str(x) for x in coins if isinstance(x, str) and x)
