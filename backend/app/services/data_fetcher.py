"""
Stock data fetching service.
Primary: Sina Finance API (quotes) + Tencent Finance API (kline/minute).
Fallback: AKShare.
"""
import json
import logging
import re
from typing import List, Optional

import requests

from app.models.schemas import KlineData, StockQuote
from app.services.cache import FileCache
from app.config import CACHE_TTL_QUOTE, CACHE_TTL_INTRADAY

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}


class DataFetcher:
    """Fetches stock data from Sina/Tencent APIs with file-based caching."""

    def __init__(self):
        self.cache = FileCache()

    # ------------------------------------------------------------------ #
    #  Market detection & helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def detect_market(code: str) -> str:
        code = code.strip().lower()
        # Explicit prefix: hk00700, sh600519, sz000001
        if code.startswith("hk"):
            return "HK"
        if code.startswith("sh"):
            return "SH"
        if code.startswith("sz"):
            return "SZ"
        # Pure digits
        if len(code) == 5 and code.isdigit():
            return "HK"
        if len(code) == 6 and code.isdigit():
            if code.startswith("6") or code.startswith("5"):
                return "SH"   # A-share + ETF (510xxx, 513xxx...)
            if code.startswith("0") or code.startswith("3") or code.startswith("1"):
                return "SZ"   # A-share + ETF (159xxx)
        return "SH"

    @staticmethod
    def _normalize_symbol(symbol: str, market: str = "") -> str:
        s = symbol.strip()
        # Strip any market prefix: hk, sh, sz (case-insensitive)
        s = re.sub(r"^(?i)(hk|sh|sz)", "", s)
        return s

    def _is_hk(self, market: str) -> bool:
        return market.upper() == "HK"

    def _cache_key(self, market: str, symbol: str, data_type: str) -> str:
        return f"{market}_{symbol}_{data_type}"

    def _sina_code(self, symbol: str, market: str) -> str:
        """Convert to Sina format: sz000001, sh600519, hk00700."""
        m = market.upper()
        if m == "HK":
            return f"hk{symbol}"
        return f"{m.lower()}{symbol}"

    def _tencent_code(self, symbol: str, market: str) -> str:
        """Convert to Tencent format: sz000001, sh600519, hk00700."""
        m = market.upper()
        if m == "HK":
            return f"hk{symbol}"
        return f"{m.lower()}{symbol}"

    # ------------------------------------------------------------------ #
    #  Real-time quotes (Sina API)
    # ------------------------------------------------------------------ #

    def get_realtime_quote(self, symbol: str, market: Optional[str] = None) -> Optional[StockQuote]:
        """Fetch real-time quote via Sina Finance API."""
        symbol = self._normalize_symbol(symbol, market or "")
        if not market:
            market = self.detect_market(symbol)

        cache_key = self._cache_key(market, symbol, "quote")
        cached = self.cache.get(cache_key)
        if cached:
            return StockQuote(**cached)

        try:
            sina_code = self._sina_code(symbol, market)
            url = f"https://hq.sinajs.cn/list={sina_code}"
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            resp.encoding = "gbk"
            text = resp.text.strip()

            if not text or '=""' in text:
                logger.warning("Empty response for %s", symbol)
                return None

            # Parse: var hq_str_sz000001="field1,field2,..."
            raw = text.split('"')[1] if '"' in text else ""
            if not raw:
                return None

            quote = self._parse_sina_quote(raw, symbol, market)
            if quote:
                self.cache.set(cache_key, quote.model_dump(), ttl=CACHE_TTL_QUOTE)
            return quote

        except Exception as e:
            logger.error("Failed to fetch quote for %s: %s", symbol, e)
            return None

    def _parse_sina_quote(self, raw: str, symbol: str, market: str) -> Optional[StockQuote]:
        """Parse Sina API response into StockQuote."""
        fields = raw.split(",")

        if self._is_hk(market):
            # HK format: ename,cname,open,prev_close,high,low,price,change,change_pct,...
            if len(fields) < 9:
                return None
            name = fields[1]
            open_price = float(fields[2] or 0)
            prev_close = float(fields[3] or 0)
            high = float(fields[4] or 0)
            low = float(fields[5] or 0)
            price = float(fields[6] or 0)
            change = float(fields[7] or 0)
            change_pct = float(fields[8] or 0)
            volume = float(fields[12] or 0) if len(fields) > 12 else 0
            turnover = float(fields[11] or 0) if len(fields) > 11 else 0
        else:
            # A-share format: name,open,prev_close,price,high,low,bid,ask,volume,...
            if len(fields) < 9:
                return None
            name = fields[0]
            open_price = float(fields[1] or 0)
            prev_close = float(fields[2] or 0)
            price = float(fields[3] or 0)
            high = float(fields[4] or 0)
            low = float(fields[5] or 0)
            volume = float(fields[8] or 0)  # in shares
            turnover = float(fields[9] or 0) if len(fields) > 9 else 0
            change = round(price - prev_close, 4) if prev_close else 0
            change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        return StockQuote(
            symbol=symbol,
            name=name,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
            market=market,
            high=high,
            low=low,
            open=open_price,
            prev_close=prev_close,
            turnover=turnover,
        )

    # ------------------------------------------------------------------ #
    #  Intraday minute data (Tencent API)
    # ------------------------------------------------------------------ #

    def get_intraday_data(self, symbol: str, market: Optional[str] = None) -> List[KlineData]:
        """Fetch minute-level intraday data via Tencent API."""
        symbol = self._normalize_symbol(symbol, market or "")
        if not market:
            market = self.detect_market(symbol)

        cache_key = self._cache_key(market, symbol, "intraday")
        cached = self.cache.get(cache_key)
        if cached:
            return [KlineData(**d) for d in cached]

        try:
            tcode = self._tencent_code(symbol, market)
            url = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
            resp = requests.get(url, params={"code": tcode}, timeout=8)
            data = resp.json()

            stock_data = data.get("data", {}).get(tcode, {})
            minutes = stock_data.get("data", {}).get("data", [])

            if not minutes:
                return []

            from datetime import date
            today = date.today().isoformat()  # YYYY-MM-DD
            records = []
            for line in minutes:
                parts = line.split()
                if len(parts) < 4:
                    continue
                time_str = parts[0]  # "0930"
                close_price = float(parts[1])
                vol = float(parts[2])
                # Use ISO datetime so lightweight-charts accepts it
                formatted_time = f"{today}T{time_str[:2]}:{time_str[2:]}:00"
                records.append(KlineData(
                    timestamp=formatted_time,
                    open=close_price,
                    high=close_price,
                    low=close_price,
                    close=close_price,
                    volume=vol,
                ))

            self.cache.set(cache_key, [d.model_dump() for d in records], ttl=CACHE_TTL_INTRADAY)
            return records

        except Exception as e:
            logger.error("Failed to fetch intraday data for %s: %s", symbol, e)
            return []

    # ------------------------------------------------------------------ #
    #  Historical K-line (Tencent API)
    # ------------------------------------------------------------------ #

    def get_kline_data(
        self,
        symbol: str,
        market: Optional[str] = None,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[KlineData]:
        """Fetch historical K-line data via Tencent API."""
        symbol = self._normalize_symbol(symbol, market or "")
        if not market:
            market = self.detect_market(symbol)

        cache_key = self._cache_key(market, symbol, f"kline_{period}_{start_date}_{end_date}")
        cached = self.cache.get(cache_key)
        if cached:
            return [KlineData(**d) for d in cached]

        try:
            tcode = self._tencent_code(symbol, market)
            tencent_period = {"daily": "day", "weekly": "week", "monthly": "month"}.get(period, "day")

            start = start_date or "2024-01-01"
            end = end_date or "2026-12-31"
            # Convert YYYYMMDD to YYYY-MM-DD if needed
            if len(start) == 8 and "-" not in start:
                start = f"{start[:4]}-{start[4:6]}-{start[6:]}"
            if len(end) == 8 and "-" not in end:
                end = f"{end[:4]}-{end[4:6]}-{end[6:]}"

            url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "_var": "kline_dayqfq",
                "param": f"{tcode},{tencent_period},{start},{end},500,qfq",
            }
            resp = requests.get(url, params=params, timeout=10)
            text = resp.text

            # Remove JS variable assignment: kline_dayqfq={...}
            if "=" in text:
                text = text[text.index("=") + 1:]

            data = json.loads(text)
            stock_data = data.get("data", {}).get(tcode, {})
            kline_raw = stock_data.get("day") or stock_data.get("qfqday") or stock_data.get(tencent_period) or stock_data.get("qfq" + tencent_period, [])

            if not kline_raw:
                return []

            records = []
            for row in kline_raw:
                # Each row: [date, open, close, high, low, volume, ...]
                if isinstance(row, list) and len(row) >= 6:
                    date_str = str(row[0])
                    records.append(KlineData(
                        timestamp=date_str,
                        open=float(row[1]),
                        high=float(row[3]),
                        low=float(row[4]),
                        close=float(row[2]),
                        volume=float(row[5]),
                    ))

            self.cache.set(cache_key, [d.model_dump() for d in records])
            return records

        except Exception as e:
            logger.error("Failed to fetch kline data for %s: %s", symbol, e)
            return []

    # ------------------------------------------------------------------ #
    #  Batch quotes
    # ------------------------------------------------------------------ #

    def get_batch_quotes(self, codes: List[str]) -> List[StockQuote]:
        """Fetch real-time quotes for multiple symbols via Sina batch API."""
        if not codes:
            return []

        # Build Sina batch request
        sina_codes = []
        code_map = {}  # sina_code -> (symbol, market)
        for code in codes:
            code = code.strip()
            if not code:
                continue
            market = self.detect_market(code)
            symbol = self._normalize_symbol(code, market)
            sc = self._sina_code(symbol, market)
            sina_codes.append(sc)
            code_map[sc] = (symbol, market)

        if not sina_codes:
            return []

        try:
            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            resp.encoding = "gbk"
            lines = resp.text.strip().split("\n")

            results = []
            for line in lines:
                line = line.strip()
                if not line or '=""' in line:
                    continue
                # Extract sina code and raw data
                match = re.match(r'var hq_str_(\w+)="(.*)"', line)
                if not match:
                    continue
                sc = match.group(1)
                raw = match.group(2)
                if sc in code_map:
                    symbol, market = code_map[sc]
                    quote = self._parse_sina_quote(raw, symbol, market)
                    if quote:
                        results.append(quote)

            return results

        except Exception as e:
            logger.error("Failed to fetch batch quotes: %s", e)
            return []
