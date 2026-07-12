"""
Thread-safe in-memory TTL cache.

Deliberately dependency-free so it runs on a single Render instance without
Redis. For multi-instance deployments swap this for a shared store.
"""

import threading
import time
from typing import Any, Callable, Optional


class TTLCache:
    def __init__(self, ttl: int = 600, max_entries: int = 2000):
        self._ttl = ttl
        self._max = max_entries
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # Evict the oldest ~10% of entries to bound memory.
                for stale_key in sorted(
                    self._store, key=lambda k: self._store[k][0]
                )[: max(1, self._max // 10)]:
                    self._store.pop(stale_key, None)
            self._store[key] = (time.time() + (ttl or self._ttl), value)

    def get_or_set(self, key: str, producer: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = producer()
        self.set(key, value, ttl)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
