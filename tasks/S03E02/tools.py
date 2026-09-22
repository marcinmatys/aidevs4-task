from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict

import requests
from dotenv import find_dotenv, load_dotenv

from common.logger_config import setup_logger

_ = load_dotenv(find_dotenv())
logger = setup_logger("S03E02Tools")

API_KEY = os.getenv("API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")

TASK_NAME = "firmware"

# Retry configuration (handled inside run_shell, does not consume agent iterations)
_MAX_RETRIES = 5
_DEFAULT_RETRY_AFTER = 10  # seconds, fallback for HTTP 429 / ban
_BACKOFF_SEQUENCE = [2, 4, 8]  # seconds, for HTTP 503
_MAX_WAIT_BAN = 300  # seconds, upper cap for wait_ban to avoid excessive blocking
_MAX_OUTPUT_CHARS = 4000  # cap run_shell output to keep the agent context small


# ---------------------------------------------------------------------------
# External references — set by S03E02 task class before agent starts
# ---------------------------------------------------------------------------
_task_verifier: Any = None


def set_task_verifier(verifier: Any) -> None:
    """Inject the BaseTask instance so submit_answer() can call BaseTask.verify()."""
    global _task_verifier
    _task_verifier = verifier


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def run_shell(cmd: str) -> str:
    """Execute a single shell command on the remote VM (POST /api/shell) and return its output.

    Retry is handled here based on the HTTP status code:
        - 429 Too Many Requests -> wait retry_after seconds (from body, default 10) and retry.
        - 503 Service Unavailable -> retry with backoff (2s, 4s, 8s).
        - Ban (e.g. HTTP 403 or a ban field in body) -> do NOT retry; return a descriptive message.
    """
    if not API_KEY or not HUB_BASE_URL:
        return json.dumps(
            {"error": "Missing API_KEY or HUB_BASE_URL environment variable."},
            ensure_ascii=False,
        )

    shell_url = f"{HUB_BASE_URL}/api/shell"
    payload = {"apikey": API_KEY, "cmd": cmd}

    logger.info("run_shell: POST %s cmd=%s", shell_url, cmd)

    last_result: Any = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(shell_url, json=payload)
        except requests.RequestException as exc:
            logger.error("run_shell: network error on attempt %d: %s", attempt, exc)
            return json.dumps({"error": f"Network error: {exc}"}, ensure_ascii=False)

        result = _parse_body(response)
        last_result = result

        if _is_ban(response, result):
            ban_time = _extract_retry_after(result)
            message = (
                f"Access banned for {ban_time}s due to a rule violation. "
                "Do not repeat this command; change approach or consider run_shell('reboot')."
            )
            logger.warning("run_shell: ban detected (status=%d): %s", response.status_code, message)
            return json.dumps({"error": message, "banned": True, "ban_time": ban_time}, ensure_ascii=False)

        if response.status_code == 429:
            retry_after = _extract_retry_after(result)
            logger.warning(
                "run_shell: 429 Too Many Requests (attempt %d/%d), sleeping %ss",
                attempt,
                _MAX_RETRIES,
                retry_after,
            )
            time.sleep(retry_after)
            continue

        if response.status_code == 503:
            backoff = _BACKOFF_SEQUENCE[min(attempt - 1, len(_BACKOFF_SEQUENCE) - 1)]
            logger.warning(
                "run_shell: 503 Service Unavailable (attempt %d/%d), backoff %ss",
                attempt,
                _MAX_RETRIES,
                backoff,
            )
            time.sleep(backoff)
            continue

        logger.info(
            "run_shell: status=%d response=%s",
            response.status_code,
            json.dumps(result, ensure_ascii=False)[:1000],
        )
        return _truncate_output(json.dumps(result, ensure_ascii=False))

    logger.error("run_shell: exhausted %d retries", _MAX_RETRIES)
    return json.dumps(
        last_result if last_result is not None else {"error": "Retries exhausted."},
        ensure_ascii=False,
    )


def submit_answer(confirmation: str) -> str:
    """Send the obtained code (ECCS-...) to the hub (POST /verify) and return the raw feedback.

    Delegates to BaseTask.verify() (like S02E05). No 429/503 handling here — this is a single,
    one-shot answer submission.
    """
    if _task_verifier is None:
        return json.dumps({"error": "Task verifier not initialized."}, ensure_ascii=False)

    if not confirmation:
        return json.dumps({"error": "confirmation must not be empty."}, ensure_ascii=False)

    logger.info("submit_answer: confirmation=%s", confirmation)

    answer = {"confirmation": confirmation}
    result = _task_verifier.verify(answer)

    response = json.dumps(result, ensure_ascii=False)
    logger.info("submit_answer: hub response=%s", response)
    return response


def wait_ban(ban_time: int) -> str:
    """Wait out an active ban by sleeping the given ban_time (seconds) before resuming."""
    if ban_time <= 0:
        return json.dumps({"error": "ban_time must be a positive number of seconds."}, ensure_ascii=False)

    wait_seconds = min(ban_time, _MAX_WAIT_BAN)
    logger.info("wait_ban: sleeping %ss (requested %ss).", wait_seconds, ban_time)
    time.sleep(wait_seconds)

    return json.dumps(
        {"status": "ban_wait_completed", "waited": wait_seconds},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(response: requests.Response) -> Any:
    """Parse the response body as JSON, falling back to raw text."""
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _truncate_output(output: str) -> str:
    """Cap the tool output length so very large responses don't flood the agent context."""
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output

    omitted = len(output) - _MAX_OUTPUT_CHARS
    logger.warning("run_shell: output truncated (%d chars omitted).", omitted)
    return (
        output[:_MAX_OUTPUT_CHARS]
        + f"\n...[truncated {omitted} chars; output too large. "
        "Avoid cat on binary files and narrow the command's output.]"
    )


def _extract_retry_after(result: Any) -> int:
    """Read retry_after / ban_time from the response body, defaulting to _DEFAULT_RETRY_AFTER."""
    if isinstance(result, dict):
        for key in ("retry_after", "ban_time"):
            value = result.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return _DEFAULT_RETRY_AFTER


def _is_ban(response: requests.Response, result: Any) -> bool:
    """Detect a ban state from the HTTP status code or the response body."""
    if response.status_code == 403:
        return True
    if isinstance(result, dict):
        if result.get("banned") is True:
            return True
        if "ban_time" in result:
            return True
    return False


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "run_shell",
        "description": "Wykonuje jedną komendę powłoki na zdalnej maszynie wirtualnej (POST /api/shell) i zwraca jej wynik (stdout/stderr).",
        "parameters": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Komenda powłoki do wykonania, np. 'help'."},
            },
            "required": ["cmd"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "submit_answer",
        "description": "Wysyła zdobyty kod (ECCS-...) do Centrali (POST /verify, task 'firmware') i zwraca odpowiedź huba.",
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation": {"type": "string", "description": "Kod w formacie ECCS-xxxx..."},
            },
            "required": ["confirmation"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "wait_ban",
        "description": "Odczekuje zadany czas bana (ban_time w sekundach), zanim agent wznowi pracę. Użyj po otrzymaniu bana z run_shell.",
        "parameters": {
            "type": "object",
            "properties": {
                "ban_time": {"type": "integer", "description": "Czas bana w sekundach do odczekania (z pola ban_time zwróconego przez run_shell)."},
            },
            "required": ["ban_time"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "run_shell": run_shell,
    "submit_answer": submit_answer,
    "wait_ban": wait_ban,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    return func(**args)
