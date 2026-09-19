from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from llmService.agent_loop import AgentLoop
from llmService.responses_service import ResponsesService, ResponsesServiceConfig
from tasks.base_task import BaseTask
from tasks.S01E05.tools import TOOL_DEFINITIONS, tool_executor


SYSTEM_PROMPT = """\
Jesteś agentem AI sterującym systemem tras kolejowych przez nieznane API. Twoim celem jest \
aktywować trasę kolejową o nazwie X-01.

## Jak działać:
- Nie masz dokumentacji API. Zacznij od wywołania call_api(action="help") — zwróci ono \
dokumentację API: dostępne akcje, ich parametry oraz wymaganą kolejność wywołań. Przeczytaj ją \
dokładnie.
- Postępuj ściśle według dokumentacji zwróconej przez 'help'. Nie zgaduj nazw akcji ani \
parametrów — używaj dokładnie tych wartości i nazw pól, które zwróciła dokumentacja.
- Parametry akcji przekazuj w polu 'parametry' narzędzia call_api jako pary klucz-wartość. \
Dla akcji bez parametrów pomiń to pole.

## Zasady:
- Czytaj komunikaty błędów uważnie — zwykle precyzyjnie wskazują, co poprawić (zły parametr, \
zła kolejność akcji, brakująca akcja poprzedzająca itp.). Skoryguj wywołanie i spróbuj ponownie.
- Gdy w treści odpowiedzi API pojawi się flaga {FLG:...}, zadanie jest ukończone — umieść tę \
flagę w swojej końcowej odpowiedzi tekstowej.
"""


class S01E05(BaseTask):
    """Activate railway route X-01 through an undocumented API via an AI agent."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="railway")

    def run(self) -> Dict[str, Any]:
        """Run the agent to solve the task."""
        self.logger.info("Starting S01E05 task execution.")

        service = self._build_responses_service()

        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=10,
        )

        result = agent.run(messages=[{"role": "user", "content": "Execute the task."}])
        assistant_message = result["assistant_message"]
        self.logger.info("Agent finished. Result: %s", assistant_message[:1000])
        return {"result": assistant_message}

    @staticmethod
    def _build_responses_service() -> ResponsesService:
        """Build provider-aware Responses API service."""
        return ResponsesService.build(config=S01E05._responses_service_config())

    @staticmethod
    def _responses_service_config() -> ResponsesServiceConfig:
        return ResponsesServiceConfig()
