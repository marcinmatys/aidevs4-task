# Plan implementacji S01E05 — "Railway" (aktywacja trasy X-01 przez nieznane API)

## Opis zadania
Aktywować trasę kolejową o nazwie **X-01** za pomocą API, do którego **nie mamy dokumentacji**.
Wiadomo, że API obsługuje akcję `help`, która zwraca własną dokumentację — od niej należy zacząć.
Zadanie realizuje **agent AI z tool callingiem**, który samodzielnie odkrywa dostępne akcje,
ich parametry oraz wymaganą kolejność wywołań i doprowadza do aktywacji trasy.

- Agent kończy pracę, gdy w odpowiedzi API otrzyma flagę `{FLG:...}` **lub** osiągnie maksymalną
  liczbę iteracji (`10`).
- Agent dysponuje **jednym** narzędziem: `call_api`.

## Decyzje architektoniczne (ustalone)
- Reużywamy istniejącej infrastruktury: `AgentLoop` (pętla agencka), `ResponsesService`
  (klient LLM z `generate_with_tools`), `BaseTask` (klasa bazowa zadania).
- Wzorujemy się na **S01E04** (struktura `tools.py` + `TOOL_DEFINITIONS` + `tool_executor`,
  klasa `S01EXX(BaseTask)`, budowa `ResponsesService`).
- **Nie używamy** `HttpUtil` ani setterów wstrzykujących zależności — narzędzie `call_api`
  wykonuje żądanie bezpośrednio przez `requests` (dostęp do `response.status_code`) i czyta
  `HUB_BASE_URL`/`API_KEY` z env.
- **Endpoint:** wszystkie akcje idą na `{HUB_BASE_URL}/verify` w formacie:
  ```json
  {
    "apikey": "{API_KEY}",
    "task": "railway",
    "answer": {
      "action": "action_name",
      "param_1_name": "param1_value",
      "param_n_name": "param_n_value"
    }
  }
  ```
  tzn. `answer` = `{"action": <action>, **<parametry>}` (action + spłaszczone parametry).
- **Narzędzie `call_api(action, parametry)`** — `parametry` jako **obiekt** (dodatkowe pola
  dozwolone, tryb **nie-strict**), bo zestaw pól jest dynamiczny (ustalany z `help`).
- **Retry** obsługiwany **wewnątrz narzędzia** `call_api` (nie zużywa iteracji agenta),
  decyzja podejmowana na podstawie **kodu statusu HTTP** odpowiedzi (nie pól JSON):
  - `429 Too Many Requests` → odczekać `retry_after` sekund (z body, domyślnie 10 s) i ponowić.
  - `503 Service Unavailable` → retry z backoffem (2s, 4s, 8s).
- **Kanał verify:** `call_api` wykonuje `POST /verify` **bezpośrednio przez `requests`**
  (a nie `HttpUtil.sendData`), aby mieć dostęp do `response.status_code` i poprawnie rozróżnić
  429/503 od odpowiedzi biznesowych. Nie używamy `BaseTask.verify()` (brak tam retry).
- **Max iteracji:** `10`.
- `task_name = "railway"`.
- Logować każde wywołanie i odpowiedź.

---

## Etap 1: Implementacja narzędzia (tools) — `tasks/S01E05/tools.py`

**Cel:** Zaimplementować jedno narzędzie `call_api` z obsługą retry + definicję + dispatcher.

### 1a. Konfiguracja
- `verify_url = f"{HUB_BASE_URL}/verify"` (z `os.getenv("HUB_BASE_URL")`).
- `API_KEY = os.getenv("API_KEY")`.
- Nie potrzebujemy settera `HttpUtil` — `call_api` używa `requests` bezpośrednio, by mieć
  dostęp do kodu statusu HTTP.

### 1b. Implementacja narzędzia `call_api`
- Sygnatura: `call_api(action: str, parametry: Dict[str, Any] | None = None) -> str`.
- Zbudować payload:
  ```python
  answer = {"action": action, **(parametry or {})}
  payload = {"apikey": API_KEY, "task": "railway", "answer": answer}
  ```
- Wysłać `POST {HUB_BASE_URL}/verify` **bezpośrednio przez `requests.post(verify_url, json=payload)`**
  (dostęp do `response.status_code`).
- **Obsługa retry na podstawie `response.status_code`** (pętla z limitem prób, np. `max_retries = 5`):
  - `status_code == 429` → odczytać `retry_after` z body (fallback 10 s), `time.sleep(retry_after)` i ponów.
  - `status_code == 503` → backoff `2, 4, 8 s` i ponów.
  - `status_code == 200` (lub inny sukces) → zwrócić body odpowiedzi.
  - Po wyczerpaniu prób → zwrócić ostatnie body/błąd, by agent mógł zareagować.
- Parsować body przez `response.json()` (defensywnie: fallback na `response.text` przy błędzie parsowania).
- Zwracać odpowiedź huba jako `json.dumps(result, ensure_ascii=False)` — gotowe do wstawienia
  jako wynik tool calla (agent czyta z niej dokumentację `help`, błędy i flagę).
- Błędy defensywnie: brak `API_KEY`/`HUB_BASE_URL` → `{"error": ...}`; wyjątki sieciowe → `{"error": ...}`.

