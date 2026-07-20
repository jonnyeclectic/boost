"""Workflow materialization: drop a command/subagent into each agent's dir.

Workflows are the easy cousin of rules. A rule has no universal home (Claude
needs a CLAUDE.md merge), but a workflow is just a Markdown file the agent reads
from a conventional directory:

  * a slash **command** -> the agent's ``commands/`` dir
  * a **subagent**      -> the agent's ``agents/`` dir

So install is a verbatim file drop — no splicing. This module is the pure logic
(which slot a workflow belongs in, and where it lands per agent); ``store`` owns
the filesystem writes and the lock record so uninstall can reverse them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

SLOT_COMMANDS = "commands"
SLOT_AGENTS = "agents"

# Source directory names that mark a workflow as a subagent rather than a
# slash command. Everything else (commands/, workflows/, or frontmatter-only)
# is treated as a command.
AGENT_DIRS = {"agents", "subagents"}


def detect_slot(source_rel: str) -> str:
    """Return the target slot (``commands`` or ``agents``) for a workflow whose
    defining file is ``source_rel`` (path relative to the tap repo root).

    A file under ``agents/`` or ``subagents/`` is a subagent; anything else —
    ``commands/``, ``workflows/``, or a bare frontmatter-tagged file — is a
    slash command.
    """
    parts = {p.lower() for p in Path(source_rel).parts}
    return SLOT_AGENTS if parts & AGENT_DIRS else SLOT_COMMANDS


def workflow_target(skills_dir: Path, slot: str, name: str,
                    base: Optional[Path] = None) -> Path:
    """Where workflow ``name`` (in ``slot``) materializes for an agent.

    ``base`` selects the scope:
      * ``None`` (user scope) — the parent of the agent's configured skills dir
        (``~/.claude/skills`` -> ``~/.claude/<slot>/<name>.md``).
      * a directory (project scope) — that repo's per-agent dotdir
        (``<base>/.claude/<slot>/<name>.md``).
    """
    root = (Path(base) / Path(skills_dir).parent.name) if base is not None \
        else Path(skills_dir).parent
    return root / slot / (name + ".md")
