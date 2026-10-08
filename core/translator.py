"""Multimodal translation through a local Ollama instance.

Each transcribed utterance is sent to a local vision-language model
together with the still frame sampled from the middle of that utterance.
The VLM therefore knows who is speaking, their gender and register, and
which props are visible - context a pure text model cannot recover.

Three work modes share this client and differ only in the prompt:

* subtitles  - concise, idiomatic subtitle text (phase 1 deliverable)
* voiceover  - fluent prose for an AI narrator (phase 2 groundwork)
* dubbing    - phonetically length-matched lines for AI dubbing (phase 2)

100% offline: the client only ever talks to the local Ollama server.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from config import OllamaSettings
from utils.errors import SudoScriptError
from utils.schema import Segment, WorkMode

logger = logging.getLogger(__name__)


def _http() -> Any:
    """Import requests lazily; pure logic stays testable without it."""
    import requests

    return requests


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*?\}", re.DOTALL)


class TranslationError(SudoScriptError):
    """Raised when the VLM backend cannot translate a segment."""


class OllamaUnavailableError(TranslationError):
    """Raised when the local Ollama server is unreachable."""


_MODE_GUIDELINES: dict[WorkMode, str] = {
    WorkMode.SUBTITLES: (
        "The result will become a subtitle. Translate concisely and "
        "idiomatically; brevity beats literalness. Do NOT add line breaks, "
        "the layout engine wraps the text itself. Keep punctuation, "
        "questions and tone. Translate only speech, not on-screen titles."
    ),
    WorkMode.VOICEOVER: (
        "The result will be read aloud by a single narrator over the "
        "original audio. Produce fluent, natural prose that is pleasant to "
        "read aloud. Length may differ from the source; natural speech "
        "rhythm matters more than literal accuracy."
    ),
    WorkMode.DUBBING: (
        "The result will be performed by a voice actor and must fit the "
        "original speaking time. Keep the spoken length close to the "
        "source (aim for a similar syllable count, within about 15%). "
        "Match the speaker's gender and register visible in the frame."
    ),
}


def build_prompt(
    text: str,
    mode: WorkMode,
    target_language: str,
    context_hint: str | None = None,
) -> str:
    """Compose the user prompt for one segment."""
    parts = [
        "You are an expert audiovisual translator working fully offline.",
        f"Translate the following transcript line into {target_language}.",
        (
            "A still frame from the exact moment the line is spoken is "
            "attached. Use it to infer the speaker's gender, age, formality, "
            "character relationships and props in the shot. Never invent "
            "content that is not in the transcript."
        ),
        _MODE_GUIDELINES[mode],
    ]
    if context_hint:
        parts.append(f"Dialogue context so far: {context_hint}")
    parts += [
        (
            'Return ONLY a JSON object: {"translation": "<translated text>"} '
            "with no markdown fences and no explanations."
        ),
        f"Transcript line: {text}",
    ]
    return "\n".join(parts)


def parse_translation(model_output: str) -> str:
    """Extract the translated text from a VLM response.

    Handles the three shapes Qwen-class models actually produce:
    clean JSON, JSON inside a markdown fence, and plain text with no
    JSON at all (fallback keeps the raw string).
    """
    content = (model_output or "").strip()
    if not content:
        raise TranslationError("The VLM returned an empty response.")

    fence_match = _JSON_FENCE_RE.search(content)
    if fence_match:
        content = fence_match.group(1).strip()

    for candidate in (content, _JSON_OBJECT_RE.search(content)):
        if not candidate:
            continue
        try:
            payload = json.loads(
                candidate if isinstance(candidate, str) else candidate.group(0)
            )
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("translation"), str):
            translation = payload["translation"].strip()
            if translation:
                return translation
        raise TranslationError(
            f"Unexpected JSON shape from the VLM: {str(payload)[:200]}"
        )

    return content


class OllamaClient:
    """Minimal, dependency-light client for the local Ollama HTTP API."""

    def __init__(self, settings: OllamaSettings):
        self._settings = settings
        self._base_url = settings.base_url.rstrip("/")

    def ensure_available(self) -> None:
        """Fail fast with a clear message when Ollama is not running."""
        requests = _http()
        try:
            response = requests.get(f"{self._base_url}/api/version", timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaUnavailableError(
                "Cannot reach the Ollama server at "
                f"{self._base_url}. Is 'ollama serve' running? "
                f"(details: {exc})"
            ) from exc

    def translate(
        self,
        text: str,
        frame_path: str | None,
        mode: WorkMode,
        target_language: str,
        context_hint: str | None = None,
    ) -> str:
        """Translate one utterance, optionally with its sampled frame."""
        prompt = build_prompt(text, mode, target_language, context_hint)
        message: dict[str, object] = {"role": "user", "content": prompt}
        image_b64 = self._encode_frame(frame_path)
        if image_b64:
            message["images"] = [image_b64]

        payload = {
            "model": self._settings.model,
            "stream": False,
            "messages": [message],
            "options": {
                "temperature": self._settings.temperature,
            },
        }
        raw = self._post_chat(payload)
        return parse_translation(raw)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _encode_frame(self, frame_path: str | None) -> str | None:
        if not frame_path:
            return None
        path = Path(frame_path)
        if not path.is_file():
            logger.debug("Frame missing, translating text-only: %s", frame_path)
            return None
        return base64.b64encode(path.read_bytes()).decode("ascii")

    def _post_chat(self, payload: dict[str, object]) -> str:
        requests = _http()
        url = f"{self._base_url}/api/chat"
        last_error: Exception | None = None
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self._settings.request_timeout_s,
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    raise TranslationError("Ollama returned an empty message.")
                return content
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self._settings.max_retries:
                    delay_s = 2.0 * attempt
                    logger.warning(
                        "Ollama request failed (attempt %d/%d), retrying in %.0fs: %s",
                        attempt,
                        self._settings.max_retries,
                        delay_s,
                        exc,
                    )
                    time.sleep(delay_s)
        raise OllamaUnavailableError(
            f"Ollama request failed after {self._settings.max_retries} attempts: "
            f"{last_error}"
        )


def translate_segments(
    segments: list[Segment],
    client: OllamaClient,
    mode: WorkMode,
    target_language: str,
    context_chars: int = 300,
) -> list[Segment]:
    """Translate every segment in place; failures degrade gracefully.

    A segment that cannot be translated (persistent transport error) keeps
    its original text so the pipeline can finish a long video instead of
    dying at line 300 of 400. The caller is expected to log the summary.
    """
    recent_translations: list[str] = []
    failures = 0
    for position, segment in enumerate(segments):
        context_hint = " | ".join(recent_translations[-3:]) or None
        try:
            segment.translated_text = client.translate(
                segment.source_text,
                segment.frame_path,
                mode,
                target_language,
                context_hint=context_hint,
            )
            recent_translations.append(segment.translated_text)
            recent_translations = recent_translations[-context_chars // 40 :]
        except TranslationError as exc:
            failures += 1
            segment.translated_text = None
            logger.error(
                "Segment %d could not be translated (%s); source text will be kept.",
                segment.index,
                exc,
            )
        if (position + 1) % 25 == 0:
            logger.info("Translated %d/%d segments.", position + 1, len(segments))

    logger.info(
        "Translation finished: %d/%d segments translated, %d failures.",
        len(segments) - failures,
        len(segments),
        failures,
    )
    return segments
