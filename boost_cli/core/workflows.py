"""Workflow materialization: drop a command/subagent into each agent's dir.

Workflows are the easy cousin of rules. A rule has no universal home (Claude
needs a CLAUDE.md merge), but a workflow is usually just a Markdown file the
agent reads from a conventional directory:

  * a slash **command** -> the agent's ``commands/`` dir
  * a **subagent**      -> the agent's ``agents/`` dir

For most agents install is therefore a verbatim file drop. Gemini CLI is the
exception, in both slots. Its **slash commands** are TOML —
``~/.gemini/commands/<name>.toml`` carrying ``prompt`` and optional
``description`` keys. Dropping a Markdown file into that directory is not a
soft failure that degrades to something usable; the file is simply never
discovered, so the user sees an install report a command that does not exist.
Its **subagents** are Markdown with YAML frontmatter, like everyone else's, but
Gemini validates that frontmatter against a *strict* Zod schema at load time
and rejects the whole file when any field fails — so a tap's agent written for
another host greets the user with a validation error every session, for a file
boost installed. Hence :func:`render`, which converts a Markdown workflow into
Gemini's TOML for one slot and repairs the frontmatter for the other.

This module is the pure logic (which slot a workflow belongs in, where it lands
per agent, and what text goes in the file); ``store`` owns the filesystem writes
and the lock record so uninstall can reverse them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

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


# --------------------------------------------------------------------------
# Gemini subagents: the schema, lifted from the shipped bundle's own validator
# --------------------------------------------------------------------------
# Not from Gemini's documentation. The docs name tools informally while
# `ALL_BUILTIN_TOOL_NAMES` resolves through per-tool constants (EDIT_TOOL_NAME
# = "replace", GREP_TOOL_NAME = "grep_search"), so a sanitizer written from the
# docs emits a list Gemini rejects. tests/unit/test_gemini_agent_sanitize.py
# re-extracts every constant below from the installed bundle and skips when it
# is absent, the way test_mcphost.py pins the MCP grammar — when Gemini's
# schema moves, that test goes red instead of somebody's startup.
GEMINI_NAME_RE = re.compile(r"^[a-z0-9-_]+$")

#: ``ALL_BUILTIN_TOOL_NAMES`` — 27 names, not the 13 the docs list.
GEMINI_TOOL_NAMES = frozenset({
    "activate_skill", "ask_user", "complete_task", "enter_plan_mode",
    "exit_plan_mode", "get_internal_docs", "glob", "google_web_search",
    "grep_search", "invoke_agent", "list_directory", "list_mcp_resources",
    "read_file", "read_many_files", "read_mcp_resource", "replace",
    "run_shell_command", "tracker_add_dependency", "tracker_create_task",
    "tracker_get_task", "tracker_list_tasks", "tracker_update_task",
    "tracker_visualize", "update_topic", "web_fetch", "write_file",
    "write_todos"})
#: ``TOOL_LEGACY_ALIASES`` — one entry, ``search_file_content -> grep_search``.
GEMINI_TOOL_ALIASES = frozenset({"search_file_content"})

#: Foreign tool names with an EXACT Gemini counterpart, one entry per line, each
#: naming the constant it targets. This is Claude Code's vocabulary, because
#: that is what the corpus is made of: 2,362 of the tapped agent files carry a
#: ``tools`` value every entry of which resolves through this table, against 405
#: that resolve only partially. Every entry is a *rename of the same capability*
#: — nothing here grants or removes one — and a name that cannot be
#: substantiated from the two documented tool sets is deliberately ABSENT, which
#: makes its list partial, which refuses the file (see :func:`_tools_verdict`).
#: Copilot's vocabulary is mostly absent for that reason: ``codebase``,
#: ``search``, ``usages``, ``problems`` and ``githubRepo`` name IDE capabilities
#: Gemini has no counterpart for. ``Edit -> replace`` is the entry to read
#: twice: Gemini's docs call the tool "Edit" while ``EDIT_TOOL_NAME`` resolves
#: to ``replace``, so a table written from the docs emits names Gemini rejects.
GEMINI_TOOL_TRANSLATIONS = {
    "AskUserQuestion": "ask_user",
    "Bash": "run_shell_command",
    "Edit": "replace",
    "Glob": "glob",
    "Grep": "grep_search",
    "LS": "list_directory",
    "MultiEdit": "replace",
    "Read": "read_file",
    "Task": "invoke_agent",
    "TodoWrite": "write_todos",
    "WebFetch": "web_fetch",
    "WebSearch": "google_web_search",
    "Write": "write_file",
}
GEMINI_DISCOVERED_PREFIX = "discovered_tool_"
GEMINI_MCP_PREFIX = "mcp_"
#: The slug ``isValidToolName`` applies to BOTH halves of ``mcp_<server>_<tool>``.
GEMINI_MCP_SLUG_RE = re.compile(r"^[a-z0-9_.:-]+$", re.IGNORECASE)

#: ``localAgentSchema`` is ``.strict()``: any key outside these ten is a hard
#: rejection, so the Gemini copy carries these and nothing else.
GEMINI_AGENT_KEYS = frozenset({
    "kind", "name", "description", "display_name", "tools", "mcp_servers",
    "model", "temperature", "max_turns", "timeout_mins"})
#: Keys that put the file on one of the two REMOTE branches of the schema
#: union, where the local allowlist would delete what makes it valid.
GEMINI_REMOTE_KEYS = frozenset({"auth", "agent_card_url", "agent_card_json"})

_MCP_SPLIT_RE = re.compile(r"^([^_]+)_(.+)$")
_ALL_UNDERSCORES_RE = re.compile(r"^_*$")


def _valid_gemini_tool(name: str) -> bool:
    """Mirror of ``isValidToolName(name, {allowWildcards: true})``.

    The ``mcp_`` rule is the one worth reading twice: it is not "starts with
    ``mcp_`` and has something after". The remainder is split on the FIRST
    underscore and both halves are slug-checked, so the Claude/Copilot spelling
    ``mcp__server__tool`` is rejected — the old ``len(name) > len(prefix)``
    test accepted it and handed Gemini a list boost thought was fine.
    """
    if name in GEMINI_TOOL_NAMES or name in GEMINI_TOOL_ALIASES:
        return True
    if name.startswith(GEMINI_DISCOVERED_PREFIX) or name == "*":
        return True
    if not name.startswith(GEMINI_MCP_PREFIX):
        return False
    if name == GEMINI_MCP_PREFIX + "*":
        return True
    split = _MCP_SPLIT_RE.match(name[len(GEMINI_MCP_PREFIX):])
    if split is None or not GEMINI_MCP_SLUG_RE.match(split.group(1)):
        return False
    tool = split.group(2)
    if tool == "*":
        return True
    return not _ALL_UNDERSCORES_RE.match(tool) and \
        bool(GEMINI_MCP_SLUG_RE.match(tool))


def _slugify(value: str) -> str:
    """``Trojan Skill Hunter`` -> ``trojan-skill-hunter``; "" when nothing survives."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug if GEMINI_NAME_RE.match(slug) else ""


