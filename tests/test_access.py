from unittest.mock import Mock

import pytest

from support_insights.access import JobGuard, password_matches, run_authorized
from support_insights.config import Settings
from support_insights.models import FatalError


def ready_settings():
    return Settings(sheet_id="sheet", api_key="test", password="a" * 24,
                    service_account={"test": "test"}, processing_enabled=True)


def test_password_check_and_missing_password():
    assert password_matches("a" * 24, "a" * 24)
    assert not password_matches("wrong", "a" * 24)
    assert not password_matches("", "")


def test_unauthorized_callback_does_not_create_pipeline():
    factory = Mock()
    with pytest.raises(FatalError, match="not_authorized"):
        run_authorized(ready_settings(), False, JobGuard(), factory)
    factory.assert_not_called()


def test_disabled_processing_denies_authenticated_session():
    with pytest.raises(FatalError, match="not_authorized"):
        run_authorized(Settings(), True, JobGuard(), Mock())


def test_lock_contention_and_release_on_error():
    guard = JobGuard(cooldown=0)
    with guard.claim():
        with pytest.raises(FatalError, match="busy"):
            with guard.claim():
                pass
    with pytest.raises(ValueError):
        with guard.claim():
            raise ValueError()
    with guard.claim():
        assert guard.lock.locked()


def test_shared_cooldown():
    guard = JobGuard(clock=lambda: 100)
    with guard.claim():
        pass
    with pytest.raises(FatalError, match="cooldown"):
        with guard.claim():
            pass