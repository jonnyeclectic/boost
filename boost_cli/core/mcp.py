# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Extensible MCP tool registry — the Phase-3 "MCP as a hub" seam.

An MCP tool is a *handler* — ``fn(args: dict) -> (text, is_error)`` — paired with
its JSON spec (``name`` / ``description`` / ``inputSchema``). Instead of a flat
``if/elif`` dispatcher, tools self-register on a :class:`Registry`; the JSON-RPC
server iterates it for both ``tools/list`` and ``tools/call``. Adding a
capability (a GitHub reach-out, a database query, some future dependency) is one
``register()`` call — no dispatcher edits, no server changes.

Handlers return ``(text, is_error)``. A handler that returns ``text is None``
signals "I did not produce a result"; :meth:`Registry.call` also returns
``(None, False)`` for an unknown tool, so the server can answer with a JSON-RPC
``unknown tool`` error in exactly one place. Reach-out handlers degrade the way
``core/ai.py`` does: probe for the dependency, and when it is absent return a
short helpful message rather than raising.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable

from ..errors import BoostError

# A handler maps parsed arguments to (text, is_error). ``text is None`` means the
# handler produced no result (treated by the server as an unknown/aborted tool).
Handler = Callable[[dict], tuple[str | None, bool]]


class Registry:
    """An ordered name -> (spec, handler) map for MCP tools."""

    def __init__(self) -> None:
        self._order: list[str] = []
        self._specs: dict[str, dict] = {}
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, description: str, input_schema: dict,
                 handler: Handler) -> None:
        """Register one tool. Raises on an empty or duplicate name."""
        if not name:
            raise ValueError("MCP tool name must be non-empty")
        if name in self._handlers:
            raise ValueError("duplicate MCP tool %r" % name)
        self._order.append(name)
        self._specs[name] = {"name": name, "description": description,
                             "inputSchema": input_schema}
        self._handlers[name] = handler

    def tool(self, name: str, description: str,
             input_schema: dict) -> Callable[[Handler], Handler]:
        """Decorator form of :meth:`register`; returns the handler unchanged."""
        def deco(fn: Handler) -> Handler:
            self.register(name, description, input_schema, fn)
            return fn
        return deco

    def specs(self) -> list[dict]:
        """The ``tools/list`` payload — specs in registration order."""
        return [self._specs[name] for name in self._order]

    def names(self) -> list[str]:
        """Registered tool names, in registration order."""
        return self._order.copy()

    def has(self, name: str) -> bool:
        return name in self._handlers

    def call(self, name: str, args: dict) -> tuple[str | None, bool]:
        """Dispatch to a handler. ``(None, False)`` for an unknown tool."""
        handler = self._handlers.get(name)
        if handler is None:
            return None, False
        return handler(args)


# ── JSON-RPC 2.0 protocol ─────────────────────────────────────────────────
# The wire protocol Claude Code speaks to `boost mcp --stdio`. handle_request is
# a *pure* request→response mapping (no I/O), so the whole protocol is unit
# testable; serve_stdio only adds the newline-delimited stdin/stdout loop.
PROTOCOL_VERSION = "2024-11-05"