# --------------------------------------------------------------------------
# Line surgery on the frontmatter TEXT
# --------------------------------------------------------------------------
# The repair edits the specific key LINES it has a verdict on and copies every
# other byte through untouched. It deliberately does NOT parse the block into a
# dict and re-serialize it: `core.frontmatter` is a flat, best-effort reader
# with no nesting, and its `dump` quotes a scalar only when it contains ":" and
# never quotes a list item. Every other caller of `dump` feeds it meta boost
# itself built; feeding it third-party frontmatter turned 52 corpus files from
# a schema error into unparseable YAML (`color: "#EF4444"` -> `color: #EF4444`
# -> null, a bare `*` item -> "name of an alias node must contain at least one
# character") and silently altered a value in 548 more.

_SCALAR, _LIST, _OTHER = "scalar", "list", "other"
#: What :func:`_tools_verdict` may decide. There is no "drop" — see
#: :func:`_key_is_dropped` for why deleting a ``tools`` list is a widening.
_KEEP, _REWRITE, _REFUSE = "keep", "rewrite", "refuse"

_LINE_RE = re.compile(r"[^\n]*\n|[^\n]+")
_KEY_LINE_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)[ \t]*:(?:[ \t]+(.*))?$")
#: Value texts js-yaml reads as something other than a string. `name: 2024`
#: matches the slug regex and still fails `z.string()` with "received number".
_NON_STRING_RE = re.compile(
    r"^(?:true|false|null|~"
    r"|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|0[xX][0-9a-fA-F]+|0o[0-7]+)$", re.IGNORECASE)
