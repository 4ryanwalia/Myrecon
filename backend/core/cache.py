"""Compatibility interface for callers: search-result caching is disabled.

Producers still run normally. No keys, inputs, or result objects are retained.
"""
from typing import Any, Callable, Optional

class TTLCache:
    def __init__(self, ttl=600, max_entries=2000):
        self._store = {}

    def get(self, key):
        return None

    def set(self, key, value, ttl=None):
        pass

    def get_or_set(self, key, producer, ttl=None):
        return producer()

    def clear(self):
        self._store.clear()
