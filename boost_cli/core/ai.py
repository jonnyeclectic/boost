"""Optional AI bridge for the Intelligence commands and --smart ranking.

Strategy: prefer the `claude` CLI if on PATH, else the Anthropic API via
urllib when ANTHROPIC_API_KEY is set, else return None so every caller
degrades to its non-AI fallback.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request

from . import config, logs, nethttp

API_URL = "https://api.anthropic.com/v1/messages"

# Bound on how much of the CLI's stderr goes into the diagnostic log — enough
# for the one-line reason ("Invalid API key"), never a whole stack dump.
STDERR_LOG_CHARS = 200


def enabled() -> bool:
    """Return True when `ai.enabled` is on and BOOST_NO_AI is unset."""
    return bool(config.get("ai.enabled", True)) and not os.environ.get("BOOST_NO_AI")


def available() -> bool:
    """Return True when AI is enabled and a backend exists: the `claude`

    CLI on PATH or ANTHROPIC_API_KEY set.
    """
    return enabled() and (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def has_cli() -> bool:
    """Return True when the `claude` CLI is on PATH."""
    return shutil.which("claude") is not None


def fallback_note() -> str:
    """Return the one-line hint shown when a command degrades to heuristics."""
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "— using the heuristic fallback")


def ask(prompt: str, system: str | None = None, model: str | None = None,
        max_tokens: int = 1500, timeout: int = 120) -> str | None:
    """Ask Claude. Returns the text reply, or None if AI is unavailable/fails."""
    if not enabled():
        return None
    model = model or str(config.get("ai.model"))
    if has_cli():
        text = _ask_cli(prompt, system, model, timeout)
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


def _ask_cli(prompt: str, system: str | None, model: str,
             timeout: int) -> str | None:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        # The exception TYPE only, never str(e): TimeoutExpired stringifies the
        # whole argv, which carries the --append-system-prompt text with it.
        _log_failure("claude CLI", type(e).__name__)
        return None
    if proc.returncode != 0:
        _log_failure("claude CLI", "exit %d: %s"
                     % (proc.returncode, _stderr_excerpt(proc.stderr)))
        return None
    out = proc.stdout.strip()
    if not out:
        _log_failure("claude CLI", "empty reply")
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