#: A ``key:`` at column 0, for the fidelity guard's independent duplicate scan.
#: Looser than :data:`_KEY_LINE_RE` on purpose — it is not trying to model the
#: block, only to notice the same name written twice.
_COLUMN0_KEY_RE = re.compile(
    r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)[ \t]*:(?=[ \t\r\n]|$)", re.MULTILINE)
_DQ_ESCAPE_RE = re.compile(r"\\(.)", re.DOTALL)
_DQ_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "0": "\0"}
#: Characters JSON leaves raw that YAML does not allow in a plain double-quoted
#: scalar: DEL, the C1 block (which includes NEL), the two Unicode line
#: separators, and a stray BOM.
_YAML_UNPRINTABLE = re.compile(r"[\x7f-\x9f\u2028\u2029\ufeff]")


class _Key(NamedTuple):
    """One top-level frontmatter key: its name, its line span and its value text."""

    name: str
    start: int
    end: int
    value: str


class _Plan(NamedTuple):
    """The exact edit to apply to a block, plus what re-reading it must yield."""

    drop: frozenset[int]
    replace: dict[int, str]
    append: list[str]
    keys: list[str]
    values: dict[str, str | list[str]]


def _locate_frontmatter(raw: str) -> tuple[int, int] | None:
    """``(end of opening fence, start of closing fence)``, or None.

    The intersection of Gemini's ``FRONTMATTER_REGEX`` and boost's own
    :func:`frontmatter.split`, and it has to be enforced rather than assumed.
    Gemini closes the block at the first ``\\n---`` *whatever follows those
    three dashes* — a rule of dashes, ``---8<---``, a fence with a trailing
    space — while boost requires the line to BE ``---``. So the first line
    STARTING with ``---`` ends the search either way: if it is exactly ``---``
    the two agree and the span is returned; if it is not, Gemini's body starts
    where boost's block would have continued, the two disagree about which
    bytes are metadata, and the answer is None. A guess about where the body
    starts is a guess about which bytes may be rewritten.
    """
    if raw.startswith("---\r\n"):
        open_end = 5
    elif raw.startswith("---\n"):
        open_end = 4
    else:
        return None
    i = open_end
    while True:
        newline = raw.find("\n", i)
        line = raw[i:len(raw) if newline < 0 else newline].rstrip("\r")
        if line.startswith("---"):
            return (open_end, i) if line == "---" else None
        if newline < 0:
            return None
        i = newline + 1


def _lines_of(block: str) -> list[tuple[str, str]]:
    """``block`` as ``[(text, line ending)]`` — the ending is kept so CRLF survives."""
    out = []
    for chunk in _LINE_RE.findall(block):
        text = chunk.rstrip("\n").removesuffix("\r")
        out.append((text, chunk[len(text):]))
    return out


def _strip_comment(text: str) -> str:
    """``text`` up to its first unquoted ``#`` comment.

    A ``#`` only opens a comment at the start of the value or after
    whitespace, which is what lets ``color: #EF4444`` be a null value and
    ``tools: [a] # was [b]`` be a one-line flow list rather than an
    unterminated one.
    """
    quote, prev = "", ""
    for i, ch in enumerate(text):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and prev in ("", " ", "\t"):
            return text[:i]
        prev = ch
    return text


def _flow_delta(text: str) -> int:
    """Net ``[{`` minus ``]}`` in ``text``, ignoring quoted spans and comments.

    A raw count, and only meaningful for a line already known to be INSIDE a
    flow collection. Whether a key's value opens one at all is
    :func:`_flow_opens` — a question this function cannot answer, because the
    same characters are ordinary text in a plain scalar.
    """
    depth, quote = 0, ""
    for ch in _strip_comment(text):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth


