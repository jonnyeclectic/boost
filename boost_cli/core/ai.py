# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Optional AI bridge for the Intelligence commands and --smart ranking.

Strategy: use the first assistant CLI on PATH that `core/aihost.py` knows —
Claude first, then Gemini — else the Anthropic API via urllib when
ANTHROPIC_API_KEY is set, else return None so every caller degrades to its
non-AI fallback.

The second CLI is why `aihost` exists. Before it, a user running Gemini got the
heuristic fallback from every AI-assisted command even with a perfectly good
assistant installed, because this module only ever spelled "claude". The
per-backend differences that would otherwise be bugs — Gemini has no
`--append-system-prompt`, and `ai.model` holds a Claude id that `gemini -m`
would reject — are handled there, as data.

The direct-API path stays Anthropic-only. Someone using Gemini CLI has the
binary by definition, so the CLI route is the one that matters; a second HTTP
client is a separate change with its own wire format and error taxonomy.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request

from . import aihost, config, frontmatter, logs, nethttp, typedvalue, util

API_URL = "https://api.anthropic.com/v1/messages"

# Bound on how much of the CLI's stderr goes into the diagnostic log — enough
# for the one-line reason ("Invalid API key"), never a whole stack dump.
STDERR_LOG_CHARS = 200

# The reason the most recent `ask()` fell through, if it did. `ask()` resets
# this before every attempt, so it always describes the last call — never a
# stale failure from an attempt several commands ago. `unavailable_reason()`
# reads it to tell "no backend" apart from "a backend ran and failed", which
# `fallback_note()` used to collapse into one PATH/API-key message regardless
# of which was true.
_last_failure: str | None = None

# Which route produced the most recent reply ("claude CLI", "Anthropic API"),
# reset by `ask()` like `_last_failure`. A caller that finds the reply unusable
# names the route through `note_bad_reply()`, and a ranking label names it
# rather than claiming a model nobody checked answered.
_last_route: str | None = None

#: How much of an unusable reply the debug log keeps — enough to see whether
#: the model refused, chatted, or wrapped its answer, never the whole reply.
BAD_REPLY_LOG_CHARS = 200


def enabled() -> bool:
    """Return True when `ai.enabled` is on and BOOST_NO_AI is unset."""
    return bool(config.get("ai.enabled", True)) and not typedvalue.env_flag("BOOST_NO_AI", unknown=True)