# Server-level guidance returned in the `initialize` result. MCP hosts load this
# into the model's context, so it is boost's one chance to tell an agent WHEN it
# is relevant — the difference between a search tool that sits unused and one an
# agent reaches for. Framed by the agent's triggers, not boost's nouns.
#
# ONE benefit, stated once: find a skill for the task in front of you. Earlier
# passes gave equal billing to "before you author a skill", and that cost more
# than it bought — authoring is the rarer moment, and an agent handed two
# triggers matches the one it can recognise fastest, which was the wrong one.
# Authoring now lives as a clause on boost_search's own description.
#
# The trigger is observable rather than a judgement call. "Before non-trivial
# work" lost to its own escape hatch every time: deciding a task is non-trivial
# takes judgement, while "this turn looks small" is free, and every turn looks
# small when it opens. Whether the task has a NAME can be pattern-matched
# without deciding anything, and a named task is exactly the kind someone has
# already written down.
#
# Three things below are load-bearing, not padding. The stated COST kills the
# hesitation over an unknown-price call. The MISS PROTOCOL stops a zero-result
# search reading as a wasted turn — without it one empty search teaches an agent
# to stop checking. And "the task stays yours" is what makes an agent willing to
# look at all: one that expects a hit to seize the work is safer not looking.
# The closing bound names concrete shapes instead of the word "trivial", which
# an unbounded "always check first" needs or the guidance gets ignored wholesale.
# Two claims were removed from this text rather than restated, and the reason
# is the same for both: they were the only numbers here an agent could not
# check, in the one block of boost prose it reads before deciding anything.
#
#   "95% of the time against 79% without it" — real, but measured over the
#   SIX-repo corpus. tests/eval/baseline.json records BM25 hit@1 at 0.4725 for
#   the twenty-repo corpus that replaced it precisely because six was
#   unrealistically small (CLAUDE.md), and docs/eval.html publishes both side by
#   side. Quoting 79% as today's baseline overstated it by 31 points, and the
#   reranked figure has never been re-measured at twenty. The mechanism is the
#   part that changes an agent's decision; the arithmetic belongs to the eval
#   gate, which floors it against a corpus it names.
#
#   "vetted" — the catalog is indexed, not reviewed. #442 struck the word from
#   every tool description for that reason and left it here, where it did the
#   same work of implying a guarantee nobody performs.
#
# THREE KINDS, stated once and early. Every line of this text used to say
# "skills", while `boost_search` has always returned rules and workflows too
# and `store.install` has always installed all three. An agent reading the old
# text had no reason to look for a guardrail or a slash-command, and no way to
# know that installing a rule edits the file it reads every session. Rules in
# particular are the kind the catalog is worst at selling itself on: their
# whole job is steering toward a better path and away from an anti-pattern,
# which is exactly the value an agent cannot infer from the bare word "rule".
#
# THE BOUNDARY is read off the REQUEST rather than judged about the work, and
# that distinction is the whole reason it works. "Before non-trivial work"
# lost to its own escape hatch every time, because deciding a task is
# non-trivial takes judgement while "this turn looks small" is free — and
# every turn looks small when it opens. Two properties of what was asked
# survive that: more than one file, or something that outlives the session.
#
# A third — "you would name it in a commit message" — was drafted and cut,
# because it is true of every edit that ships, including the one-line edit the
# skip list two paragraphs down explicitly excuses. A trigger that swallows
# its own bound is how "check first" becomes "check always", which is the
# capture this whole surface is written to avoid. The nameable-task trigger
# stays as the cheapest test of all.
#
# THE DEFEATER, and it is the one clause here that is not a trigger. Forensics
# on a Gemini CLI session: asked to build a RAG app with LangGraph, LangChain
# and LangSmith, the agent shipped it without calling a single boost tool, and
# explained afterwards that it had "immediately activated the pre-installed
# local skills — langchain-rag and rag-engineer" and "overlooked calling
# mcp_boost_boost_search". boost_search's description already named that exact
# moment — "a new project or subsystem, an architecture decision, environment
# and tooling config" — and the agent paraphrased the list back when asked.
#
# So the trigger did not fail to fire. It fired and was overruled. Every
# trigger boost ships is a predicate over the REQUEST; the gate the model
# actually applied was a predicate over its OWN CONTEXT — something already
# matched, so I am covered. That proposition appears nowhere in boost's
# agent-facing text ('already loaded' 0 hits, 'already matched' 0, 'even if' 0,
# 'enough' 0, 'sufficient' 0, 'covered' 0, 'active skill' 0 across INSTRUCTIONS
# and all six tool descriptions), and a clause that does not exist cannot have
# failed. This paragraph adds it.
#
# It is placed DOWNSTREAM of the two signals rather than beside them, because a
# fourth signal would widen the gate and this narrows an exception to it. And
# it is written as a description rather than a denial. An earlier draft said
# "an active skill does not answer this question", which compresses to "an
# active skill is never enough" — a standing order to search, i.e. the same
# capture the skip list and the stated cost exist to prevent. What ships says
# what an active skill IS (installed earlier, matched on its own description,
# one kind of three) and leaves the conclusion to the reader.
#
# NON-CAPTURING, and this is a measured knife edge rather than a manner.
# Editing only a tool's description moves how often a model calls it by more
# than 10x ("Tool Preferences in Agentic LLMs are Unreliable", EMNLP 2025),
# and assertive phrasing is precisely the lever that does it. So the skip list
# stays in plain sight, the cost stays stated, and nothing here is an order —
# a surface that captures work it cannot do gets routed around permanently the
# first time it misses, which costs more than every call it ever won.
INSTRUCTIONS = (
    "boost is a shared shelf of version-tracked procedures for AI coding "
    "agents, in three kinds: SKILLS (a procedure someone already worked out "
    "and debugged), RULES (guardrails that steer toward a better path and "
    "rule out an anti-pattern — these become part of your agent's standing "
    "instructions, either a managed block in its context file or a file in "
    "its rules directory), and WORKFLOWS (slash-commands and subagents).\n"
    "\n"
    "THE CHECK: if the task in front of you has a name — \"set up code "
    "review\", \"add commit conventions\", \"write a migration\", \"debug "
    "flaky tests\" — someone has probably already written it down. Call "
    "boost_list for what is installed on this machine and boost_search for "
    "what exists. Both are read-only and install nothing. boost_list is "
    "instant. boost_search costs 10-15 seconds: it retrieves, then an LLM "
    "reranks every match, which is what makes the top result worth acting on "
    "rather than skimming ten. Only a novel search pays it — repeating an "
    "identical search skips the LLM and answers from a local cache.\n"
    "\n"
    "WORTH THE SECONDS (boost_search — boost_list is free, call it whenever). "
    "Two signals, both readable from the request itself rather than from work "
    "you have not done: it asks you to touch more than one file, or it asks "
    "for something that outlives this session — a config, a CI job, a "
    "convention, a dependency. Check again the moment a small task turns "
    "out to be a large one — the first check only fires at a boundary you "
    "recognized at the time, and a question that became an investigation "
    "never got one.\n"
    "\n"
    "ALREADY HOLDING A MATCH is not one of those two signals, though it reads "
    "like an answer to the same question. A skill that activated here was "
    "installed on an earlier day and matched on its own description — what it "
    "covers, not what this request needs — and it is one kind of three: a rule "
    "you never installed cannot activate, and a workflow waits to be called by "
    "name. The two signals stay properties of the request, and an active skill "
    "leaves them as it found them.\n"
    "\n"
    "Finding nothing is a good outcome, not a wasted call: it tells you to "
    "build it yourself, now knowing that nothing already covers it. Finding "
    "something is a head start, not an instruction — read it, take what fits, "
    "discard the rest. The task stays yours.\n"
    "\n"
    "Flow: boost_search -> boost_install. Skip it for a question, a one-line "
    "edit, or a command you were just handed."
)


