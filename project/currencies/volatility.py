from project.api.coingecko import get_daily_currency_history
from .structures import (
    VolatilityValue,
    Ratio,
)


def get_volatility_data(currency_id: str):
    prices_data = get_daily_currency_history(
        currency_id=currency_id,
    )

    sorted_prices_data = sorted(
        prices_data,
        key=lambda x: x.unix_timestamp,
        reverse=True
    )
    latest_value = sorted_prices_data[0].value

    try:
        five_min_ago = sorted_prices_data[1].value
        fifteen_min_ago = sorted_prices_data[3].value
        thirty_min_ago = sorted_prices_data[6].value
        hour_ago = sorted_prices_data[12].value
    except KeyError:
        raise Exception('error getting historical price')

    return {
        5: calculate_volatility(five_min_ago, latest_value),
        15: calculate_volatility(fifteen_min_ago, latest_value),
        30: calculate_volatility(thirty_min_ago, latest_value),
        60: calculate_volatility(hour_ago, latest_value),
    }


def calculate_volatility(x1: float, x2: float) -> VolatilityValue:
    if x1 == x2:
        return VolatilityValue(
            ratio=Ratio.BALANCE,
            volatility=0.0,
            x1=x1,
            x2=x2,
        )

    volatility = (x2 - x1) / x1 * 100

    return VolatilityValue(
        ratio=Ratio.UPSIDE if volatility > 0 else Ratio.DOWNSIDE,
        volatility=round(abs(volatility), 1),
        x1=x1,
        x2=x2,
    )
