"""
Watchlist CRUD API — backed by SQLite.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.schemas import ApiResponse, BatchCodesRequest
from app.services.data_fetcher import DataFetcher
from app.services.database import Database

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_db: Optional[Database] = None
_fetcher: Optional[DataFetcher] = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def _get_fetcher() -> DataFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = DataFetcher()
    return _fetcher


def _parse_codes(codes_str: str):
    """Parse space/comma-separated codes into list of {symbol, market, type}."""
    raw = codes_str.replace(",", " ").split()
    results = []
    for code in raw:
        code = code.strip()
        if not code:
            continue
        market = DataFetcher.detect_market(code)
        symbol = DataFetcher._normalize_symbol(code, market)
        # Rough index detection: 6-digit starting with 399xxx or 000xxx on SH
        item_type = "stock"
        if market == "SZ" and symbol.startswith("399"):
            item_type = "index"
        elif market == "SH" and symbol.startswith("000") and symbol != "000001":
            # 000001 on SH is 上证指数, but 000001 on SZ is 平安银行
            # We rely on explicit market prefix for disambiguation
            pass
        # sh000001 → index
        if market == "SH" and symbol == "000001":
            item_type = "index"
        if market == "SH" and symbol == "000688":
            item_type = "index"
        results.append({"symbol": symbol, "market": market, "type": item_type})
    return results


@router.get("", response_model=ApiResponse)
async def list_watchlist():
    items = _get_db().get_watchlist()
    return ApiResponse(data=items)


@router.post("", response_model=ApiResponse)
async def add_single(
    symbol: str = "",
    market: str = "",
    codes: str = "",
):
    """Add stock(s) via query params."""
    db = _get_db()
    fetcher = _get_fetcher()
    added = []

    if codes:
        entries = _parse_codes(codes)
    elif symbol:
        if not market:
            market = DataFetcher.detect_market(symbol)
        symbol = DataFetcher._normalize_symbol(symbol, market)
        entries = [{"symbol": symbol, "market": market, "type": "stock"}]
    else:
        raise HTTPException(status_code=400, detail="请提供 symbol 或 codes 参数")

    for entry in entries:
        sym, mkt = entry["symbol"], entry["market"]
        name = ""
        try:
            q = fetcher.get_realtime_quote(sym, mkt)
            if q:
                name = q.name
        except Exception:
            pass
        row = db.add_to_watchlist(sym, name, mkt, entry.get("type", "stock"))
        if row:
            added.append(row)

    return ApiResponse(message=f"添加了 {len(added)} 只股票", data=added)


@router.post("/batch", response_model=ApiResponse)
async def batch_add(body: BatchCodesRequest):
    """Batch add stocks. Body: { "codes": "600519 hk00700 000001" }."""
    db = _get_db()
    fetcher = _get_fetcher()
    entries = _parse_codes(body.codes)
    added = []

    for entry in entries:
        sym, mkt = entry["symbol"], entry["market"]
        name = ""
        try:
            q = fetcher.get_realtime_quote(sym, mkt)
            if q:
                name = q.name
        except Exception:
            pass
        row = db.add_to_watchlist(sym, name, mkt, entry.get("type", "stock"))
        if row:
            added.append(row)

    return ApiResponse(message=f"批量添加了 {len(added)} 只股票", data=added)


@router.delete("/{symbol}", response_model=ApiResponse)
async def remove_from_watchlist(symbol: str, market: Optional[str] = None):
    # 传 market 则只删该市场下的这一只，避免上证指数(000001@SH) 与
    # 平安银行(000001@SZ) 互相连坐删除
    if not _get_db().remove_from_watchlist(symbol, market):
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 不在自选列表中")
    return ApiResponse(message=f"已删除 {symbol}")
