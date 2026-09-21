from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Dict

import requests
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel

from common.logger_config import setup_logger
from llmService.responses_service import ResponsesService

_ = load_dotenv(find_dotenv())
logger = setup_logger("S02E03Tools")

API_KEY = os.getenv("API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")

TASK_NAME = "failure"
TOKEN_LIMIT = 1500

# Levels considered relevant for failure analysis.
_RELEVANT_LEVELS = ("WARN", "ERRO", "CRIT")
_LEVEL_PATTERN = re.compile(r"\]\s*\[(INFO|WARN|ERRO|CRIT)\]")
_TIMESTAMP_SECONDS_PATTERN = re.compile(
    r"\[(\d{4}-\d{2}-\d{2}) (\d{1,2}:\d{2}):\d{2}\]"
)

# HTTP retry configuration (handled inside the tool, does not consume agent iterations).
_MAX_RETRIES = 5
_DEFAULT_RETRY_AFTER = 10  # seconds, fallback for HTTP 429
_BACKOFF_SEQUENCE = [2, 4, 8]  # seconds, for HTTP 503


# ---------------------------------------------------------------------------
# Module-level shared state (initialized by S02E03.run before the agent starts)
# ---------------------------------------------------------------------------

_FILTERED_LOGS: list[str] = []
_RESULT_LOGS: list[str] = []
_RESPONSES_SERVICE: ResponsesService | None = None


def init_state(
    filtered_logs: list[str],
    result_logs: list[str],
    responses_service: ResponsesService,
) -> None:
    """Initialize shared state consumed by the agent tools."""
    global _FILTERED_LOGS, _RESULT_LOGS, _RESPONSES_SERVICE
    _FILTERED_LOGS = list(filtered_logs)
    _RESULT_LOGS = _unique_preserving_order(result_logs)
    _RESPONSES_SERVICE = responses_service
    logger.info(
        "init_state: filtered=%d lines, result=%d lines",
        len(_FILTERED_LOGS),
        len(_RESULT_LOGS),
    )


def get_result_logs() -> list[str]:
    """Return the current result log lines (for the task wrapper)."""
    return list(_RESULT_LOGS)


# ---------------------------------------------------------------------------
# Deterministic log filtering (no LLM)
# ---------------------------------------------------------------------------

def extract_level(line: str) -> str | None:
    """Return the severity level of a log line, or None if absent."""
    match = _LEVEL_PATTERN.search(line)
    return match.group(1) if match else None


def filter_by_levels(lines: list[str], levels: tuple[str, ...]) -> list[str]:
    """Return only lines whose severity level is in the given set."""
    return [line for line in lines if extract_level(line) in levels]


def _unique_preserving_order(lines: list[str]) -> list[str]:
    """Deduplicate lines while keeping their first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        normalized = line.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def extract_description(line: str) -> str:
    """Return the event description (text after the severity level)."""
    match = _LEVEL_PATTERN.search(line)
    if not match:
        return line.strip()
    return line[match.end():].strip()


def dedupe_by_description(lines: list[str]) -> list[str]:
    """Drop lines whose description repeats, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        description = extract_description(line).lower()
        if not description or description in seen:
            continue
        seen.add(description)
        result.append(line)
    return result


def _normalize_timestamp(line: str) -> str:
    """Strip seconds from the timestamp so it matches the required HH:MM format."""
    return _TIMESTAMP_SECONDS_PATTERN.sub(r"[\1 \2]", line)


def _render(lines: list[str]) -> str:
    """Render result lines into the exact string sent for verification."""
    return "\n".join(_normalize_timestamp(line) for line in lines)


# ---------------------------------------------------------------------------
# Token counting (tiktoken with conservative fallback)
# ---------------------------------------------------------------------------

def _count_text_tokens(text: str) -> int:
    """Count tokens conservatively; fall back to a char-based estimate."""
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text))
    except Exception as exc:  # tiktoken missing or encoding unavailable
        logger.warning("tiktoken unavailable (%s); using char/4 estimate.", exc)
        return (len(text) + 3) // 4


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def search_logs(
    subsystem: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
) -> str:
    """Search filtered_logs by optional subsystem id, severity level and keyword.

    All provided filters are combined with AND. Matching is case-insensitive.
    Returns a JSON object with the matched lines.
    """
    subsystem_needle = subsystem.strip().upper() if subsystem else None
    level_needle = level.strip().upper() if level else None
    keyword_needle = keyword.strip().lower() if keyword else None

    matches: list[str] = []
    for line in _FILTERED_LOGS:
        upper_line = line.upper()
        if subsystem_needle and subsystem_needle not in upper_line:
            continue
        if level_needle and extract_level(line) != level_needle:
            continue
        if keyword_needle and keyword_needle not in line.lower():
            continue
        matches.append(line)

    logger.info(
        "search_logs: subsystem=%s level=%s keyword=%s -> %d matches",
        subsystem,
        level,
        keyword,
        len(matches),
    )
    return json.dumps({"count": len(matches), "lines": matches}, ensure_ascii=False)


