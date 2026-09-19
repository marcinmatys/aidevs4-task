# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na tym, aby aktywować trasę kolejową o nazwie X-01 za pomocą API, do którego nie mamy dokumentacji. Wiemy tylko, że API obsługuje akcję help, która zwraca jego własną dokumentację — od niej należy zacząć.

## Dane niezbędne do wypełnienia deklaracji:


## Sposób realizacji zadania

- Zaimplementować agenta AI bazującego na LLM, który będzie miał określone zadanie do wykonania:
  - aktywować trasę kolejową o nazwie X-01 za pomocą API

- Prompt dla agenta należy przygotować korzystając z niżej podanych wskazówek (w sekcji "Wskazówki dla agenta")
- Agent kończy pracę gdy w odpowiedzi API otrzyma flagę (FLG) lub gdy osiągnie maksymalną liczbę iteracji (np. 10 iteracji)

- Agent będzie korzystał z mechanizmu tool calling

- Agent będzie miał do syspozycji następujące narzędzia (tools, właściwie tylko jedno narzędzie):
  - call_api - wywołuje API z podaną akcją i parametrami


## Wskazówki dla agenta


### Jak do tego podejść - krok po kroku

- Zacznij od help — wyślij akcję help i dokładnie przeczytaj odpowiedź. API jest samo-dokumentujące: odpowiedź opisuje wszystkie dostępne akcje, ich parametry i kolejność wywołań potrzebną do aktywacji trasy.

### Wskazówki

- Postępuj zgodnie z dokumentacją API — nie zgaduj nazw akcji ani parametrów. Używaj dokładnie tych wartości, które zwróciło help.

- Czytaj błędy uważnie — jeśli akcja się nie powiedzie, komunikat błędu zwykle precyzyjnie wskazuje co poszło nie tak (zły parametr, zła kolejność akcji itp.).

- Szukaj flagi w odpowiedzi — gdy API zwróci w treści odpowiedzi flagę w formacie {FLG:...}, zadanie jest ukończone.

## Opis narzędzi

- call_api - wysyła zapytanie do API z podaną akcją i parametrami, przyjmuje dwa parametry: action (nazwa akcji) i parametry (obiekt z parametrami)

zapytanie do API wysyła na adres {HUB_BASE_URL}/verify w formacie JSON
{
  "apikey": "{API_KEY}",
  "task": "railway",
  "answer": {
    "action": "action_name",
    "param_1_name": "param1_value",
    "param_2_name": "param2_value",
    "param_n_name": "param_n_value"
  }
}

Jeżeli zapytanie zwróci błąd 429 (Too Many Requests) należy odczekać określoną ilość sekund (retry_after) i spróbować ponownie.


HTTP/1.1 429 Too Many Requests
{
"code": -985,
"message": "API rate limit exceeded. Please retry later.",
"retry_after": 10
}

Jeżeli zapytanie zwróci błąd 503 (Service Unavailable) należy zastosować retry z backoff (np. po 2s, 4s, 8s).

HTTP/1.1 503 Service Unavailable
{
"code": -925,
"message": "Temporary server outage. Please retry in a moment."
}

Loguj każde wywołanie i odpowiedź