def _flow_opens(value: str) -> bool:
    """Whether a key's inline ``value`` genuinely starts a flow collection.

    YAML forbids ``[`` and ``{`` only as the FIRST character of a plain
    scalar; inside one they are ordinary text, so ``description: Wrap it in {
    braces`` is a one-line plain scalar and ``model: opus]`` is the string
    "opus]". Counting those characters regardless made :func:`_span_end`
    consume following lines until the count balanced, which hid the keys in
    that span from :func:`_scan_keys` — and a hidden ``name`` is one
    :func:`_plan` appends a SECOND copy of, turning a file Gemini loads into
    "duplicated mapping key". Only a value that opens a collection can span
    lines; every other value's span is decided by indentation alone.
    """
    return _strip_comment(value).lstrip()[:1] in ("[", "{")


def _span_end(lines: list[tuple[str, str]], start: int, value: str) -> int | None:
    """Index just past the key at ``start``, continuation lines included.

    Three kinds of continuation: the rest of a flow collection the key line
    genuinely OPENED (:func:`_flow_opens`, not merely a value containing a
    bracket), every following line indented deeper than the key (nested
    mapping, folded or literal block scalar, indented list items), and — only
    when the key line carried no inline value — block-sequence items at the
    key's OWN indent, which is legal YAML and the shape 312 corpus files use
    (``tools:`` then ``- Read`` in column 0).

    Trailing blank lines are excluded so deleting a key cannot swallow the
    blank line before the next one. None means an unterminated flow collection
    — nothing to edit around.

    An indent-0 continuation of a plain *scalar* is deliberately NOT a
    continuation: js-yaml rejects it outright ("a multiline key may not be an
    implicit key"), so those 330 files have invalid source YAML and no key
    surgery can rescue them. :func:`_scan_keys` refuses them instead.
    """
    inline = _strip_comment(value).strip()
    depth = _flow_delta(value) if _flow_opens(value) else 0
    i = start + 1
    while depth > 0:
        if i >= len(lines):
            return None
        depth += _flow_delta(lines[i][0])
        i += 1
    end = i
    opens_sequence = not inline
    while i < len(lines):
        text = lines[i][0]
        if text.strip() and text[:1] not in (" ", "\t") and not (
                opens_sequence and (text == "-" or text.startswith("- "))):
            break
        i += 1
        if text.strip():
            end = i
    return end


def _scan_keys(lines: list[tuple[str, str]]) -> list[_Key] | None:
    """Top-level keys in order, or None when the block is not ours to edit.

    None covers everything the line model cannot represent: an indented line
    with no key above it, a top-level sequence item (which routes Gemini to
    ``remoteAgentsListSchema``, a different shape entirely), an explicit
    ``? key``, a quoted key, a ``%YAML`` directive, an unterminated flow
    collection. Callers hand the file back untouched.
    """
    keys: list[_Key] = []
    i = 0
    while i < len(lines):
        text = lines[i][0]
        if not text.strip() or text.lstrip().startswith("#"):
            i += 1
            continue
        if text[:1] in (" ", "\t"):
            return None
        match = _KEY_LINE_RE.match(text)
        if match is None:
            return None
        end = _span_end(lines, i, match.group(2) or "")
        if end is None:
            return None
        keys.append(_Key(match.group(1), i, end, match.group(2) or ""))
        i = end
    return keys


def _is_quoted(text: str) -> bool:
    """Whether a value's source text is a quoted scalar (so already a string)."""
    s = text.strip()
    return len(s) >= 2 and s[0] == s[-1] and s[0] in "'\""


def _scalar_text(text: str) -> str:
    """A YAML scalar's source text -> its string value, for the shapes taps write."""
    s = text.strip()
    if _is_quoted(s):
        if s[0] == "'":
            return s[1:-1].replace("''", "'")
        return _DQ_ESCAPE_RE.sub(
            lambda m: _DQ_ESCAPES.get(m.group(1), m.group(1)), s[1:-1])
    return s.split(" #", 1)[0].rstrip()


def _split_flow(inner: str) -> list[str]:
    """Split a one-line flow sequence's interior on commas, quote-aware."""
    parts, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            buf += ch
            quote = ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p.strip()]


