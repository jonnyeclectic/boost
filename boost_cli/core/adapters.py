# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Render a boost skill into another agent framework's native source.

boost installs skills as files for editor-style agents (Claude Code, Cursor,
Windsurf). Frameworks like CrewAI or the OpenAI Agents SDK are *application
code* — they have no skills directory to install into; an agent is a value
constructed in a Python source file. `boost adapt <name> --to <framework>`
bridges that gap by emitting the framework's own idiom.

Each renderer is a pure, deterministic string transform: (name, description,
body) -> valid Python source. No framework is imported here — the emitted text
is a template, so the stdlib-only, zero-dependency runtime contract holds. The
generated code's *validity* is what the tests pin (it must `compile()`); whether
a given framework version accepts the kwargs is verified out-of-gate, with that
framework installed.
"""
from __future__ import annotations

import collections
import json
import keyword
import re
from collections.abc import Callable
from pathlib import Path

from . import frontmatter

# Public: the format id shown in `--to`/errors -> its renderer.
# Populated at the bottom once the render_* functions are defined.
FORMATS: dict[str, Callable[..., str]] = {}

# Subagent (crew member) directories: a Markdown file under one of these, at any
# depth beneath a skill, is one of the skill's subagents — so both a flat
# `agents/reviewer.md` and a plugin-style `plugins/x/agents/reviewer.md` match.
SUBAGENT_DIRS = {"agents", "subagents"}
# Frontmatter keys a skill/subagent uses to declare the tools it can call.
_TOOL_KEYS = ("tools", "allowed-tools", "allowed_tools")

# One agent in a (possibly multi-agent) skill: its display name, one-line
# description/role, full instruction body, and declared tool identifiers. Built
# via collections.namedtuple (an assignment, so interrogate needs no docstring)
# rather than a NamedTuple subclass.
AgentSpec = collections.namedtuple("AgentSpec",
                                   "name description instructions tools")


def formats() -> list[str]:
    """Sorted list of supported target framework ids (for help/errors)."""
    return sorted(FORMATS)


def render(fmt: str, name: str, description: str, body: str,
           model: str | None = None) -> str:
    """Dispatch to the renderer for `fmt`. Raises KeyError on unknown fmt.

    `model` (a boost/LiteLLM model id) wires the emitted agent to a specific
    LLM; when falsy the agent inherits its framework's default provider. The
    command layer turns a KeyError into a BoostError listing formats().
    """
    return FORMATS[fmt](name, description, body, model)


# --- shared helpers -------------------------------------------------------

def _py_str(s: str) -> str:
    """A safely-escaped Python string literal for ANY input.

    JSON string syntax is a subset of Python's, so json.dumps yields a literal
    that is valid Python too — quotes, backslashes and newlines all escaped —
    with ensure_ascii=False keeping non-ASCII readable (and still valid). This
    is the whole defense against a skill body that contains quotes or `\"\"\"`.
    """
    return json.dumps(s, ensure_ascii=False)


def _ident(name: str) -> str:
    """A safe Python identifier derived from a skill name.

    `code-reviewer` -> `code_reviewer`; leading digits or a Python keyword get
    an `s_` prefix so the emitted assignment target always parses.
    """
    ident = re.sub(r"\W+", "_", name.strip().lower()).strip("_")
    if not ident or ident[0].isdigit() or keyword.iskeyword(ident):
        ident = "s_" + ident
    return ident


def _clean(text: str) -> str:
    """Collapse trailing whitespace so emitted literals stay tidy."""
    return text.strip()


def _litellm_model(model: str) -> str:
    """Normalize a boost model id to a LiteLLM `provider/model` string.

    boost's AI bridge is Anthropic (the `claude` CLI / Anthropic API), so a bare
    Claude id like `claude-haiku-4-5-20251001` gets an `anthropic/` prefix.
    A value that already names a provider (`anthropic/…`, `openai/gpt-4o`) is
    passed through unchanged. Both CrewAI and the Agents SDK route through
    LiteLLM, so this one form serves both.
    """
    m = model.strip()
    return m if "/" in m else "anthropic/" + m


def _langchain_model(model: str) -> str:
    """Normalize a boost model id to a LangChain ``init_chat_model`` string.

    LangGraph's ``create_react_agent`` builds its model via LangChain's
    ``init_chat_model``, which wants ``provider:model`` (colon) — not LiteLLM's
    ``provider/model`` (slash). A bare Claude id gets ``anthropic:``; a
    litellm-style ``anthropic/x`` becomes ``anthropic:x``; a value that already
    uses the colon form passes through.
    """
    m = model.strip()
    if ":" in m:
        return m
    if "/" in m:
        return m.replace("/", ":", 1)
    return "anthropic:" + m


# --- multi-agent detection ------------------------------------------------

def parse_tools(meta: dict) -> list[str]:
    """Tool identifiers a skill/subagent declares in its frontmatter.

    Reads the first present of the ``tools`` / ``allowed-tools`` keys — either a
    YAML list or a comma/space-separated string — normalizes each entry to a
    safe Python identifier via :func:`_ident`, and dedupes preserving first-seen
    order. Returns ``[]`` for a skill that declares no tools (the flat case).
    """
    raw = None
    for key in _TOOL_KEYS:
        if meta.get(key):
            raw = meta[key]
            break
    if raw is None:
        return []
    parts = re.split(r"[,\s]+", raw.strip()) if isinstance(raw, str) else [str(x) for x in raw]
    seen: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        ident = _ident(part)
        # `s_` is _ident's sentinel for a token with no usable characters (e.g.
        # all punctuation) — not a real tool, so drop it.
        if not ident or ident == "s_":
            continue
        if ident not in seen:
            seen.append(ident)
    return seen


def discover_subagents(skill_dir: Path, own_file: Path | None = None) -> list[AgentSpec]:
    """Discover a skill's subagents for multi-agent adaptation.

    A subagent is a Markdown file (other than ``SKILL.md`` or ``own_file``,
    the entry being adapted) that lives under an ``agents/`` or ``subagents/``
    directory strictly beneath ``skill_dir`` — not ``skill_dir`` itself, so a
    flat item whose own directory happens to be shared (a registry-wide
    ``agents/`` folder holding one Markdown file per workflow) never treats
    its siblings as subagents — and carries both a frontmatter ``name`` and
    ``description``. Files are visited in sorted path order so the emitted
    crew/graph is deterministic. Returns the subagents as :class:`AgentSpec`s
    — an empty list for a flat single-agent skill or a missing directory.
    """
    specs: list[AgentSpec] = []
    if not skill_dir or not skill_dir.is_dir():
        return specs
    for path in sorted(skill_dir.rglob("*.md")):
        if path.name == "SKILL.md" or path == own_file:
            continue
        rel_dirs = {part.lower() for part in path.relative_to(skill_dir).parts[:-1]}
        if not (SUBAGENT_DIRS & rel_dirs):
            continue
        try:
            meta, body = frontmatter.parse(
                path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        name = str(meta.get("name") or "").strip()
        description = str(meta.get("description") or "").strip()
        if not name or not description:
            continue
        specs.append(AgentSpec(name, description, _clean(body), parse_tools(meta)))
    return specs


def _unique_idents(specs: list[AgentSpec]) -> list[str]:
    """A unique Python identifier per spec, in order — two agents whose names
    normalize to the same ident get numeric suffixes so emitted assignments and
    node names never collide."""
    counts: dict[str, int] = {}
    idents: list[str] = []
    for spec in specs:
        base = _ident(spec.name)
        if base in counts:
            counts[base] += 1
            idents.append("%s_%d" % (base, counts[base]))
        else:
            counts[base] = 0
            idents.append(base)
    return idents


def _unique_tools(specs: list[AgentSpec]) -> list[str]:
    """Union of every spec's declared tools, first-seen order preserved."""
    seen: list[str] = []
    for spec in specs:
        for tool in spec.tools:
            if tool not in seen:
                seen.append(tool)
    return seen


