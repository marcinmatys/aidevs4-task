from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil
from llmService.agent_loop import AgentLoop
from llmService.responses_service import ResponsesService, ResponsesServiceConfig
from tasks.base_task import BaseTask
from tasks.S01E04.tools import (
    TOOL_DEFINITIONS,
    set_http_util,
    set_responses_service,
    set_task_verifier,
    tool_executor,
)


SYSTEM_PROMPT = """\
You are an AI agent operating the Konductor Parcel System (SPK). Your mission is to prepare a \
correctly filled transport declaration according to the SPK documentation and submit it for \
verification.

## Shipment data to put into the declaration:
- Sender identifier: 450202122
- Origin point: Gdańsk
- Destination point: Żarnowiec
- Weight: 2,8 tony (2800 kg)
- Budget: 0 PP (the shipment must be free / financed by the System)
- Contents: kasety z paliwem do reaktora
- Special remarks: none — do not add any remarks

## How to proceed:
- Start with get_main_documentation (index.md). It references other files — fetch and read ALL \
files that may be needed to fill the declaration, not only index.md.
- Not all files are text. Some documentation is delivered as images — use get_image_information \
to extract the data you need from them (e.g. the connection network, route list).
- Find the declaration template in the documentation and fill every field according to the \
shipment data and the regulations.
- Determine the correct route code for Gdańsk – Żarnowiec by checking the connection network and \
route list.
- Determine the fee from the SPK fee table. The fee depends on the parcel category, weight and \
route length. The budget is 0 PP — pay attention to which categories are financed by the System.
- If you encounter an abbreviation you do not understand, look it up in the documentation.

## Rules:
- The declaration format is strict: keep the exact formatting, separators and field order from \
the template. The hub verifies both values and format.
- Submit the final declaration with the verify tool.
- If verify returns an error, read the error message carefully, correct the declaration and \
submit again.
- When the verify tool returns a flag {FLG:...}, include it in your final text response.
"""


class S01E04(BaseTask):
    """Prepare and submit a valid SPK transport declaration via an AI agent."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="sendit")

    def run(self) -> Dict[str, Any]:
        """Run the agent to solve the task."""
        self.logger.info("Starting S01E04 task execution.")

        service = self._build_responses_service()

        set_task_verifier(self)
        set_http_util(HttpUtil(self.base_url))
        set_responses_service(service)

        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=3,
        )

        result = agent.run(messages=[{"role": "user", "content": "Execute the task."}])
        assistant_message = result["assistant_message"]
        self.logger.info("Agent finished. Result: %s", assistant_message[:1000])
        return {"result": assistant_message}

    @staticmethod
    def _build_responses_service() -> ResponsesService:
        """Build provider-aware Responses API service."""
        return ResponsesService.build(config=S01E04._responses_service_config())

    @staticmethod
    def _responses_service_config() -> ResponsesServiceConfig:
        return ResponsesServiceConfig()
