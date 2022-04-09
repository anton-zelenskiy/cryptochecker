from pycoingecko import CoinGeckoAPI
from functools import lru_cache


api = CoinGeckoAPI()


@lru_cache(maxsize=1024)
def get_currencies():
    coins = api.get_coins_list()

    return {str(coin['symbol']).upper() for coin in coins}


def is_currency_code_exists(currency_code: str) -> bool:
    return currency_code in get_currencies()
