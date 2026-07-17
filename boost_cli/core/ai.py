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
from typing import Optional

from . import config

API_URL = "https://api.anthropic.com/v1/messages"


def enabled() -> bool:
    return bool(config.get("ai.enabled", True)) and not os.environ.get("BOOST_NO_AI")


def available() -> bool:
    return enabled() and (has_cli() or bool(os.environ.get("ANTHROPIC_API_KEY")))


def has_cli() -> bool:
    return shutil.which("claude") is not None


def fallback_note() -> str:
    return ("AI features need the `claude` CLI on PATH or ANTHROPIC_API_KEY set "
            "— using the heuristic fallback")


def ask(prompt: str, system: Optional[str] = None, model: Optional[str] = None,
        max_tokens: int = 1500, timeout: int = 120) -> Optional[str]:
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


def ask_author(prompt: str, system: Optional[str] = None,
               max_tokens: int = 4000) -> Optional[str]:
    """Authoring-grade call (infer/distill/evolve) using the bigger model."""
    return ask(prompt, system=system, model=str(config.get("ai.author_model")),
               max_tokens=max_tokens, timeout=240)


def _ask_cli(prompt: str, system: Optional[str], model: str,
             timeout: int) -> Optional[str]:
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _ask_api(prompt: str, system: Optional[str], model: str,
             max_tokens: int, timeout: int) -> Optional[str]:
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    parts = [b.get("text", "") for b in data.get("content", [])
             if b.get("type") == "text"]
    return "\n".join(parts).strip() or None


def extract_markdown(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t
