"""A fake Redis for the distributed rate limiter (05D). It implements the ONE script the limiter sends (``eval`` of ``_REDIS_WINDOW_SCRIPT``) with the same
semantics as the Lua: trim the window, count, refuse at the limit (returning the oldest score), else add a member and set the key TTL. Every command is serialised
by one lock, as Redis serialises a script, so concurrency tests exercise the same atomicity guarantee. It is a model of the interface, NOT a Redis: the real Lua is
only proven by tests/test_redis_limiter_live_05d.py when ``TEST_REDIS_URL`` is set."""

from __future__ import annotations

import fnmatch
import math
import threading

from src.api import rate_limit as rl


class FakeRedis:
    def __init__(self, *, clock=lambda: 0.0) -> None:
        self.clock = clock                      # the SERVER's clock (key expiry); the limiter passes its own ``now`` to the script
        self.zsets: dict[str, list[tuple[float, str]]] = {}
        self.expires: dict[str, float] = {}
        self.commands: list[str] = []
        self.fail: BaseException | None = None   # raised by every command while set (outage simulation)
        self._lock = threading.Lock()

    def _live(self, key: str) -> list[tuple[float, str]]:
        if key in self.expires and self.clock() >= self.expires[key]:
            self.zsets.pop(key, None)
            self.expires.pop(key, None)
        return self.zsets.setdefault(key, [])

    def eval(self, script, numkeys, key, now, window, limit, member):
        assert script == rl._REDIS_WINDOW_SCRIPT, "the fake only models the shipped script"
        assert numkeys == 1
        with self._lock:
            self.commands.append("eval")
            if self.fail is not None:
                raise self.fail
            now, window, limit = float(now), float(window), int(limit)
            z = self._live(key)
            z[:] = [(s, m) for s, m in z if s > now - window]           # ZREMRANGEBYSCORE 0 .. now-window (inclusive)
            if len(z) >= limit:
                oldest = min(z)[0] if z else 0
                return [0, len(z), str(oldest)]                          # Redis returns scores as strings
            z.append((now, member))
            self.expires[key] = self.clock() + math.ceil(window) + 1
            return [1, len(z), 0]

    def scan_iter(self, match="*"):
        with self._lock:
            return iter([k for k in list(self.zsets) if fnmatch.fnmatch(k, match)])

    def delete(self, *keys):
        with self._lock:
            for k in keys:
                self.zsets.pop(k, None)
                self.expires.pop(k, None)

    def keys(self):
        with self._lock:
            return list(self.zsets)
