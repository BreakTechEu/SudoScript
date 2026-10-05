# Projekt: SudoScript
Aplikacja działająca w 100% offline, służąca do inteligentnego przetwarzania obcojęzycznego wideo i generowania zoptymalizowanych ścieżek tekstowych (napisów, a docelowo również skryptów dla AI lektora i AI dubbingu) przy użyciu modeli językowych i wizyjnych (VLM). Nazwa projektu nawiązuje do Sudoizmu – uzyskujemy uprawnienia "root" do modyfikacji i percepcji barier językowych w naszej rzeczywistości.

## 1. Cel biznesowy
Zbudowanie automatycznego potoku (pipeline), który uwzględnia kontekst wizualny (płeć mówiącego, relacje, rekwizyty w kadrze) do precyzyjnego tłumaczenia wideo na język polski. W pierwszej fazie program ma generować profesjonalne napisy filmowe spełniające rygorystyczne zasady techniczne (CPL, CPS, unikanie cięć montażowych).
Architektura musi być jednak od początku gotowa na przyszłą rozbudowę o:
* **Generowanie skryptów dla lektora AI** (tekst płynny, bez wymuszonych cięć na 2 linie, z optymalizacją pod naturalne tempo czytania).
* **Generowanie linii dialogowych dla dubbingu AI** (tekst z zachowaniem długości fonetycznej oryginalnej wypowiedzi w celu dopasowania do ruchu warg).
*Uwaga: Sam program nie zajmuje się syntezą głosu, a jedynie przygotowaniem idealnie sformatowanego tekstu/skryptu dla zewnętrznych generatorów audio.*

## 2. Architektura potoku (Pipeline)
1. **Ekstrakcja Audio:** FFmpeg wyciąga ścieżkę dźwiękową (WAV, 16kHz, mono).
2. **Rozpoznawanie Cięć:** PySceneDetect analizuje wideo i zapisuje listę znaczników czasowych z cięciami montażowymi.
3. **Transkrypcja:** faster-whisper generuje surowy tekst obcojęzyczny z dokładnymi czasami rozpoczęcia i zakończenia poszczególnych wypowiedzi.
4. **Próbkowanie Klatek:** Na podstawie czasów z Whispera, FFmpeg wycina po jednej klatce ze środka każdej wypowiedzi.
5. **Tłumaczenie Multimodalne (VLM):** Lokalna instancja Ollama (model Qwen2.5-VL) otrzymuje wyciętą klatkę, oryginalny tekst i wytyczne (np. tryb napisów, tryb lektora, tryb dubbingu). Tłumaczy i kompresuje tekst odpowiednio do wybranego trybu, uwzględniając płeć i kontekst wizualny.
6. **Moduł Eksportera (Formatowanie):** 
   * Dla napisów: pysubs2 waliduje czasy, dzieli na linie i unika cięć montażowych (.srt / .ass).
   * Dla lektora/dubbingu (w przyszłości): eksport do ustrukturyzowanych plików JSON/CSV z precyzyjnymi timingami dla narzędzi TTS.

## 3. Używane biblioteki i technologie
* `faster-whisper` - szybsza i lżejsza dla VRAM wersja Whispera.
* `scenedetect[opencv]` - do detekcji cięć montażowych.
* `ffmpeg-python` (oraz lokalnie zainstalowany FFmpeg) - do cięcia audio i próbkowania wideo.
* `requests` / `httpx` - do komunikacji z API lokalnej Ollamy (`http://localhost:11434/api/generate`).
* `pysubs2` - obróbka i formatowanie plików napisów.

## 4. Struktura plików do wygenerowania
```text
SudoScript/
├── config.py              # Konfiguracja (limity CPL/CPS, modele, URL API, tryby pracy)
├── main.py                # Główny przepływ sterowania
├── core/
│   ├── __init__.py
│   ├── audio.py           # Obsługa FFmpeg (audio)
│   ├── transcriber.py     # Obsługa faster-whisper
│   ├── scene.py           # Obsługa PySceneDetect
│   ├── video.py           # Ekstrakcja klatek (FFmpeg)
│   ├── translator.py      # Klient Ollama VLM (obsługa promptów dla napisów/lektora/dubbingu)
│   └── formatters/        # Moduły wyjściowe (przyszłościowo)
│       ├── __init__.py
│       ├── subtitle.py    # Logika dla napisów (pysubs2, CPL/CPS)
│       ├── voiceover.py   # Logika dla lektora AI (przyszłość)
│       └── dubbing.py     # Logika dla dubbingu AI (przyszłość)
└── utils/
    ├── __init__.py
    └── schema.py          # Typy danych (dataclasses / Pydantic np. ScriptSegment)
```