def add_to_result_logs(lines: list[str]) -> str:
    """Append the given lines to result_logs (deduplicated) and report token usage."""
    global _RESULT_LOGS
    if not isinstance(lines, list):
        return json.dumps({"error": "lines must be an array of strings."}, ensure_ascii=False)

    before = len(_RESULT_LOGS)
    _RESULT_LOGS = _unique_preserving_order([*_RESULT_LOGS, *lines])
    added = len(_RESULT_LOGS) - before
    tokens = _count_text_tokens(_render(_RESULT_LOGS))

    logger.info("add_to_result_logs: added=%d total=%d tokens=%d", added, len(_RESULT_LOGS), tokens)
    return json.dumps(
        {
            "added": added,
            "total_lines": len(_RESULT_LOGS),
            "tokens": tokens,
            "token_limit": TOKEN_LIMIT,
            "within_limit": tokens <= TOKEN_LIMIT,
        },
        ensure_ascii=False,
    )


def count_tokens() -> str:
    """Return the token count of the current result_logs render."""
    tokens = _count_text_tokens(_render(_RESULT_LOGS))
    logger.info("count_tokens: %d / %d", tokens, TOKEN_LIMIT)
    return json.dumps(
        {
            "tokens": tokens,
            "token_limit": TOKEN_LIMIT,
            "within_limit": tokens <= TOKEN_LIMIT,
            "total_lines": len(_RESULT_LOGS),
        },
        ensure_ascii=False,
    )


class _CondensedLogs(BaseModel):
    logs: str


_COMPRESS_SYSTEM_PROMPT = (
    "Jesteś asystentem kondensującym logi awarii elektrowni. Otrzymujesz zestaw logów "
    "(jedno zdarzenie na linię). Skróć i sparafrazuj opisy tak, aby zmieścić się w limicie "
    f"{TOKEN_LIMIT} tokenów, zachowując KAŻDE zdarzenie jako osobną linię. Dla każdej linii "
    "MUSISZ zachować: znacznik czasu w formacie [YYYY-MM-DD HH:MM], poziom ważności "
    "([WARN]/[ERRO]/[CRIT]) oraz identyfikator podzespołu (np. ECCS8, WTRPMP, WTANK07, "
    "STMTURB12, FIRMWARE, PWR01). Nie usuwaj zdarzeń, nie łącz wielu zdarzeń w jednej linii. "
    "Zwróć wynik jako pojedynczy string w polu 'logs', linie oddzielone znakiem nowej linii."
)


def compress_logs() -> str:
    """Use the LLM to shorten result_logs in place while preserving key fields."""
    global _RESULT_LOGS
    if _RESPONSES_SERVICE is None:
        return json.dumps({"error": "Responses service not initialized."}, ensure_ascii=False)

    if not _RESULT_LOGS:
        return json.dumps({"error": "result_logs is empty; nothing to compress."}, ensure_ascii=False)

    rendered = _render(_RESULT_LOGS)
    tokens_before = _count_text_tokens(rendered)

    try:
        result = _RESPONSES_SERVICE.generate_with_schema(
            system_prompt=_COMPRESS_SYSTEM_PROMPT,
            input_payload={"logs": rendered, "token_limit": TOKEN_LIMIT},
            output_model=_CondensedLogs,
        )
    except Exception as exc:
        logger.error("compress_logs: LLM error: %s", exc)
        return json.dumps({"error": f"Compression failed: {exc}"}, ensure_ascii=False)

    compressed_lines = [line.strip() for line in result.logs.splitlines() if line.strip()]
    if not compressed_lines:
        return json.dumps({"error": "Compression produced no lines."}, ensure_ascii=False)

    _RESULT_LOGS = _unique_preserving_order(compressed_lines)
    tokens_after = _count_text_tokens(_render(_RESULT_LOGS))

    logger.info(
        "compress_logs: %d -> %d tokens, %d lines",
        tokens_before,
        tokens_after,
        len(_RESULT_LOGS),
    )
    return json.dumps(
        {
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "token_limit": TOKEN_LIMIT,
            "within_limit": tokens_after <= TOKEN_LIMIT,
            "total_lines": len(_RESULT_LOGS),
        },
        ensure_ascii=False,
    )


