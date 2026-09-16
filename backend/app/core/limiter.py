"""In-process rate limiter behind one interface.

A dict keyed by user id is correct for a single worker on a single instance,
which is what Phase 0 deploys. It becomes wrong the moment a second worker
exists; swap the body of RateLimiter for a Redis-backed one without touching
callers if that day comes.
"""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, per_hour: int, per_day: int):
        self.per_hour = per_hour
        self.per_day = per_day
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> bool:
        """Returns True if the user is under both limits, without recording
        a hit. Use record() to consume one."""
        now = time.time()
        hits = self._prune(user_id, now)
        hour_count = sum(1 for t in hits if now - t < 3600)
        day_count = len(hits)
        return hour_count < self.per_hour and day_count < self.per_day

    def record(self, user_id: str) -> None:
        self._hits[user_id].append(time.time())

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
