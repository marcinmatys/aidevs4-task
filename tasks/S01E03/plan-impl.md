# Plan implementacji `S01E03`

## Weryfikacja kompletności informacji

Na potrzeby przygotowania planu dostępne są wystarczające informacje:

- opis zadania i wymagania funkcjonalne w `tasks/S01E03/AGENTS.md`
- istniejący wzorzec implementacji taska agenckiego w `tasks/S01E02/S01E02.py`
- istniejąca implementacja narzędzi w `tasks/S01E02/tools.py`
- aktualna implementacja pętli agenckiej w `llmService/agent_loop.py`
- bazowa klasa zadania w `tasks/base_task.py`

Na tym etapie nie widać blokera uniemożliwiającego przygotowanie planu. Otwarte kwestie techniczne można rozstrzygnąć podczas implementacji bez potrzeby doprecyzowania specyfikacji.

## Cel implementacji

Zbudować zadanie `S01E03`, które:

- uruchamia serwer proxy FastAPI na porcie `5000`
- udostępnia endpointy `GET /message` i `POST /message`
- utrzymuje historię rozmów per `sessionID`
- używa agenta LLM z tool calling do obsługi operatora
- wymusza przekierowanie paczek z częściami reaktora na `PWR6132PL`, nie ujawniając tego operatorowi
- rejestruje adres proxy w hubie przez `BaseTask.verify()` zgodnie z opisem zadania

## Etap 1: Projekt struktury rozwiązania

### Zakres

- ustalić docelową strukturę plików dla `S01E03`
- określić odpowiedzialności między taskiem, serwerem proxy, agentem i narzędziami
- zdefiniować model przepływu danych dla pojedynczej wiadomości operatora

### Wynik etapu

- decyzja, jakie pliki powstaną w `tasks/S01E03`
- spójny kontrakt danych między endpointem, pamięcią sesji i `AgentLoop`

### Proponowany podział odpowiedzialności

- `S01E03.py`
  - inicjalizacja taska
  - odczyt konfiguracji środowiskowej
  - sprawdzenie gotowości serwera do obsługi endpointu `/message`
  - rejestracja URL proxy przez `verify()`
- `tools.py`
  - implementacja `check_package_status`
  - implementacja `redirect_package`
  - definicje schema tools i dispatcher
- warstwa proxy
  - obsługa endpointów HTTP
  - przechowywanie sesji w pamięci
  - wywołanie agenta i aktualizacja historii
- `AgentLoop`
  - przyjęcie pełnej historii wiadomości
  - zwrócenie zaktualizowanej historii wraz z odpowiedzią końcową

## Etap 2: Refaktor `AgentLoop` pod historię rozmowy

### Zakres

- zmienić interfejs `AgentLoop`, aby operował na pełnej liście wiadomości zamiast budować rozmowę wyłącznie z `system` + pojedynczego `user_message`
- zapewnić zwrot zaktualizowanej historii oraz ostatniej odpowiedzi tekstowej agenta
- zachować kompatybilność z mechanizmem tool calling

### Zadania

- zaprojektować nowy wynik zwracany przez `AgentLoop`, np. słownik zawierający:
  - `messages`
  - `assistant_message`
- dopilnować, aby wyniki wywołań tools były dopisywane do tej samej historii
- uzupełnić logowanie, aby było jasne, jak przebiega iteracja agenta

### Wynik etapu

- `AgentLoop` gotowy do pracy w modelu sesyjnym
- jasny kontrakt do wykorzystania przez proxy i przez starsze taski

## Etap 3: Dostosowanie istniejącego `S01E02` do nowego kontraktu

### Zakres

- zaktualizować `tasks/S01E02/S01E02.py`, aby korzystał z nowego API `AgentLoop`
- upewnić się, że refaktor nie psuje istniejącego zadania

### Zadania

- przekazać do `AgentLoop` historię początkową zamiast samego `user_message`
- odebrać nowy format wyniku i zwrócić finalny tekst zgodnie z dotychczasową semantyką taska

### Wynik etapu

- `S01E02` nadal działa po refaktorze `AgentLoop`
- zminimalizowane ryzyko regresji we wspólnym komponencie LLM

## Etap 4: Implementacja narzędzi dla `S01E03`

### Zakres

- utworzyć `tasks/S01E03/tools.py`
- zaimplementować dwa tools zgodnie ze specyfikacją huba

### Zadania

- `check_package_status`
  - wywołanie `POST /api/packages/check`
  - przekazanie `apikey`, `action=check`, `packageid`
- `redirect_package`
  - wywołanie `POST /api/packages/redirect`
  - przekazanie `apikey`, `action=redirect`, `packageid`, `destination`, `code`
- przygotować definicje narzędzi dla Responses API
- przygotować funkcję `tool_executor`

### Ważna reguła biznesowa 

- wymuszenie celu `PWR6132PL` dla paczek z częściami reaktora powinno wynikać z logiki agenta i promptu systemowego
- operator ma otrzymać odpowiedź zgodną z własnym oczekiwaniem, bez ujawniania faktycznego celu przekierowania

### Wynik etapu

- komplet narzędzi dostępnych dla agenta
- gotowy moduł analogiczny do `S01E02/tools.py`

## Etap 5: Implementacja serwera proxy i pamięci sesji

### Zakres

- utworzyć serwer FastAPI na porcie `5000`
- zaimplementować endpointy `GET /message` i `POST /message`
- dodać przechowywanie historii rozmów w pamięci procesu

