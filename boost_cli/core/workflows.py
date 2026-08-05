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
import re
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


# Gemini validates a subagent's frontmatter with a Zod schema at load time, and
# rejects the whole FILE when any field fails — so a tap's agent written for
# another host greets the user with a validation error every session, for a
# file boost installed. These three constants are the schema, lifted from the
# shipped bundle's own validator rather than from its documentation: the docs
# name tools informally while `ALL_BUILTIN_TOOL_NAMES` resolves through
# per-tool constants (EDIT_TOOL_NAME = "replace", GREP_TOOL_NAME =
# "grep_search"), so a sanitizer written from the docs would emit a list Gemini
# rejects. tests/unit/test_gemini_agent_sanitize.py pins all three, the way
# test_mcphost.py pins the MCP grammar — when Gemini's schema moves, that test
# goes red instead of somebody's startup.
GEMINI_NAME_RE = re.compile(r"^[a-z0-9-_]+$")

#: The 13 built-ins the bundle ships, plus the one legacy alias its validator
#: still accepts (``search_file_content`` -> ``grep_search``).
GEMINI_TOOL_NAMES = frozenset({
    "activate_skill", "ask_user", "glob", "google_web_search", "grep_search",
    "list_directory", "read_file", "read_many_files", "replace",
    "run_shell_command", "web_fetch", "write_file", "write_todos"})
GEMINI_TOOL_ALIASES = frozenset({"search_file_content"})
#: Wildcards and prefixes ``isValidToolName`` accepts beyond the literal names.
GEMINI_TOOL_WILDCARDS = frozenset({"*", "mcp_*"})
GEMINI_TOOL_PREFIXES = ("discovered_tool_", "mcp_")


def _valid_gemini_tool(name: str) -> bool:
    """Mirror of the bundle's ``isValidToolName`` for the cases taps produce."""
    if name in GEMINI_TOOL_NAMES or name in GEMINI_TOOL_ALIASES:
        return True
    if name in GEMINI_TOOL_WILDCARDS:
        return True
    # `mcp_` alone is rejected by the validator; a real MCP tool name carries a
    # server and tool part after it, which we do not try to validate further.
    return any(name.startswith(p) and len(name) > len(p)
               for p in GEMINI_TOOL_PREFIXES)


def _slugify(value: str) -> str:
    """``Trojan Skill Hunter`` -> ``trojan-skill-hunter``; "" when nothing survives."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug if GEMINI_NAME_RE.match(slug) else ""


def sanitize_gemini_agent(name: str, raw: str) -> str:
    """Make a tap's subagent Markdown loadable by Gemini, body untouched.

    Three fields, three different failure modes, one rule each:

    - ``name`` must match Gemini's slug regex or the file is rejected. A
      display-style name is slugified and the original preserved in
      ``display_name``, which is the field Gemini provides for exactly that,
      so the agent still presents itself the way its author wrote it.
    - ``tools`` entries must be names Gemini knows. A list containing even one
      foreign entry is dropped WHOLE rather than filtered: keeping only the
      names that happen to collide would hand the agent a silently narrower
      toolset than its author intended, while an omitted list is Gemini's
      documented "inherit the parent session's tools". Translating Copilot's
      vocabulary into Gemini's is guesswork boost has no basis for.
    - ``model`` is the trap, because it *passes* validation — it is just a
      string — and then fails when the agent runs. Anything that is not
      ``inherit`` or a Gemini model is dropped, restoring the documented
      default.

    Everything else is left alone, including keys boost does not recognise:
    the same file may be read by another host with its own vocabulary. A file
    with no frontmatter at all is returned unchanged rather than given one.
    """
    meta, body = frontmatter.parse(raw)
    if not meta:
        return raw
    clean = dict(meta)

    declared = str(clean.get("name") or "")
    if not GEMINI_NAME_RE.match(declared):
        slug = _slugify(declared) or name
        # The install name is already a slug — it is what the file on disk is
        # called — so it is the fallback when nothing of the original survives.
        clean["name"] = slug if GEMINI_NAME_RE.match(slug) else name
        if declared and not clean.get("display_name"):
            clean["display_name"] = declared

    tools = clean.get("tools")
    if isinstance(tools, list) and not all(
            _valid_gemini_tool(str(t)) for t in tools):
        clean.pop("tools")

    model = str(clean.get("model") or "")
    if model and model != "inherit" and not model.startswith("gemini"):
        clean.pop("model")

    if clean == meta:
        return raw          # nothing to fix: byte-identical passthrough
    # `dump` ends at the closing fence and `parse` hands back the body with its
    # leading newline already consumed, so the separator has to be put back —
    # without it the fence and the first line of prose fuse into `---Body`,
    # which reads as a file with no frontmatter at all.
    return frontmatter.dump(clean) + "\n" + body


def render(agent: str | None, slot: str, name: str, raw: str) -> str:
    """The text to write for ``name`` in ``slot`` for ``agent``.

    Verbatim ``raw`` for every agent and slot except two, both Gemini's: its
    ``commands`` slot is converted to TOML by :func:`render_gemini_command`,
    and its ``agents`` slot has its frontmatter sanitized by
    :func:`sanitize_gemini_agent` — the body is still verbatim there. Pairs
    with :func:`target_ext`: the two agree on exactly which combination is
    special, so the extension and the content can never disagree.
    """
    if target_ext(agent, slot) == TOML_EXT:
        return render_gemini_command(name, raw)
    if agent in TOML_COMMAND_AGENTS and slot == SLOT_AGENTS:
        return sanitize_gemini_agent(name, raw)
    return raw
