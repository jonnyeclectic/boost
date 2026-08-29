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

from . import aihost, config, logs, nethttp

API_URL = "https://api.anthropic.com/v1/messages"

# Bound on how much of the CLI's stderr goes into the diagnostic log — enough
# for the one-line reason ("Invalid API key"), never a whole stack dump.
STDERR_LOG_CHARS = 200


def enabled() -> bool:
    """Return True when `ai.enabled` is on and BOOST_NO_AI is unset."""
    return bool(config.get("ai.enabled", True)) and not os.environ.get("BOOST_NO_AI")


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


def fallback_note() -> str:
    """Return the one-line hint shown when a command degrades to heuristics.

    Names every CLI that would work, not just Claude's — telling a Gemini user
    to install Claude is a worse answer than telling them boost could not find
    either.
    """
    clis = " or ".join("`%s`" % aihost.cli(n) for n in aihost.backends())
    return ("AI features need one of %s on PATH, or ANTHROPIC_API_KEY set "
            "— using the heuristic fallback" % clis)


def ask(prompt: str, system: str | None = None, model: str | None = None,
        max_tokens: int = 1500, timeout: int = 120) -> str | None:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
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
    records it, and ``--debug`` surfaces it on stderr.
    """
    logs.get_logger().debug("ai: %s call failed: %s", route, reason)


def _stderr_excerpt(text: str | None) -> str:
    """Collapse a subprocess' stderr to one bounded line fit for the log."""
    s = " ".join((text or "").split())
    return (s[:STDERR_LOG_CHARS] + "...") if len(s) > STDERR_LOG_CHARS else s


def _ask_cli(backend: str, prompt: str, system: str | None, model: str,
             timeout: int) -> str | None:
    cmd = aihost.argv(backend, model, system)
    # A backend with no system flag takes the text folded into the prompt.
    body = aihost.fold_system(backend, system, prompt)
    who = "%s CLI" % aihost.cli(backend)
    try:
        proc = subprocess.run(cmd, input=body, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        # The exception TYPE only, never str(e): TimeoutExpired stringifies the
        # whole argv, which carries the system-prompt text with it.
        _log_failure(who, type(e).__name__)
        return None
    if proc.returncode != 0:
        _log_failure(who, "exit %d: %s"
                     % (proc.returncode, _stderr_excerpt(proc.stderr)))
        return None
    out = proc.stdout.strip()
    if not out:
        _log_failure(who, "empty reply")
        return None
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
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        _log_failure("Anthropic API", "%s: %s" % (type(e).__name__, e))
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    text = "\n".join(parts).strip()
    if not text:
        _log_failure("Anthropic API", "reply had no text content")
        return None
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
