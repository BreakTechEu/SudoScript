# SudoScript — wymagania produktu (wersja robocza)

## Cel
SudoScript jest lokalnym narzędziem do tworzenia polskich napisów do materiałów wideo, z naciskiem na jakość tłumaczenia, synchronizację i powtarzalność wyników. Podstawowy przepływ ma działać bez wysyłania materiałów do chmury.

## Wynik pierwszego wydania
Dla jednego pliku wideo użytkownik otrzymuje:
- plik napisów SRT w języku docelowym;
- opcjonalnie ASS w późniejszym etapie;
- raport przebiegu: wykryty język, liczba segmentów, ostrzeżenia i błędy;
- możliwość wznowienia przerwanego zadania bez utraty poprawnie ukończonych etapów.

## Zakres MVP
1. Sprawdzenie wejściowego pliku i dostępności wymaganych narzędzi.
2. Ekstrakcja audio przez FFmpeg.
3. Transkrypcja lokalnym modelem Whisper.
4. Opcjonalne pobranie klatek wideo jako kontekstu tłumaczenia.
5. Tłumaczenie segmentów przez lokalny backend Ollama.
6. Składanie napisów z kontrolą czytelności i czasu.
7. Zapis SRT oraz raportu JSON.
8. Cache z walidacją pochodzenia i wersji etapów; bezpieczne wznowienie.
9. Testy automatyczne i CI dla każdego Pull Requesta.

## Poza zakresem MVP
- generowanie ścieżki dźwiękowej lub synteza mowy;
- automatyczne publikowanie, pobieranie lub rozpowszechnianie filmów;
- przesyłanie materiałów do usług chmurowych;
- graficzny interfejs użytkownika;
- automatyczne obchodzenie DRM lub innych zabezpieczeń.

## Zasady jakości
- Nie wolno po cichu oznaczać nieprzetłumaczonego tekstu jako poprawnego tłumaczenia.
- Każdy segment zachowuje tekst źródłowy, tekst docelowy, znaczniki czasu i status.
- Błąd segmentu musi być widoczny w raporcie; polityka eksportu określa, czy wynik może zostać zapisany jako częściowy.
- Napisy nie mogą nakładać się na siebie ani przekraczać limitów linii bez jawnego ostrzeżenia.
- Cache musi być związany z wejściowym plikiem, ustawieniami i wersją etapu.
- Wznowienie od dowolnego etapu musi weryfikować wymagane artefakty; brak artefaktu powoduje ponowne wykonanie zależnych etapów.
- Pliki wynikowe zapisuje się atomowo, aby przerwanie nie pozostawiało pozornie poprawnego wyniku.
- Żadne testy jednostkowe nie wymagają pobierania modeli ani połączenia z internetem.

## Domyślne parametry
- język docelowy: polski;
- format napisów MVP: SRT;
- transkrypcja: faster-whisper, model konfigurowalny;
- tłumaczenie: Ollama na adresie lokalnym;
- przetwarzanie: sekwencyjne i ograniczone pamięciowo, bez niekontrolowanego równoleglenia;
- katalog roboczy: osobny dla danego pliku i profilu konfiguracji.

## Prywatność i bezpieczeństwo
- domyślnie wyłącznie lokalne adresy backendu; zdalny host wymaga jawnej konfiguracji i ostrzeżenia;
- nie zapisujemy kluczy, haseł ani sekretów w logach;
- nie wykonujemy poleceń powłoki zbudowanych z tekstu użytkownika; procesy uruchamiamy jako listę argumentów;
- ścieżki i pliki cache traktujemy jako dane niezaufane i walidujemy;
- błędy są obsługiwane jawnie, bez ukrywania wyjątków jako sukcesu.

## Licencjonowanie i prawa do wyników
Licencja projektu oraz polityka użycia komercyjnego pozostają osobną decyzją. Do czasu decyzji dokumentacja nie może sugerować, że sam kod automatycznie nadaje prawa do materiału źródłowego ani do wyników tłumaczenia. Użytkownik odpowiada za posiadanie odpowiednich praw do przetwarzanego materiału.

## Kryteria akceptacji MVP
- czyste środowisko może zainstalować zależności zgodnie z dokumentacją;
- testy jednostkowe przechodzą bez Ollama i bez modeli;
- CI uruchamia testy i kontrolę składni na PR;
- błędny plik wejściowy, brak zależności, niedostępny backend i błędna odpowiedź modelu dają zrozumiały błąd;
- przerwanie i wznowienie każdego etapu nie prowadzi do użycia nieaktualnego cache;
- SRT przechodzi walidację strukturalną, ma prawidłowe czasy i raportuje nierozwiązane naruszenia czytelności;
- żadna zmiana nie jest scalana do chronionego `master` bez przeglądu i zaliczonego CI.
