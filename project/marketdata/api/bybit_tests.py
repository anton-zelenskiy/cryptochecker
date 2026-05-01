from __future__ import annotations

import datetime as dt

from project.marketdata.api.bybit import parse_public_trade_item
from project.marketdata.dto import NormalizedMarket


def test_parse_trade_item_happy_path() -> None:
    market = NormalizedMarket(base_asset="BTC", quote_asset="USDT")
    item = {"T": 1_700_000_000_000, "S": "Buy", "v": "0.1", "p": "60000", "i": "123"}
    row = parse_public_trade_item(item, market=market)
    assert row is not None
    assert row["source"] == "bybit"
    assert row["base_asset"] == "BTC"
    assert row["quote_asset"] == "USDT"
    assert row["trade_id"] == "123"
    assert row["side"] == "buy"
    assert row["price"] == 60000.0
    assert row["qty"] == 0.1
    assert row["notional_quote"] == 6000.0
    assert isinstance(row["trade_time_utc"], dt.datetime)
    assert row["trade_time_utc"].tzinfo is not None


def test_parse_trade_item_missing_trade_id_returns_none() -> None:
    market = NormalizedMarket(base_asset="BTC", quote_asset="USDT")
    item = {"T": 1_700_000_000_000, "S": "Buy", "v": "0.1", "p": "60000"}
    assert parse_public_trade_item(item, market=market) is None
