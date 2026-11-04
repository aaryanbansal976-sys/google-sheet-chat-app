from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from support_insights.models import FatalError


def provider_for_model(model: str) -> str | None:
    if not model:
        return None
    if "/" not in model:
        return "openai"
    provider, separator, model_id = model.partition("/")
    if separator and model_id.strip() and provider in {"gemini", "deepseek"}:
        return provider
    return None


@dataclass(frozen=True)
class Settings:
    sheet_id: str = ""
    worksheet: str = "Messages"
    model: str = "gpt-6-luna"
    api_key: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    service_account: dict[str, Any] = field(default_factory=dict, repr=False)
    processing_enabled: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "Settings":
        enabled = values.get("PROCESSING_ENABLED", False)
        if not isinstance(enabled, bool):
            raise FatalError("PROCESSING_ENABLED_must_be_boolean")
        account = values.get("gcp_service_account", {})
        if not isinstance(account, Mapping):
            raise FatalError("gcp_service_account_must_be_table")
        model = str(values.get("LLM_MODEL", "gpt-6-luna")).strip()
        provider = provider_for_model(model)
        key_name = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }.get(provider, "")
        return cls(
            sheet_id=str(values.get("GOOGLE_SHEET_ID", "")).strip(),
            worksheet=str(values.get("GOOGLE_WORKSHEET", "Messages")).strip(),
            model=model,
            api_key=str(values.get(key_name, "")) if key_name else "",
            password=str(values.get("DEMO_PASSWORD", "")),
            service_account=dict(account),
            processing_enabled=enabled,
        )

    @property
    def llm_configuration_error(self) -> str:
        if not self.model:
            return "llm_configuration_missing"
        if provider_for_model(self.model) is None:
            return "llm_model_unsupported"
        if not self.api_key:
            return "llm_configuration_missing"
        return ""

    def read_ready(self) -> bool:
        return bool(self.sheet_id and self.worksheet and self.service_account)

    def processing_ready(self) -> bool:
        return bool(
            self.read_ready()
            and not self.llm_configuration_error
            and len(self.password) >= 24
            and self.processing_enabled
        )
