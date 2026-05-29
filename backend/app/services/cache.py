"""
Cache backed by SQLite — drop-in replacement for the old FileCache.
"""
from typing import Any, Optional  # noqa: already imported

from app.config import CACHE_TTL, CACHE_TTL_QUOTE, CACHE_TTL_INTRADAY
from app.services.database import Database

_db: Optional[Database] = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


class FileCache:
    """Cache interface backed by SQLite.  Same API as before."""

    def __init__(self, ttl: int = CACHE_TTL):
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        return _get_db().cache_get(key, self.ttl)

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        _get_db().cache_set(key, data, ttl if ttl is not None else self.ttl)

    def delete(self, key: str) -> bool:
        return _get_db().cache_delete(key)

    def clear(self) -> int:
        return _get_db().cache_clear()
