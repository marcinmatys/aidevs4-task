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

## Etap 4 — Klasyfikacja zawodów przez LLM (Responses API + Structured Output)

1. Wyciągnąć unikalne opisy zawodów z przefiltrowanych rekordów.
2. Zbudować mapowanie `job_id -> job_description`.
3. Przygotować schema JSON dla odpowiedzi LLM z polami:
   - `job_id`,
   - `reasoning` (przed tagami),
   - `tags` (lista, wartości z dozwolonego zbioru).
4. Zaimplementować klienta/adapter do OpenAI Responses API (lub rozszerzyć istniejący serwis), aby:
   - wysłać paczkę zawodów,
   - wymusić structured output,
   - sparsować i zweryfikować odpowiedź.
5. Zbudować mapę `job_description -> tags` do użycia w finalnej odpowiedzi.

**Rezultat etapu:** przypisane tagi do każdego unikalnego zawodu.

## Etap 5 — Budowa payloadu odpowiedzi

1. Dla każdej osoby z `people_filtered.csv` zbudować obiekt odpowiedzi:
   - `name`, `surname`, `gender`,
   - `born` (rok urodzenia z `birthDate`),
   - `city` (miejsce urodzenia),
   - `tags` (na podstawie sklasyfikowanego zawodu).
2. Zweryfikować kompletność danych i brak pustych tagów.
3. Przygotować finalną listę `answer` zgodną ze specyfikacją huba.

**Rezultat etapu:** gotowy payload do wysyłki.

## Etap 6 — Wysyłka do huba i obsługa odpowiedzi

1. Wysłać wynik przez `self.verify(answer)` (endpoint `/verify`).
2. Dodać obsługę błędów sieciowych i walidacyjnych.
3. Zalogować i zwrócić odpowiedź API (w tym flagę `{FLG:...}` przy sukcesie).

**Rezultat etapu:** pełny przepływ end-to-end od pobrania CSV do odpowiedzi z huba.

## Etap 7 — Testy manualne i kontrola jakości

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
3. `feat(S01E01): jobs classification with responses api`
4. `feat(S01E01): payload build + verify submission`
5. `chore(S01E01): logging hardening + manual test notes`
