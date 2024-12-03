from kucoin.client import Market
from typing import Iterable
import datetime
import structlog

from project.currencies.structures import Coin, CandleData, HistoryData
from project.api.base import CoinMarketAPI

logger = structlog.get_logger(__name__)


class KucoinMarketAPI(CoinMarketAPI):
    def __init__(self):
        self._client = Market(url='https://api.kucoin.com')

    def get_currency_prices(self, currency_codes: Iterable[str]) -> list[Coin]:
        currency_prices: dict[str, str] = self._client.get_fiat_price(
            base='USD',
            currencies=','.join(c.upper() for c in currency_codes)
        ) # type: ignore

        return [
            Coin(
                currency_code=code,
                price=float(price),
            )
            for code, price in currency_prices.items()
        ]
        
    def get_history_price(self, currency_code: str) -> list[HistoryData]:
        data = self.get_ohlc(currency_code=currency_code)

        return [
            HistoryData(unix_timestamp=int(item.datetime.timestamp()), value=item.close)
            for item in data
        ]
        
    def get_ohlc(self, currency_code: str) -> list[CandleData]:
        now = datetime.datetime.now()
        
        now_seconds = int(now.timestamp())
        hour_ago_seconds = int((now - datetime.timedelta(hours=1)).timestamp())

        data: list[list] = self._client.get_kline(
            symbol=f'{currency_code.upper()}-USDT',
            kline_type='5min',
            startAt=hour_ago_seconds,
            endAt=now_seconds,
        )  # type: ignore
        
        return [
            CandleData(
                datetime=datetime.datetime.fromtimestamp(int(ts)),
                open=open_,
                close=close_,
                high=high_,
                low=low_,
                volume=volume_,
            )
            for ts, open_, close_, high_, low_, volume_, turnover_ in data
        ]
