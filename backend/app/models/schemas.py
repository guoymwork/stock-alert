"""
Pydantic models for request/response schemas.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    """Real-time stock quote."""
    symbol: str = Field(..., description="Stock code")
    name: str = Field(default="", description="Stock name")
    price: float = Field(default=0.0, description="Current price")
    change: float = Field(default=0.0, description="Price change")
    change_pct: float = Field(default=0.0, description="Change percentage")
    volume: float = Field(default=0.0, description="Trading volume")
    market: str = Field(default="", description="Market code (SH/SZ/HK)")
    high: float = Field(default=0.0, description="Today high")
    low: float = Field(default=0.0, description="Today low")
    open: float = Field(default=0.0, description="Today open")
    prev_close: float = Field(default=0.0, description="Previous close")
    turnover: float = Field(default=0.0, description="Turnover amount")
    timestamp: Optional[str] = Field(default=None, description="Quote timestamp")


class KlineData(BaseModel):
    """K-line (candlestick) data point."""
    timestamp: str = Field(..., description="Datetime string")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(default=0.0, description="Volume")


class MacdData(BaseModel):
    """MACD indicator data point."""
    timestamp: str = Field(..., description="Datetime string")
    dif: float = Field(..., description="DIF line")
    dea: float = Field(..., description="DEA line (signal)")
    macd: float = Field(..., description="MACD histogram")


class CrossoverInfo(BaseModel):
    """MACD crossover detection result."""
    type: str = Field(default="none", description="golden_cross / death_cross / none")
    message: str = Field(default="", description="Human-readable description")
    dif: Optional[float] = None
    dea: Optional[float] = None


class IntradayMacdResponse(BaseModel):
    """Intraday MACD response with crossover info."""
    symbol: str
    market: str
    macd: List[MacdData]
    crossover: CrossoverInfo


class DetailResponse(BaseModel):
    """Combined stock detail response."""
    quote: Optional[StockQuote] = None
    kline: List[KlineData] = []
    macd: List[MacdData] = []
    crossover: CrossoverInfo = Field(default_factory=CrossoverInfo)


class WatchlistItem(BaseModel):
    """Watchlist entry."""
    symbol: str = Field(..., description="Stock code")
    name: str = Field(default="", description="Stock name")
    market: str = Field(..., description="Market code")
    added_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Added timestamp",
    )


class BatchCodesRequest(BaseModel):
    """Request body for batch adding codes."""
    codes: str = Field(..., description="Space-separated stock codes, e.g. '600519 hk00700 000001'")


class ApiResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool = True
    message: str = ""
    data: Optional[object] = None
