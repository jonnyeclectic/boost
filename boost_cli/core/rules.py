# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Rule materialization: turn a catalog rule into each agent's native format.

Skills copy into a canonical store and symlink into every enabled agent dir.
Rules can't do that — there is no single cross-agent rules folder:

  * Cursor / Windsurf / Cline read a rules DIRECTORY (``*.mdc`` / ``*.md``).
  * Claude Code has **no** rules folder; its standing rules live in ``CLAUDE.md``.

So a rule materializes per agent: a verbatim file drop for the rules-dir agents
(their frontmatter is native metadata and must be preserved), and an idempotent
managed *block* merged into ``CLAUDE.md`` for Claude. This module is the pure
logic — where a rule lands and how the CLAUDE.md block is spliced; ``store`` owns
the filesystem writes and the lock record so uninstall can reverse them.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import BoostError
from . import util

# Name-scoped managed-block markers for CLAUDE.md. Stable + per-rule so install
# is idempotent (a re-install replaces the block) and uninstall strips exactly
# the one block it wrote, never a hand-authored neighbour.
BLOCK_START = "<!-- boost:rule:%s start -->"
BLOCK_END = "<!-- boost:rule:%s end -->"

# File extension when an agent reads a rules directory. Claude is deliberately
# absent — it uses the CLAUDE.md merge path, not a file drop.
RULE_DIR_EXT = {"cursor": ".mdc", "windsurf": ".md", "cline": ".md"}
DEFAULT_RULE_EXT = ".md"

# Agents with no rules folder: a rule becomes a managed block in the agent's
# *context file* — the standing-instructions Markdown it reads every turn.
# Claude Code reads CLAUDE.md; Gemini CLI reads GEMINI.md; Codex reads
# AGENTS.md.
#
# The value is ``(user_filename, project_filename)``. They differ for Claude
# because it documents a personal, git-ignored ``CLAUDE.local.md`` for the
# per-repo case, and installing a rule into the *committed* CLAUDE.md would
# rewrite a file the whole team reviews. Gemini CLI documents no ``.local``
# variant — its project context file is just ``<repo>/GEMINI.md`` — so both
# entries are the same and the pair still expresses the choice explicitly.
#
# Codex is the same shape as Gemini for the same reason: verified against Codex
# CLI 0.156.1, the global `$CODEX_HOME/AGENTS.md` block is emitted first, then a
# `--- project-doc ---` separator, then the project `AGENTS.md` chain root-to-
# nested. There is no documented `.local` variant — the one override it has,
# `AGENTS.override.md`, *replaces* a directory's AGENTS.md rather than layering
# on it, which is the wrong shape for a personal overlay — so both entries are
# `AGENTS.md` and a project rule lands in the committed file, as it already
# does for Gemini. That is more consequential here than there: `AGENTS.md` is a
# cross-vendor convention, so a *project* rule installed for codex is also read
# by Cursor, and it is a file the team reviews. Say so; do not invent an
# unverified `.local` sibling to dodge it.
#
# The user-scope file is `$CODEX_HOME/AGENTS.md`, and the agent dir default is
# `${CODEX_HOME:-~/.codex}/skills` so `rule_target`'s `.parent` lands there even
# when Codex has been relocated — writing the default path would produce a file
# that CLI never opens, reported as installed.
CONTEXT_FILES = {
    "claude-code": ("CLAUDE.md", "CLAUDE.local.md"),
    "gemini": ("GEMINI.md", "GEMINI.md"),
    "codex": ("AGENTS.md", "AGENTS.md"),
}

# ``MODE_CLAUDE``'s *value* is written into every rule's lock record, so it is
# frozen at "claude" even though the mode now covers any context-file agent.
# Renaming the string would orphan the materializations of already-installed
# rules — uninstall matches on it (see store._uninstall_rule).
MODE_CLAUDE = "claude"
MODE_FILE = "file"


