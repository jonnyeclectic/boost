"""boost CLI dispatcher — 72 commands across 8 groups.

Each command lives in boost_cli/commands/<module>.py as
    def cmd_<name_with_underscores>(argv: list[str]) -> int
Modules are imported lazily so `boost --help` stays instant.
"""
from __future__ import annotations

import difflib
import importlib
import sys
from typing import List

from . import PRODUCT, TAGLINE, __version__
from .core import output as out
from .errors import BoostError

# group key -> (icon token, title, description)
GROUPS = {
    "pkg":  ("pkg",  "Package Management",
             "Install, remove, update & move skills across agents"),
    "find": ("find", "Discovery & Search",
             "Find the right skill across taps and all of GitHub"),
    "info": ("info", "Skill Information",
             "Inspect, read, and explain what a skill does"),
    "tap":  ("tap",  "Registry (Taps)",
             "Add, remove, and inspect GitHub skill registries"),
    "ai":   ("ai",   "Intelligence",
             "AI-powered authoring, merging & behavior preview"),
    "chk":  ("chk",  "Quality & Health",
             "Validate, audit, and keep your setup healthy"),
    "cfg":  ("cfg",  "Configuration",
             "Config, scaffolding, policy & integrations"),
    "team": ("team", "Team & Collaboration",
             "Roll out, profile & coordinate skills across a team"),
}

# (name, group, module, summary) — the single source of truth for the
# command surface. docs/overview.html mirrors this list.
COMMANDS = [
    # Package Management (12)
    ("install",     "pkg", "pkg", "Install a skill from a tap registry"),
    ("uninstall",   "pkg", "pkg", "Remove an installed skill, rule, workflow, or config"),
    ("sync",        "pkg", "pkg", "Reconcile installed skills & symlinks against the lock file"),
    ("update",      "pkg", "pkg", "Sync taps or update installed skills"),
    ("reinstall",   "pkg", "pkg", "Reinstall a skill or all skills (force)"),
    ("bundle",      "pkg", "pkg", "Export/install skill sets via a Boostfile"),
    ("import",      "pkg", "pkg", "Import skills from a GitHub URL or local path"),
    ("migrate",     "pkg", "pkg", "Migrate skills between agents or from Skills CLI"),
    ("pin",         "pkg", "pkg", "Pin a skill to its current version"),
    ("unpin",       "pkg", "pkg", "Allow a pinned skill to update again"),
    ("snapshot",    "pkg", "pkg", "Save & restore whole skill environments"),
    ("export",      "pkg", "pkg", "Package skills as shareable zip/tar archives"),
    # Discovery & Search (8)
    ("search",      "find", "discovery", "Search skills across tap registries (AI-ranked)"),
    ("discover",    "find", "discovery", "Browse & search the GitHub-wide skill discovery index"),
    ("recommend",   "find", "discovery", "Suggest skills based on your project's tech stack"),
    ("browse",      "find", "discovery", "Interactive full-screen TUI with fuzzy search"),
    ("index",       "find", "discovery", "Build the discovery registry via GitHub Code Search"),
    ("trending",    "find", "discovery", "Show trending skills by install count"),
    ("stats",       "find", "discovery", "Install statistics & trend for a single skill"),
    ("count",       "find", "discovery", "Quick summary of installed / available / taps"),
    # Skill Information (10)
    ("list",        "info", "info", "List installed skills"),
    ("info",        "info", "info", "Show detailed info about a skill"),
    ("cat",         "info", "info", "Print a skill or rule's contents"),
    ("edit",        "info", "info", "Open a skill's SKILL.md in your editor"),
    ("preview",     "info", "info", "Render a SKILL.md with rich formatting"),
    ("explain",     "info", "info", "Explain what a skill does in plain English"),
    ("log",         "info", "info", "Git log for a skill, or boost's activity log"),
    ("home",        "info", "info", "Open a skill's GitHub page in the browser"),
    ("deps",        "info", "info", "Show dependency & conflict relationships"),
    ("tag",         "info", "info", "Custom labels for organizing skills"),
    # Registry (Taps) (4)
    ("tap",         "tap", "taps", "Add a GitHub repo as a skill registry"),
    ("untap",       "tap", "taps", "Remove a registry tap"),
    ("taps",        "tap", "taps", "List all configured registry taps"),
    ("outdated",    "tap", "taps", "Show skills with available updates"),
    # Intelligence (8)
    ("distill",     "ai", "intelligence", "Merge multiple skills into one deduplicated skill"),
    ("simulate",    "ai", "intelligence", "Preview how a skill would change Claude's behavior"),
    ("infer",       "ai", "intelligence", "Generate a SKILL.md from your codebase patterns"),
    ("absorb",      "ai", "intelligence", "Turn recurring chat-history patterns into a skill"),
    ("evolve",      "ai", "intelligence", "Iteratively improve a skill from feedback"),
    ("context",     "ai", "intelligence", "Branch-aware skill activation"),
    ("focus",       "ai", "intelligence", "Temporarily prioritize skills for a work session"),
    ("impact",      "ai", "intelligence", "Measure a skill's influence on code quality"),
    # Quality & Health (14)
    ("doctor",      "chk", "quality", "Check installation health & report issues"),
    ("lint",        "chk", "quality", "Validate SKILL.md frontmatter & quality"),
    ("audit",       "chk", "quality", "Check installed skills against a safety blocklist"),
    ("verify",      "chk", "quality", "Validate skill quality & lock-file integrity"),
    ("drift",       "chk", "quality", "Detect installed skills diverging from source"),
    ("test",        "chk", "quality", "Validate installed skills against quality checks"),
    ("fingerprint", "chk", "quality", "Deterministic hash of the skill environment"),
    ("quarantine",  "chk", "quality", "Isolate a problematic skill without uninstalling"),
    ("decay",       "chk", "quality", "Flag skills irrelevant to your current stack"),
    ("heal",        "chk", "quality", "Self-diagnose & repair the boost environment"),
    ("conflict",    "chk", "quality", "Detect contradictory rules between skills"),
    ("changelog",   "chk", "quality", "Show a skill's upstream change history"),
    ("attest",      "chk", "quality", "Display/verify the install record for skills"),
    ("health",      "chk", "quality", "Dashboard of skill-environment health"),
    # Configuration (10)
    ("config",      "cfg", "configuration", "Display or modify boost configuration"),
    ("clean",       "cfg", "configuration", "Clear stale caches & broken symlinks"),
    ("create",      "cfg", "configuration", "Scaffold a new skill from a template"),
    ("policy",      "cfg", "configuration", "Manage & enforce skill governance policies"),
    ("onboard",     "cfg", "configuration", "Add skill-tracker telemetry to a repo & open a PR"),
    ("completions", "cfg", "configuration", "Generate shell tab-completion scripts"),
    ("schedule",    "cfg", "configuration", "Manage automatic skill-sync scheduling"),
    ("serve",       "cfg", "configuration", "Serve the skill catalog over HTTP (port 8787)"),
    ("mcp",         "cfg", "configuration", "Register boost as an MCP server for Claude Code"),
    ("self-update", "cfg", "configuration", "Update boost itself to the latest version"),
    # Team & Collaboration (6)
    ("cohort",      "team", "team", "Controlled skill rollouts & team A/B testing"),
    ("profile",     "team", "team", "Named skill profiles for context switching"),
    ("protocol",    "team", "team", "Manage the boost:// one-click-install handler"),
    ("pulse",       "team", "team", "Team activity feed of skill-management events"),
    ("replay",      "team", "team", "View version history & roll back skills"),
    ("who",         "team", "team", "Discover who on the team has skill expertise"),
]

