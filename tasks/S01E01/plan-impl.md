# Plan implementacji zadania S01E01

## Weryfikacja kompletności informacji

Dostępne informacje są wystarczające, aby zaplanować implementację:
- pełna specyfikacja zadania i kroków znajduje się w `AGENTS.md`,
- znana jest struktura projektu (`BaseTask`, `TaskVerifier`, uruchamianie przez `main.py`),
- określone są wymagania dot. cache plików CSV, filtrowania, klasyfikacji LLM i wysyłki odpowiedzi.

Na etapie planowania nie widzę blokujących braków. Ewentualne decyzje techniczne (np. konkretny model OpenAI) można podjąć podczas implementacji zgodnie z obecnym stosem projektu.

## Etap 1 — Szkielet zadania i konfiguracja

1. Utworzyć klasę `S01E01` dziedziczącą po `BaseTask` w module `tasks/S01E01/S01E01.py`.
2. Ustawić parametry bazowe zadania:
   - `base_url="{HUB_BASE_URL}"`
   - `task_name="people"`
3. Dodać `run()` jako orkiestrację kroków oraz logowanie etapów.
4. Dodać `tasks/S01E01/__init__.py` (jeśli brak), by umożliwić import dynamiczny.

**Rezultat etapu:** uruchamialny szkielet zadania przez `main.py`.

## Etap 2 — Pobieranie i cache pliku `people.csv`

1. Zaimplementować metodę pobierania danych wejściowych:
   - jeśli `resources/people.csv` istnieje -> użyć lokalnej kopii,
   - w przeciwnym razie pobrać z `{HUB_BASE_URL}/data/{API_KEY}/people.csv` i zapisać do `resources/people.csv`.
2. Dodać walidację:
   - obecność `API_KEY` w środowisku,
   - poprawny status HTTP i niepusty plik.
3. Dodać czytelne logi dla trybu cache/pobranie.

**Rezultat etapu:** stabilne źródło danych wejściowych z mechanizmem cache.

## Etap 3 — Filtrowanie rekordów i cache `people_filtered.csv`

1. Zaimplementować wczytanie CSV do struktury danych (np. lista słowników).
2. Zaimplementować filtr bazowy:
   - `gender == "M"`,
   - `birthPlace == "Grudziądz"` / `"Grudziadz"` (odporność na diakrytyki),
   - wiek w przedziale 20–40 liczony względem roku 2026.
3. Jeśli istnieje `resources/people_filtered.csv`, użyć go zamiast filtrować ponownie.
4. Po przefiltrowaniu zapisać wynik do `resources/people_filtered.csv`.

**Rezultat etapu:** gotowa lista kandydatów do klasyfikacji zawodów.

## Etap 4 — Klient/adapter LLM (OpenAI SDK + Responses API)

1. Wydzielić warstwę adaptera LLM niezależną od logiki zadania (np. `llmService/responses_service.py` + konfiguracja providera).
2. Użyć OpenAI SDK jako wspólnego klienta API.
3. Ustawić OpenRouter jako domyślnego providera:
   - konfiguracja `base_url` OpenRouter,
   - uwierzytelnienie kluczem API z env,
   - możliwość wyboru modelu przez konfigurację.
4. Zaprojektować adapter tak, aby w przyszłości dodać providera Azure również przez OpenAI SDK (bez zmian w logice zadania):
   - spójny interfejs metody klasyfikacji,
   - separacja konfiguracji per provider,
   - brak twardego powiązania kodu zadania z konkretnym providerem.
5. Udostępnić metodę wywołania Responses API przyjmującą prompt, schema i dane wejściowe oraz zwracającą zwalidowany JSON.

**Rezultat etapu:** gotowy, reużywalny adapter LLM oparty o OpenAI SDK z OpenRouter jako providerem domyślnym i przygotowaniem pod Azure.

## Etap 5 — Klasyfikacja zawodów przez LLM (Responses API + Structured Output)

1. Wyciągnąć unikalne opisy zawodów z przefiltrowanych rekordów.
2. Zbudować mapowanie `job_id -> job_description`.
3. Przygotować schema JSON dla odpowiedzi LLM z polami:
   - `job_id`,
   - `reasoning` (przed tagami),
   - `tags` (lista, wartości z dozwolonego zbioru).
   - Każde pole w schemie powinno mieć `description`, aby poprawić jakość odpowiedzi modelu.
   - Ustawić `required` dla wszystkich pól biznesowych i `additionalProperties: false` na poziomie obiektu odpowiedzi oraz elementu klasyfikacji.
   - Dla `tags` wymusić: `type: array`, `minItems: 1`, `uniqueItems: true`, `items.enum` z dozwolonym zbiorem tagów.
   - Dla `reasoning` wymusić: `type: string`, `minLength: 1`.
4. Wykorzystać adapter z Etapu 4, aby:
   - wysłać paczkę zawodów,
   - stosować strategię wysyłki:
     - jeśli liczba unikalnych zawodów jest mała (np. do 30-50 krótkich opisów), wysłać jeden request,
     - jeśli liczba zawodów jest większa, podzielić dane na osobne requesty (batching, np. po 20-30 zawodów),
     - po klasyfikacji scalić wyniki i zwalidować kompletność `job_id`.
   - wymusić structured output,
   - sparsować i zweryfikować odpowiedź.
5. Zbudować mapę `job_description -> tags` do użycia w finalnej odpowiedzi.

**Rezultat etapu:** przypisane tagi do każdego unikalnego zawodu.

## Etap 6 — Budowa payloadu odpowiedzi

1. Dla każdej osoby z `people_filtered.csv` zbudować obiekt odpowiedzi:
   - `name`, `surname`, `gender`,
   - `born` (rok urodzenia z `birthDate`),
   - `city` (miejsce urodzenia),
   - `tags` (na podstawie sklasyfikowanego zawodu).
2. Wybieramy tylko osoby których zawody zaklasyfikowano jako transport
3. Zweryfikować kompletność danych i brak pustych tagów.
4. Przygotować finalną listę `answer` zgodną ze specyfikacją huba.

**Rezultat etapu:** gotowy payload do wysyłki.

## Etap 7 — Wysyłka do huba i obsługa odpowiedzi

1. Wysłać wynik przez `self.verify(answer)` (endpoint `/verify`).
2. Dodać obsługę błędów sieciowych i walidacyjnych.
3. Zalogować i zwrócić odpowiedź API (w tym flagę `{FLG:...}` przy sukcesie).

**Rezultat etapu:** pełny przepływ end-to-end od pobrania CSV do odpowiedzi z huba.

## Etap 8 — Testy manualne i kontrola jakości

1. Uruchomić zadanie lokalnie i potwierdzić przebieg wszystkich etapów.
2. Zweryfikować scenariusze:
   - pierwsze uruchomienie (pobranie + filtracja),
   - kolejne uruchomienie (użycie cache),
   - brak `API_KEY`,
   - niepoprawna odpowiedź LLM.
3. Sprawdzić strukturę JSON przed wysyłką i logi diagnostyczne.

**Rezultat etapu:** gotowa, powtarzalna implementacja z podstawową walidacją jakości.

## Podział implementacji na małe PR-y/commity (opcjonalnie)

1. `feat(S01E01): task skeleton + CSV download/cache`
2. `feat(S01E01): filtering + filtered cache`
3. `feat(llm): responses adapter with provider abstraction (openrouter default)`
4. `feat(S01E01): jobs classification with responses api`
5. `feat(S01E01): payload build + verify submission`
6. `chore(S01E01): logging hardening + manual test notes`
