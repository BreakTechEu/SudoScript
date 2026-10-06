**English** | [Polski](README.pl.md)

# SudoScript

SudoScript is a powerful, 100% offline application designed for the intelligent processing of foreign-language videos. It generates optimized text tracks (subtitles, and eventually scripts for AI voiceovers and dubbing) using Vision-Language Models (VLM).

The name refers to Sudoism – you gain "root" privileges to modify and perceive language barriers in our reality!

## 🚀 Core Features
* **Privacy & Offline Mode:** All processing is done 100% locally. No external cloud APIs are used, guaranteeing data security.
* **Visual Context:** By utilizing VLM models, the translation process considers the speaker's gender, character relationships, and props in the frame.
* **Technical Quality:** Generated subtitles adhere to strict technical guidelines (CPL - Characters Per Line, CPS - Characters Per Second) and precisely avoid scene cuts.

## 🏗️ Pipeline Architecture
1. **Audio Extraction:** FFmpeg extracts the audio track (WAV, 16kHz, mono).
2. **Cut Recognition:** PySceneDetect analyzes the video and saves timestamps of scene cuts.
3. **Transcription:** `faster-whisper` generates raw text with exact timestamps.
4. **Frame Sampling:** FFmpeg extracts a single frame from the middle of each spoken phrase.
5. **Multimodal Translation (VLM):** A local Ollama instance (default `Qwen2.5-VL`) receives the frame and text, then translates it appropriately based on the selected mode.
6. **Export Module:** `pysubs2` validates timings, formats the text, and avoids conflicts with scene cuts, outputting `.srt` or `.ass` files.

## 🛠️ Requirements & Installation
* Python 3.10+
* FFmpeg (installed locally and added to PATH)
* [Ollama](https://ollama.com/) running locally with the vision model (e.g. `Qwen2.5-VL`).

```bash
# Clone the repository
git clone https://github.com/BreakTechEu/SudoScript.git
cd SudoScript

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # on Unix/MacOS
# or on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🤝 Contributing Guidelines
We collaborate asynchronously in this project. Since engineers from different backgrounds work here, please follow these rules:
1. **Feature Branches:** Never commit directly to the `master` branch. Every new feature, fix, or refactor must be done on a separate branch (e.g. `feature/audio-extraction`, `fix/subtitle-sync`).
2. **Pull Requests (PR):** Merge changes into `master` only via Pull Requests on GitHub.
3. **Conventional Commits:** Use standard commit prefixes:
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation update
   - `refactor:` code rewrite without changing behavior
   - `chore:` dependency updates, config changes
4. **Modularity:** Keep files small and logically separated. Each service (Whisper, Ollama, FFmpeg) must have its own module with explicit exception handling.

## ⚖️ Copyright & License
This project is intended for educational and research purposes (non-commercial use). The mechanisms contained herein must only process audiovisual materials for which you have rights or permission.

Details can be found in the `DISCLAIMER.md` file.