# --- renderers ------------------------------------------------------------

def render_crewai(name: str, description: str, body: str,
                  model: str | None = None) -> str:
    """A CrewAI Agent: role=name, goal=description, backstory=instructions.

    With `model`, pins the agent's LLM via `crewai.LLM` (LiteLLM under the
    hood); without it, the agent uses CrewAI's default provider.
    """
    var = _ident(name)
    imports = "from crewai import Agent\n"
    llm = ""
    if model:
        imports = "from crewai import Agent, LLM\n"
        llm = "    llm=LLM(model=%s),\n" % _py_str(_litellm_model(model))
    return (
        "# Generated by `boost adapt %s --to crewai`. Do not edit by hand.\n"
        "%s"
        "\n"
        "%s = Agent(\n"
        "    role=%s,\n"
        "    goal=%s,\n"
        "    backstory=%s,\n"
        "%s"
        ")\n"
    ) % (
        name,
        imports,
        var,
        _py_str(name),
        _py_str(_clean(description)),
        _py_str(_clean(body)),
        llm,
    )


def render_agents_sdk(name: str, description: str, body: str,
                      model: str | None = None) -> str:
    """An OpenAI Agents SDK Agent: instructions carry the skill body.

    With `model`, pins the agent's LLM via the SDK's LiteLLM extension
    (`pip install "openai-agents[litellm]"`); without it, the agent uses the
    SDK's default OpenAI model.
    """
    var = _ident(name)
    imports = "from agents import Agent\n"
    llm = ""
    if model:
        imports = ("from agents import Agent\n"
                   "from agents.extensions.models.litellm_model import LitellmModel\n")
        llm = "    model=LitellmModel(model=%s),\n" % _py_str(_litellm_model(model))
    return (
        "# Generated by `boost adapt %s --to agents-sdk`. Do not edit by hand.\n"
        "%s"
        "\n"
        "%s = Agent(\n"
        "    name=%s,\n"
        "    handoff_description=%s,\n"
        "    instructions=%s,\n"
        "%s"
        ")\n"
    ) % (
        name,
        imports,
        var,
        _py_str(name),
        _py_str(_clean(description)),
        _py_str(_clean(body)),
        llm,
    )


