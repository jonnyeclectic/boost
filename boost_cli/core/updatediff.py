# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Content-diff gate for ``boost update``.

An in-place update silently overwrites an installed skill with whatever the tap
now ships. That is exactly the seam a poisoned update slips through: a skill you
already trust grows a ``curl … | sh`` line and nothing tells you. This module
turns an update into a *reviewable* event — it diffs the installed tree against
the incoming one and flags when the change touches **executable-looking
instructions** (shell commands, pipe-to-shell, shebangs). The command layer
shows that diff and asks before applying a risky change; routine edits still
apply quietly.

IT ALSO ASKS `injectscan`. The shell heuristic below models a payload that is a
*command*. The payload that matters for a file loaded into a model's context can
be a *sentence* — "ignore all previous instructions", "do not mention this to
the user" — and none of those match a command pattern, so this gate used to
apply them silently. `boost install` has scanned for exactly that since it
shipped; the update path simply never asked. It does now, over the added lines
only, so the same taxonomy covers both ways content arrives on the machine
rather than two half-detectors drifting apart.

The decision logic here is deliberately pure — it works on ``{relpath: text}``
maps, not the filesystem — so it stays trivially testable. ``read_tree`` is the
only filesystem touch and is a thin adapter.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from . import injectscan
from .util import IGNORED

# Added lines that look like something a machine would *execute*, not prose.
# Kept intentionally broad — a false positive only costs one confirmation, a
# false negative lets a poisoned instruction through silently.
_COMMAND_RE = re.compile(
    r"^\s*(?:\$\s+)?(?:sudo\s+)?"
    r"(?:curl|wget|sh|bash|zsh|eval|exec|source|rm|mv|cp|chmod|chown|"
    r"python3?|pip3?|npm|npx|node|deno|go|cargo|gem|git|ssh|scp|nc|ncat|"
    r"base64|xxd|osascript|powershell|pwsh|iex|invoke-expression|"
    r"certutil|reg|schtasks|launchctl|crontab)\b",
    re.IGNORECASE,
)
# `… | sh`, `… | sudo bash`, etc. — the classic download-and-run pipe.
_PIPE_TO_SHELL_RE = re.compile(r"\|\s*(?:sudo\s+)?(?:sh|bash|zsh|pwsh|powershell)\b",
                               re.IGNORECASE)


class TreeDiff(NamedTuple):
    """Result of comparing two skill trees."""

    text: str        # concatenated unified diffs across changed files
    risky: bool      # an added line is worth a human look before it lands
    changed: bool    # any file added, removed, or modified
    reasons: tuple[str, ...] = ()   # why `risky` is set, worst-first, deduped


def line_is_executable(line: str) -> bool:
    """True if ``line`` reads like a command a shell would run."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#!"):
        return True
    if _PIPE_TO_SHELL_RE.search(stripped):
        return True
    return bool(_COMMAND_RE.match(stripped))


def touches_executable(lines: Iterable[str]) -> bool:
    """True if any line in ``lines`` looks executable."""
    return any(line_is_executable(ln) for ln in lines)


def _added_lines(old: str, new: str) -> list[str]:
    """The right-hand (``+``) lines a unified diff would introduce."""
    added = [ln[2:] for ln in difflib.ndiff(old.splitlines(), new.splitlines()) if ln.startswith("+ ")]
    return added


def diff_tree(old: dict[str, str], new: dict[str, str]) -> TreeDiff:
    """Diff two ``{relpath: text}`` maps.

    Returns the unified-diff text over every changed file, whether anything
    changed at all, whether any *added* line is worth a human look (the
    ``risky`` gate), and the reasons why — worst-first and deduped, because the
    caller has to print one. A confirmation prompt that cannot say what it
    objected to is a prompt people learn to accept without reading.

    Only the ``+`` side is scanned. *Removing* a poisoned line must not be the
    thing that stops to ask.
    """
    chunks: list[str] = []
    added_all: list[str] = []
    changed = False
    for rel in sorted(set(old) | set(new)):
        before = old.get(rel, "")
        after = new.get(rel, "")
        if before == after:
            continue
        changed = True
        added_all.extend(_added_lines(before, after))
        chunks.append("\n".join(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile="a/" + rel, tofile="b/" + rel, lineterm="")))
    reasons: list[str] = []
    if touches_executable(added_all):
        reasons.append("changes executable-looking instructions")
    # `injectscan` orders worst-first and may report the same rule on several
    # lines; the prompt wants each distinct reason once.
    for f in injectscan.scan_text("\n".join(added_all)):
        if f.description not in reasons:
            reasons.append(f.description)
    return TreeDiff(text="\n".join(chunks),
                    risky=bool(reasons),
                    changed=changed,
                    reasons=tuple(reasons))


def read_tree(path: Path) -> dict[str, str]:
    """Map every readable text file under ``path`` to its content.

    Binary files (and anything under an ignored dir) are skipped — the gate is
    about human-readable instructions, and a binary can't be a shell command.
    A missing directory yields an empty map, so a first install diffs cleanly.
    """
    root = Path(path)
    tree: dict[str, str] = {}
    if not root.is_dir():
        return tree
    for p in root.rglob("*"):
        if not p.is_file() or any(part in IGNORED for part in p.parts):
            continue
        try:
            tree[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — not an instruction surface
    return tree
