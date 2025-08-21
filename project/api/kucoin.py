from calendar import c
import datetime
from collections.abc import Iterable

import structlog
from kucoin.client import Market

from project.api.base import CoinMarketAPI
from project.currencies.structures import CandleData, Coin, HistoryData
from project.utils import request_counter, retry

logger = structlog.get_logger(__name__)


class KucoinMarketAPI(CoinMarketAPI):
    def __init__(self):
        self._client = Market(url='https://api.kucoin.com')

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['429'], delay=30)
    def get_currency_prices(self, currency_codes: Iterable[str]) -> list[Coin]:
        currency_prices: dict[str, str] = self._client.get_fiat_price(
            base='USD',
            currencies=','.join(c.upper() for c in currency_codes)
        ) # type: ignore

        logger.info('got currency prices', data=currency_prices)

        if 'data' in currency_prices and not currency_prices['data']:
            return []

        return [
            Coin(
                currency_code=code.lower(),
                price=float(price),
            )
            for code, price in currency_prices.items()
        ]

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['429'], delay=30)
    def get_history_price(self, currency_code: str) -> list[HistoryData]:
        data = self.get_ohlc(currency_code=currency_code)

        logger.info('got history price', data=data)

        return [
            HistoryData(
                unix_timestamp=int(item.datetime.timestamp()),
                value=float(item.close)
            )
            for item in data
        ]

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['429'], delay=30)
    def get_ohlc(self, currency_code: str) -> list[CandleData]:
        now = datetime.datetime.now()

        now_seconds = int(now.timestamp())
        prev_seconds = int((now - datetime.timedelta(hours=3)).timestamp())

        data: list[list] = self._client.get_kline(
            symbol=f'{currency_code.upper()}-USDT',
            kline_type='5min',
            startAt=prev_seconds,
            endAt=now_seconds,
        )  # type: ignore

        logger.info('got ohlc data', data=data)

        return [
            CandleData(
                datetime=datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc),
                open=float(open_),
                close=float(close_),
                high=float(high_),
                low=float(low_),
                volume=float(volume_),
                turnover=float(turnover_)
            )
            for ts, open_, close_, high_, low_, volume_, turnover_ in data
        ]

    def get_favorite_coins(self) -> list[str]:
        raise NotImplementedError()

    def is_currency_code_exists(self, currency_code: str) -> bool:
        return len(self.get_currency_prices([currency_code])) > 0

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['429'], delay=30)
    def get_market_data(self, currency_codes: list[str]) -> list[Coin]:
        return self.get_currency_prices(currency_codes)
