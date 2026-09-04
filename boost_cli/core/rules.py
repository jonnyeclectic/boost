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
# Claude Code reads CLAUDE.md; Gemini CLI reads GEMINI.md.
#
# The value is ``(user_filename, project_filename)``. They differ for Claude
# because it documents a personal, git-ignored ``CLAUDE.local.md`` for the
# per-repo case, and installing a rule into the *committed* CLAUDE.md would
# rewrite a file the whole team reviews. Gemini CLI documents no ``.local``
# variant — its project context file is just ``<repo>/GEMINI.md`` — so both
# entries are the same and the pair still expresses the choice explicitly.
CONTEXT_FILES = {
    "claude-code": ("CLAUDE.md", "CLAUDE.local.md"),
    "gemini": ("GEMINI.md", "GEMINI.md"),
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
                base: Path | None = None) -> tuple[str, Path]:
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
    """
    # `name` comes from tap-controlled frontmatter and is about to be joined
    # onto a directory, so it has to be a single component — otherwise
    # `../../../../.ssh/authorized_keys` escapes the rules dir entirely, and
    # under project scope it escapes into the victim's own repo.
    if not util.is_safe_component(name):
        raise BoostError("invalid rule name %r" % name)
    dotdir = Path(skills_dir).parent.name          # ".claude" / ".cursor" / …
    context = CONTEXT_FILES.get(agent)
    if context is not None:
        user_name, project_name = context
        if base is not None:
            return MODE_CLAUDE, Path(base) / project_name
        return MODE_CLAUDE, Path(skills_dir).parent / user_name
    root = (Path(base) / dotdir) if base is not None else Path(skills_dir).parent
    ext = RULE_DIR_EXT.get(agent, DEFAULT_RULE_EXT)
    return MODE_FILE, root / "rules" / (name + ext)


def render_claude_body(title: str, body: str) -> str:
    """The block body for CLAUDE.md: a title header + the rule prose.

    Frontmatter is already stripped by the caller — CLAUDE.md is plain Markdown,
    not a frontmatter-carrying rule file, so only the human-readable rule text
    belongs here.
    """
    title = title.strip()
    body = body.strip("\n")
    if body:
        return "# %s\n\n%s" % (title, body)
    return "# %s" % title


def merge_block(text: str, name: str, body: str) -> str:
    """Return ``text`` with rule ``name``'s managed block set to ``body``.

    Idempotent: if a block for ``name`` already exists it is replaced in place;
    otherwise the block is appended after exactly one blank line. The result
    always ends in a single newline so repeated installs don't accrete blank
    lines at end-of-file.
    """
    start, end = markers(name)
    block = "%s\n%s\n%s" % (start, body.strip("\n"), end)
    i = text.find(start)
    if i != -1:
        j = text.find(end, i)
        if j != -1:
            j += len(end)
            merged = text[:i] + block + text[j:]
            return merged.rstrip("\n") + "\n"
    base = text.rstrip("\n")
    if base:
        return base + "\n\n" + block + "\n"
    return block + "\n"


def read_block(text: str, name: str) -> str | None:
    """Rule ``name``'s managed block body from ``text``, or None if absent.

    The inverse of `merge_block`, and the reason it exists is that an update
    needs something to diff *against*: the body sitting in the user's CLAUDE.md
    is the standing instruction about to be replaced. Without a way to read it
    back, a refresh could only be gated on the incoming half.

    Returns None for both "no block" and a start marker with no end — the second
    is malformed, and `strip_block` already declines to guess there.
    """
    start, end = markers(name)
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i)
    if j == -1:
        return None
    return text[i + len(start):j].strip("\n")


def block_span(text: str, name: str) -> tuple[int, int] | None:
    """Character offsets of rule ``name``'s block in ``text``, or None.

    ``(i, j)``: ``i`` is where the start marker begins, ``j`` is right after
    the end marker — so ``text[:i]`` / ``text[j:]`` are exactly what
    surrounds the block. None covers both "no block" and a start marker with
    no end (malformed).
    """
    start, end = markers(name)
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i)
    if j == -1:
        return None
    return i, j + len(end)


def _stripped(before: str, after: str) -> str:
    """Join the text either side of a removed block, collapsing the gap."""
    before = before.rstrip("\n")
    after = after.strip("\n")
    parts = [p for p in (before, after) if p]
    return "\n\n".join(parts) + "\n" if parts else ""


def strip_block(text: str, name: str) -> str:
    """Return ``text`` with rule ``name``'s managed block removed.

    Idempotent and lossless for the surrounding content: the block plus the
    blank-line gap it introduced is collapsed, and a file that becomes empty
    collapses to ``""`` rather than a lone newline.
    """
    span = block_span(text, name)
    if span is None:
        return text  # no block, or malformed (start with no end): untouched
    i, j = span
    return _stripped(text[:i], text[j:])


def reinsert_block(current: str, name: str, body: str,
                    prefix: str, suffix: str) -> str:
    """Restore rule ``name``'s block at the position it was quarantined from.

    ``prefix``/``suffix`` are the raw text either side of the block as it
    stood right before quarantine stripped it (see :func:`block_span`). When
    ``current`` still equals what stripping that exact split would produce —
    i.e. nothing else touched the file while the rule sat quarantined — the
    block is spliced back at that same position, byte-for-byte. Otherwise the
    recorded position can't be trusted (the surrounding text changed), so
    this falls back to :func:`merge_block`'s append behavior.
    """
    if current == _stripped(prefix, suffix):
        start, end = markers(name)
        block = "%s\n%s\n%s" % (start, body.strip("\n"), end)
        merged = prefix + block + suffix
        return merged.rstrip("\n") + "\n"
    return merge_block(current, name, body)
