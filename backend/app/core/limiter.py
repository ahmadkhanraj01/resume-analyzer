"""In-process rate limiter behind one interface.

A dict keyed by user id is correct for a single worker on a single instance.
It is wrong on a serverless host, where several short-lived copies of the
app each keep their own count, so against Postgres the getters below return
DbRateLimiter (app/db/rate_limits.py) instead. SQLite (local dev, tests)
keeps the in-memory one. Callers see the same acquire/release either way.
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


def _make(per_hour: int, per_day: int, prefix: str):
    # Imported here so app/core does not depend on app/db at import time.
    from app.db.session import engine

    if engine.dialect.name == "sqlite":
        return RateLimiter(per_hour, per_day)
    from app.db.rate_limits import DbRateLimiter

    return DbRateLimiter(engine, per_hour, per_day, prefix)


_limiter = None


def get_limiter(per_hour: int, per_day: int):
    global _limiter
    if _limiter is None:
        _limiter = _make(per_hour, per_day, "analysis")
    return _limiter


_auth_limiter = None


def get_auth_limiter(per_hour: int):
    """Separate instance for register/login, keyed by client IP rather than
    user id. The day limit is the hour limit times 24 so only the hourly
    window is ever the binding one."""
    global _auth_limiter
    if _auth_limiter is None:
        _auth_limiter = _make(per_hour, per_hour * 24, "auth")
    return _auth_limiter
