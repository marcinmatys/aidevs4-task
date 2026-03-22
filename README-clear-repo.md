# Clean git history

## obierz BFG
https://rtyley.github.io/bfg-repo-cleaner/

## Sklonuj repozytorium
git clone --mirror https://github.com/marcinmatys/aidevs4-task.git

## Utwórz plik replacements.txt z zawartością
STARY_TEKST==>NOWY_TEKST


## Uruchom BFG
java -jar bfg-1.15.0.jar --replace-text replacements.txt aidevs4-task.git  


## Oczyszczanie historii
cd aidevs4-task.git  
git reflog expire --expire=now --all  
git gc --prune=now --aggressive  

## Konfiguracja remote
Podmiana w git config na
[remote "origin"]
url = git@github.com:marcinmatys/aidevs4-task.git

[user]
email = username@gmail.com


## Wypchnięcie zmian
git push --force

## Sklonowanie repozytorium na nowo
git clone  https://github.com/marcinmatys/aidevs4-task.git