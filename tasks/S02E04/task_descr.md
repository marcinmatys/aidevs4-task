# Zadanie

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zdobyliśmy dostęp do skrzynki mailowej jednego z operatorów systemu. Wiemy, że na tę skrzynkę wpadł mail od Wiktora - nie znamy jego nazwiska, ale wiemy, że doniósł na nas. Musimy przeszukać skrzynkę przez API i wyciągnąć trzy informacje:


- date - kiedy (format YYYY-MM-DD) dział bezpieczeństwa planuje atak na naszą elektrownię

- password - hasło do systemu pracowniczego, które prawdopodobnie nadal znajduje się na tej skrzynce

- confirmation_code - kod potwierdzenia z ticketa wysłanego przez dział bezpieczeństwa (format: SEC- + 32 znaki = 36 znaków łącznie)

Skrzynka jest cały czas w użyciu - w trakcie pracy mogą na nią wpływać nowe wiadomości. Musisz to uwzględnić.

Co wiemy na start:

- Wiktor wysłał maila z domeny proton.me

- API działa jak wyszukiwarka Gmail - obsługuje operatory from:, to:, subject:, OR, AND

Nazwa zadania: mailbox

# Jak komunikować się z API?

Skrzynka mailowa dostępna jest przez API zmail:

POST {HUB_BASE_URL}/api/zmail
Content-Type: application/json


Sprawdzenie dostępnych akcji:

{
  "apikey": "tutaj-twój-klucz",
  "action": "help",
  "page": 1
}

Pobranie zawartości inboxa:

{
  "apikey": "tutaj-twój-klucz",
  "action": "getInbox",
  "page": 1
}

# Jak wysłać odpowiedź?

Wysyłasz do /verify:

{
  "apikey": "tutaj-twój-klucz",
  "task": "mailbox",
  "answer": {
    "password": "znalezione-hasło",
    "date": "2026-02-28",
    "confirmation_code": "SEC-tu-wpisz-kod"
  }
}

Gdy wszystkie trzy wartości będą poprawne, hub zwróci flagę {FLG:...}.

# Co należy zrobić w zadaniu?

1. Wywołaj akcję help na API zmail, żeby poznać wszystkie dostępne akcje i parametry.

2. Spraw aby agent korzystał z wyszukiwarki maili - na podstawie opisu zadania może zbudować odpowiednie zapytania.

3. Pobierz pełną treść znalezionych wiadomości, żeby przeczytać ich zawartość.

4. Szukaj informacji po kolei - nie musisz znaleźć wszystkich na raz.

5. Korzystaj z feedbacku huba, żeby wiedzieć, których wartości jeszcze brakuje lub które są błędne.

6. Kontynuuj przeszukiwanie skrzynki, aż zbierzesz wszystkie trzy wartości i hub zwróci flagę.

7. Pamiętaj, że skrzynka jest aktywna - jeśli szukasz czegoś i nie możesz znaleźć, spróbuj ponownie, bo nowe wiadomości mogły dopiero wpłynąć.

# Wskazówki

- Dwuetapowe pobieranie danych - API zmail działa w dwóch krokach: najpierw wyszukujesz i dostajesz listę maili z metadanymi (bez treści), a dopiero potem pobierasz pełną treść wybranych wiadomości po ich identyfikatorach. Nie próbuj odgadywać treści na podstawie samego tematu - zawsze pobieraj pełną wiadomość przed wyciąganiem wniosków.

- Aktywna skrzynka - skrzynka jest cały czas w użyciu i nowe wiadomości mogą wpływać w trakcie Twojej pracy. Jeśli przeszukałeś całą skrzynkę i nie możesz czegoś znaleźć, warto spróbować ponownie - szukana informacja mogła właśnie dotrzeć. Nie zakładaj od razu, że informacja nie istnieje.

- Operatory wyszukiwania - API obsługuje składnię podobną do Gmail. Możesz łączyć operatory. Możesz zacząć od szerokich zapytań, żeby nie przegapić istotnych maili, a potem zawęzić wyszukiwanie.