import time
from collections.abc import Callable

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter


def status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    return getattr(error, "status_code", None) or getattr(response, "status_code", None)


def retryable(error: Exception) -> bool:
    body = getattr(error, "body", {})
    if isinstance(body, dict):
        details = body.get("error", body)
        if isinstance(details, dict) and details.get("code") in {
            "insufficient_quota",
            "billing_hard_limit_reached",
        }:
            return False
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {})
    delay = headers.get("retry-after", "0")
    try:
        if float(delay) > 8:
            return False
    except (ValueError, TypeError):
        return False
    if status_code(error) in {429, 500, 502, 503, 504}:
        return True
    from httpx import TransportError
    from requests.exceptions import ConnectionError, Timeout

    if isinstance(error, (TransportError, ConnectionError, Timeout)):
        return True
    from openai import APIConnectionError

    return isinstance(error, APIConnectionError)


def execute[Result](
    operation: Callable[[], Result], sleep: Callable[[float], None] = time.sleep
) -> Result:
    def delay(state):
        backoff = wait_exponential_jitter(initial=1, max=8)(state)
        error = state.outcome.exception()
        response = getattr(error, "response", None)
        server_delay = float(getattr(response, "headers", {}).get("retry-after", "0"))
        return max(backoff, server_delay)

    return Retrying(
        stop=stop_after_attempt(3),
        wait=delay,
        retry=retry_if_exception(retryable),
        sleep=sleep,
        reraise=True,
    )(operation)
