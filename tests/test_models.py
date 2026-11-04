from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from support_insights.config import Settings
from support_insights.models import (
    PROMPT_VERSION,
    ContractError,
    Insight,
    SheetRecord,
    effective_status,
    fingerprint,
)


def test_fingerprint_detects_changes():
    initial = fingerprint("Help", "model")
    assert initial == fingerprint("Help", "model")
    assert all(
        initial != candidate
        for candidate in [
            fingerprint("Help ", "model"),
            fingerprint("Help", "other"),
            fingerprint("Help", "model", "v2"),
            fingerprint("Help", "model", "v1", "v2"),
        ]
    )


def test_current_and_stale_result():
    outputs = (
        "Billing",
        "Medium",
        "Negative",
        "Review the invoice.",
        "processed",
        fingerprint("Help", "model"),
        datetime.now(UTC).isoformat(),
        "",
        "model",
        PROMPT_VERSION,
    )
    assert effective_status(SheetRecord("001", "Help", 2, outputs), "model") == "processed"
    assert effective_status(SheetRecord("001", "Help!", 2, outputs), "model") == "pending"
    assert effective_status(SheetRecord("001", "Help", 2, outputs), "other") == "pending"


@pytest.mark.parametrize("action", ["", "  ", "x" * 401])
def test_invalid_action(action):
    with pytest.raises(ValidationError):
        Insight(category="Billing", priority="High", sentiment="Negative", suggested_action=action)


def test_unknown_status_blocks_processing():
    with pytest.raises(ContractError):
        effective_status(SheetRecord("001", "Help", 2, ("",) * 4 + ("surprise",) + ("",) * 5), "m")


def test_config_denies_processing_without_secrets():
    settings = Settings.from_mapping({})
    assert not settings.read_ready()
    assert not settings.processing_ready()
    assert "test-password" not in repr(Settings(password="test-password"))


@pytest.mark.parametrize(
    ("model", "selected_key"),
    [
        ("gpt-6-luna", "OPENAI_API_KEY"),
        ("gemini/gemini-3.8-flash", "GEMINI_API_KEY"),
        ("deepseek/deepseek-chat", "DEEPSEEK_API_KEY"),
    ],
)
def test_config_selects_only_the_matching_provider_key(model, selected_key):
    secrets = {
        "GOOGLE_SHEET_ID": "sheet",
        "GOOGLE_WORKSHEET": "Messages",
        "LLM_MODEL": model,
        "OPENAI_API_KEY": "openai-secret",
        "GEMINI_API_KEY": "gemini-secret",
        "DEEPSEEK_API_KEY": "deepseek-secret",
        "DEMO_PASSWORD": "p" * 24,
        "PROCESSING_ENABLED": True,
        "gcp_service_account": {"client_email": "service@example.test"},
    }
    settings = Settings.from_mapping(secrets)
    assert settings.api_key == secrets[selected_key]
    assert settings.processing_ready()
    assert secrets[selected_key] not in repr(settings)


def test_config_does_not_fall_back_to_another_provider_key():
    settings = Settings.from_mapping(
        {
            "LLM_MODEL": "gemini/gemini-3.8-flash",
            "OPENAI_API_KEY": "openai-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
        }
    )
    assert settings.api_key == ""
    assert settings.llm_configuration_error == "llm_configuration_missing"


@pytest.mark.parametrize("model", ["gemini/", "deepseek/", "unsupported/model"])
def test_invalid_provider_model_disables_processing(model):
    settings = Settings.from_mapping({"LLM_MODEL": model, "OPENAI_API_KEY": "openai-secret"})
    assert not settings.processing_ready()
    assert settings.llm_configuration_error == "llm_model_unsupported"


def test_unsupported_provider_keeps_read_only_configuration_available():
    settings = Settings.from_mapping(
        {
            "GOOGLE_SHEET_ID": "sheet",
            "gcp_service_account": {"client_email": "service@example.test"},
            "LLM_MODEL": "unsupported/model",
            "OPENAI_API_KEY": "openai-secret",
        }
    )
    assert settings.read_ready()
    assert not settings.processing_ready()
    assert settings.llm_configuration_error == "llm_model_unsupported"
    assert "secret-password" not in repr(Settings(password="secret-password"))
