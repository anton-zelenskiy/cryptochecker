from project.api.coingecko import get_daily_currency_history, STEP_MINUTES
from .structures import (
    VolatilityValue,
    Ratio,
)


def get_volatility_data(currency_id: str, minutes: int) -> VolatilityValue:
    prices_data = get_daily_currency_history(
        currency_id=currency_id,
    )

    sorted_prices_data = sorted(
        prices_data,
        key=lambda x: x.unix_timestamp,
        reverse=True
    )
    latest_value = sorted_prices_data[0].value

    index = minutes // STEP_MINUTES

    try:
        minutes_ago = sorted_prices_data[index].value
    except KeyError:
        raise Exception('error getting historical price')

    return calculate_volatility(minutes_ago, latest_value)


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
