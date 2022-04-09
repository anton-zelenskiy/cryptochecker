from functools import lru_cache
from typing import List

from pycoingecko import CoinGeckoAPI

from project.currencies.structures import HistoryData, CurrencyPrice

api = CoinGeckoAPI()


@lru_cache(maxsize=1024)
def get_currencies():
    coins = api.get_coins_list()

    return {str(coin['symbol']).upper() for coin in coins}


@lru_cache(maxsize=1024)
def get_currency_code_id_map() -> dict:
    coins = api.get_coins_list()

    return {
        str(coin['symbol']).upper(): coin['id']
        for coin in coins
    }


@lru_cache(maxsize=1024)
def get_currency_id_code_map():
    return {
        v: k
        for k, v in get_currency_code_id_map().items()
    }


def is_currency_code_exists(currency_code: str) -> bool:
    return currency_code in get_currencies()


def get_daily_currency_history(currency_id: str) -> List[HistoryData]:
    data = api.get_coin_market_chart_by_id(
        id=currency_id,
        vs_currency='usd',
        days=1
    )

    prices_data = data.get('prices', [])

    return [
        HistoryData(unix_timestamp=ts, value=price)
        for ts, price in prices_data
    ]


def get_currency_prices(currency_ids: List[str]):
    currency_prices = api.get_price(
        ids=currency_ids,
        vs_currencies='usd'
    )

    currency_id_code_map = get_currency_id_code_map()

    return [
        CurrencyPrice(
            currency_code=currency_id_code_map.get(currency_id),
            price=price['usd'],
        )
        for currency_id, price in currency_prices.items()
    ]