def _read_value(lines: list[tuple[str, str]], key: _Key) -> tuple[str, str, list[str]]:
    """``(shape, scalar text, list items)`` for one key's span.

    ``_OTHER`` is never a guess — it is the answer for every construct this
    module refuses to interpret from text alone (a nested mapping, a block
    scalar, an anchor or alias, a flow list that does not close on its own
    line). Callers either delete the whole span or hand the file back; nothing
    downstream ever acts on a value we could not read.
    """
    text = _strip_comment(key.value).strip()
    body = [lines[i][0] for i in range(key.start + 1, key.end)
            if lines[i][0].strip()]
    if text.startswith("["):
        if key.end != key.start + 1 or not text.endswith("]"):
            return _OTHER, "", []
        return _LIST, "", [_scalar_text(p) for p in _split_flow(text[1:-1])]
    if text[:1] in ("&", "*", "!", "{", "|", ">", "?"):
        return _OTHER, "", []
    if not text:
        items = [_scalar_text(ln.strip()[1:]) for ln in body
                 if ln.strip() == "-" or ln.strip().startswith("- ")]
        if len(items) != len(body):
            return _OTHER, "", []
        return (_LIST, "", items) if items else (_SCALAR, "", [])
    if body:
        return _OTHER, "", []           # folded continuation of a plain scalar
    return _SCALAR, _scalar_text(text), []


def _yaml_str(text: str) -> str:
    """``text`` as a double-quoted YAML scalar, valid for ANY input.

    Every escape ``json.dumps`` emits is also a YAML double-quoted escape, so a
    JSON string literal is a valid YAML one — the same subset trick
    :func:`_toml_str` uses for TOML. The second pass covers the few characters
    JSON passes through raw that YAML forbids bare.
    """
    return _YAML_UNPRINTABLE.sub(
        lambda m: "\\u%04x" % ord(m.group()),
        json.dumps(text, ensure_ascii=False))


#: Claude/Copilot spellings of "the tools this agent may use". Gemini has no
#: such key, so the strict-key rule deletes them — and a file whose ONLY grant
#: was written here then loads with no `tools` at all, which is Gemini's
#: "inherit the parent session's tools". Measured against the shipped loader:
#: 47 corpus files widened exactly this way, 4 of them gaining a shell tool
#: their author never granted. Same defect `_tools_verdict` exists to prevent,
#: arriving under a different key name.
GEMINI_ALLOW_KEYS = ("allowedTools", "allowed-tools", "allowed_tools")

#: And the deny spellings. These are the harder half: "everything except X" has
#: no Gemini form at all, so it is only expressible when an allow list exists to
#: subtract from. Deleting one always widens — by the denied names when a list
#: bounds them (331 corpus files), and to EVERYTHING when none does (18).
GEMINI_DENY_KEYS = ("disallowedTools", "disallowed-tools", "disallowed_tools")


def _grant_key(seen: dict[str, _Key], names: tuple[str, ...]) -> _Key | None:
    """The first of ``names`` present, in the order they are spelled above."""
    for name in names:
        if name in seen:
            return seen[name]
    return None


def _key_is_dropped(lines: list[tuple[str, str]], key: _Key) -> bool:
    """Whether this key's whole span has to go.

    Two rules, one per failure mode:

    - anything outside :data:`GEMINI_AGENT_KEYS`, because the schema is
      ``.strict()`` and an unknown key rejects the file outright;
    - a ``model`` that is neither ``inherit`` nor a Gemini model. This one is
      the odd rule out: ``model`` is ``z.string().optional()``, so it cannot
      fail LOAD — it passes validation and then fails at invocation, where the
      user has no reason to connect it to a file boost installed.

    ``tools`` is conspicuously NOT here, and used to be. Deleting it is a
    privilege WIDENING, not a narrowing: an omitted ``tools`` is Gemini's
    documented "inherit the parent session's tools", ``run_shell_command``
    included, so dropping a list its author wrote grants the agent tools it
    was never given. :func:`_tools_verdict` decides that key instead, and can
    only keep, translate, or refuse the file.
    """
    if key.name not in GEMINI_AGENT_KEYS:
        return True
    if key.name == "model":
        shape, text, _items = _read_value(lines, key)
        return shape != _SCALAR or not (
            text == "inherit" or text.startswith("gemini"))
    return False


