"""SudoScript command-line interface and entry point.

Example:
    python main.py movie.mkv --mode subtitles --target-language Polish
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

import config
from core.pipeline import STEP_ORDER, Pipeline, PipelineOptions
from utils.errors import SudoScriptError
from utils.schema import OutputFormat, WorkMode

logger = logging.getLogger("sudoscript")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sudoscript",
        description=(
            "SudoScript - 100% offline subtitle generation for "
            "foreign-language videos using local VLM translation."
        ),
    )
    parser.add_argument("video", type=Path, help="Path to the input video file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file (.srt/.ass/.json/.csv). Default: next to the video.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in WorkMode],
        default=WorkMode.SUBTITLES.value,
        help="Work mode: subtitles (default), voiceover or dubbing script.",
    )
    parser.add_argument(
        "--format",
        choices=[fmt.value for fmt in OutputFormat],
        default=OutputFormat.SRT.value,
        help="Output container. Voiceover/dubbing modes use json or csv.",
    )
    parser.add_argument(
        "--target-language",
        default="Polish",
        help="Target language for translation (default: Polish).",
    )
    parser.add_argument(
        "--from-step",
        choices=STEP_ORDER,
        default="audio",
        help="Resume the pipeline from a step, reusing cached artefacts.",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Working directory for caches (default: <video dir>/.sudoscript).",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        help="faster-whisper model size (default: small).",
    )
    parser.add_argument(
        "--vlm-model",
        default=None,
        help="Ollama vision model tag (default: qwen2.5vl:7b).",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Base URL of the local Ollama server (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=None,
        help="PySceneDetect ContentDetector threshold (default: 27.0).",
    )
    parser.add_argument(
        "--cpl",
        type=int,
        default=None,
        help="Maximum characters per subtitle line (default: 42).",
    )
    parser.add_argument(
        "--cps",
        type=float,
        default=None,
        help="Maximum characters per second (default: 17).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose (debug) logging.",
    )
    return parser


def build_settings(args: argparse.Namespace) -> config.Settings:
    """Apply CLI overrides on top of the default configuration."""
    settings = config.DEFAULT_SETTINGS
    if args.whisper_model:
        settings = replace(
            settings, whisper=replace(settings.whisper, model_size=args.whisper_model)
        )
    if args.vlm_model:
        settings = replace(
            settings, ollama=replace(settings.ollama, model=args.vlm_model)
        )
    if args.ollama_url:
        settings = replace(
            settings, ollama=replace(settings.ollama, base_url=args.ollama_url)
        )
    if args.scene_threshold is not None:
        settings = replace(
            settings, scene=replace(settings.scene, threshold=args.scene_threshold)
        )
    if args.cpl is not None or args.cps is not None:
        rules = settings.subtitles
        if args.cpl is not None:
            rules = replace(rules, max_chars_per_line=args.cpl)
        if args.cps is not None:
            rules = replace(rules, max_chars_per_second=args.cps)
        settings = replace(settings, subtitles=rules)
    return settings


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    if not args.video.is_file():
        logger.error("Input video does not exist: %s", args.video)
        return 2

    options = PipelineOptions(
        mode=WorkMode(args.mode),
        output_format=OutputFormat(args.format),
        target_language=args.target_language,
        output_path=args.output,
        work_dir=args.workdir,
    )
    settings = build_settings(args)

    try:
        pipeline = Pipeline(args.video, settings, options)
        output = pipeline.run(from_step=args.from_step)
    except SudoScriptError as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Done: %s", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
