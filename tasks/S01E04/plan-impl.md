# Plan implementacji S01E04 — "SendIt" (deklaracja transportu SPK)

## Opis zadania
Przygotować i wysłać do Centrali poprawnie wypełnioną **deklarację transportu** w Systemie
Przesyłek Konduktorskich (SPK), zgodnie z dokumentacją. Zadanie realizuje **agent AI z tool
callingiem**, który samodzielnie pobiera dokumentację (w tym pliki graficzne — **vision**),
wypełnia deklarację i wysyła ją do weryfikacji, poprawiając w razie odrzucenia.

### Dane niezbędne do deklaracji (z opisu zadania)
- Nadawca (identyfikator): `450202122`
- Punkt nadawczy: Gdańsk
- Punkt docelowy: Żarnowiec
- Waga: 2,8 tony (2800 kg)
- Budżet: 0 PP (przesyłka darmowa / finansowana przez System)
- Zawartość: kasety z paliwem do reaktora
- Uwagi specjalne: brak

> Format i szczegóły (kod trasy, kategoria, opłata) agent ustala **dynamicznie** z dokumentacji.

## Decyzje architektoniczne (ustalone)
- Reużywamy istniejącej infrastruktury: `AgentLoop` (pętla agencka), `ResponsesService`
  (klient LLM z `generate_with_tools`), `HttpUtil` (hub), `BaseTask.verify()` (weryfikacja).
- Wzorujemy się na S01E02: `tools.py` z implementacjami + `TOOL_DEFINITIONS` + `tool_executor`,
  wstrzykiwanie zależności przez settery, klasa zadania `S01E04(BaseTask)`.
- **Vision**: narzędzie `get_image_information` używa **tego samego skonfigurowanego modelu**
  co reszta agenta (model musi być vision-capable). Obraz jest **pobierany z huba i kodowany
  jako base64 data URL** (hub może nie być publicznie dostępny dla providera).
- **Format deklaracji**: agent ustala go w całości na podstawie dokumentacji (bez sztywnego
  szablonu w kodzie).
- **Max iteracji**: `10`.
- `task_name = "sendit"`; weryfikacja przez `BaseTask.verify(answer)` gdzie
  `answer = {"declaration": "<pełny tekst>"}`.

---

## Etap 1: Wsparcie vision w `ResponsesService`

**Cel:** Dodać do `ResponsesService` metodę do pojedynczego wywołania modelu z załączonym obrazem.

### Zakres
- Nowa metoda `analyze_image(*, query: str, image_bytes: bytes, mime_type: str) -> str`:
  - Buduje `input` Responses API z jedną wiadomością `user` zawierającą dwie części:
    - `{"type": "input_text", "text": query}`
    - `{"type": "input_image", "image_url": "data:{mime_type};base64,{b64}"}`
  - Wykorzystuje `self._model` (ten sam model co agent) oraz istniejące
    `_apply_optional_request_settings` (reasoning/temperature).
  - Zwraca `response.output_text` (tekstowy opis / wyekstrahowane dane).
  - Reużywa istniejących flag logowania (`_LOG_INPUT_ENV`, `_LOG_OUTPUT_ENV`).

**Pliki do modyfikacji:**
- `llmService/responses_service.py`

---

## Etap 2: Implementacja narzędzi (tools) — `tasks/S01E04/tools.py`

**Cel:** Zaimplementować 4 narzędzia agenta + definicje + dispatcher, wzorując się na S01E02.

### 2a. Wstrzykiwanie zależności (settery)
- `set_http_util(http_util)` — do wywołań GET na hub.
- `set_task_verifier(verifier)` — do `verify()`.
- `set_responses_service(service)` — do wywołań vision w `get_image_information`.

### 2b. Implementacje narzędzi
1. `get_main_documentation() -> str`
   - GET `{HUB_BASE_URL}/dane/doc/index.md` (tekst).
   - Zwraca treść markdown.
2. `get_md_attachment(filename: str) -> str`
   - GET `{HUB_BASE_URL}/dane/doc/{filename}` (tekst).
   - Zwraca treść markdown wskazanego załącznika.
3. `get_image_information(filename: str, query: str) -> str`
   - GET `{HUB_BASE_URL}/dane/doc/{filename}` jako **bytes** (`HttpUtil.getData(..., ResponseType.CONTENT)`).
   - Ustalić `mime_type` z rozszerzenia pliku (`.png`, `.jpg/.jpeg`, `.webp`, `.gif`).
   - Zakodować base64 i wywołać `ResponsesService.analyze_image(query=..., image_bytes=..., mime_type=...)`.
   - Zwraca tekstową odpowiedź modelu (informacje potrzebne do deklaracji).
