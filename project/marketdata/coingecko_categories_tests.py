from __future__ import annotations

import pytest

from project.marketdata.coingecko_categories import coingecko_row_has_stablecoins_category


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({}, False),
        ({"categories": None}, False),
        ({"categories": []}, False),
        ({"categories": ["Layer 1"]}, False),
        ({"categories": ["Stablecoins"]}, True),
        ({"categories": ["stablecoins"]}, True),
        ({"categories": [{"name": "Stablecoins", "id": "stablecoins"}]}, True),
        ({"categories": [{"name": "Layer 1"}]}, False),
        ({"categories": {"en": ["Stablecoins"]}}, True),
        ({"categories": {"en": ["Meme"]}}, False),
    ],
)
def test_coingecko_row_has_stablecoins_category(row: dict, expected: bool) -> None:
    assert coingecko_row_has_stablecoins_category(row) is expected
