from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict

import requests
from dotenv import find_dotenv, load_dotenv

from common.logger_config import setup_logger

_ = load_dotenv(find_dotenv())
logger = setup_logger("S01E05Tools")

API_KEY = os.getenv("API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")

TASK_NAME = "railway"

# Retry configuration (handled inside the tool, does not consume agent iterations)
_MAX_RETRIES = 5
_DEFAULT_RETRY_AFTER = 10  # seconds, fallback for HTTP 429
_BACKOFF_SEQUENCE = [2, 4, 8]  # seconds, for HTTP 503


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

def call_api(action: str, parametry: Dict[str, Any] | None = None) -> str:
    """Send a single request to the railway control API (POST /verify) and return its response.

    The payload sent to the hub has the form:
        {"apikey": API_KEY, "task": "railway", "answer": {"action": <action>, **parametry}}

    Retry is handled here based on the HTTP status code:
        - 429 Too Many Requests -> wait retry_after seconds (from body, default 10) and retry.
        - 503 Service Unavailable -> retry with backoff (2s, 4s, 8s).
    """
    if not API_KEY or not HUB_BASE_URL:
        return json.dumps(
            {"error": "Missing API_KEY or HUB_BASE_URL environment variable."},
            ensure_ascii=False,
        )

    verify_url = f"{HUB_BASE_URL}/verify"
    answer = {"action": action, **(parametry or {})}
    payload = {"apikey": API_KEY, "task": TASK_NAME, "answer": answer}

    logger.info("call_api: POST %s answer=%s", verify_url, json.dumps(answer, ensure_ascii=False))

    last_result: Any = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(verify_url, json=payload)
        except requests.RequestException as exc:
            logger.error("call_api: network error on attempt %d: %s", attempt, exc)
            return json.dumps({"error": f"Network error: {exc}"}, ensure_ascii=False)

        result = _parse_body(response)
        last_result = result

        if response.status_code == 429:
            retry_after = _extract_retry_after(result)
            logger.warning(
                "call_api: 429 Too Many Requests (attempt %d/%d), sleeping %ss",
                attempt,
                _MAX_RETRIES,
                retry_after,
            )
            time.sleep(retry_after)
            continue

        if response.status_code == 503:
            backoff = _BACKOFF_SEQUENCE[min(attempt - 1, len(_BACKOFF_SEQUENCE) - 1)]
            logger.warning(
                "call_api: 503 Service Unavailable (attempt %d/%d), backoff %ss",
                attempt,
                _MAX_RETRIES,
                backoff,
            )
            time.sleep(backoff)
            continue

        logger.info(
            "call_api: status=%d response=%s",
            response.status_code,
            json.dumps(result, ensure_ascii=False),
        )
        return json.dumps(result, ensure_ascii=False)

    logger.error("call_api: exhausted %d retries", _MAX_RETRIES)
    return json.dumps(last_result if last_result is not None else {"error": "Retries exhausted."}, ensure_ascii=False)


def _parse_body(response: requests.Response) -> Any:
    """Parse the response body as JSON, falling back to raw text."""
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _extract_retry_after(result: Any) -> int:
    """Read retry_after from the response body, defaulting to _DEFAULT_RETRY_AFTER."""
    if isinstance(result, dict):
        value = result.get("retry_after")
        if isinstance(value, (int, float)):
            return int(value)
    return _DEFAULT_RETRY_AFTER


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "call_api",
        "description": "Wysyła pojedyncze żądanie do API systemu sterowania trasami kolejowymi (POST /verify) z podaną akcją i opcjonalnymi parametrami i zwraca odpowiedź API.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Nazwa akcji API, np. 'help'"},
                "parametry": {
                    "type": "object",
                    "description": "Parametry akcji jako pary klucz-wartość, zgodnie z dokumentacją zwróconą przez 'help'. Pomiń dla akcji bez parametrów.",
                    "additionalProperties": True,
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "call_api": call_api,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    return func(**args)
