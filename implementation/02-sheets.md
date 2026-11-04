# 02: Google Sheets Adapter

## Goal and ownership

Requires 01 and shared contract 00. Budget: 55 minutes. Own `sheets.py` and `test_sheets.py`.
Parallel-safe with the LLM adapter. Do not create another record schema or local checkpoint file.

## Reads

Create google-auth credentials from the configured mapping with spreadsheet read/write scope.
Authorize gspread, set a 20-second timeout, open by spreadsheet ID and select the configured tab.
Avoid Drive search, broad Drive scope and interactive OAuth.

Bulk-read values as strings. Validate exact headers and row count. Enumerate physical row positions
before ignoring empty rows; pad omitted trailing cells. Preserve leading-zero IDs and Unicode.
Do not expect a `_row` property from gspread records. Reject duplicate/missing IDs before writes.

## Writes and recovery

Accept at most five uniquely identified `PendingWrite` objects. Reread the sheet before each
write attempt and locate current positions by ID. Verify exact original text and output snapshot.
Missing/changed records become conflicts and are left untouched. If current outputs already match
the intended payload, reconcile as persisted. Freeze payload timestamps across retries.

Batch-update only C:L with `value_input_option=RAW`; strings resembling formulas remain literal.
Never clear a sheet, overwrite A:B, append duplicate result rows, or perform per-cell writes.
If the write response is lost, the next attempt rereads and reconciles before sending again.
After bounded recovery, surface `sheet_write_unconfirmed` and known persisted/conflict IDs.
Do not call the LLM from this adapter.

Reread and write are separate operations. No atomic compare-and-swap guarantee exists here:
the supported demo prohibits simultaneous manual edits and additional writers.

## Acceptance

Tests cover wrong headers, duplicate/missing IDs, blank rows, leading zeros, missing trailing
cells, row reorder before commit, deleted/changed records, literal formula-like text, untouched
inputs, RAW batch mode, transient failures, permissions and timeout-after-success reconciliation.
With credentials, write/reread one synthetic record and confirm original inputs are unchanged.
Handoff adapter interfaces, error behavior and whether live access has actually been checked.

Reference: https://docs.gspread.org/en/latest/api/models/worksheet.html