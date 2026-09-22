from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from llmService.agent_loop import AgentLoop
from llmService.responses_service import ResponsesService, ResponsesServiceConfig
from tasks.base_task import BaseTask
from tasks.S03E02.tools import (
    TOOL_DEFINITIONS,
    set_task_verifier,
    tool_executor,
)


SYSTEM_PROMPT = """\
Uwaga! Fabuła przedstawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Jesteś agentem AI pracującym na zdalnej maszynie wirtualnej wyłącznie przez Shell API. \
Twoim celem jest uruchomić oprogramowanie sterownika /opt/firmware/cooler/cooler.bin, odczytać \
kod w formacie ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx i wysłać go do Centrali narzędziem \
submit_answer.

## Jak działać:
- Masz trzy narzędzia: run_shell(cmd) — wykonuje jedną komendę powłoki na maszynie, \
submit_answer(confirmation) — wysyła zdobyty kod ECCS-... do Centrali, oraz \
wait_ban(ban_time) — odczekuje zadany czas bana (w sekundach) zanim wznowisz pracę.
- System jest okrojony i ma NIESTANDARDOWY zestaw komend. Nie zakładaj, że typowe komendy \
Linuxa zadziałają — szczególnie edycja plików działa inaczej. Zawsze ZACZNIJ od \
run_shell("help"), aby poznać dostępne komendy, a następnie korzystaj wyłącznie z nich.
- Wykonuj jedną komendę na wywołanie (jedno wywołanie = jedno żądanie HTTP).
- NIGDY nie wykonuj cat (ani innej komendy wypisującej całą zawartość) na plikach binarnych, \
np. cooler.bin — zaśmieci to kontekst i nic nie wniesie. Pliki binarne uruchamiaj, a nie czytaj.

## Wstępny plan działania:
1. run_shell("help") — poznaj dostępne komendy i ich składnię.
2. Spróbuj uruchomić cooler.bin (podaj ścieżkę i ewentualne parametry) — dokładnie przeanalizuj \
komunikat błędu, wskaże czego brakuje.
3. Znajdź hasło dostępowe — jest zapisane w kilku miejscach w systemie. Przeszukaj DOZWOLONE \
lokalizacje (m.in. wolumen z oprogramowaniem sterownika).
4. Przekonfiguruj plik settings.ini (w katalogu firmware — wolumen zapisywalny), aby aplikacja \
działała poprawnie. UWAGA: przy odczytywaniu settings.ini uważnie i poprawnie licz linie — \
linie są rozdzielone znakiem nowej linii \\n (kolejne \\n to kolejne linie); nie myl numeracji, \
zanim wskażesz lub zmodyfikujesz konkretną linię.
5. Uruchom ponownie sterownik i odczytaj kod ECCS-....
6. Wywołaj submit_answer(confirmation="ECCS-...").
W razie potrzeby dostosuj plan działania do napotkanych okoliczności, tak aby skutecznie osiągnąć cel.

## ZASADY BEZPIECZEŃSTWA (przestrzegaj bezwzględnie — naruszenie = ban i reset maszyny):
- Działasz jako zwykły użytkownik.
- NIE zaglądaj do katalogów /etc, /root ani /proc/.
- Respektuj każdy napotkany plik .gitignore — nie czytaj i nie modyfikuj wymienionych tam \
plików ani katalogów.
- Wolumen z oprogramowaniem sterownika jest zapisywalny; większość dysku jest tylko do odczytu.
- Jeśli mocno namieszasz w systemie, użyj run_shell("reboot"), aby przywrócić stan początkowy.

## Obsługa błędów:
- Czytaj komunikaty uważnie — zwykle precyzyjnie wskazują, co poprawić.
- Jeśli narzędzie zgłosi ban lub rate limit, NIE powtarzaj tej samej komendy w pętli — zmień \
podejście lub rozważ reboot.
- Gdy run_shell zwróci ban (pole "banned": true oraz "ban_time"), wywołaj wait_ban(ban_time), \
aby odczekać ten czas, a dopiero potem spróbuj innego podejścia.
- Gdy odpowiedź submit_answer zawiera flagę {FLG:...}, zadanie jest ukończone — umieść tę flagę \
w swojej końcowej odpowiedzi tekstowej.
"""


class S03E02(BaseTask):
    """Run the cooler.bin firmware on a remote VM through the Shell API via an AI agent."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="firmware")

    def run(self) -> Dict[str, Any]:
        """Run the agent to solve the task."""
        self.logger.info("Starting S03E02 task execution.")

        service = self._build_responses_service()

        set_task_verifier(self)

        agent = AgentLoop(
            responses_service=service,
            tools=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=20,
        )

        result = agent.run(messages=[{"role": "user", "content": "Execute the task."}])
        assistant_message = result["assistant_message"]
        self.logger.info("Agent finished. Result: %s", assistant_message[:1000])
        return {"result": assistant_message}

    @staticmethod
    def _build_responses_service() -> ResponsesService:
        """Build provider-aware Responses API service."""
        return ResponsesService.build(config=S03E02._responses_service_config())

    @staticmethod
    def _responses_service_config() -> ResponsesServiceConfig:
        #return ResponsesServiceConfig(model="openai/gpt-5.5")
        return ResponsesServiceConfig(model="anthropic/claude-opus-4.8")