def render_langgraph(name: str, description: str, body: str,
                     model: str | None = None) -> str:
    """A LangGraph node factory: prebuilt ``create_react_agent`` bound to the
    skill body as its system prompt.

    Unlike CrewAI / the Agents SDK, a LangGraph agent isn't one constructor —
    it's a node compiled with a model and dropped into a ``StateGraph``. So we
    emit a *factory* (``make_<name>``) the caller invokes with a model and any
    tools, rather than a module-level value. With `model`, the factory's
    ``model`` argument defaults to the normalized LiteLLM id; without it, the
    caller must supply one (LangGraph has no default provider to inherit).
    """
    var = _ident(name)
    if model:
        sig = "model=%s, tools=None" % _py_str(_langchain_model(model))
    else:
        sig = "model, tools=None"
    return (
        "# Generated by `boost adapt %s --to langgraph`. Do not edit by hand.\n"
        "from langgraph.prebuilt import create_react_agent\n"
        "\n"
        "SYSTEM_PROMPT = %s\n"
        "\n"
        "\n"
        "def make_%s(%s):\n"
        "    %s\n"
        "    return create_react_agent(model, tools=tools or [], prompt=SYSTEM_PROMPT)\n"
    ) % (
        name,
        _py_str(_clean(body)),
        var,
        sig,
        _py_str(_clean(description)),
    )


FORMATS.update({
    "crewai": render_crewai,
    "agents-sdk": render_agents_sdk,
    "langgraph": render_langgraph,
})


# --- multi-agent renderers (crew / graph) ---------------------------------
# A flat skill projects to one Agent (above); a skill that declares subagents
# projects to a runnable *workflow* — a CrewAI Crew or a LangGraph StateGraph —
# with one agent per subagent and declared tools surfaced as stubs. Same
# contract as the single-agent renderers: pure text that must ``compile()``.

def _tool_stub(tool: str, decorator: str) -> str:
    """One tool stub — a decorated function that raises until implemented.

    ``decorator`` is the full decorator line (``@tool`` for LangChain,
    ``@tool("name")`` for CrewAI); the body is a docstring plus a
    ``NotImplementedError`` so the generated module ``compile()``s and fails
    loudly rather than silently no-op'ing if run before the tool is filled in.
    """
    return (
        "%s\n"
        "def %s(argument: str) -> str:\n"
        "    %s\n"
        "    raise NotImplementedError(%s)\n"
    ) % (decorator, tool,
         _py_str("TODO: implement the %s tool (declared by the skill)." % tool),
         _py_str("boost adapt: implement the '%s' tool" % tool))


def _crew_header(kind: str, workflow: str, description: str) -> str:
    """The two-line generated-file banner (provenance + crew description)."""
    summary = _clean(description).replace("\n", " ") or workflow
    return ("# Generated by `boost adapt %s --to %s`. Do not edit by hand.\n"
            "# %s\n") % (workflow, kind, summary)


