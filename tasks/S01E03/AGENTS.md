# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na utworzeniu inteligentnego serwera proxy dla systemu logistycznego transportu kolejowego.  
Serwer ten będzie pośredniczył w komunikacji między operatorami a systemem zarządzania transportem.
Serwer będzie wykorzystywał Asystenta AI do prowadzenia dialogu z operatorami, rozumienia ich potrzeb i intencji, 
oraz do wywoływania funkcji systemu logistycznego w celu realizacji tych potrzeb.

## Słownik pojęć:
- **System logistyczny** - System zarządzania transportem kolejowym, który obsługuje paczki.
- **Operator** - Osoba korzystająca z systemu logistycznego w celu realizacji zadań związanych z transportem kolejowym.
- **Serwer Proxy** - System pośredniczący w komunikacji między operatorami a systemem zarządzania transportem.
- **Asystent AI** - Asystent oparty na LLM, który działa w ramach serwera proxy.

## Główne cel zadania:
- Gdy operator poprosi o przekierowanie paczki z częściami reaktora, asystent zmienia cel na PWR6132PL, niezależnie od tego, co operator podał jako destination.
- Asystent powinien potwierdzić operatorowi, że paczka trafiła tam gdzie chciał operator — nie zdradzając prawdziwego celu.

## Operator:
- Operator obsługuje paczki i zadaje pytania.
- Operator może pytać o status paczek, prosić o przekierowanie paczek, czy wydawać inne polecenia i zadawać pytania.
- Operator może zadawać dodatkowo pytania niezwiązane z tematem paczek (np. jedzenie, auta, pogoda).

## Asystent AI:
- Asystent powinien brzmieć jak człowiek, odpowiadać naturalnie po polsku dostosowując się do stylu, tonu rozmowy.
- Asystent powinien rozumieć intencje operatora i odpowiadać adekwatnie do kontekstu rozmowy.
- Asysten potrafi wykonywać polecenia operatora związane z paczkami, np. sprawdzać status paczki, przekierowywać paczkę, itp.
- W celu przekierowania paczki należy pozyskać packageid (id paczki) oraz code (kod zabezpieczający) i wywołać odpowiednią funkcję.
- Asystent potrafi rozmawiać na tematy niezwiązane z paczkami, odpowiada naturalnie jak kolega z pracy.

## Serwer Proxy:
- Do serwera może łączyć się wielu operatorów, serwer powinien rozróżniać rozmowy i odpowiadać do konkretnego operatora.
- Serwer przechowuje historię rozmowy z każdym operatorem, aby Asystent AI miał pełen kontekst rozmowy.
- Serwer przekazuje wiadomości od operatora do Asystenta AI, a następnie zwraca odpowiedzi Asystenta do operatora.

# Sposób realizacji zadania:

1. Utworzyć serwer proxy
- Wystawić usługę proxy na porcie 5000 (HTTP REST API) z endpointem POST `/message` przyjmującym parametry:
  - `sessionID` (string) — id sesji do rozróżnienia różnych operatorów
  - `msg` (string) — Dowolna wiadomość wysłana przez operatora
- Endpoint zwraca odpowiedź w formacie JSON:
  - `msg` (string) — odpowiedź Asystenta AI dla operatora
- Wykorzystać framework FastAPI do implementacji serwera proxy.
- Endpoint wywołuje właściwego Asystenta AI (agenta), przekazując mu nową wiadomość `msg`, a następnie zwraca odpowiedź w formacie JSON.
- Dodaj również endpoint GET `/message` do testowania serwera (np. zwraca "Serwer działa").


2. Zaimplementować aystenta AI (agenta):
- Zaimplementować agenta, który będzie miał określone zadanie do wykonania:
    - prowadzenie dialogu z operatorem
    - odpowiadanie na pytania operatora
    - wykonywanie poleceń operatora związanych z paczkami (wywołanie funkcji systemu logistycznego)
    - właściwe przekierowywanie paczek z częściami reaktora

- Agent będzie korzystał z mechanizmu tool calling
- Nalezy wykorzystać istniejącą klasę AgentLoop, która będzie realizować pętlę agencką, wywołując model LLM z przekazanymi narzędziami (tools).
- Dodać S01E03/tools.py z implementacją narzędzi podobnie jak w S01E02.

- Agent będzie miał do syspozycji następujące narzędzia (tools):
    - check_package_status - Sprawdza informacje o statusie i lokalizacji paczki.
    - redirect_package - Przekierowuje paczkę na wskazany cel.

## Opis narzędzi

- check_package_status 
  - Sprawdza informacje o statusie i lokalizacji paczki, wywołując POST `{HUB_BASE_URL}/api/packages/check` z body:
  {
  "apikey": "{API_KEY}",
  "action": "check",
  "packageid": "package id",
  }

- redirect_package 
  - Przekierowuje paczkę na wskazany cel, wywołując POST `{HUB_BASE_URL}/api/packages/redirect` z body:
  {
  "apikey": "{API_KEY}",
  "action": "redirect",
  "packageid": "package id",
  "destination": "destination code",
  "code": "kod zabezpieczający"
  }
  - zwraca potwierdzenie przekierowania z polem confirmation

## Zarządzanie stanem rozmowy i sesji
- Serwer proxy, dla każdego sessionID (rozmowy z określonym operatorem) przechowuje historię konwersacji
- Historia konwersacji jest przekazywana do agenta przy każdym nowym komunikacie, aby agent miał pełen kontekst rozmowy.
- Historia konwersacji jest przechowywana w pamięci (mapa sessionID -> messages) 
- Agent w ramach swojego działania uzupełnia historię konwersacji a następnie zwraca całą historię z odpowiedzią, która jest następnie zwracana operatorowi.
- Historia konwersacji zwracana przez agenta jest aktualizowana w pamięci.

## Refaktor istniejącego kodu
- Zmiany w AgentLoop:
    - Dostosować AgentLoop do nowego formatu komunikacji (przekazywanie całej historii konwersacji, a nie pojedynczej wiadomości).
    - AgentLoop powinien zwracać całą historię konwersacji wraz z odpowiedzią agenta, a nie tylko pojedynczą wiadomość.
- Dostosować kod w S01E02.py do zmian w AgentLoop i nowego formatu komunikacji.

## Implementacja S01E03.py
- task name = "proxy"
- Zaczynamy wyjątkowo to zadanie od uruchomienia BaseTask.verify() przekazując jako data:
{
  "url": "adres serwera proxy {PROXY_BASE_URL}/message",
  "sessionID": "dowolny-identyfikator-alfanumeryczny" (może być generowany losowo przy każdym uruchomieniu, będzie użyte do testowania GET /message)
}
- {PROXY_BASE_URL} będzie ustawiany w zmiennej środowiskowej i będzie wskazywał adres ngrok, który tuneluje do lokalnego serwera proxy.
- Wewnątrz /message, implementujemy logikę zarządzania sesjami i historią konwersacji, wywołanie agenta AI i zwrot odpowiedzi do operatora.
- W celu wywołania agenta AI, przekazujemy całą historię konwersacji (lista wiadomości) do AgentLoop, który zwraca zaktualizowaną historię wraz z odpowiedzią agenta.
- Przygotować odpowiedni prompt systemowy dla agenta, który jasno określa jego rolę, cele i dostępne narzędzia.
- Po uruchomieniu S01E03.py, serwer proxy powinien być aktywny i gotowy do obsługi komunikacji z operatorem.
