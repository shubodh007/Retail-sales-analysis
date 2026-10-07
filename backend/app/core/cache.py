"""Tiny bounded TTL cache for immutable, dataset-scoped read models.

Datasets are immutable after status=ready, so caching aggregate responses is
safe and removes repeated dashboard round trips without introducing Redis.
The cache is process-local by design; every worker remains correct because a
cache miss simply executes the same SQL query.
"""
from collections import OrderedDict
from threading import RLock
from time import monotonic
from typing import Any


class TTLCache:
    def __init__(self, maxsize: int = 128, ttl_s: float = 120.0):
        self.maxsize = maxsize
        self.ttl_s = ttl_s
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str):
        now = monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: Any):
        with self._lock:
            self._items[key] = (monotonic() + self.ttl_s, value)
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

    def clear(self):
        with self._lock:
            self._items.clear()


analytics_cache = TTLCache(maxsize=192, ttl_s=120)
