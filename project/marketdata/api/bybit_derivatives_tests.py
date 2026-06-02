from __future__ import annotations

from project.marketdata.api.bybit_derivatives import _oi_change_pct, _parse_ticker_row
from project.screener.contracts import DerivativesContext
from project.marketdata.api.bybit_derivatives import format_derivatives_telegram_line


def test_parse_ticker_row() -> None:
    mark, oi, funding = _parse_ticker_row(
        {"markPrice": "100.5", "openInterest": "12345.6", "fundingRate": "0.0001"}
    )
    assert mark == 100.5
    assert oi == 12345.6
    assert funding == 0.0001


def test_oi_change_pct() -> None:
    rows = [
        {"openInterest": "1100"},
        {"openInterest": "1000"},
    ]
    assert _oi_change_pct(rows) == 10.0


def test_format_derivatives_telegram_line() -> None:
    line = format_derivatives_telegram_line(
        DerivativesContext(funding_rate=0.00012, oi_change_24h_pct=4.2, unavailable=False)
    )
    assert line is not None
    assert "Funding" in line
    assert "OI" in line