def available() -> bool:
    """Return True when AI is enabled and some backend exists."""
    return enabled() and (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def cli_backend() -> str | None:
    """The first assistant CLI on PATH, in `aihost` preference order."""
    for name in aihost.backends():
        if shutil.which(aihost.cli(name)):
            return name
    return None


def has_cli() -> bool:
    """Return True when any assistant CLI `aihost` knows is on PATH."""
    return cli_backend() is not None


def unavailable_reason() -> str:
    """Why the last AI attempt degraded, as a specific, attributable clause.

    Three causes used to render as one static PATH/API-key message: the user
    disabled AI (`BOOST_NO_AI` or `ai.enabled=false`), no backend exists at
    all, or a backend exists and was tried and failed (an expired login, an
    untrusted workspace, a network error). Only the middle one is a PATH/key
    problem — blaming it for the other two sends a user with a working
    backend chasing an environment issue they do not have.
    """
    if typedvalue.env_flag("BOOST_NO_AI", unknown=True):
        return "disabled (BOOST_NO_AI is set)"
    if not bool(config.get("ai.enabled", True)):
        return "disabled (ai.enabled is off)"
    if not (has_cli() or os.environ.get("ANTHROPIC_API_KEY")):
        clis = " or ".join("`%s`" % aihost.cli(n) for n in aihost.backends())
        return "unavailable — need one of %s on PATH, or ANTHROPIC_API_KEY set" % clis
    if _last_failure:
        return "%s — see ~/.boost/logs/boost.log" % _last_failure
    return "unavailable"


def fallback_note() -> str:
    """Return the one-line hint shown when a command degrades to heuristics.

    Routed through :func:`unavailable_reason` so the note names the real
    cause instead of always pointing at PATH and API keys.
    """
    return "AI %s — using the heuristic fallback" % unavailable_reason()


def ask(prompt: str, system: str | None = None, model: str | None = None,
        max_tokens: int = 1500, timeout: int = 120) -> str | None:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    global _last_failure, _last_route
    if not enabled():
        return None
    _last_failure = None
    _last_route = None
    model = model or str(config.get("ai.model"))
    backend = cli_backend()
    if backend:
        text = _ask_cli(backend, prompt, system, model, timeout)
        if text:
            return text
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ask_api(prompt, system, model, max_tokens, timeout)
    return None


def ask_author(prompt: str, system: str | None = None,
               max_tokens: int = 4000) -> str | None:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def _log_failure(route: str, reason: str) -> None:
    """Record why an AI call fell through to the caller's heuristic fallback.

    Every failure path in this module returns ``None`` and lets the caller
    degrade quietly, which is the right UX but leaves a user with an expired
    key or a flaky network no way to tell *why* every AI command went
    heuristic. DEBUG keeps it out of normal runs: the rotating log file always
    records it, and ``--debug`` surfaces it on stderr. It also lands in
    ``_last_failure`` so ``unavailable_reason()`` can name it on stderr too,
    where a user who never passes ``--debug`` will actually see it.
    """
    global _last_failure
    _last_failure = "%s failed (%s)" % (route, reason)
    logs.get_logger().debug("ai: %s call failed: %s", route, reason)


def _answered(route: str) -> None:
    global _last_route
    _last_route = route


def last_route() -> str | None:
    """The route that produced the last reply, or None if none did."""
    return _last_route


def note_bad_reply(why: str, reply: str | None) -> None:
    """Record that a backend answered, but with nothing the caller can use.

    Transport failures land in ``_last_failure`` via :func:`_log_failure`; a
    reply that arrived with exit 0 and then failed to parse (no JSON array, no
    frontmatter) used to set nothing, so ``fallback_note()`` fell through to a
    bare "AI unavailable" about a backend that had just run and replied, and
    the log held no trace of it. This names the cause on stderr and keeps the
    head of the reply in the debug log, where the user is pointed.
    """
    global _last_failure
    route = _last_route
    _last_failure = "%s was not usable (%s)" % (
        "%s reply" % route if route else "reply", why)
    head = " ".join((reply or "").split())
    if len(head) > BAD_REPLY_LOG_CHARS:
        head = head[:BAD_REPLY_LOG_CHARS] + "..."
    logs.get_logger().debug("ai: %s reply unusable (%s): %r",
                            route or "AI", why, head)


def authored_skill(reply: str | None, name: str) -> str | None:
    """An AI-authored SKILL.md reply as text that carries ``name``, or None.

    The model is asked for ``name: <name>`` and does not always write it: a
    reply naming some other skill was accepted as-is, so `boost distill
    --name merged-one` wrote a file that `boost import` installed as
    something-else, and `boost evolve --apply` renamed the installed skill out
    from under its own directory. The caller already validated ``name``, so a
    missing or different one is overwritten in place (only that line of the
    frontmatter changes). A reply with no frontmatter at all is unusable — it
    is recorded via :func:`note_bad_reply` and None tells the caller to
    degrade to its heuristic.
    """
    if not reply:
        return None
    text = extract_markdown(reply)
    if not text:
        note_bad_reply("empty after removing the code fence", reply)
        return None
    if not frontmatter.split(text)[0]:
        note_bad_reply("no SKILL.md frontmatter", reply)
        return None
    meta, _ = frontmatter.parse(text)
    if meta.get("name") != name:
        logs.get_logger().debug("ai: reply named the skill %r; using %r",
                                meta.get("name"), name)
        text = frontmatter.set_field(text, "name", name)
    return text


def ranker_label() -> str:
    """The ranking label for an order the AI produced, naming its route."""
    return "AI relevance (%s)" % _last_route if _last_route else "AI relevance"


def _stderr_excerpt(text: str | None) -> str:
    """Collapse a subprocess' stderr to one bounded line fit for the log."""
    s = " ".join((text or "").split())
    return (s[:STDERR_LOG_CHARS] + "...") if len(s) > STDERR_LOG_CHARS else s


def _exit_reason(backend: str, proc: subprocess.CompletedProcess) -> str:
    """Why a CLI exited non-zero, as one bounded line — never an empty one.

    Stderr first; then stdout, because an unauthenticated ``claude -p`` exits
    1 with "Not logged in · Please run /login" on stdout and nothing on
    stderr, which left the warning and the log it points at both reading
    ``exit 1: ``. With neither, name the one step that usually explains it.
    """
    return (_stderr_excerpt(proc.stderr) or _stderr_excerpt(proc.stdout)
            or "no output — run `%s` by itself to check it is logged in"
            % aihost.cli(backend))


def _ask_cli(backend: str, prompt: str, system: str | None, model: str,
             timeout: int) -> str | None:
    cmd = aihost.argv(backend, model, system)
    # A backend with no system flag takes the text folded into the prompt.
    body = aihost.fold_system(backend, system, prompt)
    who = "%s CLI" % aihost.cli(backend)
    try:
        # UTF-8 both ways: the prompt carries tap text (arrows, CJK, emoji)
        # the Windows code page cannot encode, and the reply is UTF-8.
        proc = subprocess.run(util.resolve_exe(cmd), input=body,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout)
        if proc.returncode != 0 and aihost.rejected_headless(backend, proc.stderr):
            # A CLI older than the flag (Claude Code < 2.0.63): retry once
            # without it rather than lose the CLI route on every call.
            cmd = aihost.argv(backend, model, system, headless=False)
            proc = subprocess.run(util.resolve_exe(cmd), input=body,
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=timeout)
    except (subprocess.TimeoutExpired, OSError, UnicodeError) as e:
        # The exception TYPE only, never str(e): TimeoutExpired stringifies the
        # whole argv, which carries the system-prompt text with it.
        _log_failure(who, type(e).__name__)
        return None
    if proc.returncode != 0:
        _log_failure(who, "exit %d: %s"
                     % (proc.returncode, _exit_reason(backend, proc)))
        return None
    out = proc.stdout.strip()
    if not out:
        _log_failure(who, "empty reply")
        return None
    _answered(who)
    return out


def _ask_api(prompt: str, system: str | None, model: str,
             max_tokens: int, timeout: int) -> str | None:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with nethttp.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        _log_failure("Anthropic API", "%s: %s" % (type(e).__name__, e))
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    text = "\n".join(parts).strip()
    if not text:
        _log_failure("Anthropic API", "reply had no text content")
        return None
    _answered("Anthropic API")
    return text


def extract_markdown(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    # `or ""`: callers hand this a model reply, which is None when the call
    # failed — tolerating None here is tested behavior, not dead defense.
    t = (text or "").strip()  # noqa: FURB143
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t
