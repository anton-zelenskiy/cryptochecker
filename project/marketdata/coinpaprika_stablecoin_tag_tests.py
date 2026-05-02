from __future__ import annotations

import pytest

from project.marketdata.coinpaprika_stablecoin_tag import coin_ids_from_stablecoin_tag_payload


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, frozenset()),
        ({"coins": None}, frozenset()),
        ({"coins": []}, frozenset()),
        ({"coins": ["usdt-tether", "usdc-usd-coin"]}, frozenset({"usdt-tether", "usdc-usd-coin"})),
        ({"coins": ["x", 1, "y"]}, frozenset({"x", "y"})),
    ],
)
def test_coin_ids_from_stablecoin_tag_payload(payload: object, expected: frozenset[str]) -> None:
    assert coin_ids_from_stablecoin_tag_payload(payload) == expected
