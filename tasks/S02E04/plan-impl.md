# Plan implementacji S02E04 — "Mailbox" (przeszukanie skrzynki mailowej przez API zmail)

## Opis zadania
Przeszukać skrzynkę mailową przez **API zmail** i wyciągnąć **trzy informacje**:

- `date` — data (format `YYYY-MM-DD`), kiedy dział bezpieczeństwa planuje atak na elektrownię.
- `password` — hasło do systemu pracowniczego, prawdopodobnie wciąż obecne w skrzynce.
- `confirmation_code` — kod potwierdzenia z ticketa działu bezpieczeństwa
  (format: `SEC-` + 32 znaki = łącznie 36 znaków).

Co wiemy na start:
- Wiadomość doniosł Wiktor (nie znamy nazwiska), wysłana z domeny **proton.me**.
- API działa jak wyszukiwarka Gmail — obsługuje operatory `from:`, `to:`, `subject:`, `OR`, `AND`.
- **Skrzynka jest aktywna** — w trakcie pracy mogą wpływać nowe maile; jeśli czegoś nie ma,
  warto ponowić wyszukiwanie.
- **Dwuetapowe pobieranie:** najpierw wyszukanie zwraca listę maili z metadanymi (bez treści),
  potem pobiera się pełną treść wybranych wiadomości po ich identyfikatorach.

Zadanie realizuje **agent AI z tool callingiem**, który samodzielnie odkrywa dostępne akcje
(zaczynając od `help`), przeszukuje skrzynkę, czyta treść maili, składa trzy wartości
i wysyła odpowiedź, korzystając z feedbacku huba aż do otrzymania flagi `{FLG:...}`.

## Komunikacja z API
- **API zmail:** `POST {HUB_BASE_URL}/api/zmail`, `Content-Type: application/json`.
  Body zawiera co najmniej: `apikey`, `action`, `page` (paginacja) oraz parametry akcji.
  Dostępne akcje i ich parametry poznajemy przez `action: "help"` — nie zgadujemy nazw.
  - `getInbox` — pobranie zawartości inboxa (paginowane przez `page`).
  - akcja wyszukiwania (nazwę i parametry ustala `help`) — obsługuje operatory `from:`, `to:`,
    `subject:`, `OR`, `AND`.
  - akcja pobrania pełnej treści maila po ID (nazwę i parametry ustala `help`).
- **Weryfikacja odpowiedzi:** `POST {HUB_BASE_URL}/verify` w formacie:
  ```json
  {
    "apikey": "{API_KEY}",
    "task": "mailbox",
    "answer": {
      "password": "znalezione-haslo",
      "date": "znaleziona-data",
      "confirmation_code": "SEC-..."
    }
  }
  ```
  Hub zwraca błąd (ze wskazaniem brakujących/błędnych wartości) albo flagę `{FLG:...}`.

## Decyzje architektoniczne (ustalone)
- Reużywamy istniejącej infrastruktury: `AgentLoop` (pętla agencka), `ResponsesService`
  (klient LLM z `generate_with_tools`), `BaseTask` (klasa bazowa zadania).
- Wzorujemy się na **S01E05** (agencki system prompt po polsku, budowa `ResponsesService`,
  `AgentLoop`) oraz na **S01E02** (wstrzykiwanie zależności do modułu `tools.py` przez
  settery: `set_http_util`, `set_task_verifier`).
- Narzędzia **nie używają `requests` bezpośrednio** — korzystają z wstrzykniętych obiektów:
  - `HttpUtil.sendData(payload, endpoint)` do wywołań API zmail (`POST /api/zmail`),
  - `BaseTask.verify(answer)` (przez wstrzyknięty `_task_verifier`) do wysyłki odpowiedzi
    na `POST /verify`.
  Obie metody zwracają już sparsowany `dict`, więc nie potrzebujemy własnego parsowania JSON.
- **BEZ obsługi 429/503** (wprost wykluczone w treści zadania) — brak pętli retry/backoff
  na kodach statusu HTTP. Wystarczy defensywna obsługa (brak wstrzykniętej zależności).
- **Dwa narzędzia:**
  1. `call_zmail(action, parametry)` — `_http_util.sendData(..., "/api/zmail")`; jedno narzędzie
     na wszystkie akcje zmail (`help`, `getInbox`, wyszukiwanie, pobranie pełnej treści).
     `parametry` jako obiekt z `additionalProperties: True` (tryb **nie-strict**), bo zestaw
     pól jest dynamiczny.
  2. `submit_answer(password, date, confirmation_code)` — `_task_verifier.verify(answer)` z
     `answer = {"password", "date", "confirmation_code"}`; zwraca **surowy feedback huba**,
     żeby agent wiedział, których wartości brakuje / które są błędne, i mógł iterować.
