# 00: Shared Contract

## Scope

Python 3.12, Streamlit, gspread, google-auth, OpenAI SDK, Pydantic, pandas and tenacity.
One private synthetic Google spreadsheet, one `Messages` worksheet, one writer at a time.
Manual processing only. Google Sheets is the durable source of truth. No separate database,
background workers, orchestration framework, automatic replies, refunds or support actions.

## Data

Exact A:L headers, in order:

```text
message_id,raw_message,category,priority,sentiment,suggested_action,status,fingerprint,processed_at,error_code,model,prompt_version
```

The owner supplies unique immutable string IDs. Runtime writes only C:L. Preserve original input.
Ignore wholly empty rows. Reject missing/duplicate/padded IDs, invalid headers, unknown status or
more than 500 records before paid calls. Reject blank messages and messages over 6,000 characters
per record as `invalid`; never silently truncate. Process at most five candidates per run.

`Insight` has four required fields, with no additional fields:

- Category: Billing, Technical, AccountAccess, FeatureRequest, General, Other.
- Priority: Low, Medium, High, Critical.
- Sentiment: Positive, Neutral, Negative, Mixed.
- Suggested action: nonempty English next step, 1-400 characters, for human review.

Stored status: pending, processed, error, invalid. Blank means pending.
Fingerprint is SHA-256 of compact UTF-8 JSON `[exact message, model, prompt version, schema version]`.
Both versions initially equal `v1`. Current processed status also requires valid insight fields,
UTC ISO timestamp, matching model/prompt metadata and no error code.
Changed inputs/configuration or malformed saved results become pending. Exclude stale insights
from successful-result metrics. Unchanged errors require explicit retry; unchanged invalid records
are skipped unless selected manually or changed.

## Interfaces

- `SheetRecord`: ID, original text, actual row number, ten output cells.
- `PendingWrite`: original snapshot and replacement output cells.
- `SheetsRepository.read_records()`: validated records.
- `SheetsRepository.write_results(writes)`: persisted/conflict IDs; sanitized persistence failure.
- `LLMExtractor.extract(text)`: validated `Insight`, row error or fatal configuration error.
- `Pipeline.process(mode, selected_ids, limit, on_progress)`: `RunSummary`.
- Modes: pending, retry_errors, selected. Selected explicitly reprocesses provided IDs only.

Success means acknowledged/reconciled persistence, not just an LLM response. A save retry must not
repeat paid extraction. Local files and session state are not durable processing checkpoints.

## Operating boundary

Do not edit/sort the worksheet during a run. Do not run local/cloud writers against the same sheet
simultaneously. A process lock cannot coordinate separate deployments or manual editors. Rereading
before writes is not compare-and-swap. A crash before persistence may lead to another paid call.
Public data is synthetic; this demo does not claim production authentication or privacy compliance.