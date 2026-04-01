from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from llmService.agent_loop import AgentLoop
from llmService.responses_service import LLMProvider, ResponsesService
from tasks.base_task import BaseTask
from common.HttpUtil import HttpUtil
from tasks.S01E02.tools import TOOL_DEFINITIONS, set_http_util, set_task_verifier, tool_executor


SYSTEM_PROMPT = """\
You are an investigative AI agent. Your mission is to identify which suspected person \
was located closest to one of the power plants, determine which power plant it was, \
retrieve that person's access level, and submit the answer for verification.

## Rules:
- Use the provided tools to gather all necessary data.
- A suspect may have multiple known locations; consider all of them when comparing distances.
- Start asking about distances for those people and power plants that seem closest to you
- The power plant identifier is a code from the power plants data, not the city name.
- When the verify tool returns a flag {FLG:...}, include it in your final text response.
- If verify returns an error, analyze the error and retry with corrected data.
"""


class S01E02(BaseTask):
    """Find the suspect closest to a power plant and verify the answer."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="findhim")

    def run(self) -> Dict[str, Any]:
        """Run the agent to solve the task."""
        self.logger.info("Starting S01E02 task execution.")

        set_task_verifier(self)
        set_http_util(HttpUtil(self.base_url))

        service = self._build_responses_service()
        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=15,
        )

        result = agent.run(messages=[{"role": "user", "content": "Execute the task."}])
        assistant_message = result["assistant_message"]
        self.logger.info("Agent finished. Result: %s", assistant_message[:1000])
        return {"result": assistant_message}

    @staticmethod
    def _build_responses_service() -> ResponsesService:
        """Build provider-aware Responses API service."""
        provider_name = os.getenv("LLM_PROVIDER", LLMProvider.OPENROUTER.value).strip().lower()

        try:
            provider = LLMProvider(provider_name)
        except ValueError as error:
            allowed_values = ", ".join([item.value for item in LLMProvider])
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{provider_name}'. Allowed: {allowed_values}."
            ) from error

        return ResponsesService(provider=provider)
