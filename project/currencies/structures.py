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
    x1: float  # old price
    x2: float  # latest price

    @classmethod
    def calculate(cls, x1: float, x2: float) -> 'VolatilityValue':
        volatility = (x2 - x1) / x1 * 100 if x1 != x2 else 0.0

        ratio =  Ratio.BALANCE
        if volatility:
            ratio = Ratio.UPSIDE if volatility > 0 else Ratio.DOWNSIDE

        return VolatilityValue(
            ratio=ratio,
            volatility=round(abs(volatility), 1),
            x1=round(x1, 3),
            x2=round(x2, 3),
        )

    def calculate_lower_value(self, x: float, percent_change: float) -> float:
        value = x * (1 - percent_change / 100)
        return round(value, 3)

    def calculate_upper_value(self, x: float, percent_change: float) -> float:
        value = x * (1 + percent_change / 100)
        return round(value, 3)


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


ICON_ALERT = '\U0000203C'
