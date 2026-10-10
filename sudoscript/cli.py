"""Command-line entry point."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import Pipeline, Settings, SudoScriptError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sudoscript",
        description="Create translated subtitles locally from a video file.",
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--target-language", default="Polish")
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--ollama-model", default="qwen2.5vl:7b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--allow-remote-ollama", action="store_true")
    parser.add_argument("--max-chars-per-line", type=int, default=42)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    settings = Settings(
        target_language=args.target_language,
        whisper_model=args.whisper_model,
        ollama_model=args.ollama_model,
        ollama_url=args.ollama_url,
        max_chars_per_line=args.max_chars_per_line,
        max_lines=args.max_lines,
        allow_remote_ollama=args.allow_remote_ollama,
    )
    try:
        output = Pipeline(args.video, settings, args.workdir).run(args.output)
    except SudoScriptError as exc:
        logging.error("%s", exc)
        return 1
    print(f"Done: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
