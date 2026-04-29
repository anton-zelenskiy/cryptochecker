import datetime
from dataclasses import dataclass
from enum import Enum, IntEnum

from project import constants


class AppMode(IntEnum):
    CHECK_SELECTED_COINS = 1
    CHECK_ALL_COINS = 2


class Ratio(Enum):
    UPSIDE = 'upside'
    DOWNSIDE = 'downside'
    BALANCE = 'balance'

    @classmethod
    def get_ratio_display(cls, ratio: 'Ratio') -> str:
        if ratio == cls.DOWNSIDE:
            return constants.ICON_ARROW_DOWN

        return constants.ICON_ARROW_UP


@dataclass(frozen=True)
class Coin:
    currency_code: str
    price: float
    ath: float = 0
    atl: float = 0

    @property
    def price_display(self) -> float:
        return round(self.price, constants.PRECISE)

    def lower_border(self, percent_change: float) -> float:
        value = self.price * (1 - percent_change / 100)
        return round(value, constants.PRECISE)

    def upper_border(self, percent_change: float) -> float:
        value = self.price * (1 + percent_change / 100)
        return round(value, constants.PRECISE)

    @classmethod
    def display(cls, coins: list['Coin'], percentage: int) -> str:
        rows = []
        for coin in coins:
            rows.append(
                f"<i>{coin.currency_code.upper()}</i>: <b>{coin.price_display}$</b> "
                f"(+-{percentage}%: {coin.lower_border(percentage)} - {coin.upper_border(percentage)}); "
                f"ATH: {coin.ath}, ATL: {coin.atl}"
            )

        return '\n'.join(rows)


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
            volatility=round(abs(volatility), 2),
            x1=round(x1, constants.PRECISE),
            x2=round(x2, constants.PRECISE),
        )

    def lower_border(self, percent_change: float) -> float:
        value = self.x2 * (1 - percent_change / 100)
        return round(value, constants.PRECISE)

    def upper_border(self, percent_change: float) -> float:
        value = self.x2 * (1 + percent_change / 100)
        return round(value, constants.PRECISE)

    def display(self, currency: str, minutes_window: int, percentage: int) -> str:
        return (
            f"{constants.ICON_ALERT} {currency}: {minutes_window} min., {self.volatility}% ({Ratio.get_ratio_display(self.ratio)}), "
            f"price: {self.x2} (+- {percentage}% {self.lower_border(percentage)} - {self.upper_border(percentage)}). "
            f"old price: {self.x1}"
        )


@dataclass(frozen=True)
class HistoryData:
    unix_timestamp: int
    value: float


@dataclass(frozen=True)
class CandleData:
    datetime: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    turnover: float = 0

    @property
    def volume_usdt(self) -> float:
        return self.volume * self.close

    @property
    def is_huge_volume(self) -> bool:
        return self.volume_usdt > 500000
