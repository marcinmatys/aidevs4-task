# aidevs4-task
Zadania zaliczeniowe dla szkolenia AI Devs 4

# Instalacja

Aby zainstalować zależności, uruchom polecenie:

```bash
uv sync
```

# Uruchamianie zadań

Uruchamianie zadań odbywa się za pomocą polecenia:

```bash
uv run main.py --dict "S01E01" --task "S01E01"
```

# UV_DEFAULT_INDEX — publiczny rejestr zamiast firmowego

Domyślnie `uv sync` odczytuje zmienną `UV_DEFAULT_INDEX` z systemowych zmiennych
środowiskowych. Jeśli wskazuje ona na firmowy rejestr, to jego namiary zostaną
zapisane w `uv.lock`. Aby w `uv.lock` znalazł się publiczny rejestr
`https://pypi.org/simple`, należy nadpisać tę zmienną dla projektu.

## Nadpisanie dla projektu (PowerShell w VS Code)

Dodaj w pliku `.vscode/settings.json`:

```json
{
  "terminal.integrated.env.windows": {
    "UV_DEFAULT_INDEX": "https://pypi.org/simple"
  }
}
```

Dzięki temu zintegrowany terminal PowerShell w VS Code potraktuje tę wartość
priorytetowo i `uv sync` użyje publicznego rejestru.

## Inne terminale (np. Git Bash)

Ustawienie `terminal.integrated.env.windows` nie zawsze jest respektowane przez
inne powłoki. W przypadku Git Bash zmienna `UV_DEFAULT_INDEX` bywa ustawiona
w pliku `~/.bashrc`, który przy starcie powłoki nadpisuje wartość z ustawień
VS Code. Dlatego wystarczy nadpisać zmienną na czas sesji w danym terminalu:

PowerShell:

```powershell
$env:UV_DEFAULT_INDEX = "https://pypi.org/simple"
```

Git Bash:

```bash
export UV_DEFAULT_INDEX="https://pypi.org/simple"
```

## Sprawdzenie aktualnej wartości zmiennej

PowerShell:

```powershell
$env:UV_DEFAULT_INDEX
```

Git Bash:

```bash
echo $UV_DEFAULT_INDEX
```

Po ustawieniu poprawnej wartości uruchom ponownie `uv sync`, aby `uv.lock`
został zaktualizowany o publiczny rejestr.
