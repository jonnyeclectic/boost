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


def block_span(text: str, name: str) -> tuple[int, int] | None:
    """``(i, j)`` such that ``text[i:j]`` is rule ``name``'s managed block.

    None for both "no block" and a malformed one: a start marker with no end
    after it, or a second start marker before that end. The second shape is
    what an orphan start becomes after one more install — merge_block appends
    a whole block below it, and "first start to first end" then spans the
    user's own text in between. Every reader and writer of the block goes
    through here so they agree on what the block is; `require_well_formed`
    tells the two Nones apart.
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


def merge_block(text: str, name: str, body: str) -> str:
    """Return ``text`` with rule ``name``'s managed block set to ``body``.

    Idempotent: if a block for ``name`` already exists it is replaced in place;
    otherwise the block is appended after exactly one blank line. The result
    always ends in a single newline so repeated installs don't accrete blank
    lines at end-of-file. A malformed block raises (`require_well_formed`)
    rather than appending a second block below the orphan start.
    """
    start, end = markers(name)
    block = "%s\n%s\n%s" % (start, body.strip("\n"), end)
    require_well_formed(text, name)
    span = block_span(text, name)
    if span is not None:
        i, j = span
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

    Returns None for both "no block" and a malformed one (`block_span`) — the
    second, and `strip_block` already declines to guess there.
    """
    span = block_span(text, name)
    if span is None:
        return None
    start, end = markers(name)
    i, j = span
    return text[i + len(start):j - len(end)].strip("\n")


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

    Idempotent and lossless for the surrounding content: the block plus the
    blank-line gap it introduced is collapsed, and a file that becomes empty
    collapses to ``""`` rather than a lone newline.
    """
    span = block_span(text, name)
    if span is None:
        return text  # absent, or malformed: leave the file untouched
    i, j = span
    before = text[:i].rstrip("\n")
    after = text[j:].strip("\n")
    parts = [p for p in (before, after) if p]
    return "\n\n".join(parts) + "\n" if parts else ""
