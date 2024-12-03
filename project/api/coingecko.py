import datetime
from functools import lru_cache
from pycoingecko import CoinGeckoAPI
from typing import Iterable
import structlog

from project.api.constants import CURRENCY_CODE_ID_OVERRIDE_MAP
from project.api.base import CoinMarketAPI
from project.currencies.structures import HistoryData, Coin, CandleData
from project.utils import request_counter

logger = structlog.get_logger(__name__)


class CoingeckoMarketAPI(CoinMarketAPI):
    def __init__(self) -> None:
        self._client = CoinGeckoAPI()

    @lru_cache(maxsize=1024)
    def get_currency_code_id_map(self) -> dict:
        coins = self._client.get_coins_list()

        result = {}
        for coin in coins:
            currency_code = str(coin['symbol']).lower()
            currency_id = (
                CURRENCY_CODE_ID_OVERRIDE_MAP.get(currency_code) or coin['id']
            )
            result.update({currency_code: currency_id})

        return result

    @lru_cache(maxsize=1024)
    def get_currency_id_code_map(self):
        return {
            v: k
            for k, v in self.get_currency_code_id_map().items()
        }

    def is_currency_code_exists(self, currency_code: str) -> bool:
        return currency_code in self.get_currency_code_id_map()

    @request_counter
    def get_history_price(self, currency_code: str) -> list[HistoryData]:
        currency_code_id_map = self.get_currency_code_id_map()
        currency_id = currency_code_id_map.get(currency_code)
        
        data = self._client.get_coin_market_chart_by_id(
            id=currency_id,
            vs_currency='usd',
            days=1
        )

        prices_data = data.get('prices', [])

        return [
            HistoryData(unix_timestamp=ts, value=price)
            for ts, price in prices_data
        ]

    @request_counter
    def get_currency_prices(self, currency_codes: Iterable[str]) -> list[Coin]:
        currency_code_id_map = self.get_currency_code_id_map()
        currency_ids = [
            currency_code_id_map.get(code)
            for code in currency_codes
        ]

        currency_prices = self._client.get_price(
            ids=currency_ids,
            vs_currencies='usd'
        )

        logger.info('got currency prices')

        currency_id_code_map = self.get_currency_id_code_map()

        return [
            Coin(
                currency_code=currency_id_code_map.get(currency_id, currency_id),
                price=price['usd'],
            )
            for currency_id, price in currency_prices.items()
        ]

    @request_counter
    def get_ohlc(self, currency_code: str) -> list[CandleData]:
        currency_code_id_map = self.get_currency_code_id_map()
        currency_id = currency_code_id_map.get(currency_code)

        data = self._client.get_coin_ohlc_by_id(
            id=currency_id,
            vs_currency='usd',
            days=1
        )

        return [
            CandleData(
                datetime=datetime.datetime.fromtimestamp(ts / 1000),
                open=open_,
                high=high_,
                low=low_,
                close=close_,
            )
            for ts, open_, high_, low_, close_ in data
        ]