def markers(name: str) -> tuple[str, str]:
    """The (start, end) CLAUDE.md marker comments for rule ``name``."""
    return BLOCK_START % name, BLOCK_END % name


def rule_target(agent: str, skills_dir: Path, name: str,
                base: Path | None = None,
                dotdir: str | None = None) -> tuple[str, Path]:
    """Where rule ``name`` materializes for ``agent``.

    Returns ``(mode, path)``: ``MODE_CLAUDE`` writes/merges the agent's context
    file; ``MODE_FILE`` drops a file into the agent's ``rules/`` dir.

    ``base`` selects the scope:
      * ``None`` (user scope) — the agent's user config: the parent of its
        configured skills dir (``~/.cursor/skills`` -> ``~/.cursor``), and
        ``~/.claude/CLAUDE.md`` / ``~/.gemini/GEMINI.md`` for the context-file
        agents.
      * a directory (project scope) — that repo: ``<base>/.cursor/rules/…`` and,
        since those agents read per-repo memory from the root,
        ``<base>/CLAUDE.local.md`` or ``<base>/GEMINI.md`` (see
        :data:`CONTEXT_FILES`).

    ``dotdir`` overrides the derived repo-local directory name, for an agent
    whose user dir is not a fixed path — `agents.project_dotdir` is what
    computes it, and passing it here rather than calling it keeps this module a
    pure function of its arguments, as its unit tests rely on. Deriving is
    still right for every agent that does not declare one, and user scope never
    consults it: the answer there is the real parent of the real skills dir.
    """
    # `name` comes from tap-controlled frontmatter and is about to be joined
    # onto a directory, so it has to be a single component — otherwise
    # `../../../../.ssh/authorized_keys` escapes the rules dir entirely, and
    # under project scope it escapes into the victim's own repo.
    if not util.is_safe_component(name):
        raise BoostError("invalid rule name %r" % name)
    dotdir = dotdir or Path(skills_dir).parent.name   # ".claude" / ".cursor" / …
    context = CONTEXT_FILES.get(agent)
    if context is not None:
        user_name, project_name = context
        if base is not None:
            return MODE_CLAUDE, Path(base) / project_name
        return MODE_CLAUDE, Path(skills_dir).parent / user_name
    root = (Path(base) / dotdir) if base is not None else Path(skills_dir).parent
    ext = RULE_DIR_EXT.get(agent, DEFAULT_RULE_EXT)
    return MODE_FILE, root / "rules" / (name + ext)


# What every block marker opens with, and what `neutralize_markers` turns it
# into. `block_span` finds markers by exact substring, so text that cannot
# contain this prefix cannot contain a marker either.
MARKER_PREFIX = BLOCK_START.split("%s")[0]
_MARKER_DEFANGED = "&lt;" + MARKER_PREFIX[1:]


def neutralize_markers(text: str) -> str:
    """``text`` with every block-marker prefix defanged (``<`` → ``&lt;``).

    A rule body is tap-controlled, and one carrying its own
    ``<!-- boost:rule:NAME end -->`` closed its block early: `block_span` stops
    at the first end marker, so uninstall removed only the head of the rule
    and left the rest standing in the user's CLAUDE.md, while doctor reported
    healthy. Defanging keeps the prose readable and makes the block's only
    markers the two `merge_block` writes. Idempotent — the output holds no
    prefix left to defang.
    """
    return text.replace(MARKER_PREFIX, _MARKER_DEFANGED)


def render_claude_body(title: str, body: str) -> str:
    """The block body for CLAUDE.md: a title header + the rule prose.

    Frontmatter is already stripped by the caller — CLAUDE.md is plain Markdown,
    not a frontmatter-carrying rule file, so only the human-readable rule text
    belongs here. Marker text in either part is neutralised
    (`neutralize_markers`), so what verify hashes is what merge_block writes.
    """
    title = title.strip()
    body = body.strip("\n")
    if body:
        return neutralize_markers("# %s\n\n%s" % (title, body))
    return neutralize_markers("# %s" % title)


