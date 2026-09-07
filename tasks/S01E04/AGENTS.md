# Opis zadania

Uwaga! Fabuła przedtawiona w zadaniu jest fikcyjna i służy wyłącznie celom edukacyjnym.

Zadanie polega na tym, aby przesłać do Centrali poprawnie wypełnioną deklarację transportu w Systemie Przesyłek Konduktorskich. Deklaracja musi byc przygotowana zgodnie z dokumentacją przesyłek i zawierać wskazane niezbędne dane.

## Dane niezbędne do wypełnienia deklaracji:
Nadawca (identyfikator): 450202122
Punkt nadawczy: Gdańsk
Punkt docelowy: Żarnowiec
Waga: 2,8 tony (2800 kg)
Budżet: 0 PP (przesyłka ma być darmowa lub finansowana przez System)
Zawartość: kasety z paliwem do reaktora
Uwagi specjalne: brak - nie dodawaj żadnych uwag

## Sposób realizacji zadania

- Zaimplementować agenta AI bazującego na LLM, który będzie miał określone zadanie do wykonania:
  - Przygotować deklarację transportu zgodnie z dokumentacją i umieścić w niej niezbędne dane
  - Wysłać deklarację do weryfikacji
  - W przypadku odrzucenia deklaracji, należy zapoznać się z komunikatem błędu, poprawić deklarację i wysłać ją ponownie

- Prompt dla agenta należy przygotować korzystając z niżej podanych wskazówek (w sekcji "Wskazówki dla agenta")
- Agent kończy pracę gdy w wyniku weryfikacji otrzyma flagę (FLG) lub gdy osiągnie maksymalną liczbę iteracji (np. 10 iteracji)

- Agent będzie korzystał z mechanizmu tool calling

- Agent będzie miał do syspozycji następujące narzędzia (tools):
  - get_main_documentation - pobiera dokumentację główną
  - get_md_attachment - pobiera załącznik do dokumentacji w formacie markdown
  - get_image_information - pobiera informacje z załącznika w postaci pliku graficznego, które mogą byc przydatne do poprawnego wypełnienia deklaracji.
  - verify - wysyła deklarację do weryfikacji


## Wskazówki dla agenta

### Jak do tego podejść - krok po kroku

- Pobierz dokumentację - zacznij od index.md. To główny plik dokumentacji, ale nie jedyny - zawiera odniesienia do wielu innych plików (załączniki, osobne pliki z danymi). Powinieneś pobrać i przeczytać wszystkie pliki które mogą być potrzebne do wypełnienia deklaracji.

- Uwaga: nie wszystkie pliki są tekstowe - część dokumentacji może być dostarczona jako pliki graficzne. Takie pliki wymagają przetworzenia z użyciem modelu z możliwościami przetwarzania obrazów (vision).


- Znajdź wzór deklaracji - w dokumentacji znajdziesz ze wzorem formularza. Wypełnij każde pole zgodnie z danymi przesyłki i regulaminem.

- Ustal prawidłowy kod trasy - trasa Gdańsk - Żarnowiec wymaga sprawdzenia sieci połączeń i listy tras.

- Oblicz lub ustal opłatę - regulamin SPK zawiera tabelę opłat. Opłata zależy od kategorii przesyłki, jej wagi i przebiegu trasy. Budżet wynosi 0 PP - zwróć uwagę, które kategorie przesyłek są finansowane przez System.

- Wyślij deklarację - gotowy tekst wyślij do /verify. Jeśli Hub odrzuci odpowiedź z komunikatem błędu, przeczytaj go uważnie - będzie zawierał wskazówki co poprawić.

- Koniec - jeśli wszystko przebiegło pomyślnie, Hub zwróci flagę {FLG:...}.

### Wskazówki

- Czytaj całą dokumentację, nie tylko index.md - regulamin SPK składa się z wielu plików. Odpowiedzi na pytania dotyczące kategorii, opłat, tras czy wzoru deklaracji mogą znajdować się w różnych załącznikach.

- Nie pomijaj plików graficznych - dokumentacja zawiera co najmniej jeden plik w formacie graficznym. Dane w nim zawarte mogą być niezbędne do poprawnego wypełnienia deklaracji.

- Wzór deklaracji jest ścisły - formatowanie musi być zachowane dokładnie tak jak we wzorze. Hub weryfikuje zarówno wartości, jak i format dokumentu.

- Skróty - jeśli trafisz na skrót, którego nie rozumiesz, użyj dokumentacji żeby dowiedzieć się co on oznacza.


## Opis narzędzi
- get_main_documentation - pobiera główną dokumentację z huba: GET {HUB_BASE_URL}/dane/doc/index.md
- get_md_attachment - pobiera treść wskazanego załącznika (pliku markdown) z huba: GET {HUB_BASE_URL}/dane/doc/{filename}
- get_image_information - pobiera informacje z załącznika w postaci pliku graficznego, które mogą byc przydatne do poprawnego wypełnienia deklaracji. Pobranie pliku z huba: GET {HUB_BASE_URL}/dane/doc/{filename} a następnie odczyt informacji z pliku za pomocą modelu, który pozwala załączać obrazy np. gpt-5.5 . Narzędzie ma dwa parametry, nazwa pliku graficznego oraz treść zapytania do modelu AI.

- verify - wysyła przygotowaną deklarację do weryfikacji na adres {HUB_BASE_URL}/verify w formacie JSON
{
  "apikey": "{API_KEY}",
  "task": "sendit",
  "answer": {
    "declaration": "tutaj-wstaw-caly-tekst-deklaracji"
  }
}
Pole declaration to pełny tekst wypełnionej deklaracji - z zachowaniem formatowania, separatorów i kolejności pól dokładnie tak jak we wzorze z dokumentacji.