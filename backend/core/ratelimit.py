"""
Sliding-window rate limiter keyed by client IP.

In-memory and thread-safe. Good enough for a single Render web service; for
horizontal scaling move the window store to Redis.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """
        Register a hit for `key`.

        Returns (allowed, retry_after_seconds). retry_after is 0 when allowed.
        """
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                retry_after = int(self.window - (now - hits[0])) + 1
                return False, max(retry_after, 1)

            hits.append(now)
            # Opportunistic cleanup to keep the dict from growing unbounded.
            if len(self._hits) > 10000:
                self._gc(cutoff)
            return True, 0

    def _gc(self, cutoff: float) -> None:
        empty = [k for k, v in self._hits.items() if not v or v[-1] < cutoff]
        for k in empty:
            self._hits.pop(k, None)
