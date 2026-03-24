# Plan implementacji S01E02 — "Find Him"

## Opis zadania
Namierzyć podejrzaną osobę, która przebywała najbliżej jednej z elektrowni. Ustalić która to była elektrownia oraz poziom dostępu (`access_level`) dla tej osoby. Zadanie realizowane przez agenta AI z mechanizmem **function calling**.

## Decyzje architektoniczne
- Agent korzysta z **natywnego function calling** (OpenAI tools) — LLM samodzielnie decyduje, które narzędzia wywołać.
- Używamy istniejącego `ResponsesService` — rozszerzamy go o metodę do pojedynczego wywołania z tools (bez pętli). `ResponsesService` pozostaje ogólnym klientem LLM.
- Pętla agencka jest wydzielona do osobnej klasy `AgentLoop` (orkiestruje wywołania LLM i narzędzi).
- Weryfikacja przez `BaseTask.verify()` — przekazujemy tylko obiekt `answer`.

---

## Etap 1: Rozszerzenie `ResponsesService` + klasa `AgentLoop`

**Cel:** Dodać do `ResponsesService` metodę do pojedynczego wywołania z tools. Wydzielić logikę pętli agenckiej do osobnej klasy.

### 1a. Nowa metoda w `ResponsesService`

Dodać metodę `generate_with_tools()` w `ResponsesService`:
- Przyjmuje: `messages` (lista wiadomości konwersacji), `tools` (definicje narzędzi w formacie OpenAI).
- Wykonuje **pojedyncze** wywołanie modelu (Responses API) z przekazanymi tools.
- Zwraca: surowy obiekt odpowiedzi (response) — bez interpretacji, czy to tool_call, czy tekst.
- `ResponsesService` **nie zawiera** logiki pętli agenta — jest tylko klientem LLM.

**Pliki do modyfikacji:**
- `llmService/responses_service.py`

### 1b. Klasa `AgentLoop`

Utworzyć klasę `AgentLoop` (np. w `llmService/agent_loop.py`):
- Przyjmuje: `ResponsesService`, `tools` (definicje), `tool_executor` (callable dispatcher), `system_prompt`, `max_iterations` (domyślnie 15).
- Metoda `run()` realizuje **pętlę agencką**:
  1. Inicjalizuje konwersację z system promptem.
  2. Wywołuje `ResponsesService.generate_with_tools()` z aktualną konwersacją.
  3. Jeśli odpowiedź zawiera `tool_calls` — wykonuje je przez `tool_executor`, dodaje wyniki do konwersacji, i wraca do kroku 2.
  4. Jeśli odpowiedź to tekst (bez tool calls) — zwraca go jako wynik końcowy.
  5. Limit iteracji jako zabezpieczenie.
- Logowanie każdej iteracji (wywołane narzędzia, wyniki).

**Pliki do utworzenia:**
- `llmService/agent_loop.py`

---

## Etap 2: Implementacja narzędzi (tools) dla agenta

**Cel:** Zaimplementować wszystkie narzędzia, z których agent będzie korzystał.

**Zakres:**
1. Utworzyć plik `tasks/S01E02/tools.py` z implementacją narzędzi:
   - `get_suspects()` — odczyt z `resources/people_suspected.csv` (kolumny: name, surname, gender, born)
   - `get_powerplants()` — GET `{HUB_BASE_URL}/data/{API_KEY}/findhim_locations.json`
   - `get_person_locations(name, surname)` — POST `{HUB_BASE_URL}/api/location`
   - `get_person_access_level(name, surname, birth_year)` — POST `{HUB_BASE_URL}/api/accesslevel`
   - `get_city_coordinates(city_name)` — GET `https://nominatim.openstreetmap.org/search?city={city_name}&country=Poland&format=json`
   - `get_distance(lat1, lon1, lat2, lon2)` — obliczenie odległości wzorem haversine (czysta logika Python, bez API)
   - `verify(name, surname, access_level, power_plant)` — wysyła wynik do weryfikacji przez `BaseTask.verify()`. Zwraca odpowiedź huba (flaga lub błąd). Agent kończy pracę gdy otrzyma flagę `{FLG:...}`, lub może spróbować ponownie w przypadku błędu.

2. Każde narzędzie zwraca wynik jako `str` (JSON lub tekst) — gotowy do wstawienia jako odpowiedź tool call w konwersacji.

3. Przygotować definicje narzędzi w formacie OpenAI function calling schema (lista `tools` z `type: "function"`, `function.name`, `function.description`, `function.parameters`).

4. Przygotować `tool_executor` — dispatcher, który na podstawie nazwy narzędzia i argumentów wywołuje odpowiednią funkcję Pythona.

**Pliki do utworzenia:**
- `tasks/S01E02/tools.py`

---

## Etap 3: Implementacja klasy zadania `S01E02`

**Cel:** Utworzyć główną klasę zadania, która uruchamia agenta i przesyła wynik do weryfikacji.

**Zakres:**
1. Utworzyć `tasks/S01E02/S01E02.py` i `tasks/S01E02/__init__.py`.
2. Klasa `S01E02(BaseTask)`:
   - `__init__()` — inicjalizacja z `task_name="findhim"`, `HttpUtil`, `ResponsesService`.
   - `run()`:
     1. Zbudować system prompt dla agenta zawierający pełną instrukcję: cel (znaleźć podejrzaną osobę najbliżej elektrowni), opis dostępnych narzędzi, instrukcję aby na końcu wywołać narzędzie `verify` z wynikiem.
     2. Utworzyć `AgentLoop` z `ResponsesService`, narzędziami z etapu 2 i system promptem.
     3. Uruchomić `AgentLoop.run()` — agent sam decyduje o kolejności wywołań narzędzi, włącznie z wywołaniem `verify`.
     4. Zwrócić wynik agenta (agent kończy pracę po otrzymaniu flagi z verify lub po osiągnięciu limitu iteracji).

**Pliki do utworzenia:**
- `tasks/S01E02/S01E02.py`
- `tasks/S01E02/__init__.py`

---

## Etap 4: Testowanie i debugowanie

**Cel:** Uruchomić zadanie i zweryfikować poprawność.

**Zakres:**
1. Uruchomić: `python main.py --dict S01E02 --task S01E02`
2. Sprawdzić logi:
   - Czy agent poprawnie wywołuje narzędzia w sensownej kolejności.
   - Czy dane z API hub i Nominatim są poprawne.
   - Czy obliczenia odległości (haversine) dają rozsądne wyniki.
   - Czy agent poprawnie identyfikuje osobę najbliżej elektrowni.
3. Sprawdzić odpowiedź weryfikacji — czy zwraca flagę `{FLG:...}`.
4. W razie problemów — debugować poszczególne narzędzia i logikę agenta.

---

## Podsumowanie plików

| Plik | Akcja |
|------|-------|
| `llmService/responses_service.py` | Modyfikacja — nowa metoda `generate_with_tools()` (single call) |
| `llmService/agent_loop.py` | Nowy — klasa `AgentLoop` z pętlą agencką |
| `tasks/S01E02/tools.py` | Nowy — implementacja narzędzi + definicje + dispatcher |
| `tasks/S01E02/S01E02.py` | Nowy — klasa zadania z agentem |
| `tasks/S01E02/__init__.py` | Nowy — pusty init |
