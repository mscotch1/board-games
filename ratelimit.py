"""A small token-bucket rate limiter, for the few places a public server needs one."""

import time
from threading import Lock


class RateLimiter:
    """Lets each key do roughly `per_second` things a second, in bursts of up to `burst`.

    Each key has a bucket that fills at `per_second` up to `burst` and is spent one token per
    `allow`. Memory is bounded: with more than `max_keys` buckets, idle (full) ones go first.
    """

    def __init__(self, per_second, burst, *, clock=time.monotonic, max_keys=20_000):
        self._per_second = per_second
        self._burst = burst
        self._clock = clock
        self._max_keys = max_keys
        self._lock = Lock()
        self._buckets = {}  # key -> (tokens, when that was counted)

    def allow(self, key, cost=1):
        """Spend `cost` tokens from `key`'s bucket. Returns False, spending nothing, if there aren't enough."""
        with self._lock:
            now = self._clock()
            tokens, counted_at = self._buckets.get(key, (self._burst, now))
            tokens = min(self._burst, tokens + (now - counted_at) * self._per_second)

            allowed = tokens >= cost
            if allowed:
                tokens -= cost
            self._buckets[key] = (tokens, now)

            if len(self._buckets) > self._max_keys:
                self._prune(now)
            return allowed

    def forget(self, key):
        with self._lock:
            self._buckets.pop(key, None)

    def _prune(self, now):
        # a bucket that has refilled completely is the same as no bucket at all
        for key, (tokens, counted_at) in list(self._buckets.items()):
            if tokens + (now - counted_at) * self._per_second >= self._burst:
                del self._buckets[key]
        if len(self._buckets) > self._max_keys:
            # still too many (a flood of distinct keys): drop the oldest half
            by_age = sorted(self._buckets, key=lambda k: self._buckets[k][1])
            for key in by_age[: len(by_age) // 2]:
                del self._buckets[key]
