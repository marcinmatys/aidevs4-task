from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil
from common.logger_config import setup_logger

_ = load_dotenv(find_dotenv())
logger = setup_logger("S02E04Tools")

API_KEY = os.getenv("API_KEY", "")

ZMAIL_ENDPOINT = "/api/zmail"

# ---------------------------------------------------------------------------
# External references — set by S02E04 task class before agent starts
# ---------------------------------------------------------------------------
_http_util: HttpUtil | None = None
_task_verifier: Any = None


def set_http_util(http_util: HttpUtil) -> None:
    """Inject the HttpUtil instance for zmail API calls."""
    global _http_util
    _http_util = http_util


def set_task_verifier(verifier: Any) -> None:
    """Inject the BaseTask instance so verify() can call BaseTask.verify()."""
    global _task_verifier
    _task_verifier = verifier


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def call_zmail(action: str, parametry: Dict[str, Any] | None = None) -> str:
    """Send a single request to the zmail API (POST /api/zmail) and return its response.

    The payload flattens the action parameters next to the action name:
        {"apikey": API_KEY, "action": <action>, **parametry}
    so that fields like 'page' and search operators land at the top level of the body.
    """
    if _http_util is None:
        return json.dumps({"error": "HttpUtil not initialized."}, ensure_ascii=False)

    payload = {"apikey": API_KEY, "action": action, **(parametry or {})}
    logger.info("call_zmail: action=%s parametry=%s", action, json.dumps(parametry or {}, ensure_ascii=False))

    data = _http_util.sendData(payload, ZMAIL_ENDPOINT)

    response = json.dumps(data, ensure_ascii=False)
    logger.info("call_zmail: response=%s", response[:1000])
    return response


def submit_answer(password: str, date: str, confirmation_code: str) -> str:
    """Submit the collected answer to the hub for verification and return the raw feedback."""
    if _task_verifier is None:
        return json.dumps({"error": "Task verifier not initialized."}, ensure_ascii=False)

    answer = {"password": password, "date": date, "confirmation_code": confirmation_code}
    logger.info("submit_answer: submitting answer=%s", json.dumps(answer, ensure_ascii=False))

    result = _task_verifier.verify(answer)
    response = json.dumps(result, ensure_ascii=False)
    logger.info("submit_answer: hub response=%s", response)
    return response


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "call_zmail",
        "description": "Wysyła pojedyncze żądanie do API zmail (POST /api/zmail) z podaną akcją i opcjonalnymi parametrami i zwraca odpowiedź API. Zacznij od action='help', aby poznać dostępne akcje.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Nazwa akcji API zmail, np. 'help', 'getInbox'.",
                },
                "parametry": {
                    "type": "object",
                    "description": "Parametry akcji jako pary klucz-wartość (np. page, query, operatory from:/to:/subject:, id maila), zgodnie z dokumentacją zwróconą przez 'help'. Pomiń dla akcji bez parametrów.",
                    "additionalProperties": True,
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "submit_answer",
        "description": "Wysyła zebraną odpowiedź do huba (POST /verify) i zwraca surowy feedback. Użyj, gdy masz komplet trzech wartości. Hub wskaże brakujące/błędne pola albo zwróci flagę {FLG:...}.",
        "parameters": {
            "type": "object",
            "properties": {
                "password": {
                    "type": "string",
                    "description": "Hasło do systemu pracowniczego znalezione w skrzynce.",
                },
                "date": {
                    "type": "string",
                    "description": "Data planowanego ataku w formacie YYYY-MM-DD.",
                },
                "confirmation_code": {
                    "type": "string",
                    "description": "Kod potwierdzenia z ticketa, format 'SEC-' + 32 znaki (łącznie 36 znaków).",
                },
            },
            "required": ["password", "date", "confirmation_code"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "call_zmail": call_zmail,
    "submit_answer": submit_answer,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    return func(**args)