4. `verify(declaration: str) -> str`
   - Wywołuje `_task_verifier.verify({"declaration": declaration})`.
   - Zwraca odpowiedź huba (flaga `{FLG:...}` lub komunikat błędu) jako JSON string.

> Każde narzędzie zwraca `str` (JSON lub tekst) — gotowe do wstawienia jako wynik tool calla.
> Błędy sieciowe/parsowania obsługiwane defensywnie (zwrot `{"error": ...}`), by agent mógł reagować.

### 2c. Definicje narzędzi (`TOOL_DEFINITIONS`)
- Format OpenAI function calling (`type: "function"`, `name`, `description`, `parameters`, `strict: True`),
  zgodnie ze schematem używanym w S01E02.
- Parametry: `get_md_attachment{filename}`, `get_image_information{filename, query}`,
  `verify{declaration}`; `get_main_documentation` bez parametrów.

### 2d. Dispatcher `tool_executor(name, args)`
- Rejestr nazw → funkcje, analogicznie do S01E02.

**Pliki do utworzenia:**
- `tasks/S01E04/tools.py`

---

## Etap 3: Klasa zadania `S01E04`

**Cel:** Uruchomić agenta i przesłać wynik do weryfikacji.

### Zakres
1. `tasks/S01E04/__init__.py` (pusty) oraz `tasks/S01E04/S01E04.py`.
2. Klasa `S01E04(BaseTask)`:
   - `__init__()` — `load_dotenv`, `base_url = HUB_BASE_URL`, `task_name="sendit"`.
   - `run()`:
     1. Wstrzyknąć zależności: `set_task_verifier(self)`, `set_http_util(HttpUtil(base_url))`,
        `set_responses_service(service)`.
     2. Zbudować `ResponsesService` (jak w S01E02 — `_build_responses_service`).
     3. Zbudować **system prompt** zawierający: cel, komplet danych przesyłki (z opisu zadania),
        instrukcję "czytaj CAŁĄ dokumentację (nie tylko index.md), nie pomijaj plików graficznych,
        zachowaj dokładny format wzoru deklaracji", oraz polecenie użycia `verify` na końcu i
        analizy komunikatu błędu przy odrzuceniu.
     4. Utworzyć `AgentLoop(service, TOOL_DEFINITIONS, tool_executor, SYSTEM_PROMPT, max_iterations=10)`.
     5. `agent.run(...)` i zwrócić wynik (flaga lub komunikat po wyczerpaniu iteracji).

**Pliki do utworzenia:**
- `tasks/S01E04/S01E04.py`
- `tasks/S01E04/__init__.py`

---

## Etap 4: Testowanie i debugowanie

**Cel:** Uruchomić zadanie i zweryfikować poprawność.

### Zakres
1. Uruchomić: `python main.py --dict S01E04 --task S01E04`.
2. Sprawdzić logi:
   - Czy agent pobiera `index.md` i wszystkie powiązane załączniki (md + graficzne).
   - Czy `get_image_information` poprawnie pobiera obraz, koduje base64 i zwraca sensowne dane.
   - Czy poprawnie ustala kod trasy Gdańsk–Żarnowiec, kategorię i opłatę (0 PP — kategoria finansowana przez System).
   - Czy format deklaracji odpowiada wzorowi z dokumentacji.
3. Sprawdzić odpowiedź `verify` — czy zwraca flagę `{FLG:...}`.
4. W razie odrzucenia — potwierdzić, że agent czyta błąd, poprawia deklarację i ponawia (w ramach 10 iteracji).

---

## Podsumowanie plików

| Plik | Akcja |
|------|-------|
| `llmService/responses_service.py` | Modyfikacja — nowa metoda `analyze_image()` (vision, single call) |
| `tasks/S01E04/tools.py` | Nowy — 4 narzędzia + `TOOL_DEFINITIONS` + `tool_executor` + settery |
| `tasks/S01E04/S01E04.py` | Nowy — klasa zadania `S01E04(BaseTask)` z agentem (task `sendit`) |
| `tasks/S01E04/__init__.py` | Nowy — pusty init |

## Kolejność realizacji
Etap 1 → Etap 2 → Etap 3 → Etap 4. Każdy etap jest samodzielnie testowalny
(Etap 1: szybki test vision na pojedynczym obrazie; Etapy 2–3: pełny przebieg agenta).
