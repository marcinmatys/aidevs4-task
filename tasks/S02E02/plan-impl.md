# Plan: S02E02 "failure" — kondensacja logów awarii

## Cel
Zbudować skondensowany log awarii elektrowni (≤1500 tokenów, jedno zdarzenie/linia),
który przejdzie weryfikację Centrali. Iterować na podstawie feedbacku techników aż do flagi {FLG:...}.

## Decyzje (potwierdzone)
- `search_logs` operuje na `filtered_logs` (WARN/ERRO/CRIT), nie na pełnym pliku
- `search_logs` deterministyczny (regex: poziom + nazwa podzespołu), bez LLM
- `compress_logs` i ewentualny LLM = domyślny `ResponsesService` (OpenRouter gpt-4o-mini)
- `result_logs` trzyma linie w oryginalnym formacie; kompresja dopiero gdy przekroczony limit
- stan współdzielony modułowo w `tools.py` (wzorzec S01E05)

## Kroki wykonania (przed agentem, deterministycznie)
1. Pobierz pełny plik logów: `HttpUtil.getData(f"/data/{API_KEY}/failure.log")`
2. `filtered_logs` = linie z poziomem WARN/ERRO/CRIT (regex)
3. `result_logs` = linie z poziomem CRIT (regex) — zestaw startowy
4. Dopiero teraz startuje `AgentLoop` z 5 narzędziami

## Narzędzia agenta (`tools.py`)
1. `search_logs(subsystem?, level?, keyword?)` -> zwraca pasujące linie z `filtered_logs` (regex)
2. `add_to_result_logs(lines)` -> dokłada linie do `result_logs` (dedup), zwraca licznik
3. `count_tokens()` -> liczba tokenów bieżącego `result_logs` (tiktoken, konserwatywnie)
4. `compress_logs()` -> LLM skraca `result_logs` in-place, zachowując timestamp/level/subsystem
5. `submit_logs()` -> POST /verify {apikey, task:"failure", answer:{logs: result_logs}}; zwraca flagę albo feedback

## Stan modułowy w `tools.py`
- `_FILTERED_LOGS: list[str]`
- `_RESULT_LOGS: list[str]` (unikalne, kolejność zachowana)
- `init_state(filtered, result, responses_service)` wywoływane przez `S02E02.run` przed `AgentLoop`
- `TOOL_DEFINITIONS` + `tool_executor` (wzorzec S01E05)

## Pętla agenta (sterowana system promptem)
1. `submit_logs()` z startowym CRIT
2. flaga? -> zwróć w finalnej odpowiedzi tekstowej, koniec
3. feedback (brakujące/niejasne podzespoły) -> `search_logs` dla tych podzespołów
   (pełna sekwencja INFO->WARN->CRIT dla kontekstu przyczynowego)
4. `add_to_result_logs(...)`
5. `count_tokens()` -> jeśli >1500: `compress_logs()`
6. `submit_logs()` ponownie -> wróć do 2
- `max_iterations ~15`; chroń podzespoły już zgłoszone przez techników przy kompresji

## Pliki
- `tasks/S02E02/S02E02.py` — klasa `S02E02(BaseTask)`, `task_name="failure"`
- `tasks/S02E02/tools.py` — 5 narzędzi, stan modułowy, `TOOL_DEFINITIONS`, `tool_executor`
- `tasks/S02E02/__init__.py` — pusty
- `pyproject.toml` — zależność `tiktoken`

## Zabezpieczenia formatu / tokenów
- Normalizacja godziny: oryginał `HH:MM:SS` -> `HH:MM` przy renderowaniu do wysyłki
- Konserwatywny margines tokenów (limit twardy 1500; ostrzeżenie powyżej progu)
- Plik zmienia się o północy — pobieraj świeżo przy każdym uruchomieniu

## Weryfikacja
1. `uv run main.py --dict "S02E02" --task "S02E02"`
2. Log pokazuje: rozmiar pliku, liczbę linii, tokeny filtered/CRIT
3. `count_tokens(result_logs) <= 1500` przed każdym submit
4. Odpowiedź Centrali logowana; iteracje wg feedbacku aż do {FLG:...}
