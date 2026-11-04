import json
from collections.abc import Callable

from pydantic import ValidationError

from support_insights.config import Settings, provider_for_model
from support_insights.models import FatalError, Insight, RowError
from support_insights.prompts import SYSTEM_PROMPT
from support_insights.retries import execute, status_code


class LLMExtractor:
    def __init__(
        self, settings: Settings, client=None, retry: Callable = execute, completion_call=None
    ):
        if settings.llm_configuration_error:
            raise FatalError(settings.llm_configuration_error)
        self.model = settings.model
        self.api_key = settings.api_key
        self.provider = provider_for_model(settings.model)
        self.client = None
        self.completion = completion_call
        if self.provider == "openai":
            from openai import OpenAI

            self.client = client or OpenAI(api_key=settings.api_key, timeout=20, max_retries=0)
        elif client is not None:
            raise FatalError("llm_client_invalid_for_provider")
        self.retry = retry

    def extract(self, raw_message: str) -> Insight:
        from openai import APIError, APIResponseValidationError

        try:
            if self.provider == "openai":
                response = self.retry(self._openai_request(raw_message))
                return self._parse_openai_response(response)
            response = self.retry(self._litellm_request(raw_message))
            return self._parse_completion_response(response)
        except ValidationError:
            raise RowError("llm_invalid_output") from None
        except APIResponseValidationError:
            raise RowError("llm_invalid_output") from None
        except APIError as error:
            body = getattr(error, "body", {})
            details = body.get("error", body) if isinstance(body, dict) else {}
            exhausted = isinstance(details, dict) and details.get("code") in {
                "insufficient_quota",
                "billing_hard_limit_reached",
            }
            if status_code(error) in {400, 401, 402, 403, 404, 422} or exhausted:
                raise FatalError("llm_configuration_or_billing_error") from None
            raise RowError("llm_request_failed") from None

    def _openai_request(self, raw_message: str):
        return lambda: self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_message},
            ],
            text_format=Insight,
            reasoning={"effort": "none"},
            max_output_tokens=500,
            store=False,
        )

    def _litellm_request(self, raw_message: str):
        system_prompt = SYSTEM_PROMPT
        request_options: dict[str, object] = {"response_format": Insight}
        if self.provider == "deepseek":
            schema = json.dumps(Insight.model_json_schema(), separators=(",", ":"))
            system_prompt += (
                "\nReturn only a valid JSON object matching this schema. Do not use Markdown "
                f"fences or add text outside the JSON object:\n{schema}"
            )
            request_options["response_format"] = {"type": "json_object"}
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_message},
        ]

        def request():
            completion_call = self.completion
            if completion_call is None:
                from litellm import completion as completion_call

            return completion_call(
                model=self.model,
                messages=messages,
                api_key=self.api_key,
                timeout=20,
                max_tokens=500,
                stream=False,
                num_retries=0,
                **request_options,
            )

        return request

    @staticmethod
    def _parse_openai_response(response) -> Insight:
        if response.status != "completed":
            raise RowError("llm_incomplete")
        if any(
            getattr(content, "type", "") == "refusal"
            for output in response.output
            for content in getattr(output, "content", [])
        ):
            raise RowError("llm_refused")
        if response.output_parsed is None:
            raise RowError("llm_invalid_output")
        try:
            return Insight.model_validate(response.output_parsed)
        except ValidationError:
            raise RowError("llm_invalid_output") from None

    @staticmethod
    def _parse_completion_response(response) -> Insight:
        choices = getattr(response, "choices", None)
        if not isinstance(choices, (list, tuple)) or len(choices) != 1:
            raise RowError("llm_invalid_output")
        message = getattr(choices[0], "message", None)
        if message is None:
            raise RowError("llm_invalid_output")
        if getattr(message, "refusal", None):
            raise RowError("llm_refused")
        finish_reason = getattr(choices[0], "finish_reason", None)
        if finish_reason == "content_filter":
            raise RowError("llm_refused")
        if finish_reason == "length":
            raise RowError("llm_incomplete")
        if finish_reason != "stop":
            raise RowError("llm_incomplete")
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RowError("llm_invalid_output")
        try:
            return Insight.model_validate_json(content)
        except ValidationError:
            raise RowError("llm_invalid_output") from None
