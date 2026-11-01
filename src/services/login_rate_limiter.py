"""Thread-safe in-memory rate limiting for login attempts."""

import math
import threading
import time
from collections import deque


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 15 * 60,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, client_id: str, now: float) -> None:
        attempts = self._attempts.get(client_id)

        if attempts is None:
            return

        cutoff = now - self.window_seconds

        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

        if not attempts:
            self._attempts.pop(client_id, None)

    def retry_after(self, client_id: str) -> int | None:
        """Return remaining block time, or None if the client is allowed."""

        with self._lock:
            now = time.monotonic()
            self._prune(client_id, now)

            attempts = self._attempts.get(client_id)

            if attempts is None or len(attempts) < self.max_attempts:
                return None

            remaining = self.window_seconds - (now - attempts[0])
            return max(1, math.ceil(remaining))

    def record_failure(self, client_id: str) -> None:
        """Record one failed login attempt."""

        with self._lock:
            now = time.monotonic()
            self._prune(client_id, now)

            attempts = self._attempts.setdefault(
                client_id,
                deque(),
            )
            attempts.append(now)

    def clear(self, client_id: str) -> None:
        """Clear failed attempts after successful authentication."""

        with self._lock:
            self._attempts.pop(client_id, None)


login_rate_limiter = LoginRateLimiter()