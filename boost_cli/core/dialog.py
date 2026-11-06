# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Ask a yes/no question in a desktop dialog, for callers with no terminal.

The ``boost://`` URL handler is launched by the OS or a browser: no TTY, so
``output.confirm`` can only return its default, and every link the handler
was given cancelled. The bypass (``-y``) is not an answer there — any web page
can open a ``boost://`` link, so a handler that passed it would install
whatever a page named without asking anyone. This module is the other way
out: ask the person at the desktop, and treat anything but an explicit
"yes" as "no".

Security notes, because the question text comes from the URL:

* The prompt is passed to ``osascript`` as a script **argument** (``on run
  argv``), never spliced into AppleScript source, so a quote in a skill name
  cannot become code.
* ``zenity`` gets ``--no-markup`` and ``kdialog`` auto-detects rich text, so
  :func:`sanitize` drops ``<``/``>`` and control characters and caps the
  length: a link cannot restyle the dialog or push the real question off it.
* Cancel is the default button, a timeout is a decline, and a dialog tool
  that fails to start is a decline — failing closed every time.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unicodedata
from collections.abc import Callable, Mapping

#: Longest prompt shown; the rest is cut and marked with an ellipsis.
MAX_PROMPT = 300
#: Seconds before an unanswered dialog counts as "no".
TIMEOUT = 120

_OSASCRIPT_BODY = ('display dialog (item 1 of argv) with title "boost" '
                   'buttons {"Cancel", (item 2 of argv)} '
                   'default button "Cancel" cancel button "Cancel" '
                   'with icon caution giving up after %d' % TIMEOUT)


def sanitize(prompt: str) -> str:
    """``prompt`` with markup brackets, control and format characters removed, capped."""
    # Cc (C0/C1 controls, DEL) become a space; Cf (bidi overrides such as
    # U+202E, zero-width joiners) are dropped, or a link could make the
    # dialog display a name other than the one it installs.
    clean = "".join(" " if unicodedata.category(ch) == "Cc" else ch
                    for ch in prompt
                    if ch not in "<>" and unicodedata.category(ch) != "Cf")
    if len(clean) > MAX_PROMPT:
        clean = clean[:MAX_PROMPT - 1] + "…"
    return clean


def argv_for(prompt: str, ok_label: str, system: str,
             which: Callable[[str], str | None] | None = None,
             env: Mapping[str, str] | None = None) -> list[str] | None:
    """The dialog command for ``system``, or ``None`` when none can be shown.

    Darwin uses ``osascript``. Linux uses ``zenity`` then ``kdialog``, and only
    with a display to draw on (``DISPLAY`` or ``WAYLAND_DISPLAY``).
    """
    # Looked up per call, not bound as defaults, so a test patching
    # ``shutil.which`` / ``os.environ`` reaches the call it means to.
    which = shutil.which if which is None else which
    env = os.environ if env is None else env
    text = sanitize(prompt)
    if system == "Darwin":
        if not which("osascript"):
            return None
        return ["osascript", "-e", "on run argv", "-e", _OSASCRIPT_BODY,
                "-e", "end run", text, ok_label]
    if system != "Linux":
        return None
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return None
    if which("zenity"):
        return ["zenity", "--question", "--no-markup", "--title=boost",
                "--ok-label=" + ok_label, "--cancel-label=Cancel",
                "--timeout=%d" % TIMEOUT, "--text=" + text]
    if which("kdialog"):
        return ["kdialog", "--title", "boost", "--yes-label", ok_label,
                "--no-label", "Cancel", "--yesno", text]
    return None


def answered_yes(argv: list[str], ok_label: str, returncode: int,
                 stdout: str) -> bool:
    """Whether a finished dialog process means "yes".

    zenity and kdialog say it with exit 0 alone. ``osascript`` exits 0 on a
    timeout too (``gave up:true``), so it must also name the OK button.
    """
    if returncode != 0:
        return False
    if argv[0] == "osascript":
        return ("button returned:%s" % ok_label) in stdout \
            and "gave up:true" not in stdout
    return True


def ask(prompt: str, ok_label: str, system: str,
        which: Callable[[str], str | None] | None = None,
        run: Callable[..., subprocess.CompletedProcess] | None = None,
        env: Mapping[str, str] | None = None) -> bool | None:
    """Ask ``prompt`` in a dialog: True/False, or None when no dialog exists.

    ``None`` is distinct from ``False`` so the caller can say *why* nothing
    happened — there was nobody to ask — rather than report a decline.
    """
    argv = argv_for(prompt, ok_label, system, which=which, env=env)
    if argv is None:
        return None
    run = subprocess.run if run is None else run
    try:
        proc = run(argv, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=TIMEOUT + 30)
    except (OSError, subprocess.SubprocessError):
        return False
    return answered_yes(argv, ok_label, proc.returncode, proc.stdout or "")
