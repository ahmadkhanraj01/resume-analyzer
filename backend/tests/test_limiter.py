from app.core.limiter import RateLimiter


def test_acquire_consumes_a_slot_immediately():
    limiter = RateLimiter(per_hour=2, per_day=10)
    assert limiter.acquire("u")
    assert limiter.acquire("u")
    # Third call in the same instant is rejected: no window between check
    # and record for parallel requests to slip through.
    assert not limiter.acquire("u")


def test_release_refunds_the_slot():
    limiter = RateLimiter(per_hour=1, per_day=10)
    assert limiter.acquire("u")
    limiter.release("u")
    assert limiter.acquire("u")


def test_users_are_independent():
    limiter = RateLimiter(per_hour=1, per_day=10)
    assert limiter.acquire("a")
    assert limiter.acquire("b")
