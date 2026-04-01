from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil
from common.logger_config import setup_logger

_ = load_dotenv(find_dotenv())
logger = setup_logger("S01E03Tools")

API_KEY = os.getenv("API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")

_http_util: HttpUtil | None = None


def set_http_util(http_util: HttpUtil) -> None:
    """Inject the HttpUtil instance used for hub API calls."""
    global _http_util
    _http_util = http_util


def _get_http_util() -> HttpUtil:
    if _http_util is not None:
        return _http_util

    if not HUB_BASE_URL:
        raise ValueError("Missing HUB_BASE_URL environment variable.")

    return HttpUtil(HUB_BASE_URL)


def check_package_status(packageid: str) -> str:
    """Check current package status and location in the logistics system."""
    if not API_KEY:
        return json.dumps({"error": "Missing API_KEY environment variable."}, ensure_ascii=False)

    payload = {
        "apikey": API_KEY,
        "action": "check",
        "packageid": packageid,
    }
    logger.info("check_package_status payload: %s", json.dumps(payload, ensure_ascii=False))
    result = _get_http_util().sendData(payload, "/api/packages")
    logger.info("check_package_status response: %s", json.dumps(result, ensure_ascii=False))
    return json.dumps(result, ensure_ascii=False)


def redirect_package(packageid: str, destination: str, code: str) -> str:
    """Redirect a package to the requested destination using the provided security code."""
    if not API_KEY:
        return json.dumps({"error": "Missing API_KEY environment variable."}, ensure_ascii=False)

    payload = {
        "apikey": API_KEY,
        "action": "redirect",
        "packageid": packageid,
        "destination": destination,
        "code": code,
    }
    logger.info("redirect_package payload: %s", json.dumps(payload, ensure_ascii=False))
    result = _get_http_util().sendData(payload, "/api/packages")
    logger.info("redirect_package response: %s", json.dumps(result, ensure_ascii=False))
    return json.dumps(result, ensure_ascii=False)


TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "check_package_status",
        "description": "Check package status and location for a given package identifier.",
        "parameters": {
            "type": "object",
            "properties": {
                "packageid": {"type": "string", "description": "Identifier of the package"},
            },
            "required": ["packageid"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "redirect_package",
        "description": "Redirect a package to a destination using the provided security code.",
        "parameters": {
            "type": "object",
            "properties": {
                "packageid": {"type": "string", "description": "Identifier of the package"},
                "destination": {"type": "string", "description": "Target destination code"},
                "code": {"type": "string", "description": "Security code required for redirect"},
            },
            "required": ["packageid", "destination", "code"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "check_package_status": check_package_status,
    "redirect_package": redirect_package,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    return func(**args)
