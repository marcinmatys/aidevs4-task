# Plan implementacji S03E02 — "Firmware" (uruchomienie sterownika `cooler.bin` na zdalnej maszynie)

## Opis zadania
Uruchomić oprogramowanie sterownika `/opt/firmware/cooler/cooler.bin` na zdalnej maszynie
wirtualnej, do której dostęp mamy wyłącznie przez **Shell API** (`{HUB_BASE_URL}/api/shell`).
System jest okrojony (nietypowy zestaw komend, większość dysku tylko do odczytu, wolumen
z oprogramowaniem zapisywalny). Po poprawnym uruchomieniu na ekranie pojawi się kod w formacie
`ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`, który należy odesłać do Centrali.

Zadanie realizuje **agent AI z tool callingiem** (pętla agencka), który samodzielnie:
1. odkrywa dostępne komendy powłoki (start od `help`),
2. próbuje uruchomić `cooler.bin`,
3. zdobywa hasło dostępowe (zapisane w kilku miejscach w systemie),
4. przekonfigurowuje `settings.ini`, aby oprogramowanie działało poprawnie,
5. odczytuje kod `ECCS-...` i wysyła go do `/verify`.

- Agent kończy pracę, gdy zdobędzie kod i pomyślnie go wyśle (odpowiedź huba z flagą `{FLG:...}`)
  **lub** osiągnie maksymalną liczbę iteracji (`15`).
- Nazwa zadania (task): **`firmware`**.

## Zasady bezpieczeństwa (kluczowe — naruszenie = ban + reset maszyny)
- Praca na koncie zwykłego użytkownika.
- **Zakaz** zaglądania do katalogów `/etc`, `/root`, `/proc/`.
- Respektować pliki `.gitignore` — nie dotykać plików/katalogów tam wymienionych.
- W razie „namieszania” w systemie użyć komendy `reboot` (przez `run_shell`).
- Powyższe zasady egzekwujemy **wyłącznie przez system prompt** (bez twardej blokady w narzędziu,
  zgodnie z ustaleniem). System prompt musi je wyraźnie i stanowczo opisywać.

## Podobieństwo do S01E05
Zadanie jest architektonicznie bliźniacze do **S01E05** (agent + nieznane API odkrywane przez `help`).
Reużywamy tej samej infrastruktury i wzorców:
- `AgentLoop` (pętla agencka), `ResponsesService` (klient LLM `generate_with_tools`),
  `BaseTask` (klasa bazowa).
- Struktura plików: `tools.py` (`TOOL_DEFINITIONS` + `tool_executor` + funkcje narzędzi) oraz
  klasa `S03E02(BaseTask)`.
- **Różnica względem S01E05:** kanał odpowiedzi (`submit_answer`) NIE idzie przez bezpośrednie
  `requests`, lecz przez `BaseTask.verify()` wstrzyknięty metodą `set_task_verifier(...)` —
  wzorzec z **S02E05** (`send_drone_instructions`). Bezpośrednio przez `requests`
  (z dostępem do `response.status_code`) działa tylko `run_shell` (Shell API `/api/shell`).
- Retry (429 rate limit / 503 / ban) obsługiwany **wewnątrz narzędzia `run_shell`**
  (nie zużywa iteracji agenta). `submit_answer` **nie** ma własnego retry — to jednorazowe
  wysłanie odpowiedzi przez `verify()`.

## Decyzje architektoniczne (ustalone)
- **Dwa narzędzia** (zgodnie ze wskazówką zadania — jedno do powłoki, jedno do odpowiedzi):
  - `run_shell(cmd)` — wykonuje jedną komendę powłoki na maszynie (`POST /api/shell`).
    `reboot` traktujemy jako zwykłą komendę przekazaną w `cmd` (brak osobnego narzędzia).
  - `submit_answer(confirmation)` — wysyła zdobyty kod do Centrali i zwraca odpowiedź huba
    (z ewentualną flagą `{FLG:...}`). Realizowane **jak w S02E05**: przez `BaseTask.verify()`
    wstrzyknięty do modułu `tools.py` metodą `set_task_verifier(...)` (wzorzec z
    `send_drone_instructions`). **Bez obsługi 429/503** — to zwykłe, jednorazowe wysłanie odpowiedzi.
