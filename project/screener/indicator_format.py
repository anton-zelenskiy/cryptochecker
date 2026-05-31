from __future__ import annotations


def format_indicator_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def format_screener_context_suffix(
    *,
    decision_str: str,
    decision_conf: float,
    rsi: float | None,
    macd: float | None,
    adx: float | None,
) -> str:
    return (
        f"Screener context: {decision_str} conf={decision_conf:.4f} "
        f"rsi14={format_indicator_value(rsi)} "
        f"macd_hist={format_indicator_value(macd)} "
        f"adx14={format_indicator_value(adx)}"
    )
