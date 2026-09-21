# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na pobraniu listy towarów w formacie csv z dostępnego huba {HUB_BASE_URL}
Następnie każdy towar z listy nalezy wysłać na adres {HUB_BASE_URL}/verify
w celu klasyfikacji towaru DNG - niebezpieczny, NEU - neutralny.
Poniżej znajdziesz opis poszczególnych kroków zadania.

1. Pobranie listy towarów. Znajdziesz ją pod linkiem:
{HUB_BASE_URL}/data/tutaj-twój-klucz/categorize.csv
- use API_KEY from env
- otrzymasz plik w formacie CSV np.:
code,description
i3344,"Tiny precision screwdriver set in a waterproof plastic case"
i6047,"Reactor fuel cassette with experimental thorium-based fuel composition"
i8450,"Collapsible baton made of hardened steel"
- nie zapisuj pliku na dysku


2. Wysyłanie do klasyfikacji
- Każdy towar z listy należy wysłać na adres {HUB_BASE_URL}/verify w formacie JSON:

{
       "apikey": "tutaj-twój-klucz-api",
       "task": "categorize",
       "answer": {
          "prompt": "IF item is reactor part: NEU; ELSE: classify item as DNG or NEU. \n code={code}; description={description}"
        }
}
- loguj każdą odpowiedź z serwera
