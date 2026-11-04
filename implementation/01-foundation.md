# 01: Foundation

## Goal and context

Read 00 plus this sheet. Budget: 45 minutes. Establish the package, shared types and safe settings.
Own package metadata, `models.py`, `config.py`, `retries.py`, configuration examples and model tests.

## Implementation

Use an installable `src/support_insights` package, Python 3.12, pytest and Ruff. Keep runtime
dependencies, including the LiteLLM SDK, in `pyproject.toml`; deployment `requirements.txt`
installs `.`. Never make network calls on import. Core models/configuration must not import
Streamlit.

Implement the shared schema, `SheetRecord`, `PendingWrite`, `WriteReport`, `RunSummary`, typed
sanitized errors, fingerprint and effective-status functions. A malformed processed row must not
be displayed as a current successful insight.

`Settings.from_mapping` accepts `GOOGLE_SHEET_ID`, `GOOGLE_WORKSHEET`, `LLM_MODEL`, provider-specific
`OPENAI_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`, `DEMO_PASSWORD`, boolean
`PROCESSING_ENABLED`, and a `gcp_service_account` table. Unprefixed models select legacy OpenAI;
`gemini/` and `deepseek/` prefixes select their corresponding provider and key. Never fall back
to another provider's key. Read readiness does not depend on an LLM key or operator password.
Processing requires all read settings, a valid model/provider and matching API key, enabled flag,
and a password of at least 24 characters. Secret values are excluded from representations, logs
and errors. Ignore the local secrets file and credentials directory.

Network retries: three total attempts, explicit 20-second request timeouts, exponential jitter,
maximum eight-second waits. Respect Retry-After within this bound; surface longer delays instead
of immediate repeated requests. Retry network failures, 429 and transient 5xx. Do not retry invalid
credentials, insufficient credit, unknown models or invalid request/schema errors.

Prepare 30 synthetic records with stable IDs. Include realistic mixed sentiment, varied categories,
multiple languages and one blank message. Oversized/duplicate-ID cases belong in tests, not normal
successful fixtures. Do not add a silent local-data fallback to live processing.

## Owner prerequisites

Select the repository directory. Obtain GitHub/Community Cloud access, an LLM API account and a
Google Cloud project with Sheets API enabled. Create a service account and private synthetic sheet;
share that sheet with the service-account email as Editor. No broad project Editor IAM role is
needed just to edit a shared spreadsheet. If organization policy blocks service-account keys,
resolve it with an administrator. Never collect secrets through an AI chat.

## Acceptance and handoff

Editable install succeeds. Model/configuration tests verify enums, extra fields, action limits,
fingerprint changes, malformed/stale results and fail-closed settings. Imports do not call APIs.
Record installed versions and external access blockers before starting dependent tasks.