from dataclasses import dataclass
from enum import Enum
from datetime import datetime

import requests

from project.config import ALPHAVANTAGE_API_KEY


class ExchangeMarket(Enum):
    USD = 'USD'


class Ratio(Enum):
    UPSIDE = 'upside'
    DOWNSIDE = 'downside'
    BALANCE = 'balance'

    @classmethod
    def get_ratio_display(cls, ratio: 'Ratio'):
        if ratio == cls.DOWNSIDE:
            return 'downside'

        return 'upside'


@dataclass(frozen=True)
class VolatilityValue:
    ratio: Ratio
    volatility: float  # percentage
    latest_value: float
    old_value: float


@dataclass(frozen=True)
class Volatility:
    five_min: VolatilityValue
    fifteen_min: VolatilityValue
    thirty_min: VolatilityValue
    hour: VolatilityValue


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

    def get_volatility(self, currency: str):
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
            5: self.calculate_volatility(latest_value, five_min_ago),
            15: self.calculate_volatility(latest_value, fifteen_min_ago),
            30: self.calculate_volatility(latest_value, thirty_min_ago),
            60: self.calculate_volatility(latest_value, hour_ago),
        }

    def calculate_volatility(self, latest_value, old_value) -> VolatilityValue:
        if latest_value == old_value:
            return VolatilityValue(
                ratio=Ratio.BALANCE,
                volatility=0.0,
                latest_value=latest_value,
                old_value=old_value,
            )

        if latest_value > old_value:
            x1, x2 = latest_value, old_value
            ratio = Ratio.UPSIDE
        else:
            x1, x2 = old_value, latest_value
            ratio = Ratio.DOWNSIDE

        return VolatilityValue(
            ratio=ratio,
            volatility=round((x1 - x2) / x1 * 100, 1),
            latest_value=latest_value,
            old_value=old_value,
        )

    def _get_ratio(self, latest_value, old_value):
        if latest_value == old_value:
            return Ratio.BALANCE
        if latest_value > old_value:
            return Ratio.UPSIDE

        return Ratio.DOWNSIDE

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