def block_names(text: str) -> list[str]:
    """The rule names whose start marker ``text`` carries, in order, once each.

    Only names a rule could be installed under (:func:`util.is_safe_component`):
    a marker naming anything else is no block boost wrote.
    """
    head, tail = BLOCK_START.split("%s")
    found: list[str] = []
    at = text.find(head)
    while at != -1:
        end = text.find(tail, at + len(head))
        if end == -1:
            break
        name = text[at + len(head):end]
        if (util.is_safe_component(name) and "\n" not in name
                and name not in found):
            found.append(name)
        at = text.find(head, at + len(head))
    return found


def block_span(text: str, name: str) -> tuple[int, int] | None:
    """``(i, j)`` such that ``text[i:j]`` is rule ``name``'s managed block.

    None for both "no block" and a malformed one: a start marker with no end
    after it, or a second start marker before that end. The second shape is
    what an orphan start becomes after one more install — merge_block appends
    a whole block below it, and "first start to first end" then spans the
    user's own text in between. A body cannot forge an end marker: merge_block
    neutralises marker text before writing (`neutralize_markers`). Every
    reader and writer of the block goes through here so they agree on what
    the block is; `require_well_formed` tells the two Nones apart.
    """
    start, end = markers(name)
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i)
    if j == -1 or text.find(start, i + len(start), j) != -1:
        return None
    return i, j + len(end)


def require_well_formed(text: str, name: str,
                        path: Path | None = None) -> None:
    """Raise if any start marker for ``name`` in ``text`` is not a clean block.

    The refusal every write and removal takes before touching the file:
    guessing where a damaged block ends is guessing which of the user's lines
    to delete. *Every* start counts, not just the first: a clean block with a
    stray start below it passes `block_span`, so strip_block removed the clean
    one and uninstall dropped the lock row while the stray start stayed.
    Two clean blocks are not refused — each start has its own end.
    """
    start, end = markers(name)
    pos = 0
    damaged = False
    while (i := text.find(start, pos)) != -1:
        j = text.find(end, i + len(start))
        if j == -1 or text.find(start, i + len(start), j) != -1:
            damaged = True
            break
        pos = j + len(end)
    if damaged:
        where = " in %s" % path if path is not None else ""
        raise BoostError(
            "rule %s's managed block%s has no matching end marker, so boost "
            "cannot tell where its text stops and yours begins" % (name, where),
            hint="restore `%s` after the rule's text (or delete `%s`), then "
                 "run the command again" % (end, start),
            wrap=True)


def line_ending(text: str) -> str:
    """The line ending ``text`` mostly uses: ``"\\r\\n"`` or ``"\\n"``.

    A context file is the user's, and a Windows checkout of a committed
    ``AGENTS.md`` is CRLF. The block boost inserts takes the file's own
    ending, so an install adds lines in the style already there instead of
    a mix git reports on every line it touches. A tie, an empty file and a
    file with no newline at all are ``"\\n"``.
    """
    crlf = text.count("\r\n")
    return "\r\n" if crlf > text.count("\n") - crlf else "\n"


def _ends_with_newline(text: str) -> bool:
    return text.endswith("\n")


def _cut_trailing_newline(text: str) -> tuple[str, bool]:
    """``text`` less one trailing line ending (either style), and whether
    there was one."""
    for eol in ("\r\n", "\n"):
        if text.endswith(eol):
            return text[:-len(eol)], True
    return text, False


def _cut_leading_newline(text: str) -> tuple[str, bool]:
    """``text`` less one leading line ending (either style), and whether
    there was one."""
    for eol in ("\r\n", "\n"):
        if text.startswith(eol):
            return text[len(eol):], True
    return text, False


