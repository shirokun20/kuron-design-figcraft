#!/usr/bin/env python3
"""Lightweight runtime harness detection for FigCraft parallel workflows.

Detection reads only well-known marker *names* and the generic terminal name
from the process environment. It never opens credentials, config files, or
private paths, and it has no dependencies outside the Python standard library.

Priority is fixed and deterministic: an explicit override, then a specific
harness marker, then a terminal-name hint, then ``generic`` or ``unknown``.
"""

import os
from typing import Mapping, Optional

SUPPORTED_HARNESSES = (
    "antigravity", "claude-code", "opencode", "codex", "generic", "unknown",
)

# Marker names only. A marker counts as present when it has a non-empty,
# non-disabled value; the value itself is never logged or stored.
HARNESS_MARKERS = {
    "antigravity": ("ANTIGRAVITY", "ANTIGRAVITY_SESSION", "ANTIGRAVITY_SESSION_ID"),
    "claude-code": ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION"),
    "opencode": ("OPENCODE", "OPENCODE_SESSION_ID", "OPENCODE_COMMAND"),
    "codex": ("CODEX", "CODEX_HOME", "CODEX_SESSION_ID"),
}
_DETECTION_ORDER = ("antigravity", "claude-code", "opencode", "codex")
_GENERIC_MARKERS = ("AI_AGENT", "AGENT_NAME")
_DISABLED = ("", "0", "false", "no", "off")
_OVERRIDE_VAR = "FIGCRAFT_HARNESS"


def detect_harness(environ: Optional[Mapping[str, str]] = None) -> str:
    """Return the detected harness name from a fixed, documented vocabulary.

    Args:
        environ: Optional mapping to inspect; defaults to ``os.environ``.
            Passing a mapping makes detection pure and easy to test.

    Returns:
        One of ``SUPPORTED_HARNESSES``. ``generic`` means an unidentified agent
        terminal is present; ``unknown`` means no runtime marker was found.
    """
    env = os.environ if environ is None else environ

    override = str(env.get(_OVERRIDE_VAR, "") or "").strip().lower()
    if override in SUPPORTED_HARNESSES:
        return override

    for name in _DETECTION_ORDER:
        for key in HARNESS_MARKERS[name]:
            value = str(env.get(key, "") or "").strip().lower()
            if value and value not in _DISABLED:
                return name

    terminal = str(env.get("TERM_PROGRAM", "") or "").strip().lower()
    for name in _DETECTION_ORDER:
        if name in terminal or (name == "claude-code" and "claude" in terminal):
            return name
    if terminal or any(str(env.get(key, "") or "").strip().lower() not in _DISABLED
                       for key in _GENERIC_MARKERS):
        return "generic"
    return "unknown"


if __name__ == "__main__":
    print(detect_harness())
