"""AI agent targets: where installed skills get symlinked."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from . import config, paths

DISPLAY = {"claude-code": "Claude Code", "windsurf": "Windsurf", "cursor": "Cursor"}


def known_agents() -> Dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool}} for every configured agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
        }
    return out


def enabled_agents() -> Dict[str, Path]:
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def display_name(agent: str) -> str:
    return DISPLAY.get(agent, agent)


def ensure_agent_dirs() -> None:
    for d in enabled_agents().values():
        d.mkdir(parents=True, exist_ok=True)
