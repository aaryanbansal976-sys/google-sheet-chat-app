# 04: Processing and Recovery

## Goal and ownership

Requires 02, 03 and shared contract 00. Budget: 75 minutes. Own `pipeline.py` and pipeline tests.
Inject repository/extractor dependencies; do not import the UI. Optional CLI must reuse the service.

## Processing flow

1. Caller obtains the process-wide writer guard; service validates mode and maximum-five limit.
2. Fresh-read validated records; compute effective statuses before paid calls.
3. Pending mode selects new/changed/malformed-result rows; retry_errors selects unchanged errors;
   selected mode reprocesses only explicit existing unique IDs, at most the requested limit.
4. Validate text; blank/overlong input is invalid without a paid request.
5. Extract/validate each eligible message. Isolate row failures and continue other candidates.
6. Stage results and persist one batch of at most five outcomes through the repository.
7. Report durable successes/errors/invalids, conflicts, unpersisted IDs and any abort code.

Browsing filters must not silently change processing scope. A selected run is an explicit overwrite
of that record's prior attempt, including replacement with an error on a failed new attempt.
Success clears old error code and records UTC time, fingerprint, model and prompt version.
Error/invalid clears old insight fields and timestamp and records sanitized error metadata.

Flush already completed outcomes if a later record has a fatal LLM configuration error. On a save
outage, stop and report unconfirmed records; never repeat extraction just to retry persistence.
Conflicts leave existing cells untouched. A normal unchanged rerun makes zero paid calls for current
successful/invalid records. Changed text/model/prompt/schema automatically becomes pending.

Do not persist an in-progress state that could become stuck. Do not maintain local JSON/SQLite
checkpoints. Crashes before a commit can cause another paid analysis on the next run: do not claim
exactly-once execution. Local/cloud writers require separate sheets or mutually exclusive operation.

## Acceptance and handoff

Test partial success, blank/oversized inputs, explicit retries, changed fingerprints, normal rerun,
selected reprocessing, invalid limits/IDs, persistence-before-success, conflict and save failures,
and flushing earlier results on fatal errors. Confirm no extra extraction on save retry.
A real five-row smoke must preserve inputs, save four insights and demonstrate an unchanged no-op.
Handoff exact mode semantics, summary fields and known recovery limitations.