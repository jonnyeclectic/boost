"""Workflow materialization: drop a command/subagent into each agent's dir.

Workflows are the easy cousin of rules. A rule has no universal home (Claude
needs a CLAUDE.md merge), but a workflow is usually just a Markdown file the
agent reads from a conventional directory:

  * a slash **command** -> the agent's ``commands/`` dir
  * a **subagent**      -> the agent's ``agents/`` dir

For most agents install is therefore a verbatim file drop. Gemini CLI is the
exception, and only for one of the two slots: its **subagents** are Markdown
with YAML frontmatter (so the verbatim drop is already right), but its **slash
commands** are TOML — ``~/.gemini/commands/<name>.toml`` carrying ``prompt``
and optional ``description`` keys. Dropping a Markdown file into that directory
is not a soft failure that degrades to something usable; the file is simply
never discovered, so the user sees an install report a command that does not
exist. Hence :func:`render`, which converts a Markdown workflow into Gemini's
TOML on the way out.

This module is the pure logic (which slot a workflow belongs in, where it lands
per agent, and what text goes in the file); ``store`` owns the filesystem writes
and the lock record so uninstall can reverse them.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..errors import BoostError
from . import frontmatter, util

SLOT_COMMANDS = "commands"
SLOT_AGENTS = "agents"

# Source directory names that mark a workflow as a subagent rather than a
# slash command. Everything else (commands/, workflows/, or frontmatter-only)
# is treated as a command.
AGENT_DIRS = {"agents", "subagents"}

# Agents whose slash commands are TOML rather than Markdown, and the extension
# they use. Only the ``commands`` slot differs — a Gemini *subagent* is Markdown
# with YAML frontmatter, exactly like Claude's, so it is absent from this map
# and takes the verbatim path.
TOML_COMMAND_AGENTS = {"gemini"}
TOML_EXT = ".toml"
DEFAULT_EXT = ".md"


def detect_slot(source_rel: str) -> str:
    """Return the target slot (``commands`` or ``agents``) for a workflow whose
    defining file is ``source_rel`` (path relative to the tap repo root).

    A file under ``agents/`` or ``subagents/`` is a subagent; anything else —
    ``commands/``, ``workflows/``, or a bare frontmatter-tagged file — is a
    slash command.
    """
    parts = {p.lower() for p in Path(source_rel).parts}
    return SLOT_AGENTS if parts & AGENT_DIRS else SLOT_COMMANDS


def target_ext(agent: str | None, slot: str) -> str:
    """The file extension workflow files use for ``agent`` in ``slot``.

    ``.toml`` only for a :data:`TOML_COMMAND_AGENTS` agent's ``commands`` slot;
    ``.md`` everywhere else, including that same agent's ``agents`` slot. A
    caller that does not know the agent (``None``) gets the Markdown default,
    which keeps the historical single-argument behaviour.
    """
    if slot == SLOT_COMMANDS and agent in TOML_COMMAND_AGENTS:
        return TOML_EXT
    return DEFAULT_EXT


def workflow_target(skills_dir: Path, slot: str, name: str,
                    base: Path | None = None,
                    agent: str | None = None) -> Path:
    """Where workflow ``name`` (in ``slot``) materializes for an agent.

    ``base`` selects the scope:
      * ``None`` (user scope) — the parent of the agent's configured skills dir
        (``~/.claude/skills`` -> ``~/.claude/<slot>/<name>.md``).
      * a directory (project scope) — that repo's per-agent dotdir
        (``<base>/.claude/<slot>/<name>.md``).

    ``agent`` selects the file *extension* via :func:`target_ext`. It is
    optional and trails ``base`` so the pre-Gemini call signature still works;
    omitting it always yields the Markdown name.
    """
    # Same guard as rule_target: `name` is tap-controlled and is about to become
    # a path component, so traversal has to be refused before the join.
    if not util.is_safe_component(name):
        raise BoostError("invalid workflow name %r" % name)
    root = (Path(base) / Path(skills_dir).parent.name) if base is not None \
        else Path(skills_dir).parent
    return root / slot / (name + target_ext(agent, slot))


def _toml_str(s: str) -> str:
    """``s`` as a TOML basic string literal, safe for ANY input.

    Every escape ``json.dumps`` emits — ``\\"`` ``\\\\`` ``\\b`` ``\\f`` ``\\n``
    ``\\r`` ``\\t`` ``\\uXXXX`` — is also a TOML basic-string escape, and the one
    JSON escape TOML lacks (``\\/``) is never emitted because ``/`` is passed
    through raw. So a JSON string literal is always a valid TOML one. This is
    the same subset trick ``adapters._py_str`` uses for Python literals.

    Deliberately a *single-line* basic string rather than the prettier ``\"\"\"``
    multi-line form: a workflow body is arbitrary tap-controlled Markdown, and
    bodies containing ``\"\"\"`` or a trailing quote cannot be embedded in the
    multi-line form without escaping anyway. Correctness for every input beats
    readability for most of them.
    """
    return json.dumps(s, ensure_ascii=False)


def render_gemini_command(name: str, raw: str) -> str:
    """A Markdown workflow rendered as a Gemini CLI ``.toml`` slash command.

    The Markdown body becomes ``prompt`` and the frontmatter ``description``
    becomes ``description`` — the two keys Gemini's TOML v1 format defines
    (``prompt`` required, ``description`` optional). Frontmatter is dropped
    rather than carried: it is Claude's metadata vocabulary, and TOML keys
    Gemini does not know are ignored, so emitting them would only be noise.

    A body that is empty after stripping frontmatter still emits ``prompt = ""``
    — a valid, discoverable (if useless) command — because the alternative is a
    file with no ``prompt`` key at all, which Gemini rejects outright.
    """
    meta, body = frontmatter.parse(raw)
    lines = []
    description = str(meta.get("description") or "").strip()
    if description:
        lines.append("description = %s" % _toml_str(description))
    lines.append("prompt = %s" % _toml_str(body.strip("\n")))
    return "\n".join(lines) + "\n"


def render(agent: str | None, slot: str, name: str, raw: str) -> str:
    """The text to write for ``name`` in ``slot`` for ``agent``.

    Verbatim ``raw`` for every agent and slot except a TOML-command agent's
    ``commands`` slot, which is converted by :func:`render_gemini_command`.
    Pairs with :func:`target_ext`: the two agree on exactly which combination is
    special, so the extension and the content can never disagree.
    """
    if target_ext(agent, slot) == TOML_EXT:
        return render_gemini_command(name, raw)
    return raw
