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
from typing import Optional, Tuple

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


def markers(name: str) -> Tuple[str, str]:
    """The (start, end) CLAUDE.md marker comments for rule ``name``."""
    return BLOCK_START % name, BLOCK_END % name


def rule_target(agent: str, skills_dir: Path, name: str,
                base: Optional[Path] = None) -> Tuple[str, Path]:
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


def strip_block(text: str, name: str) -> str:
    """Return ``text`` with rule ``name``'s managed block removed.

    Idempotent and lossless for the surrounding content: the block plus the
    blank-line gap it introduced is collapsed, and a file that becomes empty
    collapses to ``""`` rather than a lone newline.
    """
    start, end = markers(name)
    i = text.find(start)
    if i == -1:
        return text
    j = text.find(end, i)
    if j == -1:
        return text  # no end marker: malformed, leave the file untouched
    j += len(end)
    before = text[:i].rstrip("\n")
    after = text[j:].strip("\n")
    parts = [p for p in (before, after) if p]
    return "\n\n".join(parts) + "\n" if parts else ""
