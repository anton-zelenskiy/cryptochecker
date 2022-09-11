from dataclasses import dataclass
from enum import Enum
import datetime


class Ratio(Enum):
    UPSIDE = 'upside'
    DOWNSIDE = 'downside'
    BALANCE = 'balance'

    @classmethod
    def get_ratio_display(cls, ratio: 'Ratio'):
        if ratio == cls.DOWNSIDE:
            return '\u2B07'  # arrow down

        return '\u2B06'  # up arrow


@dataclass(frozen=True)
class VolatilityValue:
    ratio: Ratio
    volatility: float  # percentage
    x1: float
    x2: float


@dataclass(frozen=True)
class HistoryData:
    unix_timestamp: int
    value: float


@dataclass(frozen=True)
class CurrencyPrice:
    currency_code: str
    price: float


@dataclass(frozen=True)
class CandleData:
    datetime: datetime.datetime
    open: int
    high: int
    low: int
    close: int
