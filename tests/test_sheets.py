import re

import pytest
from requests.exceptions import Timeout

from support_insights.models import HEADERS, ContractError, PendingWrite
from support_insights.sheets import SheetsRepository, parse_records


class Worksheet:
    def __init__(self):
        self.values = [list(HEADERS), ["001", "Help"] + [""] * 10,
                       ["002", "Other"] + [""] * 10]
        self.calls = 0
        self.lose_response = False

    def get_all_values(self):
        return self.values

    def batch_update(self, updates, value_input_option):
        assert value_input_option == "RAW"
        self.calls += 1
        for update in updates:
            match = re.fullmatch(r"C(\d+):L\1", update["range"])
            assert match
            self.values[int(match[1]) - 1][2:] = update["values"][0]
        if self.lose_response:
            self.lose_response = False
            raise Timeout()


def retry_twice(operation):
    try:
        return operation()
    except Timeout:
        return operation()


def test_preserves_ids_and_blank_row_positions():
    records = parse_records([list(HEADERS), [], ["001", "hello"]])
    assert records[0].row_number == 3
    assert records[0].message_id == "001"
    assert len(records[0].outputs) == 10


@pytest.mark.parametrize("rows", [[], [["wrong"]], [list(HEADERS), ["", "hello"]],
                                  [list(HEADERS), ["001", "a"], ["001", "b"]]])
def test_rejects_bad_contract(rows):
    with pytest.raises(ContractError):
        parse_records(rows)


def test_reorder_and_raw_write():
    worksheet = Worksheet()
    repository = SheetsRepository(worksheet)
    original = repository.read_records()[0]
    worksheet.values[1], worksheet.values[2] = worksheet.values[2], worksheet.values[1]
    output = ("=literal",) + ("",) * 9
    report = repository.write_results([PendingWrite(original, output)])
    assert report.persisted == {"001"}
    assert worksheet.values[2][:3] == ["001", "Help", "=literal"]
    assert worksheet.calls == 1


def test_changed_input_is_conflict():
    worksheet = Worksheet()
    repository = SheetsRepository(worksheet)
    original = repository.read_records()[0]
    worksheet.values[1][1] = "Changed"
    report = repository.write_results([PendingWrite(original, ("x",) * 10)])
    assert report.conflicts == {"001"}
    assert worksheet.calls == 0


def test_lost_success_response_reconciles_without_duplicate_write():
    worksheet = Worksheet()
    worksheet.lose_response = True
    repository = SheetsRepository(worksheet, retry=retry_twice)
    original = repository.read_records()[0]
    output = ("",) * 4 + ("error",) + ("",) * 5
    report = repository.write_results([PendingWrite(original, output)])
    assert report.persisted == {"001"}
    assert worksheet.calls == 1