# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na tym, aby namierzyć podejrzaną osobę, która przebywała najbliżej jednej z elektrowni. Trzeba ustalić która to była elektrownia oraz poziom dostępu (access_level) dla tej osoby.

## Posiadane informacje:
- lista podejrzanych osób (imię, nazwisko, rok urodzenia)
- lista elektrowni z nazwami miast i kodami identyfikacyjnymi
- Dla każdej osoby możemy pobrać współrzędne geograficzne (latitude, longitude), gdzie ta osoba była ostatnio widziana
- Dla każdej osoby możemy pobrać poziom dostępu (access_level)
- Dla każdego miasta (miejsce elektrowni) możemy pobrać współrzędne geograficzne (latitude, longitude)

## Sposób realizacji zadania

- Zaimplementować agenta AI bazującego na LLM, który będzie miał określone zadanie do wykonania:
  - Znaleźć podejrzaną osobę, która przebywała najbliżej jednej z elektrowni
  - Ustalić która to była elektrownia
  - Ustalić poziom dostępu (access_level) dla tej osoby
  - Wysłać odpowiedź do weryfikacji

- Agent kończy pracę gdy w wyniku weryfikacji otrzyma flagę (FLG) lub gdy osiągnie maksymalną liczbę iteracji (np. 10 iteracji)

- Agent będzie korzystał z mechanizmu tool calling

- Agent będzie miał do syspozycji następujące narzędzia (tools):
  - get_suspects - pobiera listę podejrzanych osób
  - get_powerplants - pobiera listę elektrowni (w tym nazwy miast i kody identyfikacyjne)
  - get_person_locations - pobiera listę współrzędnych geograficznych (latitude, longitude), gdzie widziano daną osobę
  - get_person_access_level - pobiera poziom dostępu dla danej osoby
  - get_city_coordinates - pobiera współrzędne geograficzne (latitude, longitude) dla danego miasta
  - get_distance – oblicza odległość między dwoma punktami na podstawie współrzędnych geograficznych (latitude, longitude) przy użyciu wzoru haversine
  - verify - wysyła odnalezioną osobę (najbliżej elektrowni) do weryfikacji


## Opis narzędzi
- get_suspects - pobiera listę osób z pliku resources/people_suspected.csv (tylko name,surname,gender,born)
- get_powerplants - pobiera listę elektrowni z huba: GET {HUB_BASE_URL}/data/{API_KEY}/findhim_locations.json
- get_person_locations - pobiera listę współrzędnych dla danej osoby z huba: POST {HUB_BASE_URL}/api/location
  - body: {
  "apikey": "{API_KEY}",
  "name": "first_name",
  "surname": "last_name"
}
- get_person_access_level - pobiera poziom dostępu dla danej osoby z huba: POST {HUB_BASE_URL}/api/accesslevel
  - body: {
  "apikey": "{API_KEY}",
  "name": "first name",
  "surname": "last name",
  "birthYear": "birth year"
}
- get_city_coordinates - pobiera współrzędne geograficzne dla danego miasta z adresu URL: GET https://nominatim.openstreetmap.org/search?city={city_name}&country=Poland&format=json

- get_distance – oblicza odległość między dwoma punktami na podstawie współrzędnych geograficznych (latitude, longitude) przy użyciu wzoru haversine

- verify - wysyła odnalezioną osobę do weryfikacji na adres {HUB_BASE_URL}/verify w formacie JSON
{
  "apikey": "{API_KEY}",
  "task": "findhim",
  "answer": {
    "name": "first_name",
    "surname": "last_name",
    "accessLevel": "access_level",
    "powerPlant": "powerplant code"
  }
}