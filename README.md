# Support Insights

**Hosted demo: not deployed yet.** Google/LLM credentials and hosting account access are required
for the live release. The application does not silently substitute mocked output for live APIs.

A Python utility and Streamlit dashboard that reads support messages from Google Sheets,
extracts category, priority, sentiment and a suggested action, and writes results to the same rows.
The public demo must use synthetic data only. Processing requires a private operator password.

## Local setup

Run from the project root with Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The default local address is http://localhost:8501. For another port append `--server.port 8511`.
Without secrets, the app opens in an explicit unconfigured state; it makes no paid calls.

## Google Sheet and secrets

1. Create a Google Cloud project, enable the Google Sheets API, and create a service account.
   Obtain its JSON key through your authorized account. If key creation is restricted, contact
   the administrator; do not bypass organization controls.
2. Create a private spreadsheet with a tab called `Messages`. Import `data/sample_messages.csv`
   with automatic number/date/formula conversion disabled. Preserve the exact header order.
3. Share that spreadsheet with the service-account `client_email` as Editor. No public edit access
   or broad project Editor IAM permission is needed.
4. Create local `.streamlit/secrets.toml` using `.streamlit/secrets.toml.example` as the structure.
   Enter the spreadsheet ID, service-account fields and the API key for the selected LLM provider.
   Preserve private-key newline characters. Never put secrets into chat, screenshots, logs or
   version control.
5. Set a random operator password of at least 24 characters and `PROCESSING_ENABLED = true`.
   Share only this demo password with assessors, privately. Restart Streamlit after changing secrets.

`LLM_MODEL` selects the LLM provider and model. Unprefixed model names use the legacy OpenAI
Responses integration and `OPENAI_API_KEY`. For Gemini AI Studio, use a `gemini/` model prefix
and `GEMINI_API_KEY`; for DeepSeek, use a `deepseek/` prefix and `DEEPSEEK_API_KEY`. Only the
selected provider's key is used. Change the model and matching key in secrets, then restart
Streamlit to switch providers. Gemini uses schema-based structured output; DeepSeek uses JSON
mode and validates every response locally. Verify that the chosen model supports the request
options and that the account can access it before live processing. No provider or model is silently
substituted. The examples intentionally contain no usable credentials.

## Sheet contract

```text
message_id,raw_message,category,priority,sentiment,suggested_action,status,fingerprint,processed_at,error_code,model,prompt_version
```

Only output columns C:L are updated. IDs are immutable, unique strings supplied by the owner.
Never edit or sort the sheet while processing. Wholly empty rows are ignored; blank messages
with IDs become invalid. Maximum: 500 records, 6,000 characters per input and five records per run.

Categories: Billing, Technical, AccountAccess, FeatureRequest, General, Other.
Priorities: Low, Medium, High, Critical. Sentiments: Positive, Neutral, Negative, Mixed.
Actions are English human-review suggestions, never automatically executed.

## Usage and recovery

Public visitors can search/filter saved results. Unlock processing in the sidebar for Pending,
Retry errors, or Selected mode. Selected explicitly replaces the selected record's prior outcome.
Processing is independent of browsing filters. Refresh respects a 60-second public snapshot cache;
authenticated refresh bypasses it. Stored results survive app restarts.

Fingerprint changes make edited inputs/model/prompt/schema eligible again. Unchanged successful
records are skipped. Errors require Retry errors or Selected; invalid inputs normally require an edit.
The UI reports only persisted successes. If saving cannot be confirmed, refresh and inspect the
affected IDs before retrying. Row conflicts are not overwritten. Transient requests have at most
three attempts; authentication, invalid configuration and insufficient credit are not retried.

There is one process-wide writer lock and a ten-second cooldown. Do not run local and hosted
writers against the same sheet simultaneously. The lock does not coordinate different machines.
Reads and writes are not an atomic transaction; concurrent manual edits remain unsupported.
A crash after analysis but before persistence can result in another paid request later.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Automated tests use fakes and do not require credentials. See `docs/verification.md` for actual
verification status and `data/review_cases.json` for the live semantic-review cases.

## Deployment

With owner approval, publish to GitHub and connect the repository to Streamlit Community Cloud.
Choose `streamlit_app.py` and Python 3.12. The root requirements file installs the local package.
Enter all secrets in Cloud Advanced Settings, never in the repository. Confirm permissions and
one synthetic LLM call before processing the dataset. Configure provider billing alerts/available
limits; the password, cooldown and batch cap are not a hard global spending cap.

Verify the actual hosted HTTPS URL in an incognito browser, including password-protected processing
and write-back to Google Sheets. Replace the release status at the top only after that succeeds.
Community Cloud can sleep and has resource limits. A screenshot is not an executable demo.

## Implementation handoff

The eight small spec-sheets and their dependency order are in `docs/specs/README.md`.
The assessor walkthrough is in `docs/demo.md`. This is a one-day demo, not production identity,
privacy compliance, multi-tenant infrastructure or an exactly-once job system.