def submit_logs() -> str:
    """Send the current result_logs to Centrala for verification and return the response."""
    if not API_KEY or not HUB_BASE_URL:
        return json.dumps(
            {"error": "Missing API_KEY or HUB_BASE_URL environment variable."},
            ensure_ascii=False,
        )

    rendered = _render(_RESULT_LOGS)
    tokens = _count_text_tokens(rendered)
    if tokens > TOKEN_LIMIT:
        return json.dumps(
            {
                "error": "Token limit exceeded; compress before submitting.",
                "tokens": tokens,
                "token_limit": TOKEN_LIMIT,
            },
            ensure_ascii=False,
        )

    verify_url = f"{HUB_BASE_URL}/verify"
    payload = {"apikey": API_KEY, "task": TASK_NAME, "answer": {"logs": rendered}}
    logger.info("submit_logs: POST %s (%d lines, %d tokens)", verify_url, len(_RESULT_LOGS), tokens)

    last_result: Any = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(verify_url, json=payload)
        except requests.RequestException as exc:
            logger.error("submit_logs: network error on attempt %d: %s", attempt, exc)
            return json.dumps({"error": f"Network error: {exc}"}, ensure_ascii=False)

        result = _parse_body(response)
        last_result = result

        if response.status_code == 429:
            retry_after = _extract_retry_after(result)
            logger.warning("submit_logs: 429 (attempt %d/%d), sleeping %ss", attempt, _MAX_RETRIES, retry_after)
            time.sleep(retry_after)
            continue

        if response.status_code == 503:
            backoff = _BACKOFF_SEQUENCE[min(attempt - 1, len(_BACKOFF_SEQUENCE) - 1)]
            logger.warning("submit_logs: 503 (attempt %d/%d), backoff %ss", attempt, _MAX_RETRIES, backoff)
            time.sleep(backoff)
            continue

        logger.info("submit_logs: status=%d response=%s", response.status_code, json.dumps(result, ensure_ascii=False))
        return json.dumps(result, ensure_ascii=False)

    logger.error("submit_logs: exhausted %d retries", _MAX_RETRIES)
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
# Tool definitions (OpenAI Responses API function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_logs",
        "description": (
            "Przeszukuje przefiltrowane logi (WARN/ERRO/CRIT) po opcjonalnym identyfikatorze "
            "podzespołu, poziomie ważności i słowie kluczowym. Filtry łączone są operatorem AND."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subsystem": {"type": "string", "description": "Identyfikator podzespołu, np. 'ECCS8', 'WTANK07'."},
                "level": {"type": "string", "description": "Poziom ważności: 'WARN', 'ERRO' lub 'CRIT'."},
                "keyword": {"type": "string", "description": "Słowo kluczowe do wyszukania w treści zdarzenia."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "add_to_result_logs",
        "description": "Dodaje podane linie do zestawu wynikowego (z deduplikacją) i zwraca aktualne zużycie tokenów.",
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Linie logów do dodania do zestawu wynikowego.",
                }
            },
            "required": ["lines"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "count_tokens",
        "description": "Zwraca liczbę tokenów bieżącego zestawu wynikowego oraz informację, czy mieści się w limicie.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "compress_logs",
        "description": (
            "Kompresuje (parafrazuje/skraca) bieżący zestaw wynikowy za pomocą LLM, zachowując dla każdej "
            "linii znacznik czasu, poziom ważności i identyfikator podzespołu. Użyj gdy przekroczono limit tokenów."
        ),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "submit_logs",
        "description": (
            "Wysyła bieżący zestaw wynikowy do Centrali (POST /verify) i zwraca odpowiedź: flagę {FLG:...} "
            "przy sukcesie albo feedback techników wskazujący brakujące lub niejasne podzespoły."
        ),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "search_logs": search_logs,
    "add_to_result_logs": add_to_result_logs,
    "count_tokens": count_tokens,
    "compress_logs": compress_logs,
    "submit_logs": submit_logs,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    return func(**args)
