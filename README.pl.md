[English](README.md) | **Polski**

# SudoScript

SudoScript to potężna aplikacja działająca w 100% offline, służąca do inteligentnego przetwarzania obcojęzycznego wideo i generowania zoptymalizowanych ścieżek tekstowych (napisów, a docelowo również skryptów dla AI lektora i AI dubbingu) przy użyciu modeli językowych i wizyjnych (VLM). 

Nazwa projektu nawiązuje do Sudoizmu – zyskujesz uprawnienia "root" do modyfikacji i percepcji barier językowych!

## 🚀 Główne założenia
* **Prywatność i tryb Offline:** Przetwarzanie odbywa się w 100% lokalnie. Zewnętrzne API chmurowe nie są używane, co gwarantuje pełne bezpieczeństwo danych.
* **Kontekst wizualny:** Dzięki modelom VLM (Vision-Language Models), tłumaczenie uwzględnia płeć mówiącego, relacje między postaciami oraz rekwizyty w kadrze.
* **Jakość techniczna:** Wygenerowane napisy przestrzegają rygorystycznych norm (CPL - Characters Per Line, CPS - Characters Per Second) oraz precyzyjnie omijają cięcia montażowe.

## 🏗️ Architektura potoku (Pipeline)
1. **Ekstrakcja Audio:** FFmpeg wyciąga ścieżkę dźwiękową (WAV, 16kHz, mono).
2. **Rozpoznawanie Cięć:** PySceneDetect analizuje wideo i zapisuje listę znaczników czasowych z cięciami montażowymi.
3. **Transkrypcja:** `faster-whisper` generuje surowy tekst obcojęzyczny wraz z dokładnymi czasami.
4. **Próbkowanie Klatek:** FFmpeg wycina pojedyncze klatki ze środka każdej wypowiedzi.
5. **Tłumaczenie Multimodalne (VLM):** Lokalna instancja Ollama (model `Qwen2.5-VL`) otrzymuje klatkę oraz tekst, po czym precyzyjnie go tłumaczy, dostosowując do trybu pracy (napisy, lektor).
6. **Moduł Eksportera:** `pysubs2` waliduje czasy, formatuje tekst i unika konfliktów z cięciami montażowymi, generując plik `.srt` lub `.ass`.

## 🛠️ Wymagania i instalacja
* Python 3.10+
* FFmpeg (zainstalowany w systemie i dodany do zmiennej PATH)
* [Ollama](https://ollama.com/) uruchomiona lokalnie z pobranym modelem wizyjnym (domyślnie `Qwen2.5-VL`).

```bash
# Sklonuj repozytorium
git clone https://github.com/BreakTechEu/SudoScript.git
cd SudoScript

# Utwórz i aktywuj wirtualne środowisko
python -m venv .venv
source .venv/bin/activate  # na systemach Unix/MacOS
# lub na Windows: .venv\Scripts\activate

# Zainstaluj zależności
pip install -r requirements.txt
```

## 🤝 Zasady współpracy (Ważne dla programistów)
W tym projekcie współpracujemy asynchronicznie. Ponieważ pracują tu inżynierowie z różnych środowisk, stosujemy poniższe zasady:
1. **Praca na branchach (Feature Branches):** Nigdy nie commituj bezpośrednio do gałęzi `master`. Każda nowa funkcjonalność, poprawka czy refaktoryzacja musi być realizowana na osobnej gałęzi (np. `feature/audio-extraction`, `fix/subtitle-sync`).
2. **Pull Requesty (PR):** Zmiany włączaj do `master` wyłącznie poprzez Pull Request na GitHubie.
3. **Conventional Commits:** Stosuj spójne nazewnictwo w commitach:
   - `feat:` nowa funkcja
   - `fix:` usunięcie usterki
   - `docs:` aktualizacja dokumentacji
   - `refactor:` zmiany w kodzie bez zmiany działania
   - `chore:` aktualizacje zależności, konfiguracje
4. **Modułowość:** Dbaj o małe, dobrze wyizolowane pliki. Każda usługa (np. Whisper, Ollama, FFmpeg) powinna znajdować się w osobnym module, z pełną obsługą wyjątków.

## ⚖️ Prawa autorskie i licencja
Projekt powstał w celach edukacyjnych i badawczych (użytek niekomercyjny). Mechanizmy tu zawarte mogą przetwarzać wyłącznie materiały audiowizualne, do których posiadasz prawa lub zgodę.

Szczegóły znajdują się w pliku `DISCLAIMER.pl.md`.