def merge_block(text: str, name: str, body: str) -> str:
    """Return ``text`` with rule ``name``'s managed block set to ``body``.

    Idempotent: if a block for ``name`` already exists only that span is
    replaced, and every byte around it is kept; otherwise the block is
    appended after one blank line. Nothing outside the block is rewritten —
    the block takes the file's own line ending (:func:`line_ending`), and a
    file that did not end in a newline still does not, so that
    :func:`strip_block` can hand back the original bytes exactly. A
    malformed block raises (`require_well_formed`) rather than appending a
    second block below the orphan start.
    """
    eol = line_ending(text)
    start, end = markers(name)
    lines = (neutralize_markers(body).replace("\r\n", "\n").strip("\n")
             .replace("\n", eol))
    block = start + eol + lines + eol + end
    require_well_formed(text, name)
    span = block_span(text, name)
    if span is not None:
        i, j = span
        return text[:i] + block + text[j:]
    if not text:
        return block + eol
    if _ends_with_newline(text):
        return text + eol + block + eol
    # No final newline: the gap goes before the block and none after it, so
    # the file keeps the state it was in and the removal can tell this
    # shape from a file that did end in one.
    return text + eol + eol + block


def read_block(text: str, name: str) -> str | None:
    """Rule ``name``'s managed block body from ``text``, or None if absent.

    The inverse of `merge_block`, and the reason it exists is that an update
    needs something to diff *against*: the body sitting in the user's CLAUDE.md
    is the standing instruction about to be replaced. Without a way to read it
    back, a refresh could only be gated on the incoming half.

    Returns None for both "no block" and a malformed one (`block_span`) — the
    second, and `strip_block` already declines to guess there.
    """
    span = block_span(text, name)
    if span is None:
        return None
    start, end = markers(name)
    i, j = span
    # LF whatever the file uses: the hash `boost verify` compares against was
    # taken over the rendered (LF) body, and a CRLF file read with
    # ``newline=""`` must read back as the same text.
    return (text[i + len(start):j - len(end)]
            .replace("\r\n", "\n").strip("\n"))


def unclosed_block(text: str, name: str) -> bool:
    """True when ``text`` has rule ``name``'s start marker and no end after it.

    The case `read_block` folds into "absent". `boost doctor` needs it apart:
    a start marker on its own read as a block that was there, and the remedy
    for it is a hand edit -- restore the end marker or delete the orphan --
    not the reinstall that answers a block that is gone.
    """
    start, end = markers(name)
    i = text.find(start)
    return i != -1 and text.find(end, i) == -1


def strip_block(text: str, name: str) -> str:
    """Return ``text`` with rule ``name``'s managed block removed.

    The exact inverse of :func:`merge_block`'s append: the block, its line
    ending and the blank-line gap it introduced come out, and every other
    byte stays as it was — CRLF, a missing final newline, trailing blank
    lines. Install then uninstall leaves the file byte-identical. A file that
    held only the block collapses to ``""``.
    """
    span = block_span(text, name)
    if span is None:
        return text  # absent, or malformed: leave the file untouched
    i, j = span
    before, after = text[:i], text[j:]
    after, terminated = _cut_leading_newline(after)
    if terminated and (not after or after[0] in "\r\n"):
        # Appended after a newline-terminated file: one blank line went in
        # above the block. Take it only if it is still there, so a user who
        # deleted the gap by hand keeps their own line ending — and only when
        # the block ended the file or a gap follows it (another block's): text
        # written straight under the block keeps the blank line above it
        # rather than being run into the paragraph before.
        trimmed, cut = _cut_trailing_newline(before)
        if cut and _ends_with_newline(trimmed):
            before = trimmed
        elif not before and after:
            # The block opened the file, so the gap below it is the one the
            # next block was appended after: it goes with this one.
            after, _ = _cut_leading_newline(after)
    elif not after:
        # The block ends the file with no newline after it: merge_block put
        # two line endings in front of it and none behind (see there).
        before, cut = _cut_trailing_newline(before)
        if cut:
            before, _ = _cut_trailing_newline(before)
    return before + after
