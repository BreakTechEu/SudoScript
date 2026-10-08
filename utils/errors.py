"""Exception hierarchy for SudoScript.

Every pipeline module raises a subclass of SudoScriptError so callers can
distinguish expected, well-described application failures from genuine bugs.
"""

from __future__ import annotations


class SudoScriptError(Exception):
    """Base class for all expected SudoScript failures."""


class StepSkippedError(SudoScriptError):
    """Raised when a pipeline step cannot run because inputs are missing."""