def render_crew(workflow: str, description: str, specs: list[AgentSpec],
                model: str | None = None) -> str:
    """Render a multi-agent skill as a CrewAI ``Crew``.

    Each :class:`AgentSpec` becomes an ``Agent`` (role / goal / backstory) paired
    with a ``Task``, assembled into a sequential ``Crew``. Tools any agent
    declares are surfaced as ``NotImplementedError`` stubs to fill in. `model`
    pins every agent's LLM via ``crewai.LLM``; without it CrewAI's default
    provider is used. ``description`` documents the crew as a whole.
    """
    idents = _unique_idents(specs)
    tools = _unique_tools(specs)
    imports = ["from crewai import Agent, Crew, Process, Task" + (", LLM" if model else "")]
    if tools:
        imports.append("from crewai.tools import tool")
    llm_line = "    llm=LLM(model=%s),\n" % _py_str(_litellm_model(model)) if model else ""

    blocks: list[str] = []
    for ident, spec in zip(idents, specs, strict=True):
        tline = "    tools=[%s],\n" % ", ".join(spec.tools) if spec.tools else ""
        blocks.append(
            "%s = Agent(\n"
            "    role=%s,\n"
            "    goal=%s,\n"
            "    backstory=%s,\n"
            "%s%s"
            ")\n" % (ident, _py_str(_clean(spec.name)),
                     _py_str(_clean(spec.description)),
                     _py_str(_clean(spec.instructions)), tline, llm_line))
    for ident, spec in zip(idents, specs, strict=True):
        blocks.append(
            "%s_task = Task(\n"
            "    description=%s,\n"
            "    expected_output=%s,\n"
            "    agent=%s,\n"
            ")\n" % (ident, _py_str(_clean(spec.description)),
                     _py_str("The result of the %s step." % _clean(spec.name)), ident))
    crew = ("crew = Crew(\n"
            "    agents=[%s],\n"
            "    tasks=[%s],\n"
            "    process=Process.sequential,\n"
            ")\n") % (", ".join(idents), ", ".join(i + "_task" for i in idents))

    parts = [_crew_header("crewai", workflow, description), "\n".join(imports) + "\n", "\n"]
    if tools:
        parts.extend(("\n".join(_tool_stub(t, "@tool(%s)" % _py_str(t)) for t in tools), "\n"))
    parts.extend(("\n".join(blocks), "\n" + crew))
    return "".join(parts)


def render_graph(workflow: str, description: str, specs: list[AgentSpec],
                 model: str | None = None) -> str:
    """Render a multi-agent skill as a LangGraph ``StateGraph``.

    Emits a ``build_<workflow>(model)`` factory that constructs one
    ``create_react_agent`` node per :class:`AgentSpec`, wires them into a
    sequential graph (``START`` → … → ``END``) over ``MessagesState``, and
    returns the compiled graph. Declared tools become ``@tool`` stubs. With
    `model` the factory's ``model`` argument defaults to the normalized LangChain
    id; without it the caller must supply one (LangGraph has no default
    provider). ``description`` documents the graph.
    """
    idents = _unique_idents(specs)
    tools = _unique_tools(specs)
    imports = ["from langgraph.graph import END, START, MessagesState, StateGraph",
               "from langgraph.prebuilt import create_react_agent"]
    if tools:
        imports.append("from langchain_core.tools import tool")
    sig = "model=%s" % _py_str(_langchain_model(model)) if model else "model"

    prompts = "SYSTEM_PROMPTS = {\n%s}\n" % "".join(
        "    %s: %s,\n" % (_py_str(ident), _py_str(_clean(spec.instructions)))
        for ident, spec in zip(idents, specs, strict=True))

    lines: list[str] = ['    """Build and compile the %s crew as a graph."""' % workflow]
    lines.extend(
        "    %s = create_react_agent(model, tools=[%s], prompt=SYSTEM_PROMPTS[%s])"
        % (ident, ", ".join(spec.tools), _py_str(ident))
        for ident, spec in zip(idents, specs, strict=True))
    lines.append("")
    for ident in idents:
        lines.extend(("    def %s_node(state):" % ident,
                      "        return {\"messages\": %s.invoke(state)[\"messages\"]}" % ident))
    lines.extend(("", "    builder = StateGraph(MessagesState)"))
    lines.extend("    builder.add_node(%s, %s_node)" % (_py_str(ident), ident)
                 for ident in idents)
    prev = "START"
    for ident in idents:
        lines.append("    builder.add_edge(%s, %s)" % (prev, _py_str(ident)))
        prev = _py_str(ident)
    lines.extend(("    builder.add_edge(%s, END)" % prev, "    return builder.compile()"))
    factory = "def build_%s(%s):\n%s\n" % (_ident(workflow), sig, "\n".join(lines))

    parts = [_crew_header("langgraph", workflow, description),
             "\n".join(imports) + "\n", "\n", prompts, "\n"]
    if tools:
        parts.extend(("\n".join(_tool_stub(t, "@tool") for t in tools), "\n\n"))
    parts.append(factory)
    return "".join(parts)


