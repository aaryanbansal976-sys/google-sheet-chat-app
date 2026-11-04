from dataclasses import replace

import pytest

from support_insights.models import (
    ContractError,
    FatalError,
    Insight,
    PersistenceError,
    RowError,
    SheetRecord,
    WriteReport,
)
from support_insights.pipeline import Pipeline


class MemoryRepository:
    def __init__(self, records):
        self.records = records
        self.fail = False

    def read_records(self):
        return self.records

    def write_results(self, writes):
        if self.fail:
            raise PersistenceError("sheet_write_unconfirmed", WriteReport())
        results = {item.original.message_id: item.outputs for item in writes}
        self.records = [replace(record, outputs=results.get(record.message_id, record.outputs))
                        for record in self.records]
        return WriteReport(persisted=set(results))


class FakeExtractor:
    def __init__(self):
        self.calls = 0

    def extract(self, message):
        self.calls += 1
        if message == "refusal":
            raise RowError("llm_refused")
        if message == "fatal":
            raise FatalError("llm_configuration_or_billing_error")
        return Insight(category="Billing", priority="Medium", sentiment="Negative",
                       suggested_action="Review the invoice.")


def test_partial_success_restart_and_changed_input():
    repository = MemoryRepository([SheetRecord("001", "Help", 2), SheetRecord("002", "", 3),
                                   SheetRecord("003", "refusal", 4)])
    extractor = FakeExtractor()
    pipeline = Pipeline(repository, extractor, "model")
    result = pipeline.process()
    assert (result.processed, result.invalid, result.errors, extractor.calls) == (1, 1, 1, 2)
    assert Pipeline(repository, extractor, "model").process().llm_calls == 0
    repository.records[0] = replace(repository.records[0], raw_message="Updated")
    assert pipeline.process().processed == 1
    assert extractor.calls == 3
    assert pipeline.process("retry_errors").errors == 1


def test_write_failure_does_not_repeat_extraction():
    repository = MemoryRepository([SheetRecord("001", "Help", 2)])
    repository.fail = True
    extractor = FakeExtractor()
    result = Pipeline(repository, extractor, "model").process()
    assert result.processed == 0
    assert result.unpersisted == ["001"]
    assert extractor.calls == 1


def test_fatal_error_flushes_earlier_success():
    repository = MemoryRepository([SheetRecord("001", "Help", 2), SheetRecord("002", "fatal", 3)])
    result = Pipeline(repository, FakeExtractor(), "model").process()
    assert result.processed == 1
    assert result.abort_code


@pytest.mark.parametrize("limit", [0, 6, True, 1.5])
def test_core_limit_is_enforced(limit):
    with pytest.raises(ContractError):
        Pipeline(MemoryRepository([]), FakeExtractor(), "model").process(limit=limit)


def test_selected_reprocessing_and_unknown_id():
    repository = MemoryRepository([SheetRecord("001", "Help", 2)])
    pipeline = Pipeline(repository, FakeExtractor(), "model")
    assert pipeline.process().processed == 1
    assert pipeline.process("selected", ["001"]).processed == 1
    with pytest.raises(ContractError):
        pipeline.process("selected", ["missing"])