- **Endpoint powłoki:** `POST {HUB_BASE_URL}/api/shell`, payload:
  ```json
  { "apikey": "{API_KEY}", "cmd": "help" }
  ```
- **Endpoint verify:** `POST {HUB_BASE_URL}/verify`, payload:
  ```json
  {
    "apikey": "{API_KEY}",
    "task": "firmware",
    "answer": { "confirmation": "ECCS-...." }
  }
  ```
- **Brak twardej blokady** komend w `run_shell` — zasady bezpieczeństwa egzekwuje system prompt.
- **Obsługa błędów Shell API wewnątrz `run_shell`** (na podstawie kodu statusu HTTP i/lub body):
  - `429 Too Many Requests` → odczytać `retry_after` (fallback 10 s), `sleep`, ponów.
  - `503 Service Unavailable` → backoff `2, 4, 8 s`, ponów.
  - **Ban** (naruszenie zasad) → wykryć w body/statusie, **nie ponawiać w kółko**; zwrócić agentowi
    **opisowy komunikat** (np. „Dostęp zbanowany na N s — nie powtarzaj tej komendy; rozważ reboot”).
  - Sukces → zwrócić body odpowiedzi (stdout/stderr komendy) do agenta.
- **`submit_answer`** — **bez** obsługi 429/503; deleguje do `BaseTask.verify()` (jak S02E05).
  Retry/ban dotyczy wyłącznie Shell API (`run_shell`).
- **Max iteracji:** `15`.
- `task_name = "firmware"`.
- Logować każde wywołanie narzędzia i odpowiedź (skrócone w logach przy dużym rozmiarze).

---

## Etap 1: Narzędzia — `tasks/S03E02/tools.py`

**Cel:** Zaimplementować dwa narzędzia (`run_shell`, `submit_answer`) z obsługą retry/ban,
definicje `TOOL_DEFINITIONS` oraz dispatcher `tool_executor`.

### 1a. Konfiguracja modułu
- `_ = load_dotenv(find_dotenv())`.
- `API_KEY = os.getenv("API_KEY", "")`, `HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")`.
- `TASK_NAME = "firmware"`.
- Stałe retry (tylko `run_shell`): `_MAX_RETRIES = 5`, `_DEFAULT_RETRY_AFTER = 10`, `_BACKOFF_SEQUENCE = [2, 4, 8]`.
- `logger = setup_logger("S03E02Tools")`.
- **Wstrzykiwana referencja verifiera** (wzorzec z S02E05):
  ```python
  _task_verifier: Any = None

  def set_task_verifier(verifier: Any) -> None:
      """Inject the BaseTask instance so submit_answer() can call BaseTask.verify()."""
      global _task_verifier
      _task_verifier = verifier
  ```

### 1b. Narzędzie `run_shell(cmd)`
- Sygnatura: `run_shell(cmd: str) -> str`.
- Walidacja wejścia: brak `API_KEY`/`HUB_BASE_URL` → `{"error": ...}`.
- `shell_url = f"{HUB_BASE_URL}/api/shell"`; payload `{"apikey": API_KEY, "cmd": cmd}`.
- Pętla `for attempt in range(1, _MAX_RETRIES + 1)`:
  - `requests.post(shell_url, json=payload)` (łapać `requests.RequestException` → `{"error": ...}`).
  - `result = _parse_body(response)` (JSON, fallback `{"raw": response.text}`).
  - `429` → `sleep(_extract_retry_after(result))`, `continue`.
  - `503` → `sleep(_BACKOFF_SEQUENCE[...])`, `continue`.
  - **Ban** (np. `status_code == 403` lub pole w body typu `banned`/`ban_time`) → **nie ponawiać**;
    zwrócić opisowy komunikat z czasem bana, jeśli dostępny.
  - Sukces → `return json.dumps(result, ensure_ascii=False)`.
