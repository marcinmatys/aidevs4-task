# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na pobraniu listy osób w formacie csv z dostępnego huba {HUB_BASE_URL}
Następnie listę należy odfiltrować według podanych niżej kryteriów.
Interesują nas tylko mężczyźni, w wieku 20-40 lat, urodzeni w Grudziądzu, pracujący w branży transportowej.
Podstawowe filtrowanie wykonamy standardowym programowaniem, natomiast do klasyfikacji zawodów będziemy używać LLM.
Następnie listę osób nalezy wysłać na adres {HUB_BASE_URL}/verify
Poniżej znajdziesz opis poszczególnych kroków zadania.

1. Pobranie listy osób. Znajdziesz ją pod linkiem:
{HUB_BASE_URL}/data/tutaj-twój-klucz/people.csv
- use API_KEY from env
- before downloading, check if the file already exists in resources/people.csv
- after downloading, save the file in resources/people.csv

2. Filtrowanie osób:
- W pliku people.csv są dane osób w formacie
name,surname,gender (M/F),birthDate (YYYY-MM-DD),birthPlace,birthCountry,job (opis stanowiska pracy)
- Należy znaleźć osoby, którzy są mężczyznami (M), urodzili się w Grudziądzu, teraz w 2026 roku mają między 20 a 40 lat
- Po odfiltrowaniu tych osób, listę należy zapisać w pliku resources/people_filtered.csv
- Zanim rozpoczniemy filtrowanie, sprawdź czy plik resources/people_filtered.csv już istnieje i jeśli tak, to użyj go zamiast filtrować ponownie.

3. Klasyfikacja zawodów.
- Na podstawie pliku resources/people_filtered.csv, przygotuj listę unikalnych zawodów.
- Dla każdego unikalnego zawodu przyporządkuj unikalny identyfikator (numer).
- Wykorzystaj LLM do klasyfikacji zawodów. Każdy zawód musisz odpowiednio otagować. Mamy do dyspozycji następujące tagi: IT, transport, edukacja, medycyna, praca z ludźmi, praca z pojazdami, praca fizyczna.
- Wykorzystaj nowe responses api aby odpytać LLM o klasyfikację zawodów.
- Użyj mechanizmu Structured Output, aby wymusić odpowiedź modelu w określonym formacie JSON
- Opis zawodu może mieć jednocześnie wiele tagów. Uwzględnij to przy definiowaniu struktury odpowiedzi (JSON schema).
- W strukturze odpowiedzi dodaj dodatkowo pole reasoning, które będzie zawierać krótkie uzasadnienie przypisania tagów.
- Ważne aby pole reasoning było w strukturze przed tagami.

4. Wysyłanie odpowiedzi
- Przygotowaną listę osób należy wysłać na adres {HUB_BASE_URL}/verify w formacie JSON
- Przykład formatu odpowiedzi:

{
       "apikey": "tutaj-twój-klucz-api",
       "task": "people",
       "answer": [
         {
           "name": "Jan",
           "surname": "Kowalski",
           "gender": "M",
           "born": 1987,
           "city": "Warszawa",
           "tags": ["tag1", "tag2"]
         },
         {
           "name": "Anna",
           "surname": "Nowak",
           "gender": "F",
           "born": 1993,
           "city": "Grudziądz",
           "tags": ["tagA", "tagB", "tagC"]
         }
       ]
     }
