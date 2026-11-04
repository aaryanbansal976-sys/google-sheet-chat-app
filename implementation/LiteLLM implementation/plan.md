# LiteLLM Provider Integration Plan

## Goal and scope

Add **Google Gemini AI Studio** and **DeepSeek** as configurable LLM providers through the
LiteLLM Python SDK. Provider selection is configuration-only; do not add a dashboard selector.

Use the SDK directly. Do not introduce a proxy server, Router, LangChain, automatic provider
fallback, or provider-selection UI.

Keep the application-facing contract unchanged:

```python
LLMExtractor(settings).extract(raw_message) -> Insight
```

Preserve the current OpenAI Responses implementation for backward compatibility. Add LiteLLM
requests for Gemini and DeepSeek without changing Sheets, authorization, processing limits, or
persistence behavior.

## Repository context

| File | Current responsibility |
|---|---|
| `src/support_insights/config.py` | Model, credentials, processing readiness |
| `src/support_insights/llm.py` | Direct OpenAI Responses integration |
| `src/support_insights/retries.py` | Shared three-attempt retry policy |
| `src/support_insights/models.py` | Output validation and model-sensitive fingerprints |
| `src/support_insights/pipeline.py` | Processing and persisted model metadata |
| `src/support_insights/dashboard.py` | Constructs the extractor and pipeline |
| `tests/test_llm.py` | LLM request, output, and failure tests |

## Task 1 — Add configuration and dependency support

**Files:** `pyproject.toml`, `src/support_insights/config.py`,
`.streamlit/secrets.toml.example`, and focused configuration tests.

### Configuration examples

Gemini AI Studio:

```toml
LLM_MODEL = "gemini/<verified-model-id>"
GEMINI_API_KEY = ""
```

DeepSeek:

```toml
LLM_MODEL = "deepseek/deepseek-chat"
DEEPSEEK_API_KEY = ""
```

These are configuration formats, not proof that a model is available for a particular account.
Verify the model and request options before live use.

### Requirements

1. Infer the provider from `LLM_MODEL`:
   - `gemini/...` selects Gemini AI Studio.
   - `deepseek/...` selects DeepSeek.
   - Existing unprefixed model names preserve legacy OpenAI behavior.
   - Reject unsupported prefixes and empty model suffixes with a sanitized configuration error.
2. Resolve only the selected provider credential:
   - Gemini: `GEMINI_API_KEY`
   - DeepSeek: `DEEPSEEK_API_KEY`
   - Legacy OpenAI: `OPENAI_API_KEY`
3. Keep the resolved credential in `Settings.api_key`, excluded from representations.
4. Preserve direct construction such as `Settings(api_key="test")` used by existing tests.
5. Do not copy secrets into environment variables or LiteLLM globals.
6. Missing LLM credentials disable processing, but must not prevent read-only dashboard browsing.
7. Gemini API keys are separate from Google Sheets service-account credentials.
8. Add a bounded LiteLLM dependency. Retain the OpenAI dependency for the compatibility path and
   existing retry code. Leave `requirements.txt` installing the local package.

**Acceptance:** Provider and credential resolution are deterministic. A Gemini configuration
cannot accidentally use an OpenAI or DeepSeek key.

## Task 2 — Add the LiteLLM request path

**Files:** `src/support_insights/llm.py`, `src/support_insights/prompts.py`,
`tests/test_llm.py`.

Keep the existing OpenAI path unchanged. Add Gemini and DeepSeek paths using synchronous
`litellm.completion`.

### Shared request requirements

- Pass the full provider-prefixed model and the selected API key explicitly.
- Keep system instructions separate from the raw customer message.
- Set a 20-second timeout and preserve the 500-token output budget through the supported
  LiteLLM parameter.
- Disable streaming.
- Set `num_retries=0` so the existing shared retry wrapper remains the only retry owner.
- Do not configure tools, fallback models, response caching, or external logging callbacks.
- Do not globally enable `drop_params`.
- Do not forward OpenAI Responses-specific request parameters to other providers.
- Preserve test seams: allow injection of a completion callable while keeping the existing
  injected OpenAI client supported.

### Structured-output requirements

| Provider | Required behavior |
|---|---|
| Gemini AI Studio | Use JSON-schema structured output for a verified compatible model |
| DeepSeek | Use JSON-object mode, with explicit JSON instructions and local validation |
| Legacy OpenAI | Preserve the current Responses structured parsing behavior |

DeepSeek JSON-object mode does **not** guarantee the required fields, enum values, or a valid
`Insight`. Validate every response locally.

For DeepSeek:

- Send `response_format={"type": "json_object"}`.
- Include explicit JSON-only instructions and the schema derived from
  `Insight.model_json_schema()` in the system message.
- Do not maintain a separately hand-written schema.
- Do not automatically switch output modes after an error.

Keep the OpenAI system prompt unchanged. Avoid a global prompt-version bump unless the actual
prompt behavior changes; changing the version can make existing rows eligible for paid
reprocessing.

**Acceptance:** Offline tests inspect the exact request arguments, including provider, model,
credential, timeout, token limit, response format, and retry settings.

## Task 3 — Validate responses and normalize failures

**Files:** `src/support_insights/llm.py`, `src/support_insights/retries.py`,
`tests/test_llm.py`.

### LiteLLM response validation

1. Require one usable response choice.
2. Detect refusal or content filtering before accepting content.
3. Accept only a successful completion finish reason.
4. Require nonempty string content.
5. Parse with `Insight.model_validate_json(content)`.
6. Do not strip Markdown fences, repair JSON, accept partial objects, or automatically reprompt.

### Application errors

Preserve the application’s existing sanitized error vocabulary:

