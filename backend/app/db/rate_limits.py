"""Database-backed rate limiter with the same interface as RateLimiter in
app/core/limiter.py. See RateHit for why it exists.

Each acquire runs in one transaction. On Postgres a transaction-scoped
advisory lock on the bucket serializes concurrent requests for the same
user, so a burst cannot all pass the count before any of them is recorded.
A database error fails open, with a log line: a blip should not lock every
user out, and the LLM providers' own quotas still bound the damage.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import RateHit

logger = logging.getLogger(__name__)


class DbRateLimiter:
    def __init__(self, engine, per_hour: int, per_day: int, prefix: str):
        self._engine = engine
        self.per_hour = per_hour
        self.per_day = per_day
        self._prefix = prefix

    def acquire(self, key: str) -> bool:
        bucket = f"{self._prefix}:{key}"
        now = datetime.now(UTC)
        try:
            with self._engine.begin() as conn:
                if conn.dialect.name == "postgresql":
                    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:b))"), {"b": bucket})
                conn.execute(
                    delete(RateHit).where(
                        RateHit.bucket == bucket, RateHit.created_at < now - timedelta(days=1)
                    )
                )
                day = conn.execute(
                    select(func.count()).where(RateHit.bucket == bucket)
                ).scalar_one()
                hour = conn.execute(
                    select(func.count()).where(
                        RateHit.bucket == bucket, RateHit.created_at >= now - timedelta(hours=1)
                    )
                ).scalar_one()
                if hour >= self.per_hour or day >= self.per_day:
                    return False
                conn.execute(RateHit.__table__.insert().values(bucket=bucket, created_at=now))
                return True
        except SQLAlchemyError:
            logger.warning("rate limit check failed; allowing the request", exc_info=True)
            return True

    def release(self, key: str) -> None:
        """Refunds the most recent hit, as RateLimiter.release does."""
        bucket = f"{self._prefix}:{key}"
        try:
            with self._engine.begin() as conn:
                newest = conn.execute(
                    select(func.max(RateHit.id)).where(RateHit.bucket == bucket)
                ).scalar_one()
                if newest is not None:
                    conn.execute(delete(RateHit).where(RateHit.id == newest))
        except SQLAlchemyError:
            logger.warning("rate limit refund failed", exc_info=True)
