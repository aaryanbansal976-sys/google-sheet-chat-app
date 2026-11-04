from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest
from test_pipeline import FakeExtractor, MemoryRepository

from support_insights import dashboard
from support_insights.access import JobGuard
from support_insights.models import SheetRecord
from support_insights.pipeline import Pipeline


def test_unconfigured_app_is_actionable_without_crashing():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py"))
    app.run(timeout=30)
    assert not app.exception
    assert any("not configured" in warning.value for warning in app.warning)


def configured_app():
    from support_insights.config import Settings
    from support_insights.dashboard import render
    render(Settings(sheet_id="test", api_key="test", password="a" * 24,
                    service_account={"test": "test"}, processing_enabled=True))


def test_anonymous_filter_and_authenticated_processing(monkeypatch):
    repository = MemoryRepository([SheetRecord("001", "Invoice issue", 2)])
    extractor = FakeExtractor()
    loader = Mock(side_effect=lambda *args: (repository.read_records(), "now"))
    factory = Mock(return_value=Pipeline(repository, extractor, "gpt-6-luna"))
    monkeypatch.setattr(dashboard, "load_records", loader)
    monkeypatch.setattr(dashboard, "make_pipeline", factory)
    monkeypatch.setattr(dashboard, "processing_guard", lambda: JobGuard(cooldown=0))
    app = AppTest.from_function(configured_app).run(timeout=30)
    assert not app.exception
    assert extractor.calls == 0
    assert all(button.label != "Process" for button in app.sidebar.button)
    app.text_input[1].set_value("invoice").run()
    factory.assert_not_called()
    app.text_input(key="operator_password").set_value("a" * 24)
    unlock_button = next(button for button in app.sidebar.button
                         if button.label == "Unlock processing")
    unlock_button.click().run()
    assert not app.exception
    process_button = next(button for button in app.sidebar.button if button.label == "Process")
    process_button.click().run(timeout=30)
    assert not app.exception
    assert extractor.calls == 1
    app.run()
    assert extractor.calls == 1
    assert repository.records[0].status == "processed"


def test_stale_insights_are_hidden():
    repository = MemoryRepository([SheetRecord("001", "Help", 2)])
    Pipeline(repository, FakeExtractor(), "old-model").process()
    frame = dashboard.build_frame(repository.records, "new-model")
    assert frame.iloc[0]["Status"] == "pending"
    assert frame.iloc[0]["Category"] == ""