import hmac
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager

from support_insights.config import Settings
from support_insights.models import FatalError


def password_matches(supplied: str, expected: str) -> bool:
    return len(expected) >= 24 and hmac.compare_digest(supplied.encode(), expected.encode())


class JobGuard:
    def __init__(self, clock: Callable[[], float] = time.monotonic, cooldown: float = 10):
        self.lock = threading.Lock()
        self.clock = clock
        self.cooldown = cooldown
        self.last_started = float("-inf")

    @contextmanager
    def claim(self):
        if not self.lock.acquire(blocking=False):
            raise FatalError("processing_busy")
        try:
            now = self.clock()
            if now - self.last_started < self.cooldown:
                raise FatalError("processing_cooldown")
            self.last_started = now
            yield
        finally:
            self.lock.release()


def run_authorized(settings: Settings, authenticated: bool, guard: JobGuard,
                   pipeline_factory: Callable, **options):
    if not authenticated or not settings.processing_ready():
        raise FatalError("processing_not_authorized")
    with guard.claim():
        return pipeline_factory().process(**options)