### Zadania

- przygotować model request/response dla `POST /message`
- utrzymywać mapę `sessionID -> messages`
- przy każdym żądaniu:
  - pobrać historię dla sesji
  - dopisać nową wiadomość operatora
  - przekazać historię do `AgentLoop`
  - zapisać zaktualizowaną historię
  - zwrócić ostatnią odpowiedź agenta w polu `msg`
- zapewnić prosty `GET /message`, np. ze stałą informacją diagnostyczną

### Aspekty techniczne do dopilnowania

- inicjalizacja pojedynczych zależności współdzielonych przez aplikację
- ostrożne zarządzanie stanem globalnym w pamięci procesu
- zachowanie poprawnego formatu wiadomości zgodnego z Responses API

### Wynik etapu

- działający lokalnie serwer proxy z obsługą wielu sesji
- kompletna ścieżka request -> agent -> tools -> response
- serwer możliwy do uruchomienia niezależnie od taska, np. ręcznie jako osobny proces

## Etap 6: Implementacja `S01E03.py` jako taska uruchamiającego proxy

### Zakres

- stworzyć główną klasę `S01E03` dziedziczącą po `BaseTask`
- skonfigurować `task_name="proxy"`
- zaimplementować logikę rejestracji publicznego URL przez `verify()` po potwierdzeniu gotowości serwera

### Zadania

- odczytać `HUB_BASE_URL`, `PROXY_BASE_URL`, `API_KEY` i konfigurację modelu
- wygenerować testowy `sessionID`
- w wariancie rekomendowanym założyć, że serwer FastAPI jest uruchamiany ręcznie jako osobny proces
- sprawdzić dostępność i gotowość endpointu `/message` przed wywołaniem `verify()`
- wywołać `verify()` z payloadem:
  - `url`: `{PROXY_BASE_URL}/message`
  - `sessionID`: losowy identyfikator
- dopilnować, by sposób startu taska był zgodny z przyjętą strukturą repo

### Uwaga implementacyjna

- w obecnej strukturze repo `main.py` uruchamia `task.run()` synchronicznie, więc automatyczne podniesienie serwera wewnątrz taska wymagałoby dodatkowej orkiestracji w tle
- wariant rekomendowany: wydzielić aplikację FastAPI tak, aby można ją było uruchamiać ręcznie jako osobny proces, a `S01E03.py` niech tylko waliduje gotowość endpointu i wykonuje `verify()`
- prosta alternatywa automatyczna jest możliwa, jeśli `S01E03.py` uruchomi serwer w osobnym wątku lub subprocessie, poczeka na gotowość `/message`, a dopiero potem wykona `verify()`, ale jest to wariant opcjonalny, a nie bazowy
- `verify()` musi zostać wywołane dopiero po potwierdzeniu gotowości endpointu `/message`, ponieważ po rejestracji mogą od razu pojawić się żądania z huba

### Wynik etapu

- task gotowy do zgłoszenia w hubie i do obsługi ruchu z testów zadania przy ręcznie lub automatycznie uruchomionym serwerze

## Etap 7: Testy manualne i walidacja scenariuszy

### Zakres

- sprawdzić poprawność działania serwera, pamięci sesji i logiki przekierowania
- upewnić się, że agent poprawnie maskuje rzeczywisty cel dla odpowiednich paczek

### Scenariusze do sprawdzenia

- `GET /message` zwraca poprawną odpowiedź kontrolną
- zwykłe pytanie niezwiązane z paczką daje naturalną odpowiedź po polsku
- pytanie o status paczki poprawnie używa `check_package_status`
- prośba o przekierowanie zwykłej paczki korzysta z celu podanego przez operatora
- prośba o przekierowanie paczki z częściami reaktora skutkuje wywołaniem `redirect_package` z `PWR6132PL`
- odpowiedź do operatora nie ujawnia prawdziwego celu przekierowania
- kilka różnych `sessionID` utrzymuje niezależne historie rozmów

### Wynik etapu

- potwierdzenie gotowości rozwiązania do użycia z hubem
- lista ewentualnych poprawek końcowych

## Sugerowana kolejność realizacji

1. Refaktor `AgentLoop`
2. Dostosowanie `S01E02`
3. Implementacja `S01E03/tools.py`
4. Implementacja serwera proxy i pamięci sesji
5. Implementacja `S01E03.py`
6. Testy manualne i korekty

## Ryzyka i punkty kontrolne

- `AgentLoop` jest komponentem współdzielonym, więc wymaga ostrożnego refaktoru
- trzeba dopilnować zgodności formatu historii z Responses API i tool calling
- automatyczne uruchamianie serwera z poziomu taska zwiększa złożoność przez potrzebę startu w tle i synchronizacji gotowości HTTP
- pamięć sesji w procesie wystarczy do zadania, ale nie będzie trwała po restarcie aplikacji
- prompt systemowy musi bardzo precyzyjnie wymuszać ukrywanie prawdziwego celu przekierowania

## Definition of Done

Implementację można uznać za zakończoną, gdy:

- istnieje komplet plików dla `S01E03`
- proxy działa na porcie `5000`
- agent obsługuje dialog i tool calling
- historia sesji jest zachowywana per `sessionID`
- `S01E02` działa po refaktorze `AgentLoop`
- task może zostać zarejestrowany i przetestowany przez hub
- logika dla paczek z częściami reaktora działa zgodnie ze specyfikacją
