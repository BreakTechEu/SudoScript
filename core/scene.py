"""Scene-cut detection with PySceneDetect.

Subtitle timing must never cross a montage cut: a line that stays on
screen through a shot change reads as a sync error. This module returns
the list of cut timestamps (in seconds) the export step has to respect.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import SceneSettings
from utils.errors import SudoScriptError

logger = logging.getLogger(__name__)


class SceneDetectionError(SudoScriptError):
    """Raised when scene analysis fails or PySceneDetect is unavailable."""


def detect_scene_cuts(video_path: str | Path, settings: SceneSettings) -> list[float]:
    """Return scene-cut timestamps (seconds) detected in *video_path*.

    Consecutive cuts closer than SceneSettings.min_scene_len_s are merged,
    which filters out jitter from fades and flash shots.
    """
    video = Path(video_path)
    if not video.is_file():
        raise SceneDetectionError(f"Input file does not exist: {video}")

    try:
        from scenedetect import ContentDetector, detect
    except ImportError as exc:  # pragma: no cover - environment specific
        raise SceneDetectionError(
            "PySceneDetect is not installed. Run: pip install 'scenedetect[opencv]'"
        ) from exc

    try:
        scenes = detect(str(video), ContentDetector(threshold=settings.threshold))
    except Exception as exc:  # scenedetect/opencv raise a wide range of errors
        raise SceneDetectionError(
            f"Scene detection failed for '{video.name}': {exc}"
        ) from exc

    cuts: list[float] = []
    for start_timecode, _end_timecode in scenes[1:]:  # first scene start is not a cut
        cut_s = float(start_timecode.get_seconds())
        if cuts and cut_s - cuts[-1] < settings.min_scene_len_s:
            continue
        cuts.append(cut_s)

    logger.info("Detected %d scene cuts in '%s'.", len(cuts), video.name)
    return cuts
