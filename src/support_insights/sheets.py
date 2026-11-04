from collections.abc import Callable

import gspread
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from requests.exceptions import RequestException

from support_insights.config import Settings
from support_insights.models import (
    HEADERS,
    MAX_PER_RUN,
    MAX_ROWS,
    STATUSES,
    ContractError,
    FatalError,
    PendingWrite,
    PersistenceError,
    SheetRecord,
    WriteReport,
)
from support_insights.retries import execute

SHEETS_ERRORS = (gspread.exceptions.GSpreadException, GoogleAuthError, RequestException)


def parse_records(values: list[list[str]]) -> list[SheetRecord]:
    if not values or tuple(values[0]) != HEADERS:
        raise ContractError("sheet_headers_invalid")
    records = []
    seen = set()
    for row_number, raw in enumerate(values[1:], start=2):
        if not any(raw):
            continue
        if len(raw) > len(HEADERS):
            raise ContractError("sheet_columns_invalid")
        cells = [str(value) for value in raw] + [""] * (len(HEADERS) - len(raw))
        identifier = cells[0]
        if not identifier.strip() or identifier != identifier.strip():
            raise ContractError("message_id_missing_or_padded")
        if identifier in seen:
            raise ContractError("message_id_duplicate")
        if cells[6] not in STATUSES:
            raise ContractError("unknown_status")
        seen.add(identifier)
        records.append(SheetRecord(identifier, cells[1], row_number, tuple(cells[2:])))
        if len(records) > MAX_ROWS:
            raise ContractError("sheet_row_limit_exceeded")
    return records


class SheetsRepository:
    def __init__(self, worksheet, retry: Callable = execute):
        self.worksheet = worksheet
        self.retry = retry

    @classmethod
    def connect(cls, settings: Settings) -> "SheetsRepository":
        if not settings.read_ready():
            raise FatalError("sheet_configuration_missing")

        def connect():
            credentials = Credentials.from_service_account_info(
                settings.service_account,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            client = gspread.authorize(credentials)
            client.set_timeout(20)
            return client.open_by_key(settings.sheet_id).worksheet(settings.worksheet)

        try:
            return cls(execute(connect))
        except (*SHEETS_ERRORS, ValueError, KeyError):
            raise FatalError("sheet_connection_failed") from None

    def _read_once(self) -> list[SheetRecord]:
        return parse_records(self.worksheet.get_all_values())

    def read_records(self) -> list[SheetRecord]:
        try:
            return self.retry(self._read_once)
        except SHEETS_ERRORS:
            raise FatalError("sheet_read_failed") from None

    def write_results(self, writes: list[PendingWrite]) -> WriteReport:
        identifiers = {item.original.message_id for item in writes}
        if len(writes) > MAX_PER_RUN or len(identifiers) != len(writes):
            raise ContractError("write_batch_invalid")
        if any(len(item.outputs) != 10 for item in writes):
            raise ContractError("write_columns_invalid")
        report = WriteReport()
        remaining = {item.original.message_id: item for item in writes}

        def commit():
            current = {row.message_id: row for row in self._read_once()}
            updates = []
            sending = []
            for identifier, item in list(remaining.items()):
                record = current.get(identifier)
                if record is None or record.raw_message != item.original.raw_message:
                    report.conflicts.add(identifier)
                    del remaining[identifier]
                elif record.outputs == item.outputs:
                    report.persisted.add(identifier)
                    del remaining[identifier]
                elif record.outputs != item.original.outputs:
                    report.conflicts.add(identifier)
                    del remaining[identifier]
                else:
                    updates.append({"range": f"C{record.row_number}:L{record.row_number}",
                                    "values": [list(item.outputs)]})
                    sending.append(identifier)
            if updates:
                self.worksheet.batch_update(updates, value_input_option="RAW")
                report.persisted.update(sending)
                for identifier in sending:
                    del remaining[identifier]

        try:
            if writes:
                self.retry(commit)
        except (*SHEETS_ERRORS, ContractError):
            raise PersistenceError("sheet_write_unconfirmed", report) from None
        return report