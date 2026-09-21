# Plan implementacji zadania S02E01

## Weryfikacja kompletności informacji

Dostępne informacje są wystarczające do zaplanowania zadania:
- Znamy adres i format endpointu, z którego ma być pobrany plik CSV z towarami.
- Znamy ograniczenie o zakazie zapisywania pliku na dysku (parsowanie w pamięci operacyjnej).
- Znamy dokładny format payloadu, jaki ma być wysłany na adres endpointu `verify`.
- Posiadamy klasę `BaseTask` oraz metody odpowiedzialne za logowanie i weryfikację ułatwiające sprawę.

## Etap 1: Szkielet zadania i pobranie danych

1. **Utworzenie modułu i klasy zadania**
   - W katalogu `tasks/S02E01` utworzyć plik `S02E01.py` oraz upewnić się o istnieniu `__init__.py`.
   - Klasa `S02E01` dziedziczy po `BaseTask` i konfiguruje zadanie z `task_name="categorize"`.
2. **Pobranie i parsowanie CSV**
   - Zaimplementować metodę wewnętrzną, pobierającą dane korzystając z `HttpUtil`.
   - Adres: `/data/{API_KEY}/categorize.csv`.
   - Sprawdzić dostępność `API_KEY` w zmiennych środowiskowych.
   - Pobrane dane w formacie tekstowym zdekodować do stringa i sparsować za pomocą `io.StringIO` oraz `csv.DictReader` bezpośrednio w pamięci bez udziału systemu dyskowego.

**Rezultat etapu:** Metoda odczytująca asynchronicznie dane z Huba i zwracająca w pamięci listę towarów (dict'ów) o polach `code` oraz `description`.

## Etap 2: Wysłanie towarów do klasyfikacji

1. **Główna pętla wykonania**
   - W metodzie `run()` rozpocząć przechodzenie przez listę wyodrębnionych towarów z Etapu 1.
2. **Budowanie zapytania dla Huba**
   - Dla każdego towaru przygotować pole `answer`:
     ```python
     answer = {
         "prompt": f"IF item is reactor part: NEU; ELSE: classify item as DNG or NEU. \n code={code}; description={description}"
     }
     ```
3. **Komunikacja i logowanie**
   - Wysłać każdy zbudowany zapytanie przez `self.verify(answer)`.
   - Zapewnić logowanie zwróconej odpowiedzi z każdego rekordu oddzielnie. `TaskVerifier.verify` zajmie się podstawnym logowaniem, ewentualnie można zalogować sam rezultat na poziomie `S02E01`.
4. **Zakończenie i raportowanie**
   - Gromadzić wszystkie otrzymane wyniki odpowiedzi z żądań `/verify`.
   - Na zakończenie `run()` zwrócić pełen słownik reprezentujący wykonanie akcji (np. z kluczem `"results"` zawierającym wszystkie uzyskane na koniec wyniki bądź z logiką przechwytywania konkretnej flagi `{FLG:...}`).

**Rezultat etapu:** Kompletna aplikacja pozwalająca z sukcesem przejść weryfikację zadania na serwerze po wykonaniu pełnej klasyfikacji każdego elementu na liście.
