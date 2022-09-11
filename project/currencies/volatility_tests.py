import pytest

from project.currencies.structures import Ratio, VolatilityValue
from project.currencies.volatility import calculate_volatility


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
    actual = calculate_volatility(x1, x2)
    assert actual == VolatilityValue(
        ratio=expected_ratio,
        volatility=expected_volatility,
        x1=x1,
        x2=x2,
    )
