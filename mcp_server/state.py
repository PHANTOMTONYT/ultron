"""
In-process cache of the most recent successful tool results, so resources can
expose "last known" data as ambient context without forcing a live re-fetch.
"""

from datetime import datetime, timezone

_cache = {}


def set_cached(key: str, text: str) -> None:
    _cache[key] = {"text": text, "fetched_at": datetime.now(timezone.utc).isoformat()}


def get_cached(key: str):
    return _cache.get(key)