- Po wyczerpaniu prób → zwrócić ostatnie body/błąd.

### 1c. Narzędzie `submit_answer(confirmation)` — jak S02E05 (`send_drone_instructions`)
- Sygnatura: `submit_answer(confirmation: str) -> str`.
- Walidacja: `if _task_verifier is None:` → `{"error": "Task verifier not initialized."}`.
- Zbudować `answer = {"confirmation": confirmation}` i wywołać `result = _task_verifier.verify(answer)`
  (`BaseTask.verify()` sam składa payload `{apikey, task, answer}` i wysyła do `/verify`).
- **Bez** własnej obsługi 429/503 i bez bezpośredniego `requests` — delegujemy do `verify()`.
- Zwrócić `json.dumps(result, ensure_ascii=False)` (agent szuka w niej flagi `{FLG:...}`).

### 1d. Helpery
- `_parse_body(response)` — `response.json()`, fallback `{"raw": response.text}`.
- `_extract_retry_after(result)` — odczyt `retry_after`/`ban_time` z body, fallback `_DEFAULT_RETRY_AFTER`.
- (opcjonalnie) `_is_ban(response, result)` — wykrycie stanu bana.

### 1e. `TOOL_DEFINITIONS` (schema OpenAI function calling)
- `run_shell`:
  ```json
  {
    "type": "function",
    "name": "run_shell",
    "description": "Wykonuje jedną komendę powłoki na zdalnej maszynie wirtualnej (POST /api/shell) i zwraca jej wynik (stdout/stderr).",
    "parameters": {
      "type": "object",
      "properties": {
        "cmd": { "type": "string", "description": "Komenda powłoki do wykonania, np. 'help'." }
      },
      "required": ["cmd"],
      "additionalProperties": false
    },
    "strict": true
  }
  ```
- `submit_answer`:
  ```json
  {
    "type": "function",
    "name": "submit_answer",
    "description": "Wysyła zdobyty kod (ECCS-...) do Centrali (POST /verify, task 'firmware') i zwraca odpowiedź huba.",
    "parameters": {
      "type": "object",
      "properties": {
        "confirmation": { "type": "string", "description": "Kod w formacie ECCS-xxxx..." }
      },
      "required": ["confirmation"],
      "additionalProperties": false
    },
    "strict": true
  }
  ```

### 1f. Dispatcher `tool_executor(name, args)`
- Rejestr `{"run_shell": run_shell, "submit_answer": submit_answer}` → `func(**args)`.
- Nieznane narzędzie → `{"error": "Unknown tool: ..."}`.

**Pliki do utworzenia:** `tasks/S03E02/tools.py`

---

## Etap 2: Klasa zadania `S03E02` — `tasks/S03E02/S03E02.py`

**Cel:** Zbudować agenta, skonfigurować system prompt i uruchomić pętlę.

### Zakres
1. `tasks/S03E02/__init__.py` (pusty).
2. Klasa `S03E02(BaseTask)`:
   - `__init__()` — `load_dotenv`, `base_url = HUB_BASE_URL`, `task_name="firmware"`.
   - `run()`:
     1. Zbudować `ResponsesService` (`ResponsesService.build(config=ResponsesServiceConfig())`).
     2. **Wstrzyknąć verifier**: `set_task_verifier(self)` (aby `submit_answer` mogło wołać `self.verify()`).
     3. Zbudować **system prompt** (patrz niżej).
     4. `AgentLoop(service, TOOL_DEFINITIONS, tool_executor, SYSTEM_PROMPT, max_iterations=15)`.
     5. `agent.run(messages=[{"role": "user", "content": "Execute the task."}])`.
     6. Zalogować wynik i zwrócić `{"result": assistant_message}`.

### System prompt — kluczowe punkty
- **Cel:** uruchomić `/opt/firmware/cooler/cooler.bin` i zdobyć kod `ECCS-...`, następnie wysłać go
  narzędziem `submit_answer`.
