"""In-process rate limiter behind one interface.

A dict keyed by user id is correct for a single worker on a single instance,
which is what Phase 0 deploys. It becomes wrong the moment a second worker
exists; swap the body of RateLimiter for a Redis-backed one without touching
callers if that day comes.
"""

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, per_hour: int, per_day: int):
        self.per_hour = per_hour
        self.per_day = per_day
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def acquire(self, user_id: str) -> bool:
        """Checks both limits and records a hit in one step. Checking first
        and recording after the 8 to 25 second analysis let a burst of
        parallel requests all pass the check; consuming the slot up front
        closes that window. Call release() if the work then fails so the
        user is not charged for an analysis they never got."""
        now = time.time()
        with self._lock:
            hits = self._prune(user_id, now)
            hour_count = sum(1 for t in hits if now - t < 3600)
            if hour_count >= self.per_hour or len(hits) >= self.per_day:
                return False
            hits.append(now)
            return True

    def release(self, user_id: str) -> None:
        """Refunds the most recent hit."""
        with self._lock:
            hits = self._hits[user_id]
            if hits:
                hits.pop()

    def _prune(self, user_id: str, now: float) -> list[float]:
        hits = [t for t in self._hits[user_id] if now - t < 86400]
        self._hits[user_id] = hits
        return hits


_limiter: RateLimiter | None = None


def get_limiter(per_hour: int, per_day: int) -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(per_hour, per_day)
    return _limiter


_auth_limiter: RateLimiter | None = None


def get_auth_limiter(per_hour: int) -> RateLimiter:
    """Separate instance for register/login, keyed by client IP rather than
    user id. The day limit is the hour limit times 24 so only the hourly
    window is ever the binding one."""
    global _auth_limiter
    if _auth_limiter is None:
        _auth_limiter = RateLimiter(per_hour, per_hour * 24)
    return _auth_limiter
