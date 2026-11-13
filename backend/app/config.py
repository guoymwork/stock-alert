"""
Application configuration constants.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# SQLite database
# 容器部署时可用 STOCK_ALERT_DB_PATH 指向挂载卷（如 /app/data/stock.db）
DB_PATH = os.environ.get("STOCK_ALERT_DB_PATH") or os.path.join(DATA_DIR, "stock.db")

# Cache TTL (seconds) — still used as default TTL parameter
CACHE_TTL = 300          # kline (historical)
CACHE_TTL_QUOTE = 5       # real-time quotes
CACHE_TTL_INTRADAY = 5     # intraday data

# Supported markets
SUPPORTED_MARKETS = ["SH", "SZ", "HK"]

MARKET_NAMES = {
    "SH": "上海",
    "SZ": "深圳",
    "HK": "港股",
}
