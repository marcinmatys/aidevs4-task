from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from common.HttpUtil import HttpUtil
from llmService.agent_loop import AgentLoop
from llmService.responses_service import ResponsesService, ResponsesServiceConfig
from tasks.base_task import BaseTask
from tasks.S02E02 import tools
from tasks.S02E02.tools import (
    TOOL_DEFINITIONS,
    dedupe_by_description,
    filter_by_levels,
    tool_executor,
)


SYSTEM_PROMPT = """\
Jesteś agentem AI przygotowującym skondensowany raport logów z awarii elektrowni dla Centrali.

## Cel
Zbuduj skondensowany log (jedno zdarzenie na linię), na podstawie którego technicy przeprowadzą \
analizę przyczyny awarii, i uzyskaj flagę w formacie {FLG:...}.

## Twarde ograniczenia
- Wynik NIE może przekroczyć 1500 tokenów. Przed każdą wysyłką sprawdzaj tokeny.
- Jedno zdarzenie = jedna linia. Nigdy nie łącz wielu zdarzeń w jednej linii.
- Każda linia zachowuje: znacznik czasu [YYYY-MM-DD HH:MM], poziom ważności i identyfikator podzespołu.

## Narzędzia
- search_logs(subsystem?, level?, keyword?): przeszukuje przefiltrowane logi (WARN/ERRO/CRIT).
- add_to_result_logs(lines): dodaje wybrane linie do zestawu wynikowego (z deduplikacją).
- count_tokens(): sprawdza liczbę tokenów bieżącego zestawu.
- compress_logs(): skraca zestaw wynikowy, gdy przekracza limit tokenów.
- submit_logs(): wysyła zestaw do Centrali i zwraca flagę albo feedback techników.

## Jak działać
1. Zestaw wynikowy jest już zainicjowany zdarzeniami CRIT. Zacznij od submit_logs(), aby poznać feedback.
2. Czytaj feedback techników dokładnie — wskazuje on konkretne podzespoły, które są nieobecne, \
niejasne lub niewystarczająco opisane.
3. Dla każdego zgłoszonego podzespołu użyj search_logs(subsystem=...), aby znaleźć jego zdarzenia — \
dołączaj także zdarzenia poprzedzające (WARN/ERRO), które pokazują narastanie problemu, nie tylko CRIT.
4. Dodawaj znalezione linie przez add_to_result_logs(). Po dodaniu sprawdzaj count_tokens().
5. Jeśli przekroczysz 1500 tokenów, wywołaj compress_logs(). Przy kompresji nie trać podzespołów, \
o które prosili technicy.
6. Ponownie wywołaj submit_logs(). Powtarzaj aż otrzymasz flagę {FLG:...}.

## Zakończenie
Gdy w odpowiedzi pojawi się flaga {FLG:...}, umieść ją w swojej końcowej odpowiedzi tekstowej.
"""


class S02E02(BaseTask):
    """Condense power-plant failure logs and iterate with Centrala feedback until the flag."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="failure")
        self.http_util = HttpUtil(self.base_url)

    def run(self) -> Dict[str, Any]:
        """Run the deterministic filtering, then the agent loop to obtain the flag."""
        self.logger.info("Starting S02E02 task execution.")

        api_key = self._ensure_api_key()
        raw_log = self._download_log(api_key)

        all_lines = [line for line in raw_log.splitlines() if line.strip()]
        filtered_logs = filter_by_levels(all_lines, ("WARN", "ERRO", "CRIT"))
        result_logs = dedupe_by_description(filter_by_levels(all_lines, ("CRIT",)))

        self.logger.info(
            "Log stats: total=%d lines, filtered(WARN/ERRO/CRIT)=%d, CRIT(start, deduped)=%d",
            len(all_lines),
            len(filtered_logs),
            len(result_logs),
        )

        service = ResponsesService.build(config=ResponsesServiceConfig())
        tools.init_state(filtered_logs, result_logs, service)

        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=2,
        )

        result = agent.run(messages=[{"role": "user", "content": "Wykonaj zadanie."}])
        assistant_message = result["assistant_message"]
        self.logger.info("Agent finished. Result: %s", assistant_message[:1000])
        return {"result": assistant_message, "result_lines": len(tools.get_result_logs())}

    def _ensure_api_key(self) -> str:
        """Validate API_KEY availability in environment variables."""
        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("Missing API_KEY environment variable.")
        return api_key

    def _download_log(self, api_key: str) -> str:
        """Download the full failure.log from HUB and return it as text."""
        endpoint = f"/data/{api_key}/failure.log"
        self.logger.info("Downloading failure log from endpoint: %s", endpoint)
        raw_log = self.http_util.getData(endpoint)
        self.logger.info("Downloaded failure log: %d characters", len(raw_log))
        return raw_log