def hit_line(entry: dict, *, installed: bool = False) -> str:
    """One search hit rendered for an agent: name, kind, description, tap.

    The kind marker is the load-bearing part. ``boost_install``'s description
    warns that installing a rule is the more invasive change — it merges into
    the context file the agent loads every session rather than copying a file
    into the store — and tells the caller to check what they are installing.
    Until this marked it, the reply that warning applies to never said which
    hits were rules, so the check it asked for was impossible.

    Skills render unmarked: they are the common case, and a marker on every
    line would spend a token per hit to say "nothing unusual here". A missing
    ``kind`` reads as a skill for the same reason it does everywhere else in
    the catalog — thin scanner output must not surface ``[None]`` to an agent.

    ``installed`` adds a second marker after the kind, and is keyword-only with
    a False default so every existing caller and assertion renders byte-for-byte
    what it did before. It is **name-keyed** — the caller tests the name against
    the lock file — which means a hit from a *different tap* that happens to
    share a name is marked. That is a real false-positive rate (the corpus holds
    13 distinct skills called ``code-reviewer``) and it errs toward suppressing
    a search, so it is disclosed rather than hidden: :func:`overlap_note` says
    so in the reply itself, and every hit line names its own tap.

    Keying it more precisely was the alternative and was rejected. The lock file
    IS name-keyed (``lockfile.find_any``), and so is ``store.install``, so a
    tap-qualified marker would disagree with the tool it is advising about — a
    hit marked "not installed" that ``boost_install <name>`` then resolves to
    the item already in the lock. One notion of identity per reply, plus the
    field that resolves it, beats two that contradict each other.
    """
    kind = entry.get("kind") or "skill"
    marker = "" if kind == "skill" else " [%s]" % kind
    if installed:
        marker += " [installed]"
    return "%s%s — %s (%s)" % (entry.get("name", "?"), marker,
                               entry.get("description", ""),
                               entry.get("tap", "?"))