_BY_NAME = {name: (group, module, summary)
            for name, group, module, summary in COMMANDS}


def resolve(name: str):
    return _BY_NAME.get(name)


def print_version() -> None:
    print("%s %s" % (PRODUCT, __version__))


def print_help() -> None:
    print(out.c(PRODUCT, out.BOLD) + " — Homebrew for AI coding skills"
          + out.c("  (%s · v%s)" % (TAGLINE, __version__), out.DIM))
    print()
    print(out.c("Usage:", out.BOLD) + "  boost <command> [args]   "
          + out.c("boost help <command> for details", out.DIM))
    width = max(len(n) for n, _, _, _ in COMMANDS)
    for gkey, (_icon, title, desc) in GROUPS.items():
        cmds = [(n, s) for n, g, _m, s in COMMANDS if g == gkey]
        print()
        print(out.c("%s" % title, out.BOLD, out.YELLOW)
              + out.c("  — %s" % desc, out.DIM))
        for n, s in cmds:
            print("  " + out.c(n.ljust(width + 2), out.CYAN) + s)
    print()
    print(out.c("%d commands · %d groups" % (len(COMMANDS), len(GROUPS)), out.DIM))


def print_command_help(name: str) -> int:
    meta = resolve(name)
    if not meta:
        return _unknown(name)
    _group, module, summary = meta
    print(out.c("boost %s" % name, out.BOLD) + " — " + summary)
    # delegate to the command's own --help for flags
    return _dispatch(name, ["--help"], soft=True)


def _unknown(name: str) -> int:
    close = difflib.get_close_matches(name, list(_BY_NAME), n=3)
    out.err("unknown command: %s" % name,
            hint=("did you mean: %s?" % ", ".join(close)) if close
            else "see `boost --help`")
    return 2


def _dispatch(name: str, argv: List[str], soft: bool = False) -> int:
    group, module, _summary = _BY_NAME[name]
    mod = importlib.import_module("boost_cli.commands.%s" % module)
    func = getattr(mod, "cmd_%s" % name.replace("-", "_"), None)
    if func is None:
        if soft:
            return 0
        out.err("command %s is not implemented yet" % name)
        return 3
    rc = func(argv)
    return int(rc or 0)


def main(argv: List[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print_version()
        return 0
    if argv[0] == "help":
        if len(argv) > 1:
            return print_command_help(argv[1])
        print_help()
        return 0
    name, rest = argv[0], argv[1:]
    if name not in _BY_NAME:
        return _unknown(name)
    try:
        return _dispatch(name, rest)
    except BoostError as e:
        out.err(e.message, hint=e.hint)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0
