"""
Stock data API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    ApiResponse,
    CrossoverInfo,
    DetailResponse,
    IntradayMacdResponse,
)
from app.services.data_fetcher import DataFetcher
from app.services.indicators import calculate_macd, detect_crossover
from app.services.stock_list import get_stock_list_service

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
fetcher = DataFetcher()


def _resolve(symbol: str, market: Optional[str] = None):
    """Resolve symbol + market.  Handles 'symbol@market' shorthand."""
    if '@' in symbol:
        parts = symbol.split('@', 1)
        symbol = parts[0]
        market = parts[1]
    if not market:
        market = DataFetcher.detect_market(symbol)
    symbol = DataFetcher._normalize_symbol(symbol, market)
    return symbol, market


# ---- Single stock endpoints (market via query param) ---- #

@router.get("/quote/{symbol}", response_model=ApiResponse)
async def get_quote(symbol: str, market: Optional[str] = Query(None)):
    symbol, market = _resolve(symbol, market)
    quote = fetcher.get_realtime_quote(symbol, market)
    if not quote:
        raise HTTPException(status_code=404, detail=f"未找到股票 {symbol}")
    return ApiResponse(data=quote.model_dump())


@router.get("/intraday/{symbol}", response_model=ApiResponse)
async def get_intraday(symbol: str, market: Optional[str] = Query(None)):
    symbol, market = _resolve(symbol, market)
    data = fetcher.get_intraday_data(symbol, market)
    return ApiResponse(data=[d.model_dump() for d in data])


@router.get("/kline/{symbol}", response_model=ApiResponse)
async def get_kline(
    symbol: str,
    period: str = Query("daily"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
):
    symbol, market = _resolve(symbol, market)
    data = fetcher.get_kline_data(symbol, market, period, start, end)
    return ApiResponse(data=[d.model_dump() for d in data])


@router.get("/macd/{symbol}", response_model=ApiResponse)
async def get_macd(
    symbol: str,
    period: str = Query("daily"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    fast: int = Query(12),
    slow: int = Query(26),
    signal: int = Query(9),
):
    symbol, market = _resolve(symbol, market)
    kline = fetcher.get_kline_data(symbol, market, period, start, end)
    if not kline:
        raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的K线数据")
    macd_data = calculate_macd(kline, fast, slow, signal)
    return ApiResponse(data=[d.model_dump() for d in macd_data])


@router.get("/intraday-macd/{symbol}", response_model=ApiResponse)
async def get_intraday_macd(
    symbol: str,
    market: Optional[str] = Query(None),
    fast: int = Query(12),
    slow: int = Query(26),
    signal: int = Query(9),
):
    symbol, market = _resolve(symbol, market)
    intraday = fetcher.get_intraday_data(symbol, market)
    if not intraday:
        raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的分时数据")
    macd_data = calculate_macd(intraday, fast, slow, signal)
    crossover = detect_crossover(macd_data)
    resp = IntradayMacdResponse(
        symbol=symbol, market=market, macd=macd_data, crossover=crossover,
    )
    return ApiResponse(data=resp.model_dump())


@router.get("/detail/{symbol}", response_model=ApiResponse)
async def get_detail(
    symbol: str,
    market: Optional[str] = Query(None),
    period: str = Query("daily"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    symbol, market = _resolve(symbol, market)
    quote = fetcher.get_realtime_quote(symbol, market)
    kline = fetcher.get_kline_data(symbol, market, period, start, end)
    macd_data = calculate_macd(kline) if kline else []
    crossover = detect_crossover(macd_data) if macd_data else CrossoverInfo()
    detail = DetailResponse(
        quote=quote, kline=kline, macd=macd_data, crossover=crossover,
    )
    return ApiResponse(data=detail.model_dump())


# ---- Batch endpoint ---- #

@router.get("/search", response_model=ApiResponse)
async def search_stocks(q: str = Query(..., min_length=1, description="Search by code, name, or pinyin")):
    """Fuzzy search stocks by code, Chinese name, or pinyin."""
    svc = get_stock_list_service()
    results = svc.search(q, limit=20)
    return ApiResponse(data=results)


@router.get("/batch-quotes", response_model=ApiResponse)
async def get_batch_quotes(symbols: str = Query(...)):
    """
    Fetch quotes for multiple symbols.
    Format: ?symbols=000001@SH,399006@SZ,00700@HK
    """
    codes = [s.strip() for s in symbols.replace(",", " ").split() if s.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="请提供至少一个股票代码")
    results = []
    for code in codes:
        sym, mkt = _resolve(code)
        q = fetcher.get_realtime_quote(sym, mkt)
        if q:
            results.append(q.model_dump())
    return ApiResponse(data=results)