def _tools_entries(lines: list[tuple[str, str]],
                   key: _Key) -> tuple[list[str], bool] | None:
    """``(names, already a YAML sequence)`` for a ``tools`` value, or None.

    Two readable shapes: a YAML sequence, and the plain string
    ``Read, Grep, Bash`` — Claude Code's own documented spelling, which Gemini
    rejects with "Expected array, received string" and which 1,460 corpus
    files use. Everything else (a null value, a nested mapping, a block
    scalar, an anchor, a tag, a flow list that does not close on its own line)
    is None, because a value that cannot be read is one whose grant cannot be
    preserved — and refusing the file is the only move that neither widens nor
    narrows it.
    """
    shape, text, items = _read_value(lines, key)
    if shape == _LIST:
        return items, True
    if shape == _SCALAR and text:
        return [part.strip() for part in text.split(",") if part.strip()], False
    return None


def _tools_verdict(lines: list[tuple[str, str]],
                   key: _Key) -> tuple[str, list[str]]:
    """``(verdict, translated names)`` for a ``tools`` key.

    Three outcomes, in order:

    - :data:`_KEEP` — already a sequence of names Gemini accepts, so the tap's
      own bytes stand (wildcards, quoting and all);
    - :data:`_REWRITE` — every entry resolves, through
      :data:`GEMINI_TOOL_TRANSLATIONS` or by already being valid, so the line
      is re-emitted in Gemini's vocabulary. The names dedupe (``Edit`` and
      ``MultiEdit`` are both ``replace``) because the set of capabilities is
      what has to survive, not the arity of the list;
    - :data:`_REFUSE` — the value is unreadable, or the map is only PARTIAL.
      Translating the entries that happen to resolve would silently narrow the
      agent's grant, exactly as dropping the list silently widens it. The file
      goes back unedited and keeps failing with the tap's own error, which is
      the one outcome the user can act on.
    """
    read = _tools_entries(lines, key)
    if read is None:
        return _REFUSE, []
    names, is_sequence = read
    if is_sequence and all(_valid_gemini_tool(t) for t in names):
        return _KEEP, []
    out: list[str] = []
    for name in names:
        target = GEMINI_TOOL_TRANSLATIONS.get(
            name, name if _valid_gemini_tool(name) else "")
        if not target:
            return _REFUSE, []
        if target not in out:
            out.append(target)
    return _REWRITE, out


def _plan(install: str, lines: list[tuple[str, str]],
          keys: list[_Key]) -> _Plan | None:
    """The edit to make, or None for "hand this file back untouched"."""
    seen = {key.name: key for key in keys}
    if len(seen) != len(keys):
        return None                     # duplicate top-level key: js-yaml takes
                                        # the last; we decline to pick for it
    if not GEMINI_REMOTE_KEYS.isdisjoint(seen):
        return None
    if "kind" in seen and _read_value(lines, seen["kind"])[:2] != (_SCALAR, "local"):
        return None
    if "description" not in seen:
        return None
    shape, text, _items = _read_value(lines, seen["description"])
    if shape == _SCALAR and not text:
        return None

    drop = {i for key in keys if _key_is_dropped(lines, key)
            for i in range(key.start, key.end)}
    replace: dict[int, str] = {}
    append: list[str] = []
    values: dict[str, str | list[str]] = {}

    # The agent's tool grant, wherever its author wrote it. `tools` is Gemini's
    # own key; the Claude/Copilot allow spellings mean the same thing and would
    # otherwise be deleted by the strict-key rule, leaving the agent inheriting
    # everything. A deny list has no Gemini form on its own, so it is only
    # honoured by SUBTRACTING it from an allow list — and a file that denies
    # without allowing is refused rather than silently un-denied.
    tools_key = seen.get("tools") or _grant_key(seen, GEMINI_ALLOW_KEYS)
    deny_key = _grant_key(seen, GEMINI_DENY_KEYS)
    if tools_key is None and deny_key is not None:
        return None
    if tools_key is not None:
        verdict, tools = _tools_verdict(lines, tools_key)
        if verdict == _REFUSE:
            return None
        if verdict == _KEEP and (deny_key is not None
                                 or tools_key.name != "tools"):
            # A grant we would otherwise have left byte-identical still has to
            # be re-emitted when it is moving key, or losing denied names.
            read = _tools_entries(lines, tools_key)
            if read is None:
                return None
            tools, verdict = list(read[0]), _REWRITE
        if verdict == _REWRITE and deny_key is not None:
            denied = _tools_entries(lines, deny_key)
            if denied is None:
                return None     # a deny we cannot read is one we cannot honour
            blocked = {GEMINI_TOOL_TRANSLATIONS.get(d, d) for d in denied[0]}
            tools = [t for t in tools if t not in blocked]
        if verdict == _REWRITE:
            replace[tools_key.start] = "tools: [%s]" % ", ".join(
                _yaml_str(t) for t in tools)
            # An allow-spelling is ALSO in the strict-key drop set, since it is
            # not one of Gemini's ten. Reclaim its first line — that is the one
            # the grant is re-emitted on — and drop the remainder of its span.
            drop -= {tools_key.start}
            drop |= set(range(tools_key.start + 1, tools_key.end))
            values["tools"] = tools

    name_key = seen.get("name")
    declared = ""
    if name_key is not None:
        shape, declared, _items = _read_value(lines, name_key)
        if shape != _SCALAR:
            return None                 # a name we cannot read is one we cannot repair
    quoted = name_key is not None and _is_quoted(_strip_comment(name_key.value))
    if not GEMINI_NAME_RE.match(declared) or (
            not quoted and _NON_STRING_RE.match(declared)):
        slug = _slugify(declared) or _slugify(install)
        if not slug:
            return None                 # nothing to build a valid slug out of
        values["name"] = slug
        line = "name: " + _yaml_str(slug)
        if name_key is None:
            append.append(line)
        else:
            replace[name_key.start] = line
        if declared and declared != slug and "display_name" not in seen:
            values["display_name"] = declared
            append.append("display_name: " + _yaml_str(declared))

    if not (drop or replace or append):
        return None
    # Read the surviving name off the REPLACEMENT line, not off the input key:
    # a grant written as `allowedTools` is re-emitted as `tools`, so the input
    # name would describe a key the output does not have and the fidelity guard
    # would reject a correct edit.
    out_keys = [replace[key.start].split(":", 1)[0] if key.start in replace
                else key.name
                for key in keys if key.start not in drop]
    out_keys += [line.split(":", 1)[0] for line in append]
    return _Plan(frozenset(drop), replace, append, out_keys, values)