- **Feedback loop w agencie:** agent sam wywołuje `submit_answer`, czyta odpowiedź huba,
  poprawia brakujące/błędne pola (ew. ponawiając wyszukiwanie na aktywnej skrzynce)
  i kończy, gdy w odpowiedzi pojawi się flaga `{FLG:...}`.
- **Max iteracji:** `15`.
- `task_name = "mailbox"`.
- Logować każde wywołanie narzędzia i odpowiedź (jak w S01E05).

---

## Etap 1: Implementacja narzędzi — `tasks/S02E04/tools.py`

**Cel:** Zaimplementować dwa narzędzia (`call_zmail`, `submit_answer`) + definicje + dispatcher.

### 1a. Konfiguracja modułu
- `API_KEY = os.getenv("API_KEY", "")`.
- `logger = setup_logger("S02E04Tools")`.
- **Wstrzykiwane zależności** (wzorzec S01E02) — zmienne modułowe + settery:
  ```python
  _http_util: HttpUtil | None = None
  _task_verifier: Any = None

  def set_http_util(http_util: HttpUtil) -> None: ...
  def set_task_verifier(verifier: Any) -> None: ...
  ```
  Ustawiane przez `S02E04.run()` przed startem agenta.

### 1b. Narzędzie `call_zmail`
- Sygnatura: `call_zmail(action: str, parametry: Dict[str, Any] | None = None) -> str`.
- Zbudować payload przez spłaszczenie parametrów obok `action`:
  ```python
  payload = {"apikey": API_KEY, "action": action, **(parametry or {})}
  ```
  (dzięki temu `page` i operatory wyszukiwania trafiają na najwyższy poziom body,
  zgodnie z przykładami z treści zadania; dokładne nazwy pól ustala `help`).
- Wywołanie: `data = _http_util.sendData(payload, "/api/zmail")` — zwraca `dict`;
  zwrócić `json.dumps(data, ensure_ascii=False)`.
- Defensywnie: brak wstrzykniętego `_http_util` → `{"error": "HttpUtil not initialized."}`.
  **Bez retry na 429/503.**
- Logować `action` oraz skrót odpowiedzi.

### 1c. Narzędzie `submit_answer`
- Sygnatura: `submit_answer(password: str, date: str, confirmation_code: str) -> str`.
- Zbudować obiekt odpowiedzi i wysłać przez wstrzyknięty verifier:
  ```python
  answer = {"password": password, "date": date, "confirmation_code": confirmation_code}
  result = _task_verifier.verify(answer)  # BaseTask.verify -> POST /verify, zwraca dict
  ```
- Zwrócić `json.dumps(result, ensure_ascii=False)` (surowy feedback huba — agent czyta
  z niego brakujące/błędne pola oraz flagę).
- Defensywnie: brak `_task_verifier` → `{"error": "Task verifier not initialized."}`.
  **Bez retry 429/503.**

### 1d. Definicje narzędzi (`TOOL_DEFINITIONS`) — schema OpenAI function calling
- `call_zmail` (nie-strict):
  - `action`: string (wymagane), opis: "Nazwa akcji API zmail, np. 'help', 'getInbox'".
  - `parametry`: object, `additionalProperties: True`, opis: "Parametry akcji jako pary
    klucz-wartość (np. page, query, operatory from:/to:/subject:, id maila), zgodnie z
    dokumentacją zwróconą przez 'help'. Pomiń dla akcji bez parametrów."
  - `required: ["action"]`, `additionalProperties: False` na poziomie głównym.
- `submit_answer` (może być strict):
  - `password`, `date` (format `YYYY-MM-DD`), `confirmation_code` (format `SEC-` + 32 znaki)
    — wszystkie string i wymagane.

### 1e. Dispatcher `tool_executor(name, args)`
- Rejestr `{"call_zmail": call_zmail, "submit_answer": submit_answer}` → `func(**args)`.
- Nieznane narzędzie → `{"error": "Unknown tool: ..."}`.

**Pliki do utworzenia:**
- `tasks/S02E04/tools.py`

---

## Etap 2: Klasa zadania `S02E04` — `tasks/S02E04/S02E04.py`

**Cel:** Zbudować agenta, skonfigurować prompt i uruchomić pętlę.

