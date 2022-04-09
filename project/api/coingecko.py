from functools import lru_cache
from typing import List, Iterable

from pycoingecko import CoinGeckoAPI

from project.currencies.structures import HistoryData, CurrencyPrice

api = CoinGeckoAPI()


CURRENCY_CODE_ID_OVERRIDE_MAP = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
}


@lru_cache(maxsize=1024)
def get_currency_code_id_map() -> dict:
    coins = api.get_coins_list()

    result = {}
    for coin in coins:
        currency_code = str(coin['symbol']).upper()
        currency_id = (
            CURRENCY_CODE_ID_OVERRIDE_MAP.get(currency_code) or coin['id']
        )
        result.update({currency_code: currency_id})

    return result


@lru_cache(maxsize=1024)
def get_currency_id_code_map():
    return {
        v: k
        for k, v in get_currency_code_id_map().items()
    }


def is_currency_code_exists(currency_code: str) -> bool:
    return currency_code in get_currency_code_id_map()


def get_daily_currency_history(currency_id: str) -> List[HistoryData]:
    data = api.get_coin_market_chart_by_id(
        id=currency_id,
        vs_currency='usd',
        days=1
    )

    prices_data = data.get('prices', [])

    return [
        HistoryData(unix_timestamp=ts, value=round(price, 2))
        for ts, price in prices_data
    ]


def get_currency_prices(currency_codes: Iterable[str]):
    currency_code_id_map = get_currency_code_id_map()
    currency_ids = [
        currency_code_id_map.get(code)
        for code in currency_codes
    ]

    currency_prices = api.get_price(
        ids=currency_ids,
        vs_currencies='usd'
    )

    currency_id_code_map = get_currency_id_code_map()

    return [
        CurrencyPrice(
            currency_code=currency_id_code_map.get(currency_id),
            price=round(price['usd'], 2),
        )
        for currency_id, price in currency_prices.items()
    ]
