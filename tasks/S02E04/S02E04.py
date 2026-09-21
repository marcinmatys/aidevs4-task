from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil
from llmService.agent_loop import AgentLoop
from llmService.responses_service import ResponsesService, ResponsesServiceConfig
from tasks.base_task import BaseTask
from tasks.S02E04.tools import (
    TOOL_DEFINITIONS,
    set_http_util,
    set_task_verifier,
    tool_executor,
)


SYSTEM_PROMPT = """\
Jesteś agentem AI przeszukującym skrzynkę mailową operatora przez API zmail. Twoim celem jest \
zebranie trzech wartości:
- date — data (format YYYY-MM-DD), kiedy dział bezpieczeństwa planuje atak na elektrownię,
- password — hasło do systemu pracowniczego, prawdopodobnie wciąż obecne w skrzynce,
- confirmation_code — kod potwierdzenia z ticketa działu bezpieczeństwa (format 'SEC-' + 32 znaki \
= łącznie 36 znaków).

## Jak działać:
- Nie masz dokumentacji API. Zacznij od call_zmail(action="help") — dokładnie przeczytaj, jakie \
akcje są dostępne, jakie mają parametry, jak wyszukiwać maile i jak pobierać ich pełną treść.
- Postępuj ściśle według dokumentacji zwróconej przez 'help'. Nie zgaduj nazw akcji ani \
parametrów — używaj dokładnie tych, które zwróciła dokumentacja. Parametry akcji przekazuj w polu \
'parametry' narzędzia call_zmail. Dla akcji bez parametrów pomiń to pole.
- Działaj dwuetapowo: najpierw wyszukaj/pobierz listę maili (metadane), potem pobierz PEŁNĄ treść \
wybranych wiadomości po ich identyfikatorach. Nie wnioskuj z samego tematu — zawsze czytaj pełną \
treść przed wyciąganiem wniosków.
- Buduj zapytania z operatorów from:, to:, subject:, OR, AND. Wiktor doniósł na nas i pisał z \
domeny proton.me — zacznij szeroko (np. from:proton.me), potem zawężaj.

## Zasady:
- Aktywna skrzynka: nowe maile mogą wpływać w trakcie pracy. Jeśli czegoś nie znajdujesz, ponów \
wyszukiwanie lub pobierz kolejne strony (page) — informacja mogła dopiero dotrzeć. Nie zakładaj od \
razu, że nie istnieje.
- Szukaj wartości po kolei — nie musisz znaleźć wszystkiego naraz.
- Gdy masz komplet trzech wartości, wyślij je przez submit_answer(password, date, \
confirmation_code) i przeczytaj feedback huba. Popraw brakujące/błędne pola (ew. ponawiając \
wyszukiwanie) i wyślij ponownie.
- Zwróć uwagę na format: date = YYYY-MM-DD, confirmation_code = 'SEC-' + 32 znaki (36 znaków \
łącznie).
- Gdy w odpowiedzi huba pojawi się flaga {FLG:...}, zadanie jest ukończone — umieść tę flagę w \
swojej końcowej odpowiedzi tekstowej.
"""


class S02E04(BaseTask):
    """Search a mailbox through the zmail API and collect three values via an AI agent."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="mailbox")

    def run(self) -> Dict[str, Any]:
        """Run the agent to solve the task."""
        self.logger.info("Starting S02E04 task execution.")

        service = self._build_responses_service()

        set_http_util(HttpUtil(self.base_url))
        set_task_verifier(self)

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
        return ResponsesService.build(config=S02E04._responses_service_config())

    @staticmethod
    def _responses_service_config() -> ResponsesServiceConfig:
        return ResponsesServiceConfig()
