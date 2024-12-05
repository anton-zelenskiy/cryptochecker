from typing import Iterable

from project.currencies.structures import Coin, HistoryData, CandleData


class CoinMarketAPI:
    def get_currency_prices(self, currency_codes: Iterable[str]) -> list[Coin]:
        ...

    def get_history_price(self, currency_code: str) -> list[HistoryData]:
        ...

    def get_ohlc(self, currency_code: str) -> list[CandleData]:
        ...
        
    def get_market_data(self, currency_code: str) -> dict:
        raise NotImplementedError()