### 1c. Definicja narzędzia (`TOOL_DEFINITIONS`)
- Format OpenAI function calling. **Tryb nie-strict** dla elastycznych parametrów:
  ```python
  {
      "type": "function",
      "name": "call_api",
      "description": "Wysyła pojedyncze żądanie do API systemu sterowania trasami kolejowymi (POST /verify) z podaną akcją i opcjonalnymi parametrami i zwraca odpowiedź API.",
      "parameters": {
          "type": "object",
          "properties": {
              "action": {"type": "string", "description": "Nazwa akcji API, np. 'help'"},
              "parametry": {
                  "type": "object",
                  "description": "Parametry akcji jako pary klucz-wartość, zgodnie z dokumentacją zwróconą przez 'help'. Pomiń dla akcji bez parametrów.",
                  "additionalProperties": True
              }
          },
          "required": ["action"],
          "additionalProperties": False
      }
      # UWAGA: brak "strict": True — bo parametry mają additionalProperties: True
  }
  ```

### 1d. Dispatcher `tool_executor(name, args)`
- Rejestr `{"call_api": call_api}` → wywołanie `func(**args)`.

**Pliki do utworzenia:**
- `tasks/S01E05/tools.py`

---

## Etap 2: Klasa zadania `S01E05` — `tasks/S01E05/S01E05.py`

**Cel:** Zbudować agenta, skonfigurować prompt i uruchomić pętlę.

### Zakres
1. `tasks/S01E05/__init__.py` (pusty) oraz `tasks/S01E05/S01E05.py`.
2. Klasa `S01E05(BaseTask)`:
   - `__init__()` — `load_dotenv`, `base_url = HUB_BASE_URL`, `task_name="railway"`.
   - `run()`:
     1. Zbudować `ResponsesService` (jak w S01E04 — `_build_responses_service` /
        `ResponsesService.build(config=ResponsesServiceConfig())`).
     2. Zbudować **system prompt** (patrz niżej).
        (Narzędzie `call_api` samodzielnie czyta `HUB_BASE_URL`/`API_KEY` z env —
        brak wstrzykiwania `HttpUtil`.)
     3. Utworzyć `AgentLoop(service, TOOL_DEFINITIONS, tool_executor, SYSTEM_PROMPT, max_iterations=10)`.
     4. `agent.run(messages=[{"role": "user", "content": "Execute the task."}])`,
        zalogować wynik i zwrócić `{"result": assistant_message}`.

### System prompt — kluczowe punkty (na podstawie "Wskazówek dla agenta")
- Cel: **aktywować trasę kolejową X-01** przez API bez dokumentacji.
- **Zacznij od `call_api(action="help")`** — dokładnie przeczytaj zwróconą dokumentację
  (dostępne akcje, parametry, wymagana kolejność wywołań).
- **Postępuj ściśle wg dokumentacji** — nie zgaduj nazw akcji ani parametrów; używaj dokładnie
  wartości zwróconych przez `help`.
- **Czytaj błędy uważnie** — komunikat błędu zwykle precyzyjnie wskazuje, co poprawić
  (zły parametr, zła kolejność akcji itp.).
- **Szukaj flagi** — gdy w treści odpowiedzi pojawi się `{FLG:...}`, zadanie ukończone;
  umieść flagę w końcowej odpowiedzi tekstowej.

**Pliki do utworzenia:**
- `tasks/S01E05/S01E05.py`
- `tasks/S01E05/__init__.py`

---

## Etap 3: Testowanie i debugowanie

**Cel:** Uruchomić zadanie i zweryfikować poprawność.

### Zakres
1. Uruchomić: `python main.py --dict S01E05 --task S01E05`.
2. Sprawdzić logi:
   - Czy pierwszy call to `call_api(action="help")` i czy zwraca sensowną dokumentację.
   - Czy agent poprawnie odczytuje dostępne akcje i kolejność wywołań.
   - Czy `call_api` prawidłowo buduje payload (`answer = {action, **parametry}`).
   - Czy retry dla 429/503 działa (jeśli wystąpią) — odpowiednie `sleep`/backoff.
   - Czy agent reaguje na komunikaty błędów i koryguje wywołania.
3. Sprawdzić, czy w odpowiedzi pojawia się flaga `{FLG:...}` i czy agent kończy pracę.
4. Potwierdzić zachowanie limitu `max_iterations=10`.

---

## Podsumowanie plików

| Plik | Akcja |
|------|-------|
| `tasks/S01E05/tools.py` | Nowy — narzędzie `call_api` (POST przez `requests` + retry 429/503 wg statusu HTTP) + `TOOL_DEFINITIONS` + `tool_executor` |
| `tasks/S01E05/S01E05.py` | Nowy — klasa zadania `S01E05(BaseTask)` z agentem (task `railway`) |
| `tasks/S01E05/__init__.py` | Nowy — pusty init |

## Kolejność realizacji
Etap 1 → Etap 2 → Etap 3. Etap 1 można wstępnie przetestować samodzielnie
(wywołanie `call_api(action="help")` i sprawdzenie odpowiedzi huba przed podłączeniem agenta).
