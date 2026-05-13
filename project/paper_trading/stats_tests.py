from __future__ import annotations

import pytest

from project.paper_trading.stats import format_win_rate_report_message_ru, win_rate_pct


@pytest.mark.parametrize(
    ("closed", "wins", "expected"),
    [
        (0, 0, None),
        (4, 3, 75.0),
        (3, 1, 33.33),
    ],
)
def test_win_rate_pct(closed: int, wins: int, expected: float | None) -> None:
    assert win_rate_pct(closed_total=closed, wins=wins) == expected


def test_format_win_rate_report_message_ru_with_closed() -> None:
    text = format_win_rate_report_message_ru(
        open_positions=1,
        closed_total=10,
        wins=6,
        losses=3,
        breakeven=1,
        win_rate_pct=60.0,
        avg_pnl_pct_closed=0.42,
    )
    assert "Винрейт: 60.0%" in text
    assert "победы 6" in text
    assert "Средний PnL" in text


def test_format_win_rate_report_message_ru_no_closed() -> None:
    text = format_win_rate_report_message_ru(
        open_positions=0,
        closed_total=0,
        wins=0,
        losses=0,
        breakeven=0,
        win_rate_pct=None,
        avg_pnl_pct_closed=None,
    )
    assert "нет закрытых" in text
    assert "Средний PnL" not in text