- **Zacznij od `run_shell("help")`** — Shell API ma niestandardowy zestaw komend; nie zakładaj,
  że standardowe komendy Linuxa zadziałają (szczególnie edycja plików działa inaczej — sprawdź `help`).
- **Plan działania (sekwencyjnie, jedno wywołanie = jedno żądanie HTTP):**
  1. `help` → poznaj dostępne komendy.
  2. Spróbuj uruchomić `cooler.bin` (podaj ścieżkę i parametry) — przeanalizuj komunikat błędu.
  3. Znajdź **hasło dostępowe** (zapisane w kilku miejscach w systemie) — przeszukaj dozwolone lokalizacje.
  4. Przekonfiguruj `settings.ini` (w katalogu firmware, wolumen zapisywalny), aby aplikacja działała.
  5. Uruchom ponownie i odczytaj kod `ECCS-...`.
  6. Wywołaj `submit_answer(confirmation="ECCS-...")`.
- **ZASADY BEZPIECZEŃSTWA (bezwzględnie przestrzegaj — naruszenie = ban i reset):**
  - Nie zaglądaj do `/etc`, `/root`, `/proc/`.
  - Respektuj każdy napotkany `.gitignore` — nie czytaj/nie modyfikuj wymienionych tam plików/katalogów.
  - Działasz jako zwykły użytkownik.
  - Jeśli mocno namieszasz w systemie, użyj `run_shell("reboot")`, aby przywrócić stan początkowy.
- **Obsługa błędów:** czytaj komunikaty uważnie; jeśli narzędzie zgłosi ban/rate limit, **nie
  powtarzaj tej samej komendy w pętli** — zmień podejście lub rozważ reboot.
- **Zakończenie:** gdy odpowiedź `submit_answer` zawiera flagę `{FLG:...}`, umieść tę flagę
  w końcowej odpowiedzi tekstowej.

**Pliki do utworzenia:** `tasks/S03E02/S03E02.py`, `tasks/S03E02/__init__.py`

---

## Etap 3: Testowanie i debugowanie

**Cel:** Uruchomić zadanie i zweryfikować poprawność.

### Zakres
1. Uruchomić: `uv run main.py --dict S03E02 --task S03E02`.
2. Sprawdzić logi:
   - Czy pierwsze wywołanie to `run_shell("help")` i czy zwraca listę dostępnych komend.
   - Czy agent poprawnie eksploruje system, znajduje hasło i lokalizuje `settings.ini`.
   - Czy `run_shell` poprawnie buduje payload (`{"apikey", "cmd"}`) i obsługuje 429/503/ban.
   - Czy agent **nie narusza** zasad bezpieczeństwa (brak dostępu do `/etc`, `/root`, `/proc`,
     respektowanie `.gitignore`).
   - Czy po rekonfiguracji `settings.ini` aplikacja zwraca kod `ECCS-...`.
   - Czy `submit_answer` wysyła poprawny payload i zwraca flagę `{FLG:...}`.
3. W razie zablokowania/niepowodzenia — `run_shell("reboot")` i ponowna próba.
4. Potwierdzić zachowanie limitu `max_iterations=15`.

---

## Podsumowanie plików

| Plik | Akcja |
|------|-------|
| `tasks/S03E02/tools.py` | Nowy — `run_shell` (POST /api/shell + retry/ban 429/503) + `submit_answer` (przez `BaseTask.verify()` — jak S02E05, `set_task_verifier`) + `TOOL_DEFINITIONS` + `tool_executor` |
| `tasks/S03E02/S03E02.py` | Nowy — klasa `S03E02(BaseTask)` z agentem (task `firmware`, max_iterations=15) |
| `tasks/S03E02/__init__.py` | Nowy — pusty init |

## Kolejność realizacji
Etap 1 → Etap 2 → Etap 3. Etap 1 można wstępnie przetestować samodzielnie
(wywołanie `run_shell("help")` i sprawdzenie odpowiedzi Shell API przed podłączeniem agenta).
