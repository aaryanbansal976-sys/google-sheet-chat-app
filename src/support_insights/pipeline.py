from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol

from support_insights.models import (
    MAX_MESSAGE_CHARS,
    MAX_PER_RUN,
    PROMPT_VERSION,
    ContractError,
    FatalError,
    Insight,
    PendingWrite,
    PersistenceError,
    RowError,
    RunSummary,
    SheetRecord,
    WriteReport,
    effective_status,
    fingerprint,
)


class Repository(Protocol):
    def read_records(self) -> list[SheetRecord]: ...
    def write_results(self, writes: list[PendingWrite]) -> WriteReport: ...


class Extractor(Protocol):
    def extract(self, raw_message: str) -> Insight: ...


class Pipeline:
    def __init__(self, repository: Repository, extractor: Extractor, model: str):
        self.repository = repository
        self.extractor = extractor
        self.model = model

    def process(
        self, mode: str = "pending", selected_ids: Sequence[str] = (),
        limit: int = MAX_PER_RUN, on_progress: Callable[[int, int], None] | None = None,
    ) -> RunSummary:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PER_RUN:
            raise ContractError("run_limit_invalid")
        if mode not in {"pending", "retry_errors", "selected"}:
            raise ContractError("run_mode_invalid")
        records = self.repository.read_records()
        statuses = {record.message_id: effective_status(record, self.model) for record in records}
        if mode == "selected":
            if (not selected_ids or len(selected_ids) > limit
                    or len(set(selected_ids)) != len(selected_ids)
                    or not set(selected_ids).issubset(statuses)):
                raise ContractError("selected_ids_invalid")
            candidates = [record for record in records if record.message_id in selected_ids]
        else:
            wanted = "error" if mode == "retry_errors" else "pending"
            candidates = [
                record for record in records if statuses[record.message_id] == wanted
            ][:limit]
        summary = RunSummary(skipped=len(records) - len(candidates))
        writes = []
        for index, record in enumerate(candidates, start=1):
            insight = None
            status, code, stamp = "processed", "", ""
            if not record.raw_message.strip():
                status, code = "invalid", "message_blank"
            elif len(record.raw_message) > MAX_MESSAGE_CHARS:
                status, code = "invalid", "message_too_long"
            else:
                summary.llm_calls += 1
                try:
                    insight = self.extractor.extract(record.raw_message)
                    stamp = datetime.now(UTC).isoformat()
                except RowError as error:
                    status, code = "error", error.code
                except FatalError as error:
                    summary.abort_code = error.code
                    break
            fields = tuple(insight.model_dump().values()) if insight else ("",) * 4
            outputs = fields + (status, fingerprint(record.raw_message, self.model), stamp, code,
                                self.model, PROMPT_VERSION)
            writes.append(PendingWrite(record, outputs))
            if on_progress:
                on_progress(index, len(candidates))
        if not writes:
            return summary
        try:
            report = self.repository.write_results(writes)
        except PersistenceError as error:
            report = error.report
            summary.abort_code = error.code
            summary.unpersisted = [item.original.message_id for item in writes
                                   if item.original.message_id not in report.persisted
                                   and item.original.message_id not in report.conflicts]
        summary.conflicts = sorted(report.conflicts)
        for item in writes:
            if item.original.message_id in report.persisted:
                match item.outputs[4]:
                    case "processed":
                        summary.processed += 1
                    case "error":
                        summary.errors += 1
                    case "invalid":
                        summary.invalid += 1
        return summary