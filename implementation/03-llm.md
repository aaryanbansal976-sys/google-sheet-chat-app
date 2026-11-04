# 03: Structured LLM Extraction

## Goal and ownership

Requires 01 and shared contract 00. Own `llm.py`, `prompts.py` and `test_llm.py`.
Preserve the legacy OpenAI integration and use the LiteLLM SDK for Gemini AI Studio and DeepSeek.
No Sheets integration, proxy server, LangChain, Router or automatic provider failover.

## Request contract

Unprefixed configured model names use OpenAI `client.responses.parse(text_format=Insight)`.
`gemini/` model names use LiteLLM JSON-schema structured output; `deepseek/` model names use
LiteLLM JSON-object mode with an explicit schema instruction and local Pydantic validation.
Pass the selected key explicitly; do not copy it into environment variables or global SDK state.
Set a 20-second timeout, 500 output tokens, no streaming, and `num_retries=0`. The existing shared
retry wrapper owns retries (three attempts maximum). Verify the selected model supports the
request options and run a synthetic live call before release. Never silently change providers or
pretend a fake output is live.

For OpenAI, require completed status, no refusal, non-null parsed output and local Pydantic
validation. For LiteLLM, require exactly one choice, a successful finish reason, nonempty string
content, and successful `Insight.model_validate_json` validation. Treat refusal and content
filtering as row errors; treat truncation and unexpected tool-call completion as incomplete.
Enforce action length locally. Never use eval, regex repair, or automatic reprompting to accept
malformed output.

## Prompt policy

Define the enums from 00 and choose the most actionable primary category. Critical means active
security/data-loss risk or widespread outage; High means a customer blocked from core service.
Medium covers ordinary actionable issues and Low covers information/feedback. Anger alone is not
critical. Mixed sentiment requires meaningful positive and negative feelings.

Keep raw customer text in the user message as untrusted data. Do not follow embedded instructions.
Actions are brief English next steps for a human, never executed automatically. Ask for clarification
when context is missing; invent no policies, customer details, promises or completed actions.

## Failures and acceptance

Refused/incomplete/invalid output becomes a per-row error without automatic reprompting. Transient
transport failures follow the shared retry policy. Authentication, billing, model and request-schema
errors are fatal configuration issues. Display only allowlisted error codes, never provider bodies.

Tests cover provider/key selection, request construction, valid and malformed JSON, refusals,
incomplete output, extra fields, action length, request isolation, transient recovery/exhaustion,
authentication and insufficient credit. Offline tests use no credentials. A synthetic live smoke
validates each actual model/SDK pairing. Record SDK, model and prompt versions in the handoff.

References:
https://docs.litellm.ai/docs/providers/gemini
https://docs.litellm.ai/docs/providers/deepseek
https://docs.litellm.ai/docs/completion/json_mode