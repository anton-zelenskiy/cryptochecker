from __future__ import annotations

STABLECOINS_CATEGORY_NAME = "Stablecoins"


def coingecko_row_has_stablecoins_category(row: dict) -> bool:
    """
    True when CoinGecko includes the Stablecoins category on this row.

    `/coins/markets` may expose `categories` as list[str] or list[{name: str}];
    `/coins/{id}` uses list[str]. Payloads may nest locale keys in a dict.
    """
    raw = row.get("categories")
    if raw is None:
        return False

    labels: list[str] = []
    if isinstance(raw, str):
        labels.append(raw)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str):
                    labels.append(name)
    elif isinstance(raw, dict):
        for v in raw.values():
            if isinstance(v, str):
                labels.append(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, str):
                        labels.append(x)

    target = STABLECOINS_CATEGORY_NAME.casefold()
    return any(label.casefold() == target for label in labels)
