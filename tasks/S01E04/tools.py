from __future__ import annotations

import json
import os
from pathlib import PurePosixPath
from typing import Any, Callable, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil, ResponseType
from common.logger_config import setup_logger
from llmService.responses_service import ResponsesService

_ = load_dotenv(find_dotenv())
logger = setup_logger("S01E04Tools")

API_KEY = os.getenv("API_KEY", "")

DOC_BASE_PATH = "/dane/doc"

_MIME_TYPES: Dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# ---------------------------------------------------------------------------
# External references — set by S01E04 task class before agent starts
# ---------------------------------------------------------------------------
_task_verifier: Any = None
_http_util: HttpUtil | None = None
_responses_service: ResponsesService | None = None


def set_task_verifier(verifier: Any) -> None:
    """Inject the BaseTask instance so verify() can call BaseTask.verify()."""
    global _task_verifier
    _task_verifier = verifier


def set_http_util(http_util: HttpUtil) -> None:
    """Inject the HttpUtil instance for hub documentation calls."""
    global _http_util
    _http_util = http_util


def set_responses_service(service: ResponsesService) -> None:
    """Inject the ResponsesService instance for vision-based image analysis."""
    global _responses_service
    _responses_service = service


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_main_documentation() -> str:
    """Fetch the main SPK documentation (index.md) from the hub."""
    endpoint = f"{DOC_BASE_PATH}/index.md"
    logger.info("get_main_documentation: GET %s", endpoint)

    content = _http_util.getData(endpoint)
    logger.info("get_main_documentation: received %d chars", len(content))
    return content


def get_md_attachment(filename: str) -> str:
    """Fetch a markdown documentation attachment from the hub."""
    endpoint = f"{DOC_BASE_PATH}/{filename}"
    logger.info("get_md_attachment: GET %s", endpoint)

    content = _http_util.getData(endpoint)
    logger.info("get_md_attachment: %s -> %d chars", filename, len(content))
    return content


def get_image_information(filename: str, query: str) -> str:
    """Download an image attachment and extract information from it using a vision model."""
    endpoint = f"{DOC_BASE_PATH}/{filename}"
    logger.info("get_image_information: GET %s (query=%s)", endpoint, query)

    mime_type = _MIME_TYPES.get(PurePosixPath(filename).suffix.lower())
    if mime_type is None:
        return json.dumps(
            {"error": f"Unsupported image type for file: {filename}"},
            ensure_ascii=False,
        )

    image_bytes = _http_util.getData(endpoint, response_type=ResponseType.CONTENT)
    information = _responses_service.analyze_image(
        query=query,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )
    logger.info("get_image_information: %s -> %d chars", filename, len(information))
    return information


def verify(declaration: str) -> str:
    """Submit the filled transport declaration to the hub for verification."""
    if _task_verifier is None:
        return json.dumps({"error": "Task verifier not initialized."})

    answer = {"declaration": declaration}
    logger.info("verify: submitting declaration:\n%s", declaration)

    result = _task_verifier.verify(answer)
    logger.info("verify: hub response: %s", json.dumps(result, ensure_ascii=False))
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_main_documentation",
        "description": "Fetch the main SPK documentation file (index.md). This is the entry point and references other attachments (markdown and image files) needed to fill the declaration.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_md_attachment",
        "description": "Fetch a markdown documentation attachment referenced by the main documentation. Use the exact filename (e.g. 'regulamin.md').",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Name of the markdown file to fetch, e.g. 'regulamin.md'"},
            },
            "required": ["filename"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_image_information",
        "description": "Download an image attachment (e.g. .png/.jpg) from the documentation and extract information from it using a vision model. Provide the exact filename and a precise question describing what information you need from the image.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Name of the image file to fetch, e.g. 'siec.png'"},
                "query": {"type": "string", "description": "Question describing what information to extract from the image"},
            },
            "required": ["filename", "query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "verify",
        "description": "Submit the fully filled transport declaration to the hub for verification. Pass the complete declaration text with exact formatting, separators and field order as required by the documentation template. The hub responds with a flag {FLG:...} on success or an error message describing what to fix.",
        "parameters": {
            "type": "object",
            "properties": {
                "declaration": {"type": "string", "description": "The complete filled declaration text"},
            },
            "required": ["declaration"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "get_main_documentation": get_main_documentation,
    "get_md_attachment": get_md_attachment,
    "get_image_information": get_image_information,
    "verify": verify,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return func(**args)
