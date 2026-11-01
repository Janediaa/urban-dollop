import time

from src.services.login_rate_limiter import LoginRateLimiter


def test_allows_requests_below_limit():
    limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)

    for _ in range(4):
        limiter.record_failure("client-a")

    assert limiter.retry_after("client-a") is None


def test_blocks_after_maximum_failed_attempts():
    limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)

    for _ in range(5):
        limiter.record_failure("client-a")

    assert limiter.retry_after("client-a") is not None


def test_different_clients_have_independent_limits():
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=900)

    limiter.record_failure("client-a")
    limiter.record_failure("client-a")

    assert limiter.retry_after("client-a") is not None
    assert limiter.retry_after("client-b") is None


def test_successful_login_can_clear_failed_attempts():
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=900)

    limiter.record_failure("client-a")
    limiter.record_failure("client-a")

    limiter.clear("client-a")

    assert limiter.retry_after("client-a") is None


def test_attempts_expire_after_window(monkeypatch):
    import src.services.login_rate_limiter as rate_limiter_module

    current_time = [1000.0]
    monkeypatch.setattr(
        rate_limiter_module.time,
        "monotonic",
        lambda: current_time[0],
    )

    limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)

    limiter.record_failure("client-a")
    limiter.record_failure("client-a")

    assert limiter.retry_after("client-a") is not None

    current_time[0] = 1061.0

    assert limiter.retry_after("client-a") is None