import pytest
from unittest.mock import patch

from .alphavantage_api import (
    AlphadvantageAPI,
    VolatilityValue,
    Ratio,
)


@pytest.fixture()
def f_daily_history():
    return {
        'Meta Data': {
            '1. Information': 'Crypto Intraday (5min) Time Series',
            '2. Digital Currency Code': 'ETH',
            '3. Digital Currency Name': 'Ethereum',
            '4. Market Code': 'USD',
            '5. Market Name': 'United States Dollar',
            '6. Last Refreshed': '2022-03-13 08:55:00',
            '7. Interval': '5min',
            '8. Output Size': 'Compact',
            '9. Time Zone': 'UTC'
        },
        'Time Series Crypto (5min)': {
            '2022-03-13 08:55:00': {
                '1. open': '2577.93000',
                '2. high': '2578.19000',
                '3. low': '2577.80000',
                '4. close': '1000',
                '5. volume': 151
            },
            '2022-03-13 08:50:00': {
                '1. open': '2579.68000',
                '2. high': '2579.69000',
                '3. low': '2576.40000',
                '4. close': '1100',
                '5. volume': 974
            },
            '2022-03-13 08:45:00': {
                '1. open': '2578.90000',
                '2. high': '2579.73000',
                '3. low': '2577.71000',
                '4. close': '1200',
                '5. volume': 352
            },
            '2022-03-13 08:40:00': {
                '1. open': '2579.77000',
                '2. high': '2579.77000',
                '3. low': '2578.00000',
                '4. close': '1200',
                '5. volume': 259
            },
            '2022-03-13 08:35:00': {
                '1. open': '2582.46000',
                '2. high': '2582.46000',
                '3. low': '2579.37000',
                '4. close': '2579.77000',
                '5. volume': 238
            },
            '2022-03-13 08:30:00': {
                '1. open': '2579.39000',
                '2. high': '2583.91000',
                '3. low': '2579.38000',
                '4. close': '2582.45000',
                '5. volume': 958
            },
            '2022-03-13 08:25:00': {
                '1. open': '2576.77000',
                '2. high': '2580.75000',
                '3. low': '2576.35000',
                '4. close': '2000',
                '5. volume': 533
            },
            '2022-03-13 08:20:00': {
                '1. open': '2576.70000',
                '2. high': '2579.78000',
                '3. low': '2575.93000',
                '4. close': '2576.77000',
                '5. volume': 494
            },
            '2022-03-13 08:15:00': {
                '1. open': '2577.31000',
                '2. high': '2581.73000',
                '3. low': '2575.88000',
                '4. close': '2576.69000',
                '5. volume': 859
            },
            '2022-03-13 08:10:00': {
                '1. open': '2580.35000',
                '2. high': '2580.36000',
                '3. low': '2576.76000',
                '4. close': '2577.30000',
                '5. volume': 525
            },
            '2022-03-13 08:05:00': {
                '1. open': '2583.95000',
                '2. high': '2584.79000',
                '3. low': '2578.84000',
                '4. close': '2580.36000',
                '5. volume': 1637
            },
            '2022-03-13 08:00:00': {
                '1. open': '2580.92000',
                '2. high': '2584.65000',
                '3. low': '2580.91000',
                '4. close': '2583.96000',
                '5. volume': 1439
            },
            '2022-03-13 07:55:00': {
                '1. open': '2580.92000',
                '2. high': '2584.65000',
                '3. low': '2580.91000',
                '4. close': '2100',
                '5. volume': 1439
            },
            '2022-03-13 07:50:00': {
                '1. open': '2580.92000',
                '2. high': '2584.65000',
                '3. low': '2580.91000',
                '4. close': '2583.96000',
                '5. volume': 1439
            },
        }
    }


@pytest.fixture()
def m_get_history(f_daily_history):
    with patch(
        'project.api.alphavantage_api.AlphadvantageAPI._make_request',
        return_value=f_daily_history
    ):
        yield


def test_get_volatility(
    m_get_history,
):
    api = AlphadvantageAPI()
    actual = api.get_volatility(currency='ETH')
    assert actual == {
        5: VolatilityValue(
            ratio=Ratio.DOWNSIDE,
            volatility=9.1,
            x1=1100,
            x2=1000,
        ),
        15: VolatilityValue(
            ratio=Ratio.DOWNSIDE,
            volatility=16.7,
            x1=1200,
            x2=1000,
        ),
        30: VolatilityValue(
            ratio=Ratio.DOWNSIDE,
            volatility=50,
            x1=2000,
            x2=1000,
        ),
        60: VolatilityValue(
            ratio=Ratio.DOWNSIDE,
            volatility=52.4,
            x1=2100,
            x2=1000,
        ),
    }


@pytest.mark.parametrize(
    'x1, x2, expected_volatility, expected_ratio',
    [
        (100, 93, 7.0, Ratio.DOWNSIDE),
        (93, 100, 7.5, Ratio.UPSIDE),
    ]
)
def test_calculate_volatility(
    x1,
    x2,
    expected_volatility,
    expected_ratio,
):
    api = AlphadvantageAPI()
    actual = api.calculate_volatility(x1, x2)
    assert actual == VolatilityValue(
        ratio=expected_ratio,
        volatility=expected_volatility,
        x1=x1,
        x2=x2,
    )
