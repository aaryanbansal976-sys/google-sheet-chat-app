import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

HEADERS = (
    "message_id", "raw_message", "category", "priority", "sentiment", "suggested_action",
    "status", "fingerprint", "processed_at", "error_code", "model", "prompt_version",
)
PROMPT_VERSION = "v1"
SCHEMA_VERSION = "v1"
MAX_ROWS = 500
MAX_PER_RUN = 5
MAX_MESSAGE_CHARS = 6000
STATUSES = {"", "pending", "processed", "error", "invalid"}


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["Billing", "Technical", "AccountAccess", "FeatureRequest", "General", "Other"]
    priority: Literal["Low", "Medium", "High", "Critical"]
    sentiment: Literal["Positive", "Neutral", "Negative", "Mixed"]
    suggested_action: str

    @field_validator("suggested_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 400:
            raise ValueError("Action must contain 1-400 characters")
        return value


class AppError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ContractError(AppError):
    pass


class RowError(AppError):
    pass


class FatalError(AppError):
    pass


class PersistenceError(AppError):
    def __init__(self, code: str, report: "WriteReport"):
        super().__init__(code)
        self.report = report


@dataclass(frozen=True)
class SheetRecord:
    message_id: str
    raw_message: str
    row_number: int
    outputs: tuple[str, ...] = ("",) * 10

    @property
    def status(self) -> str:
        return self.outputs[4]

    def insight(self) -> Insight:
        return Insight.model_validate(dict(zip(HEADERS[2:6], self.outputs[:4], strict=True)))


def fingerprint(
    text: str,
    model: str,
    prompt_version: str = PROMPT_VERSION,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    payload = json.dumps([text, model, prompt_version, schema_version], ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def effective_status(record: SheetRecord, model: str) -> str:
    if record.status not in STATUSES:
        raise ContractError("unknown_status")
    if record.outputs[5] != fingerprint(record.raw_message, model):
        return "pending"
    if record.status == "processed":
        try:
            record.insight()
            stamp = datetime.fromisoformat(record.outputs[6])
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                return "pending"
        except (ValidationError, ValueError):
            return "pending"
        if record.outputs[8:] != (model, PROMPT_VERSION) or record.outputs[7]:
            return "pending"
    return record.status or "pending"


@dataclass(frozen=True)
class PendingWrite:
    original: SheetRecord
    outputs: tuple[str, ...]


@dataclass
class WriteReport:
    persisted: set[str] = field(default_factory=set)
    conflicts: set[str] = field(default_factory=set)


@dataclass
class RunSummary:
    processed: int = 0
    errors: int = 0
    invalid: int = 0
    skipped: int = 0
    conflicts: list[str] = field(default_factory=list)
    unpersisted: list[str] = field(default_factory=list)
    llm_calls: int = 0
    abort_code: str | None = None