# The lock sections, in the order every boost surface names them. Fixed here
# rather than read off the caller's dict, so the footer's column order cannot
# drift between a machine that has rules and one that does not.
_KINDS = ("skill", "rule", "workflow")


def coverage_line(installed: dict, *, tapped: int) -> str:
    """``boost_list``'s closing footer: what this machine holds, per kind.

    ``installed`` is the ``lockfile.all_installed()`` shape — ``{kind: {name:
    entry}}`` — and a missing section counts as zero.

    boost_list used to answer "what do I have" and nothing else, which made it
    the amplifier for the failure this footer exists to defeat: an agent that
    stopped because something had already matched would, on calling the one
    free tool, have been told only about the things it already had. This is the
    other half — a kind sitting at zero is a kind nothing on this machine could
    have loaded, and boost_search is what reads the registries themselves.

    Only INSTALLED counts appear. An earlier draft closed with the size of the
    tapped catalog, and that number cannot be substantiated: those are
    un-de-duplicated index entries, and boost's own ranked list de-duplicates
    on the content hash precisely because 13 distinct skills named
    ``code-reviewer`` collapsing into one slot credited the ranker with a
    compression that existed only in the scoring code. Printing the raw total
    as the size of what the user is missing would be the only claim in this
    surface an agent cannot check. Dropping it also keeps the tool honest about
    its cost: with no catalog read, boost_list stays the "instant" tool
    INSTRUCTIONS advertises.

    ``tapped`` selects the closing sentence, keyed the way :func:`no_results`
    and ``boost_doctor`` key theirs and naming the same one command in the same
    order — an agent that calls two of these in one session must not see the
    recommendation flip and read it as two different fixes.
    """
    body = " · ".join(
        "%d %s%s" % (n, kind, "" if n == 1 else "s")
        for kind, n in ((k, len(installed.get(k) or {})) for k in _KINDS))
    if tapped > 0:
        return ("%s installed here — what this machine holds, not what exists. "
                "boost_search reads the tapped registries themselves, across "
                "all three kinds." % body)
    return ("%s installed here. Nothing is tapped yet, so there is no catalog "
            "behind boost_search either — ask the user to run `boost tap "
            "--defaults` to add the recommended registries." % body)


def overlap_note(installed_hits: int, total_hits: int) -> str:
    """How much of a search reply this machine already has. ``""`` for no hits.

    The counterpart to :func:`hit_line`'s ``[installed]`` marker: the marker
    says which line, this says how many, and it is the only agent-facing place
    the marker's name-keying is disclosed. Both serve one decision — "I already
    have something" is a claim about the machine, and until the reply separated
    the two halves it was a guess.

    Zero overlap gets its own sentence rather than silence. It is the plainest
    available answer to "something already matched, so I am covered", and
    silence would read as absence of information rather than as the answer.

    The empty reply belongs to :func:`no_results` — including its
    untapped-machine branch — so nothing bolts onto it here.
    """
    if total_hits <= 0:
        return ""
    if installed_hits <= 0:
        return "\n(none of these are installed on this machine.)"
    return ("\n(%d of %d already installed here, marked [installed]. The match "
            "is on the name alone — the same test boost_install and boost_info "
            "use — so an item from a different tap that shares a name is "
            "marked too; each line names its tap.)"
            % (installed_hits, total_hits))


def no_results(query: str, *, tapped: int) -> str:
    """The reply for a search that returned nothing.

    Two different situations wore one sentence. On a configured machine
    nothing matching the query is a real answer, and saying so is what makes
    "finding nothing is a good outcome" true. On a machine with no taps
    nothing could have matched *anything*, and reporting that as a failed
    search is how a new user's first question teaches their agent that boost
    is empty — the reply is byte-identical to a genuine miss.

    So the empty-catalog branch does not repeat the query back: the query was
    fine. It names the state and the one command that changes it, the way
    ``tool-design`` asks agent-facing errors to carry their own recovery path.
    """
    if tapped > 0:
        return "no skills match %r" % query
    # Addressed to the user via the agent, and naming ONE command. Telling an
    # agent to run `boost mcp --seed` itself would have it re-register the
    # server with every CLI on PATH as a side effect, and would step straight
    # over a BOOST_NO_SEED the user set deliberately — `--seed` is exactly the
    # flag that overrides it. `boost tap --defaults` is the precise fix, and
    # _tool_doctor names the same one in the same order.
    return ("nothing is tapped yet, so there is no catalog to search — this "
            "is a setup state, not a miss. Ask the user to run "
            "`boost tap --defaults` to add the recommended registries, then "
            "search again.")