def _rebuild(lines: list[tuple[str, str]], plan: _Plan) -> str:
    """The edited block. Every line the plan does not name keeps its own bytes."""
    eol = lines[-1][1] or "\n"
    out = [(plan.replace.get(i, text), end)
           for i, (text, end) in enumerate(lines) if i not in plan.drop]
    out += [(line, eol) for line in plan.append]
    return "".join(text + end for text, end in out)


def _duplicated_column0_key(block: str) -> bool:
    """Whether any ``key:`` at column 0 of ``block`` appears more than once.

    Deliberately a SECOND reader, and a dumb one: a flat regex with no notion
    of spans, continuations or value shapes. That is the whole point — it can
    disagree with :func:`_scan_keys`, which is what makes it able to catch a
    mistake :func:`_scan_keys` made. js-yaml refuses a duplicated mapping key
    outright, so this is the exact shape of corruption an appended key
    produces when the scanner never saw the one already there.
    """
    names = _COLUMN0_KEY_RE.findall(block)
    return len(names) != len(set(names))


def _verify_output(raw: str, out: str, span: tuple[int, int],
                   want_keys: list[str],
                   want_values: dict[str, str | list[str]]) -> bool:
    """Whether ``out`` is exactly the edit we intended, and nothing else.

    Four checks, and it is worth being precise about which of them can catch
    what — the previous version of this docstring was not, and the bug it
    missed was the one that shipped:

    - the fence must sit where it did and the bytes outside the block must be
      the same slice of ``raw`` — a raw comparison, independent of every
      reader in this module, so it catches a body that moved;
    - **no key may appear twice at column 0** (:func:`_duplicated_column0_key`)
      — also independent, and the one check that survives a mis-PARSE: when
      the reader misjudges where a value ends, the keys it swallowed are
      invisible to the plan AND to the re-read, so appending one of them again
      looks perfectly consistent to both;
    - the surviving keys must be the ones we meant to survive, and each value
      we wrote must read back as written — these two re-read ``out`` with
      ``_scan_keys`` and ``_read_value``, *the same model that built the
      edit*. They catch a mis-EDIT (wrong lines deleted, a value that does not
      round-trip) and are structurally blind to a mis-PARSE, because intent
      and observation then agree on the same wrong answer.

    A deeper oracle would mean a YAML parser, which the CLI does not ship;
    ``tests/unit/test_gemini_agent_sanitize.py`` runs one (PyYAML, with
    duplicate keys made fatal) over every shape, gated on its presence.

    If any check fails the caller returns ``raw``: corrupting a file is
    strictly worse than leaving it broken, because the user can act on the
    tap's own error message and cannot act on boost's damage.
    """
    found = _locate_frontmatter(out)
    if found is None:
        return False
    if out[:found[0]] != raw[:span[0]] or out[found[1]:] != raw[span[1]:]:
        return False
    block = out[found[0]:found[1]]
    if _duplicated_column0_key(block):
        return False
    lines = _lines_of(block)
    keys = _scan_keys(lines)
    if not keys or [key.name for key in keys] != want_keys:
        return False
    seen = {key.name: key for key in keys}
    return all(_value_reads_back(lines, seen[name], want)
               for name, want in want_values.items())


