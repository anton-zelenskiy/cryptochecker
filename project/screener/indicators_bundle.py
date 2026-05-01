from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import MFIIndicator, OnBalanceVolumeIndicator


def _last_float(s: pd.Series) -> float | None:
    if s is None or len(s) == 0:
        return None
    v = s.iloc[-1]
    return float(v) if pd.notna(v) else None


def compute_indicator_bundle_row(
    *,
    high: list[float],
    low: list[float],
    close: list[float],
    volume: list[float],
) -> dict[str, float | None]:
    if len(close) < 60:
        return {}

    h = pd.Series(high, dtype="float64")
    l = pd.Series(low, dtype="float64")
    c = pd.Series(close, dtype="float64")
    v = pd.Series(volume, dtype="float64")

    if v.sum() == 0 or v.isna().all():
        v = pd.Series([1e-12] * len(c), dtype="float64")

    rsi = RSIIndicator(close=c, window=14).rsi()
    ema20 = EMAIndicator(close=c, window=20).ema_indicator()
    ema50 = EMAIndicator(close=c, window=50).ema_indicator()
    ema200 = EMAIndicator(close=c, window=200).ema_indicator() if len(c) >= 200 else None
    macd_ind = MACD(close=c)
    macd_line = macd_ind.macd()
    macd_sig = macd_ind.macd_signal()
    macd_hist = macd_ind.macd_diff()
    atr = AverageTrueRange(high=h, low=l, close=c, window=14).average_true_range()
    adx = ADXIndicator(high=h, low=l, close=c, window=14).adx()
    bb = BollingerBands(close=c, window=20, window_dev=2)
    mfi = MFIIndicator(high=h, low=l, close=c, volume=v, window=14).money_flow_index()
    obv = OnBalanceVolumeIndicator(close=c, volume=v).on_balance_volume()
    st = StochRSIIndicator(close=c, window=14, smooth1=3, smooth2=3)

    row: dict[str, float | None] = {
        "rsi_14": _last_float(rsi),
        "ema_20": _last_float(ema20),
        "ema_50": _last_float(ema50),
        "ema_200": _last_float(ema200) if ema200 is not None else None,
        "macd": _last_float(macd_line),
        "macd_signal": _last_float(macd_sig),
        "macd_hist": _last_float(macd_hist),
        "atr_14": _last_float(atr),
        "adx_14": _last_float(adx),
        "bb_upper": _last_float(bb.bollinger_hband()),
        "bb_mid": _last_float(bb.bollinger_mavg()),
        "bb_lower": _last_float(bb.bollinger_lband()),
        "mfi_14": _last_float(mfi),
        "obv": _last_float(obv),
        "stochrsi_k": _last_float(st.stochrsi_k()),
        "stochrsi_d": _last_float(st.stochrsi_d()),
    }
    return row
