# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
import hashlib
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

from . import injectscan
from .util import BINARY_SNIFF, IGNORED

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


class TreeFile(NamedTuple):
    """One file of a tree as the gate sees it.

    ``text`` is the content decoded as UTF-8 with undecodable bytes replaced,
    so one stray Latin-1 byte cannot hide the ``curl … | sh`` beside it.
    ``binary`` marks a file that really is not text (it holds a NUL byte, the
    rule git uses, and is not text with a NUL smuggled in — see
    :func:`read_file`), whose ``text`` is a digest so two versions still
    compare.
    """

    text: str
    binary: bool = False
    executable: bool = False


#: How many leading bytes decide whether a file is binary — git's window.
_SNIFF = BINARY_SNIFF


def _as_file(value: str | TreeFile | None) -> TreeFile | None:
    """A bare string is a text file: the shape every caller used to pass."""
    if value is None or isinstance(value, TreeFile):
        return value
    return TreeFile(value)


#: Suffixes an agent or a shell reads as text, whatever bytes they hold.
_TEXT_SUFFIXES = frozenset((
    ".md", ".mdc", ".markdown", ".txt", ".rst", ".cursorrules",
    ".windsurfrules", ".clinerules", ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".bat", ".cmd", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl",
    ".json", ".yaml", ".yml", ".toml"))

#: Share of a NUL-stripped sniff window that may be garbage (U+FFFD or a
#: non-printing character) for it still to read as text. Measured: text
#: with a NUL in it is ~0; Mach-O, .so and PNG files sit at 0.33-0.69.
_GARBAGE_MAX = 0.1


def _smuggled_text(p: Path, data: bytes) -> str | None:
    """``data`` decoded, if it is text with NULs in it rather than a binary.

    One NUL is all git's rule needs, so without this a NUL appended to a
    SKILL.md or a script took every line above it out of the diff and the
    scan. A real binary is left alone: its string tables are full of words
    like ``exec`` and ``/bin/sh``, and gating on those would ask about every
    PDF and ``.so`` with a reason nobody could inspect.
    """
    text = data.replace(b"\0", b"").decode("utf-8", errors="replace")
    if (p.suffix.lower() in _TEXT_SUFFIXES or p.name.lower() in _TEXT_SUFFIXES
            or data.startswith(b"#!")):
        return text
    window = text[:_SNIFF]
    garbage = sum(1 for c in window if c == "\ufffd"
                  or (not c.isprintable() and c not in "\t\n\r"))
    return text if garbage <= _GARBAGE_MAX * len(window) else None


def _binary_chunk(rel: str, before: TreeFile | None,
                  after: TreeFile | None) -> str:
    """The diff line for a change on either side of which is binary."""
    how = ("added" if before is None else "removed" if after is None
           else "changed")
    return "Binary file %s %s" % (rel, how)


def diff_tree(old: Mapping[str, str | TreeFile],
              new: Mapping[str, str | TreeFile]) -> TreeDiff:
    """Diff two ``{relpath: text | TreeFile}`` maps.

    Returns the unified-diff text over every changed file, whether anything
    changed at all, whether any *added* line is worth a human look (the
    ``risky`` gate), and the reasons why — worst-first and deduped, because the
    caller has to print one. A confirmation prompt that cannot say what it
    objected to is a prompt people learn to accept without reading.

    Only the ``+`` side is scanned. *Removing* a poisoned line must not be the
    thing that stops to ask. A binary file has no lines to scan; it is listed
    as ``Binary file <rel> added|changed|removed``, and one that arrives
    executable — new, newly made so, or with its bytes swapped — is a reason
    of its own, since it is a program the update puts on the machine with
    nothing to read.
    """
    chunks: list[str] = []
    added_all: list[str] = []
    exec_binaries: list[str] = []      # "adds|changes executable binary <rel>"
    changed = False
    for rel in sorted(set(old) | set(new)):
        before = _as_file(old.get(rel))
        after = _as_file(new.get(rel))
        if before == after:
            continue
        changed = True
        if (before is not None and before.binary) or (
                after is not None and after.binary):
            chunks.append(_binary_chunk(rel, before, after))
            if after is not None and after.binary and after.executable:
                exec_binaries.append("%s executable binary %s" % (
                    "changes" if before is not None and before.executable
                    else "adds", rel))
            continue
        old_text = before.text if before is not None else ""
        new_text = after.text if after is not None else ""
        if before is not None and after is not None and old_text == new_text:
            # Same bytes, other mode: say so rather than print an empty diff.
            chunks.append("Mode of %s changed: %s executable"
                          % (rel, "now" if after.executable else "no longer"))
            continue
        added_all.extend(_added_lines(old_text, new_text))
        chunks.append("\n".join(difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines(),
            fromfile="a/" + rel, tofile="b/" + rel, lineterm="")))
    reasons: list[str] = []
    if touches_executable(added_all):
        reasons.append("changes executable-looking instructions")
    # Added, newly +x, or its bytes swapped: each puts a program on the
    # machine that nobody can read in the diff.
    reasons.extend(exec_binaries)
    # `injectscan` orders worst-first and may report the same rule on several
    # lines; the prompt wants each distinct reason once.
    for f in injectscan.scan_text("\n".join(added_all)):
        if f.description not in reasons:
            reasons.append(f.description)
    return TreeDiff(text="\n".join(chunks),
                    risky=bool(reasons),
                    changed=changed,
                    reasons=tuple(reasons))


def read_file(p: Path) -> TreeFile:
    """Read one file for the gate; raises ``OSError`` if it cannot be read."""
    data = p.read_bytes()
    executable = bool(p.stat().st_mode & 0o111)
    if b"\0" in data[:_SNIFF]:
        text = _smuggled_text(p, data)
        if text is not None:
            return TreeFile(text, executable=executable)
        return TreeFile(hashlib.sha256(data).hexdigest(), binary=True,
                        executable=executable)
    return TreeFile(data.decode("utf-8", errors="replace"),
                    executable=executable)


def read_tree(path: Path) -> dict[str, TreeFile]:
    """Map every readable file under ``path`` to its :class:`TreeFile`.

    Nothing readable is skipped any more. This used to drop every file that
    was not valid UTF-8, so one stray byte took a ``curl … | sh`` or an
    injection sentence out of the diff and the scan, and a new executable
    binary landed unlisted. Text is decoded with replacement; a binary is kept
    as a digest so it can be listed and judged. Only an unreadable file or an
    ignored dir is left out. A missing directory yields an empty map, so a
    first install diffs cleanly.
    """
    root = Path(path)
    tree: dict[str, TreeFile] = {}
    if not root.is_dir():
        return tree
    for p in root.rglob("*"):
        if not p.is_file() or any(part in IGNORED for part in p.parts):
            continue
        try:
            tree[p.relative_to(root).as_posix()] = read_file(p)
        except OSError:
            continue  # unreadable — store.install reports the real error
    return tree
