# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""AI agent targets: where installed skills get symlinked."""
from __future__ import annotations

from pathlib import Path

from . import config, paths

DISPLAY = {"claude-code": "Claude Code", "windsurf": "Windsurf",
           "cursor": "Cursor", "gemini": "Gemini CLI",
           "antigravity": "Antigravity CLI", "codex": "Codex"}


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
            # Defaults True: nearly every agent reads a repo-local copy of its
            # own dotdir, so a project install lands in `<repo>/.claude/skills`
            # and its siblings. False marks an agent whose project layout boost
            # does not know — see :func:`project_agents`.
            "project_scope": bool(spec.get("project_scope", True)),
            # Defaults False: most agents take all three kinds. True marks an
            # agent where only the skills surface is known — see
            # :func:`materializing_agents`.
            "skills_only": bool(spec.get("skills_only", False)),
            # Defaults True. False marks an agent whose *rules* surface is
            # verified but whose slash-command format is not, so it takes rules
            # and skills but no workflows — a finer cut than `skills_only`,
            # which turns both off. See :func:`workflow_agents`.
            "workflows": bool(spec.get("workflows", True)),
            # Defaults False: assume an agent shown the same skill through two
            # of its discovery tiers will complain about it, because Gemini CLI
            # does. True marks one that collapses them instead — see
            # :func:`dedupes_by_path`.
            "dedupes_by_path": bool(spec.get("dedupes_by_path", False)),
        }
    return out


def enabled_agents() -> dict[str, Path]:
    """{name: dir Path} for just the agents whose "enabled" flag is true."""
    return {n: s["dir"] for n, s in known_agents().items() if s["enabled"]}


def linking_agents() -> dict[str, Path]:
    """The enabled agents that need a skill *symlinked* into their own dir.

    Most agents do: they only look inside their own config directory, so a
    skill is invisible until boost links it there. Gemini CLI and Codex are the
    exceptions — both discover ``~/.agents/skills`` directly, which is exactly
    :func:`paths.store_dir`. Linking for them would put the same skill in two of
    their discovery tiers, and since the ``.agents`` alias out-ranks
    ``.gemini/skills`` within Gemini's user tier, the copy boost linked could
    never win — it would only make Gemini log a "Skill conflict detected" line
    per skill, every session. Codex collapses the pair silently instead (see
    :func:`dedupes_by_path`), so there the cost is redundant work rather than
    noise; not linking is right either way.

    So this is the set to iterate for anything symlink-shaped (link, unlink,
    stale-link sweeps, coverage checks) — including the sweep in
    :func:`store.sync_plan`, whose only ownership test is ``points_into_store``:
    over a native-store agent's skills dir it would delete links boost never
    created. What materializes *into* an agent's dotdir is a different set again
    (:func:`materializing_agents` for rules, :func:`workflow_agents` for
    workflows), because those have no canonical store to be read from.
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and s["links_skills"]}


def project_agents() -> dict[str, Path]:
    """Enabled agents whose *project* layout boost actually knows.

    Project scope is derived from the agent's own dotdir
    (``scopes.agent_root``: ``<repo>/.claude/skills/…``), which holds for every
    agent whose skills dir is one level under a dotdir. Antigravity CLI's is
    two — ``~/.gemini/antigravity-cli/skills`` — so the derivation would create
    a dotless ``<repo>/antigravity-cli/`` that nothing reads, and boost would
    report a coverage it does not have. Its documented project location is
    inside ``~/.gemini/config/projects/``, which is not a repo-local directory
    at all; until that is verified against the CLI, the honest answer is to
    leave it out of project scope rather than invent a path for it.
    """
    return {n: s["dir"] for n, s in known_agents().items()
            if s["enabled"] and s["project_scope"]}


def agents_for_scope(base) -> dict[str, Path]:
    """Enabled agents for user scope (``base is None``) or project scope."""
    return enabled_agents() if base is None else project_agents()


def materializing_agents(base=None) -> dict[str, Path]:
    """Agents a *rule* or *workflow* may be written into.

    A skill is a directory boost symlinks; a rule and a workflow are files
    boost writes in a format the agent has to already read — a context file at
    a known path, or a slash command in a known dir and syntax. So this set is
    narrower than :func:`agents_for_scope`: an agent whose rule and workflow
    formats have not been verified is skills-only, and writing a plausible file
    into its config tree would claim a coverage that does not exist.

    Antigravity CLI is the current case. Its rules arrive anyway, through the
    ``gemini`` agent, which already writes the ``~/.gemini/GEMINI.md`` it reads.
    """
    return {n: d for n, d in agents_for_scope(base).items()
            if not known_agents()[n]["skills_only"]}


def workflow_agents(base=None) -> dict[str, Path]:
    """Agents a *workflow* may be written into: :func:`materializing_agents`
    minus those with no verified slash-command format.

    Rules and workflows are not one surface. An agent can document exactly
    where its standing instructions live and still have no user-installable
    command format at all, and `skills_only` cannot express that — it turns
    both off, which would under-claim a surface boost has verified.

    Codex CLI is the case. Its instructions file is `AGENTS.md`
    (:data:`rules.CONTEXT_FILES`), but 0.156.1 ships no `prompts/` or
    `commands/` directory, no command subcommand, and its plugin importer
    *rewrites* a Claude `commands/*.md` into a `SKILL.md` on disk rather than
    running it as a command. A Markdown file dropped in `~/.codex/commands/`
    would be installed, reported, and never loaded.
    """
    return {n: d for n, d in materializing_agents(base).items()
            if known_agents()[n]["workflows"]}


def dedupes_by_path() -> set[str]:
    """Agents that collapse two discovery entries resolving to the same file.

    The assumption everywhere else is Gemini CLI's behaviour: show it one skill
    through two tiers and it logs a "Skill conflict detected" line per skill per
    session, which is what :func:`store.duplicate_discovery` exists to warn
    about. Codex CLI de-duplicates by *resolved* path instead — a symlink in
    `~/.codex/skills` pointing at a store skill is listed exactly once, under
    the canonical path, with no warning (verified against 0.156.1 via
    `codex debug prompt-input` and the app-server's `skills/list`). Reporting
    that as an issue would be a false positive, so these agents are skipped.

    It is deliberately not a reason to start linking: see the `codex` entry in
    :data:`config.DEFAULTS`.
    """
    return {n for n, s in known_agents().items()
            if s["enabled"] and s["dedupes_by_path"]}


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