### Zakres
1. `tasks/S02E04/__init__.py` (pusty) oraz `tasks/S02E04/S02E04.py`.
2. Klasa `S02E04(BaseTask)`:
   - `__init__()` — `load_dotenv(find_dotenv())`, `base_url = HUB_BASE_URL`,
     `super().__init__(base_url=base_url, task_name="mailbox")`.
   - `run()`:
     1. Zbudować `ResponsesService` (jak w S01E05 — `_build_responses_service` /
        `ResponsesService.build(config=ResponsesServiceConfig())`).
     2. **Wstrzyknąć zależności do `tools`** (wzorzec S01E02):
        - `set_http_util(HttpUtil(self.base_url))`,
        - `set_task_verifier(self)` (klasa dziedziczy `BaseTask.verify`).
     3. Zbudować **system prompt** po polsku (patrz niżej).
     4. `AgentLoop(service, TOOL_DEFINITIONS, tool_executor, SYSTEM_PROMPT, max_iterations=15)`.
     5. `agent.run(messages=[{"role": "user", "content": "Execute the task."}])`,
        zalogować wynik, zwrócić `{"result": assistant_message}`.
   - `_build_responses_service` / `_responses_service_config` — jak w S01E05.

### System prompt — kluczowe punkty (po polsku)
- **Cel:** przeszukać skrzynkę mailową przez API zmail i zebrać trzy wartości:
  `date` (YYYY-MM-DD — planowany atak działu bezpieczeństwa), `password` (hasło do systemu
  pracowniczego), `confirmation_code` (kod z ticketa, format `SEC-` + 32 znaki = 36 znaków).
- **Zacznij od `call_zmail(action="help")`** — dokładnie przeczytaj dokumentację
  (dostępne akcje, ich parametry, sposób wyszukiwania i pobierania pełnej treści).
- **Dwuetapowo:** najpierw wyszukaj/pobierz listę maili (metadane), potem pobierz **pełną treść**
  wybranych wiadomości po ID — nie wnioskuj z samego tematu.
- **Buduj zapytania** z operatorów `from:`, `to:`, `subject:`, `OR`, `AND`. Wiktor pisał
  z domeny **proton.me** — zacznij szeroko (np. `from:proton.me`), potem zawężaj.
- **Aktywna skrzynka:** jeśli czegoś nie znajdujesz, ponów wyszukiwanie / pobierz kolejne
  strony (`page`) — nowe maile mogły dopiero wpłynąć. Nie zakładaj od razu, że informacja
  nie istnieje.
- **Szukaj po kolei** — nie musisz znaleźć wszystkiego naraz.
- **Wysyłaj odpowiedź** przez `submit_answer(password, date, confirmation_code)` i czytaj
  feedback huba — poprawiaj brakujące/błędne wartości i wysyłaj ponownie.
- **Flaga:** gdy w odpowiedzi huba pojawi się `{FLG:...}`, zadanie ukończone — umieść flagę
  w końcowej odpowiedzi tekstowej.

**Pliki do utworzenia:**
- `tasks/S02E04/S02E04.py`
- `tasks/S02E04/__init__.py`

---

## Etap 3: Testowanie i debugowanie

**Cel:** Uruchomić zadanie i zweryfikować poprawność.

### Zakres
1. Uruchomić: `uv run main.py --dict S02E04 --task S02E04`.
2. Sprawdzić logi:
   - Czy pierwszy call to `call_zmail(action="help")` i czy zwraca sensowną dokumentację
     (nazwy akcji wyszukiwania i pobierania treści, parametry, paginacja).
   - Czy agent buduje poprawne zapytania z operatorów i czyta **pełną treść** maili.
   - Czy `submit_answer` zwraca feedback huba i czy agent poprawnie iteruje na brakujące/błędne pola.
   - Czy obsłużono aktywną skrzynkę (ponowne wyszukiwanie / kolejne strony).
3. Zweryfikować format wartości: `date` = `YYYY-MM-DD`, `confirmation_code` = `SEC-` + 32 znaki.
4. Potwierdzić pojawienie się flagi `{FLG:...}` i zakończenie w ramach `max_iterations=15`.

---

## Podsumowanie plików

| Plik | Akcja |
|------|-------|
| `tasks/S02E04/tools.py` | Nowy — `call_zmail` (przez `HttpUtil.sendData` → `/api/zmail`) + `submit_answer` (przez `BaseTask.verify` → `/verify`, feedback) + settery `set_http_util`/`set_task_verifier` + `TOOL_DEFINITIONS` + `tool_executor`; bez retry 429/503 |
| `tasks/S02E04/S02E04.py` | Nowy — klasa zadania `S02E04(BaseTask)`; wstrzykuje `HttpUtil`/verifier do `tools`, buduje agenta (task `mailbox`, `max_iterations=15`, polski system prompt) |
| `tasks/S02E04/__init__.py` | Nowy — pusty init |

## Kolejność realizacji
Etap 1 → Etap 2 → Etap 3. Etap 1 można wstępnie przetestować samodzielnie
(wywołanie `call_zmail(action="help")` i sprawdzenie odpowiedzi API zmail przed podłączeniem agenta).
