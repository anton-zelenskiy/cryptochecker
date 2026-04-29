import pytest

from project.marketdata.timeframes import normalize_timeframe


def test_normalize_timeframe_ok():
    tf = normalize_timeframe("5m")
    assert tf.code == "5m"
    assert tf.seconds == 300


def test_normalize_timeframe_bad():
    with pytest.raises(ValueError):
        normalize_timeframe("2m")

