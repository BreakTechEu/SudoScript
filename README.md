# SudoScript

SudoScript is a local-first command-line tool for transcribing video speech and producing translated subtitles. The initial implementation targets SRT output and a local Ollama translation backend.

## Requirements

- Python 3.11+
- FFmpeg available on PATH
- Ollama running locally with a vision-language or text model installed
- Python dependencies installed from this repository

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[test]"
```

## Run

```bash
sudoscript "input video.mp4" --target-language Polish
```

By default, the SRT is written next to the input video. Working files are isolated under `.sudoscript/<video-name>/`. Use `--workdir` to choose a different work directory and `--ollama-url` to configure the backend explicitly.

The default Ollama URL is loopback-only (`http://127.0.0.1:11434`). Remote backends are rejected unless `--allow-remote-ollama` is supplied.

## Privacy

Audio, transcripts and extracted frames are processed locally by default. The translation backend is configured to use local Ollama. No cloud translation service is built into the application.

## Status

This is an early rebuild. Treat output as a draft requiring review. Licensing and commercial-use policy are not yet finalized. Users are responsible for ensuring they have rights to process source media.
