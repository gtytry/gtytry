import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        window_start = now - 60
        events = self._events[user_id]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True
