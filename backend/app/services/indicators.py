"""
Technical indicators calculation (MACD, etc.).
"""
from typing import List, Union

import numpy as np
import pandas as pd

from app.models.schemas import KlineData, MacdData, CrossoverInfo


def _ema(series: pd.Series, span: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def calculate_macd(
    data: Union[List[KlineData], List[float]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> List[MacdData]:
    """
    Calculate MACD indicator.

    Args:
        data: List of KlineData or list of close prices.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal EMA period (default 9).

    Returns:
        List of MacdData with DIF, DEA, MACD histogram.
    """
    if not data:
        return []

    # Extract close prices and timestamps
    if isinstance(data[0], KlineData):
        closes = pd.Series([d.close for d in data])
        timestamps = [d.timestamp for d in data]
    else:
        closes = pd.Series(data)
        timestamps = [str(i) for i in range(len(data))]

    if len(closes) < slow:
        # Not enough data for meaningful MACD
        return []

    # Calculate EMA
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    # DIF = fast EMA - slow EMA
    dif = ema_fast - ema_slow

    # DEA = signal EMA of DIF
    dea = _ema(dif, signal)

    # MACD histogram = 2 * (DIF - DEA)
    macd_hist = 2 * (dif - dea)

    result: List[MacdData] = []
    for i in range(len(closes)):
        result.append(MacdData(
            timestamp=timestamps[i],
            dif=round(float(dif.iloc[i]), 4),
            dea=round(float(dea.iloc[i]), 4),
            macd=round(float(macd_hist.iloc[i]), 4),
        ))

    return result


def detect_crossover(macd_data: List[MacdData]) -> CrossoverInfo:
    """
    Detect MACD crossover from the last 2 data points.

    Returns:
        CrossoverInfo with type: 'golden_cross', 'death_cross', or 'none'.
    """
    if len(macd_data) < 2:
        return CrossoverInfo(type="none", message="数据不足，无法判断金叉/死叉")

    prev = macd_data[-2]
    curr = macd_data[-1]

    # Golden cross: DIF crosses above DEA
    if prev.dif <= prev.dea and curr.dif > curr.dea:
        return CrossoverInfo(
            type="golden_cross",
            message=f"出现金叉信号：DIF({curr.dif:.4f}) 上穿 DEA({curr.dea:.4f})",
            dif=curr.dif,
            dea=curr.dea,
        )

    # Death cross: DIF crosses below DEA
    if prev.dif >= prev.dea and curr.dif < curr.dea:
        return CrossoverInfo(
            type="death_cross",
            message=f"出现死叉信号：DIF({curr.dif:.4f}) 下穿 DEA({curr.dea:.4f})",
            dif=curr.dif,
            dea=curr.dea,
        )

    return CrossoverInfo(
        type="none",
        message="暂无金叉/死叉信号",
        dif=curr.dif,
        dea=curr.dea,
    )