| Condition | Application result |
|---|---|
| Refusal or safety block | `RowError("llm_refused")` |
| Truncation or incomplete generation | `RowError("llm_incomplete")` |
| Empty, malformed, or schema-invalid output | `RowError("llm_invalid_output")` |
| Exhausted transient request failure | `RowError("llm_request_failed")` |
| Invalid credentials, model, parameters, or billing | `FatalError("llm_configuration_or_billing_error")` |

Inspect the pinned LiteLLM version’s exception hierarchy. Handle refusal and validation
exceptions before broader request-error types where inheritance requires it.

### Retry behavior

The existing retry wrapper must remain the only retry owner:

- Three total attempts maximum.
- Retry transient rate limits, supported transient server errors, connection failures, and
  timeouts.
- Do not retry authentication, invalid request/schema, refusal, invalid output, or exhausted
  credit.
- Treat HTTP 402 as fatal billing failure.
- Preserve the existing bounded `Retry-After` behavior.
- Reuse quota detection where possible instead of adding a divergent duplicate.

Retry code is shared with Sheets; verify existing Sheets retry behavior remains unchanged.
Never expose provider response bodies, raw messages, or credentials in user-facing errors.

**Acceptance:** Tests assert exact attempt counts and sanitized error codes.

## Task 4 — Preserve fingerprints and dashboard behavior

**Inspect:** `src/support_insights/models.py`, `src/support_insights/pipeline.py`,
`src/support_insights/dashboard.py`.

The current fingerprint includes the configured model string. Reuse it; do not add sheet
columns or change the fingerprint format.

- Preserve the full configured model string in `Settings.model`.
- Use that exact string for request selection, fingerprints, persisted model metadata, and
  dashboard status checks.
- Do not replace it with an unprefixed model ID returned by a provider.
- Switching providers or models makes prior results stale/pending.
- Unchanged provider/model settings continue to skip successful rows.
- Preserve legacy unprefixed OpenAI identities so existing rows are not unnecessarily
  invalidated.
- No dashboard provider selector is needed; changing configuration and restarting selects the
  provider.

**Acceptance:** Pipeline and dashboard tests agree on whether a saved result is current.

## Task 5 — Add offline tests

Extend existing test modules; add a focused configuration test module if it improves clarity.
All tests must run without credentials or paid API calls.

| Area | Required cases |
|---|---|
| Configuration | Both new prefixes, legacy OpenAI, unknown prefix, empty suffix, missing selected key, unrelated keys ignored, secret values absent from representations |
| Request construction | Correct provider/model/key, separate user message, structured-output mode, timeout, token budget, retries disabled, no tools or fallbacks |
| Valid output | Gemini and DeepSeek each return a validated `Insight` |
| Invalid output | Missing choices, null/empty content, malformed JSON, fenced JSON, list instead of object, extra/missing fields, invalid enums |
| Action constraints | Empty/whitespace and 401-character values rejected; valid 1- and 400-character values accepted |
| Completion status | Truncation, refusal, safety filtering, unexpected tool-call completion |
| Failures | Authentication, unknown model, unsupported parameters, 402 billing, exhausted quota |
| Retries | Transient recovery, three-attempt exhaustion, nonretryable failures attempted once |
| Integration | Provider changes invalidate old results; unchanged configuration skips successes |
| Regression | Existing OpenAI tests, authorization, dashboard, and Sheets behavior remain intact |

Prefer normalized LiteLLM response objects or faithful typed fixtures; arbitrary mocks can hide
incorrect assumptions about SDK response attributes. Where feasible, mock the HTTP transport
to verify that provider adapters do not multiply requests beyond the application retry policy.

## Task 6 — Update documentation and verify

Update the following documentation:

- `README.md`: provider configuration, credentials, restart requirement, and structured-output
  differences.
- `.streamlit/secrets.toml.example`: commented provider alternatives with empty credentials.
- `docs/specs/01-foundation.md` and `implementation/01-foundation.md`: configuration keys.
- `docs/specs/03-llm.md` and `implementation/03-llm.md`: replace the outdated single-direct-SDK
  requirement.
- `docs/verification.md`: distinguish offline tests from actual provider verification.

### Validation sequence

Run focused tests first, adding any new test modules to the command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_llm.py tests\test_models.py tests\test_pipeline.py tests\test_dashboard.py tests\test_sheets.py
```

Then run the full test suite and the documented Ruff checks. Record any pre-existing failures
separately; do not make unrelated formatting changes.

### Owner-authorized live verification

For each new provider:

1. Verify the selected model and request options.
2. Run one synthetic extraction.
3. Confirm schema-valid output and successful Sheet persistence.
4. Confirm a subsequent unchanged run skips that row.
5. Run the existing `data/review_cases.json` cases before declaring semantic quality verified.

Do not present mocked tests as proof of live provider compatibility.

## Handoff instructions for the implementing model

> Complete Tasks 1–6 in order. Keep changes small and confined to the listed responsibilities.
> Do not redesign the pipeline, change the Sheet schema, add automatic fallback, or remove legacy
> OpenAI support. After each task, report changed files, tests run, and unresolved blockers. Finish
> with exact tested LiteLLM/model versions and clearly separate automated verification from live
> verification.

## References

- [LiteLLM Gemini AI Studio provider](https://docs.litellm.ai/docs/providers/gemini)
- [LiteLLM DeepSeek provider](https://docs.litellm.ai/docs/providers/deepseek)
- [LiteLLM structured outputs and JSON mode](https://docs.litellm.ai/docs/completion/json_mode)
- [LiteLLM exception mapping](https://docs.litellm.ai/docs/exception_mapping)
- [LiteLLM retries and fallbacks](https://docs.litellm.ai/docs/completion/reliable_completions)