# Multi-agent (crew/graph) renderers, keyed by the same format id as FORMATS.
# A format absent here has no multi-agent path; the command layer falls back to
# the single-agent renderer (flattening the skill to its primary agent).
MULTI_FORMATS: dict[str, Callable[..., str]] = {
    "crewai": render_crew,
    "langgraph": render_graph,
}


def supports_multi(fmt: str) -> bool:
    """True if `fmt` has a multi-agent (crew/graph) renderer."""
    return fmt in MULTI_FORMATS


def render_multi(fmt: str, workflow: str, description: str,
                 specs: list[AgentSpec], model: str | None = None) -> str:
    """Dispatch to the crew/graph renderer for `fmt`.

    Raises ``KeyError`` for a format with no multi-agent path — callers guard
    with :func:`supports_multi` and fall back to :func:`render` (single agent).
    """
    return MULTI_FORMATS[fmt](workflow, description, specs, model)


# A default read-only toolset appended to the adapted agent so it can *act*,
# not roleplay. Emitted as text (never imported here) — the framework only loads
# when the generated runner is executed. `chr(10)` avoids escaping newlines in
# this template; the inner `%s`/`%d` are runtime formatting in the emitted code
# and must NOT be touched by render_runner's `%` on _RUNNER_MAIN alone.
_RUNNER_TOOLS = '''
# --- boost run: default read-only tools (the agent's hands) ---
import pathlib as _boost_pl
from agents import Runner as _boost_Runner, function_tool as _boost_tool


@_boost_tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file and return its first ~16000 characters."""
    return _boost_pl.Path(path).read_text(encoding="utf-8", errors="replace")[:16000]


@_boost_tool
def list_dir(path: str = ".") -> str:
    """List a directory's entries, one per line (directories end with /)."""
    entries = sorted(p.name + ("/" if p.is_dir() else "")
                     for p in _boost_pl.Path(path).iterdir())
    return chr(10).join(entries)


@_boost_tool
def grep(pattern: str, path: str = ".") -> str:
    """Case-insensitive substring search across text files under path."""
    root = _boost_pl.Path(path)
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    hits = []
    for _f in files[:500]:
        try:
            _text = _f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for _i, _line in enumerate(_text.splitlines(), 1):
            if pattern.lower() in _line.lower():
                hits.append("%s:%d: %s" % (_f, _i, _line.strip()[:200]))
                if len(hits) >= 200:
                    return chr(10).join(hits)
    return chr(10).join(hits) or "no matches"
'''

_RUNNER_MAIN = '''
# --- boost run: wire the tools onto the adapted agent and execute ---
_boost_agent = Agent(name=_boost_brain.name, instructions=_boost_brain.instructions,
                     model=getattr(_boost_brain, "model", None),
                     tools=[read_file, list_dir, grep])
print(_boost_Runner.run_sync(_boost_agent, %s).final_output)
'''


def render_runner(name: str, description: str, body: str,
                  model: str | None = None, target: str | None = None) -> str:
    """A self-contained OpenAI Agents SDK *runner* for ``boost run``.

    The adapted agent (its brain — instructions + model, via
    :func:`render_agents_sdk`) plus a default read-only toolset (its hands) and a
    ``Runner.run_sync`` call on a prompt built from ``target``. Like the rest of
    this module it imports no framework — the text only needs to ``compile()``;
    ``boost run`` either prints it (``--print``) or executes it where the SDK is
    installed.
    """
    brain = render_agents_sdk(name, description, body, model)
    # Capture the adapted agent under a reserved name *before* the tool defs — a
    # skill literally named `grep`/`read-file`/`list-dir` normalizes (_ident) to
    # a tool identifier, and the emitted `def grep(...)` would otherwise rebind
    # (clobber) the brain. `_boost_*` names never collide: _ident strips the
    # leading underscore, so no skill name maps onto them.
    capture = "\n_boost_brain = %s\n" % _ident(name)
    tgt = _clean(target or "")
    where = "`" + tgt + "`" if tgt else "the current directory (`.`)"
    prompt = ("Apply your instructions to %s. Use the read_file, list_dir, and "
              "grep tools to inspect it, then produce your output." % where)
    return brain + capture + _RUNNER_TOOLS + (_RUNNER_MAIN % _py_str(prompt))
