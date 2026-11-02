"""DbRateLimiter keeps the in-memory limiter's contract: both windows
enforced, release refunds one hit, buckets independent, and a database
error fails open rather than locking every user out."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app.db.models import RateHit
from app.db.rate_limits import DbRateLimiter


def _engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_hour_limit_blocks_and_release_refunds():
    limiter = DbRateLimiter(_engine(), per_hour=2, per_day=10, prefix="analysis")
    assert limiter.acquire("u")
    assert limiter.acquire("u")
    assert not limiter.acquire("u")
    limiter.release("u")
    assert limiter.acquire("u")


def test_day_limit_counts_hits_older_than_an_hour():
    engine = _engine()
    with engine.begin() as conn:
        two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
        conn.execute(
            RateHit.__table__.insert(),
            [{"bucket": "analysis:u", "created_at": two_hours_ago}] * 3,
        )
    limiter = DbRateLimiter(engine, per_hour=10, per_day=3, prefix="analysis")
    assert not limiter.acquire("u")


def test_hits_older_than_a_day_are_pruned():
    engine = _engine()
    with engine.begin() as conn:
        old = datetime.now(UTC) - timedelta(days=2)
        conn.execute(RateHit.__table__.insert(), [{"bucket": "analysis:u", "created_at": old}] * 5)
    limiter = DbRateLimiter(engine, per_hour=10, per_day=3, prefix="analysis")
    assert limiter.acquire("u")
    with engine.connect() as conn:
        assert conn.execute(RateHit.__table__.select()).fetchall().__len__() == 1


def test_buckets_and_prefixes_are_independent():
    engine = _engine()
    analysis = DbRateLimiter(engine, per_hour=1, per_day=10, prefix="analysis")
    auth = DbRateLimiter(engine, per_hour=1, per_day=10, prefix="auth")
    assert analysis.acquire("u")
    assert not analysis.acquire("u")
    assert analysis.acquire("other")
    assert auth.acquire("u")


def test_missing_table_fails_open():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    limiter = DbRateLimiter(engine, per_hour=1, per_day=1, prefix="analysis")
    assert limiter.acquire("u")
    assert limiter.acquire("u")
    limiter.release("u")
