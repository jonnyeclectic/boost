"""AI agent targets: where installed skills get symlinked."""
from __future__ import annotations

from pathlib import Path

from . import config, paths

DISPLAY = {"claude-code": "Claude Code", "windsurf": "Windsurf",
           "cursor": "Cursor", "gemini": "Gemini CLI"}


def known_agents() -> dict[str, dict]:
    """{name: {"dir": Path, "enabled": bool, "links_skills": bool}} per agent."""
    out = {}
    for name, spec in (config.get("agents") or {}).items():
        out[name] = {
            "dir": paths.expand(str(spec.get("dir", ""))),
            "enabled": bool(spec.get("enabled", True)),
            # Defaults True: an agent only reads the canonical store if it
            # implements the Agent Skills standard's `~/.agents/skills` path,
            # which most do not, so the symlink is the safe assumption.
            "links_skills": bool(spec.get("links_skills", True)),
        }
    return out


def enabled_agents() -> dict[str, Path]:
    """{name: dir Path} for just the agents whose "enabled" flag is true."""
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def linking_agents() -> dict[str, Path]:
    """The enabled agents that need a skill *symlinked* into their own dir.

    Most agents do: they only look inside their own config directory, so a
    skill is invisible until boost links it there. Gemini CLI is the exception —
    it implements the Agent Skills standard and discovers ``~/.agents/skills``
    directly, which is exactly :func:`paths.store_dir`. Linking for it would put
    the same skill in two of its discovery tiers, and since the ``.agents``
    alias out-ranks ``.gemini/skills`` within the user tier, the copy boost
    linked could never win — it would only make Gemini log a "Skill conflict
    detected" line per skill, every session.

    So this is the set to iterate for anything symlink-shaped (link, unlink,
    stale-link sweeps, coverage checks). :func:`enabled_agents` remains the set
    for everything that materializes *into* an agent's dotdir — rules and
    workflows — because those have no canonical store to be read from.
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and s["links_skills"]}


def native_store_agents() -> dict[str, Path]:
    """Enabled agents that read the canonical store without a symlink.

    The complement of :func:`linking_agents` within :func:`enabled_agents` —
    reported at install time so "linked → a · b · c" never reads as "and not
    the agent you actually use".
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and not s["links_skills"]}


def display_name(agent: str) -> str:
    """`claude-code` -> "Claude Code"; unknown names pass through unchanged."""
    return DISPLAY.get(agent, agent)


def ensure_agent_dirs() -> None:
    """Create every *linking* agent's skills dir (`mkdir -p`, idempotent).

    Not :func:`enabled_agents`: this exists so a skill has somewhere to be
    linked, and boost never links into a native-store agent's dir. Creating
    ``~/.gemini/skills`` anyway would leave an empty directory nothing ever
    writes to, which ``boost heal`` would first report as a missing directory
    it needed to create.
    """
    for d in linking_agents().values():
        d.mkdir(parents=True, exist_ok=True)
