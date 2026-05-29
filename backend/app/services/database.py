"""
SQLite database service — single source of truth for watchlist + cache.
"""
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, List, Optional

from app.config import DB_PATH

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Default watchlist: three major indices
# ------------------------------------------------------------------ #
DEFAULT_WATCHLIST = [
    {"symbol": "000001", "name": "上证指数", "market": "SH", "type": "index"},
    {"symbol": "399006", "name": "创业板指", "market": "SZ", "type": "index"},
    {"symbol": "000688", "name": "科创50", "market": "SH", "type": "index"},
]


class Database:
    """SQLite wrapper with auto-init schema and default data."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()
        self._seed_defaults()

    # ---- connection helper ----

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- schema ----

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol   TEXT    NOT NULL,
                    name     TEXT    DEFAULT '',
                    market   TEXT    NOT NULL,
                    type     TEXT    DEFAULT 'stock',   -- stock | index
                    added_at TEXT    NOT NULL,
                    UNIQUE(symbol, market)
                );

                CREATE TABLE IF NOT EXISTS cache (
                    cache_key  TEXT PRIMARY KEY,
                    data       TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    ttl        INTEGER NOT NULL DEFAULT 300
                );

                CREATE TABLE IF NOT EXISTS annotations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol     TEXT NOT NULL,
                    market     TEXT NOT NULL,
                    time       TEXT NOT NULL,
                    price      REAL NOT NULL,
                    text       TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ann_symbol ON annotations(symbol);
            """)

    def _seed_defaults(self):
        """Insert default indices if watchlist is empty."""
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM watchlist").fetchone()
            if row["cnt"] > 0:
                return
            from datetime import datetime
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in DEFAULT_WATCHLIST:
                conn.execute(
                    "INSERT OR IGNORE INTO watchlist (symbol, name, market, type, added_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (item["symbol"], item["name"], item["market"], item["type"], now),
                )
            logger.info("Seeded %d default indices into watchlist", len(DEFAULT_WATCHLIST))

    # ================================================================ #
    #  Watchlist CRUD
    # ================================================================ #

    def get_watchlist(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, name, market, type, added_at FROM watchlist ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def add_to_watchlist(self, symbol: str, name: str, market: str,
                         item_type: str = "stock") -> Optional[dict]:
        """Add one item. Returns the new row dict or None if duplicate."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO watchlist (symbol, name, market, type, added_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (symbol, name, market, item_type, now),
                )
                return {"symbol": symbol, "name": name, "market": market,
                        "type": item_type, "added_at": now}
            except sqlite3.IntegrityError:
                return None  # duplicate

    def remove_from_watchlist(self, symbol: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
            return cur.rowcount > 0

    def watchlist_has(self, symbol: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM watchlist WHERE symbol = ?", (symbol,)
            ).fetchone()
            return row is not None

    # ================================================================ #
    #  Cache (drop-in replacement for FileCache)
    # ================================================================ #

    def cache_get(self, key: str, ttl: int = 300) -> Optional[Any]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data, updated_at, ttl FROM cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            if time.time() - row["updated_at"] > (row["ttl"] or ttl):
                conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
                return None
            return json.loads(row["data"])

    def cache_set(self, key: str, data: Any, ttl: int = 300):
        blob = json.dumps(data, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (cache_key, data, updated_at, ttl) "
                "VALUES (?, ?, ?, ?)",
                (key, blob, time.time(), ttl),
            )

    def cache_delete(self, key: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
            return cur.rowcount > 0

    def cache_clear(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM cache")
            return cur.rowcount

    # ================================================================ #
    #  Annotations
    # ================================================================ #

    def get_annotations(self, symbol: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, symbol, market, time, price, text, created_at FROM annotations WHERE symbol = ? ORDER BY id",
                (symbol,),
            ).fetchall()
            return [dict(r) for r in rows]

    def add_annotation(self, symbol: str, market: str, time: str, price: float, text: str) -> dict:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO annotations (symbol, market, time, price, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (symbol, market, time, price, text, now),
            )
            return {"id": cur.lastrowid, "symbol": symbol, "market": market, "time": time, "price": price, "text": text, "created_at": now}

    def delete_annotation(self, ann_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
            return cur.rowcount > 0
