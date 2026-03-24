from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from llmService.agent_loop import AgentLoop
from llmService.responses_service import LLMProvider, ResponsesService
from tasks.base_task import BaseTask
from tasks.S01E02.tools import TOOL_DEFINITIONS, set_task_verifier, tool_executor


SYSTEM_PROMPT = """\
You are an investigative AI agent. Your goal is to find which suspected person \
was located closest to one of the power plants, determine which power plant it was, \
and retrieve that person's access level.

## Your task step by step:
1. Call get_suspects() to get the list of suspected persons.
2. Call get_powerplants() to get the list of power plants with city names and codes.
3. For each suspect, call get_person_locations(name, surname) to get their last-known coordinates.
4. For each power plant city, call get_city_coordinates(city_name) to get the coordinates.
5. Use get_distance(lat1, lon1, lat2, lon2) to calculate distances between each suspect's \
location(s) and each power plant's coordinates. Find the suspect-location pair with the \
smallest distance to any power plant.
6. Once you identify the closest suspect and the corresponding power plant, call \
get_person_access_level(name, surname, birth_year) to get their access level. \
The birth_year is available from the suspects list ("born" field).
7. Finally, call verify(name, surname, access_level, power_plant) with the suspect's \
first name, last name, their access level, and the power plant code.

## Important rules:
- Always use the tools provided — do not guess coordinates or distances.
- A suspect may have multiple location entries; check all of them.
- The power plant code is an identifier from the power plants list, not the city name.
- When you receive a flag {FLG:...} from verify, include it in your final text response.
- If verify returns an error, analyze it and try again with corrected data.
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

        service = self._build_responses_service()
        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=15,
        )

        result = agent.run()
        self.logger.info("Agent finished. Result: %s", result[:1000])
        return {"result": result}

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
