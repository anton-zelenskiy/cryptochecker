from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

import requests

from project.currencies.structures import VolatilityValue
from project.settings import ALPHAVANTAGE_API_KEY


class ExchangeMarket(Enum):
    USD = 'USD'


@dataclass(frozen=True)
class HistoryData:
    timestamp: datetime
    value: float


class AlphadvantageAPI:
    """
    Stock API. See https://www.alphavantage.co/documentation/
    """

    BASE_URL = 'https://www.alphavantage.co/query'
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    def get_daily_history(self, currency: str):
        """
        Calculates open, high, low, close, volume for given cryptocurrency
        """
        params = {
            'function': 'CRYPTO_INTRADAY',
            'symbol': currency,
            'market': ExchangeMarket.USD.value,
            'interval': '5min',
        }
        data = self._make_request(
            url=self.BASE_URL,
            method='get',
            params=params,
        )

        return data.get('Time Series Crypto (5min)', {})

    def get_volatility(
        self,
        currency: str
    ) -> Optional[Dict[int, VolatilityValue]]:
        daily_history = self.get_daily_history(currency)

        if not daily_history:
            return None

        price_data = []
        for timestamp, data in daily_history.items():
            price_data.append(
                HistoryData(
                    timestamp=datetime.strptime(
                        timestamp, self.DATETIME_FORMAT
                    ),
                    value=float(data.get('4. close'))
                )
            )

        sorted_price_data = sorted(
            price_data,
            key=lambda x: x.timestamp,
            reverse=True
        )
        latest_value = sorted_price_data[0].value

        try:
            five_min_ago = sorted_price_data[1].value
            fifteen_min_ago = sorted_price_data[3].value
            thirty_min_ago = sorted_price_data[6].value
            hour_ago = sorted_price_data[12].value
        except KeyError:
            raise Exception('history data is empty')

        return {
            5: VolatilityValue.calculate(five_min_ago, latest_value),
            15: VolatilityValue.calculate(fifteen_min_ago, latest_value),
            30: VolatilityValue.calculate(thirty_min_ago, latest_value),
            60: VolatilityValue.calculate(hour_ago, latest_value),
        }

    def _make_request(self, method: str, url: str, params: dict):
        response = requests.request(
            method=method,
            url=url,
            params={
                'apikey': ALPHAVANTAGE_API_KEY,
                **params,
            }
        )

        response.raise_for_status()

        return response.json()
