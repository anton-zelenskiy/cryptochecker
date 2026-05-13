from __future__ import annotations


def win_rate_pct(*, closed_total: int, wins: int) -> float | None:
    if closed_total <= 0:
        return None
    return round(wins / closed_total * 100.0, 2)


def format_win_rate_report_message_ru(
    *,
    open_positions: int,
    closed_total: int,
    wins: int,
    losses: int,
    breakeven: int,
    win_rate_pct: float | None,
    avg_pnl_pct_closed: float | None,
) -> str:
    lines = [
        "Paper trading — сводка стратегии",
        f"Открыто позиций: {open_positions}",
        f"Закрыто сделок: {closed_total}",
    ]
    if win_rate_pct is not None:
        lines.append(f"Винрейт: {win_rate_pct}% (победы {wins} / убытки {losses} / в ноль {breakeven})")
    else:
        lines.append("Винрейт: нет данных (нет закрытых сделок)")
    if avg_pnl_pct_closed is not None:
        lines.append(f"Средний PnL по закрытым: {avg_pnl_pct_closed:.2f}%")
    return "\n".join(lines)