def engine_note() -> str:
    """One line telling the agent which retrieval engine `boost_search` will use.

    MCP hosts load `instructions` into the agent's context, and an agent that
    cannot tell a keyword index from a semantic one will phrase queries for a
    vector search that is not running — asking "my containers keep restarting"
    of a BM25 index that needs the word "docker". Naming the engine, and the one
    command that upgrades it, costs a line and removes the guess.

    Appended at `initialize` rather than baked into INSTRUCTIONS because the
    answer depends on machine state at connect time, not on the build.
    """
    from . import dense
    st = dense.status()
    if st.get("ready"):
        return ("\n\nSEARCH ENGINE: hybrid — BM25 keywords fused with dense "
                "vectors (%s). Natural-language problem descriptions retrieve "
                "well; you do not need to guess the skill's vocabulary."
                % st.get("model"))
    return ("\n\nSEARCH ENGINE: BM25 keyword matching only — dense vectors are "
            "not configured, so queries are matched on shared words rather than "
            "meaning. Prefer concrete terms over paraphrase. To enable semantic "
            "search, %s." % dense.fix_hint(st.get("reason", ""), st))


def handle_request(req: dict, *, version: str,
                   registry: Registry) -> dict | None:
    """Map one parsed JSON-RPC request to its response dict.

    Returns ``None`` for a notification (a request with no ``id``) — the caller
    sends nothing back. Handlers that raise during ``tools/call`` are turned into
    an error *result* (``isError``) rather than a protocol error, so a failing
    tool never kills the session.
    """
    method = str(req.get("method", ""))
    if "id" not in req:  # notification (e.g. notifications/initialized)
        return None
    resp: dict = {"jsonrpc": "2.0", "id": req.get("id")}
    if method == "initialize":
        resp["result"] = {"protocolVersion": PROTOCOL_VERSION,
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "boost", "version": version},
                          "instructions": INSTRUCTIONS + engine_note()}
    elif method == "ping":
        resp["result"] = {}
    elif method == "tools/list":
        resp["result"] = {"tools": registry.specs()}
    elif method == "tools/call":
        params = req.get("params") or {}
        tool = str(params.get("name", ""))
        try:
            text, is_err = registry.call(tool, params.get("arguments") or {})
        except BoostError as e:
            text = "Error: %s" % e.message + ("\nhint: %s" % e.hint if e.hint else "")
            is_err = True
        except Exception as e:
            text, is_err = "Error: %s" % e, True
        if text is None:
            resp["error"] = {"code": -32602, "message": "unknown tool %r" % tool}
        else:
            # Annotated: the literal alone infers a list-only value type, so
            # adding the `isError` bool below would be a type error.
            result: dict = {"content": [{"type": "text", "text": text}]}
            if is_err:
                result["isError"] = True
            resp["result"] = result
    else:
        resp["error"] = {"code": -32601, "message": "method not found: %s" % method}
    return resp


def serve_stdio(registry: Registry, *, version: str,
                stdin=None, stdout=None) -> int:
    """Newline-delimited JSON-RPC 2.0 MCP server on stdin/stdout.

    ``stdin``/``stdout`` default to the process streams but can be injected
    (e.g. ``io.StringIO``) so the loop is testable end to end.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    def send(msg: dict) -> bool:
        try:
            stdout.write(json.dumps(msg) + "\n")
            stdout.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    while True:
        try:
            line = stdin.readline()
        except (KeyboardInterrupt, OSError):
            return 0
        if not line:  # EOF
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            if not send({"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "parse error"}}):
                return 0
            continue
        resp = handle_request(req, version=version, registry=registry)
        if resp is None:  # notification — nothing to send
            continue
        if not send(resp):
            return 0
