# SudoScript — architektura techniczna

## Podejście
Najpierw mały, testowalny rdzeń z wyraźnymi granicami między etapami. Nie budujemy jednego dużego pipeline'u, który przechowuje ukryty stan i nie potrafi odzyskać się po przerwaniu.

## Pipeline
1. **Preflight** — sprawdzenie pliku, narzędzi, konfiguracji i miejsca na dysku.
2. **Audio** — ekstrakcja do formatu roboczego przez FFmpeg.
3. **Transcription** — lokalny faster-whisper, wynik w ujednoliconym schemacie segmentów.
4. **Visual context** — opcjonalna ekstrakcja klatek, zależna od konfiguracji; brak klatki nie może być mylony z sukcesem analizy wizualnej.
5. **Translation** — adapter backendu lokalnego; walidacja odpowiedzi modelu i status każdego segmentu.
6. **Subtitle assembly** — podział tekstu, układ linii, kontrola czasów i scen.
7. **Validation** — niezależna walidacja wyjścia; naruszenia są raportowane.
8. **Export** — zapis atomowy SRT oraz raportu JSON.

## Kontrakty etapów
Każdy etap otrzymuje jawne dane wejściowe i konfigurację, a zwraca artefakt z:
- identyfikatorem schematu;
- nazwą i wersją etapu;
- skrótem wejść i istotnych ustawień;
- statusem i ostrzeżeniami;
- ścieżką artefaktu oraz sumą kontrolną.

Cache jest ważny tylko wtedy, gdy zgadzają się skróty wejściowe, konfiguracji i wersji etapu. Zmiana pliku źródłowego unieważnia wszystkie zależne artefakty.

## Wznawianie
Wznowienie od etapu N sprawdza wszystkie zależności poprzedzające N. Jeśli artefakt jest brakujący, nieczytelny lub niezgodny, odpowiedni etap i zależne od niego etapy są ponownie wykonywane. Stan nie może zakładać, że plik istnieje tylko dlatego, że zapisano jego ścieżkę.

## Błędy
- błędy wejścia i konfiguracji: kończą zadanie przed kosztownym przetwarzaniem;
- błędy infrastruktury: ograniczone ponowienia z timeoutem;
- błędy pojedynczego segmentu: jawny status i raport, bez cichego fallbacku do tekstu źródłowego jako tłumaczenia;
- błędy zapisu: wynik końcowy pozostaje niezmieniony albo jest w pełni zapisany.

## Moduły
- `sudoscript/cli.py` — argumenty i kod wyjścia;
- `sudoscript/config.py` — walidowana konfiguracja;
- `sudoscript/models.py` — typy danych i statusy;
- `sudoscript/pipeline.py` — orkiestracja i graf zależności;
- `sudoscript/stages/` — audio, transkrypcja, klatki, tłumaczenie;
- `sudoscript/subtitles/` — układ, czas, walidacja, eksport;
- `sudoscript/cache.py` — manifesty, skróty i walidacja artefaktów;
- `sudoscript/reporting.py` — raporty;
- `tests/` — testy jednostkowe, regresyjne i integracyjne.

## Testowanie
Testy logiki są izolowane przez interfejsy i atrapę backendu. Testy z prawdziwym FFmpeg/Ollama są osobną, opcjonalną grupą integracyjną. CI nie pobiera modeli i nie potrzebuje GPU.
