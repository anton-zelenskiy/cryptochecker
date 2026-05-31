from __future__ import annotations

import pytest

from project.screener.indicator_format import format_indicator_value, format_screener_context_suffix


def test_format_indicator_value_rounds_to_four_decimals() -> None:
    assert format_indicator_value(57.576716307759526) == "57.5767"
    assert format_indicator_value(1.1714678926177176e-05) == "0.0000"
    assert format_indicator_value(15.270724131622726) == "15.2707"


def test_format_indicator_value_none() -> None:
    assert format_indicator_value(None) == "n/a"


def test_format_screener_context_suffix() -> None:
    text = format_screener_context_suffix(
        decision_str="WAIT",
        decision_conf=0.2,
        rsi=57.576716307759526,
        macd=1.1714678926177176e-05,
        adx=15.270724131622726,
    )
    assert text == (
        "Screener context: WAIT conf=0.2000 "
        "rsi14=57.5767 macd_hist=0.0000 adx14=15.2707"
    )