def _value_reads_back(lines: list[tuple[str, str]], key: _Key,
                      want: str | list[str]) -> bool:
    """Whether ``key``'s value re-reads as the scalar or list we wrote."""
    shape, text, items = _read_value(lines, key)
    if isinstance(want, list):
        return shape == _LIST and items == want
    return (shape, text) == (_SCALAR, want)


def _sanitize_once(name: str, raw: str) -> str:
    """One repair pass: ``raw`` edited, or ``raw`` itself when we decline."""
    span = _locate_frontmatter(raw)
    if span is None:
        return raw
    lines = _lines_of(raw[span[0]:span[1]])
    keys = _scan_keys(lines)
    if not keys:
        return raw
    plan = _plan(name, lines, keys)
    if plan is None:
        return raw
    out = raw[:span[0]] + _rebuild(lines, plan) + raw[span[1]:]
    return out if _verify_output(raw, out, span, plan.keys, plan.values) else raw


def sanitize_gemini_agent(name: str, raw: str) -> str:
    """Make a tap's subagent Markdown loadable by Gemini, body byte-identical.

    Four rules, applied to the frontmatter TEXT (see :func:`_key_is_dropped`
    and :func:`_tools_verdict` for each rule and why it exists):

    - every key outside :data:`GEMINI_AGENT_KEYS` is deleted, span and all,
      because ``localAgentSchema`` is ``.strict()``. This is safe *because it
      is the Gemini copy*: ``store.render`` runs once per enabled agent and
      writes four separate regular files, so ``~/.gemini/agents/<x>.md`` is
      read by Gemini and by nothing else. Claude, Cursor and Windsurf still get
      the tap's bytes verbatim, keys boost has never heard of included.
    - ``tools`` is kept when Gemini already accepts it, translated when every
      entry has an exact Gemini counterpart, and otherwise the whole FILE is
      refused. It is never deleted: an omitted ``tools`` is Gemini's
      documented "inherit the parent session's tools", so dropping the list
      would widen the agent's grant rather than narrow it.
    - ``model`` must be ``inherit`` or a Gemini model, or it goes.
    - ``name`` must be a *string* matching Gemini's slug regex. A display-style
      name is slugified and the original preserved in ``display_name``, the
      field Gemini provides for exactly that. A slug-shaped name that js-yaml
      would read as a number or a bool (``name: 2024``) is re-emitted quoted.

    **A missing or empty ``description`` means hands off.** It is
    ``z.string().min(1)`` — required — and no metadata surgery can supply one.
    boost will not invent it: a subagent's description is what the dispatcher
    reads to decide when to delegate, so a fabricated line would not fix the
    file, it would make boost responsible for a routing decision the author
    never wrote, and a wrong description fails silently where an absent one
    fails at load. Those files are returned byte-identical (6 of 5,005 in the
    tapped corpus), as are remote agents, duplicated keys, and every construct
    :func:`_scan_keys` and :func:`_read_value` decline to interpret.

    The result is verified before it is returned (:func:`_verify_output`) and
    then required to be a fixed point — ``sanitize(sanitize(x)) ==
    sanitize(x)`` — so a repair that would need a second pass to settle is
    refused instead. A renderer that does not settle makes ``boost sync``
    rewrite files that never changed.
    """
    out = _sanitize_once(name, raw)
    if out == raw:
        return raw
    return out if _sanitize_once(name, out) == out else raw


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
