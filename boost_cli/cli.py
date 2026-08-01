"""boost CLI dispatcher — 78 commands across 8 groups.

Each command lives in boost_cli/commands/<module>.py as
    def cmd_<name_with_underscores>(argv: list[str]) -> int
Modules are imported lazily so `boost --help` stays instant.
"""
from __future__ import annotations

import contextlib
import difflib
import importlib
import sys
import time
from typing import List

from . import PRODUCT, TAGLINE, __version__
from .core import logs, nethttp
from .core import output as out
from .errors import BoostError

# Global flags handled before dispatch, stripped from the command's own argv.
_GLOBAL_FLAGS = {
    "--verbose": "verbose", "-v": "verbose",
    "--debug": "debug",
    "--quiet": "quiet", "-q": "quiet",
}

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
    # Package Management (14)
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
    ("adapt",       "pkg", "pkg", "Render a skill as another framework's agent source (CrewAI, Agents SDK)"),
    ("run",         "pkg", "run", "Adapt a skill, wire tools & run it as a live agent"),
    # Discovery & Search (9)
    ("search",      "find", "discovery", "Search skills across tap registries (AI-ranked)"),
    ("reindex",     "find", "discovery", "Build/refresh the full-content search index"),
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
    ("chat",        "ai", "intelligence", "Ask about skills in plain language (RAG-grounded)"),
    ("distill",     "ai", "intelligence", "Merge multiple skills into one deduplicated skill"),
    ("simulate",    "ai", "intelligence", "Preview how a skill would change Claude's behavior"),
    ("infer",       "ai", "intelligence", "Generate a SKILL.md from your codebase patterns"),
    ("absorb",      "ai", "intelligence", "Turn recurring chat-history patterns into a skill"),
    ("evolve",      "ai", "intelligence", "Iteratively improve a skill from feedback"),
    ("context",     "ai", "intelligence", "Branch-aware skill activation"),
    ("focus",       "ai", "intelligence", "Temporarily prioritize skills for a work session"),
    ("impact",      "ai", "intelligence", "Measure a skill's influence on code quality"),
    # Quality & Health (15)
    ("doctor",      "chk", "quality", "Check installation health & report issues"),
    ("lint",        "chk", "quality", "Validate SKILL.md frontmatter & quality"),
    ("audit",       "chk", "safety", "Check installed skills against a safety blocklist"),
    ("verify",      "chk", "safety", "Validate skill quality & lock-file integrity"),
    ("drift",       "chk", "quality", "Detect installed skills diverging from source"),
    ("test",        "chk", "quality", "Validate installed skills against quality checks"),
    ("fingerprint", "chk", "quality", "Deterministic hash of the skill environment"),
    ("quarantine",  "chk", "safety", "Isolate a problematic skill without uninstalling"),
    ("decay",       "chk", "quality", "Flag skills irrelevant to your current stack"),
    ("heal",        "chk", "quality", "Self-diagnose & repair the boost environment"),
    ("conflict",    "chk", "quality", "Detect contradictory rules between skills"),
    ("changelog",   "chk", "quality", "Show a skill's upstream change history"),
    ("attest",      "chk", "safety", "Display/verify the install record for skills"),
    ("health",      "chk", "quality", "Dashboard of skill-environment health"),
    ("trust",       "chk", "quality", "Manage signing keys & verify tap provenance"),
    # Configuration (12)
    ("config",      "cfg", "configuration", "Display or modify boost configuration"),
    ("clean",       "cfg", "configuration", "Clear stale caches & broken symlinks"),
    ("create",      "cfg", "configuration", "Scaffold a new skill from a template"),
    ("policy",      "cfg", "configuration", "Manage & enforce skill governance policies"),
    ("onboard",     "cfg", "configuration", "Add skill-tracker telemetry to a repo & open a PR"),
    ("completions", "cfg", "configuration", "Generate shell tab-completion scripts"),
    ("schedule",    "cfg", "configuration", "Manage automatic skill-sync scheduling"),
    ("serve",       "cfg", "configuration", "Serve the skill catalog over HTTP (port 8787)"),
    ("mcp",         "cfg", "configuration", "Register boost as an MCP server (Claude Code, Gemini CLI)"),
    ("hooks",       "cfg", "hooks", "Manage Claude Code hooks (scope-aware) in settings.json"),
    ("bmad",        "cfg", "bmad", "Install & manage the BMAD Method (scope-aware, toggleable)"),
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


# Per-group accent hue — mirrors the roadmap's colored track-icons, cycling the
# Aurora palette so each command group carries its own brand color.
_GROUP_HUES = ("cyan", "violet", "pink", "green", "yellow")


def print_help() -> None:
    print(out.gradient(PRODUCT) + " — Homebrew for AI coding skills"
          + out.c("  (%s · v%s)" % (TAGLINE, __version__), out.DIM))
    print()
    print(out.c("Usage:", out.BOLD) + "  boost <command> [args]   "
          + out.c("boost help <command> for details", out.DIM))
    width = max(len(n) for n, _, _, _ in COMMANDS)
    for idx, (gkey, (_icon, title, desc)) in enumerate(GROUPS.items()):
        cmds = [(n, s) for n, g, _m, s in COMMANDS if g == gkey]
        bullet = out.aurora("●", _GROUP_HUES[idx % len(_GROUP_HUES)])
        print()
        print(bullet + " " + out.c(title, out.BOLD)
              + out.c("  — %s" % desc, out.DIM))
        for n, s in cmds:
            print("  " + out.c(n.ljust(width + 2), out.CYAN) + s)
    print()
    print(out.c("%d commands · %d groups" % (len(COMMANDS), len(GROUPS)), out.DIM))


def print_command_help(name: str) -> int:
    meta = resolve(name)
    if not meta:
        return _unknown(name)
    _group, _module, summary = meta
    print(out.c("boost %s" % name, out.BOLD) + " — " + summary)
    # delegate to the command's own --help for flags
    return _dispatch(name, ["--help"], soft=True)


def _crash_hint(report) -> str:
    where = ("a crash report was written to %s" % report if report
             else "set BOOST_DEBUG=1 to see the full traceback")
    return "%s — re-run with --debug for the traceback, or file it at %s" % (
        where, "https://github.com/jonnyeclectic/boost/issues")


def _unknown(name: str) -> int:
    close = difflib.get_close_matches(name, list(_BY_NAME), n=3)
    out.err("unknown command: %s" % name,
            hint=("did you mean: %s?" % ", ".join(close)) if close
            else "see `boost --help`")
    return 2


def _complete_candidates(argv: List[str]) -> int:
    """`boost __complete <words…>` — one candidate per line, for a shell.

    Runs on every TAB, so it never fails loudly: core.complete swallows its own
    errors and a traceback here would land in the line the user is typing.
    """
    from .core import complete
    for candidate in complete.candidates(argv.copy(), COMMANDS):
        print(candidate)
    return 0


_PLUMBING = {"__complete": _complete_candidates}


def _dispatch(name: str, argv: List[str], soft: bool = False) -> int:
    _group, module, _summary = _BY_NAME[name]
    mod = importlib.import_module("boost_cli.commands.%s" % module)
    func = getattr(mod, "cmd_%s" % name.replace("-", "_"), None)
    if func is None:
        if soft:
            return 0
        out.err("command %s is not implemented yet" % name)
        return 3
    rc = func(argv)
    return int(rc or 0)


def _extract_globals(argv: List[str]) -> tuple[dict, List[str]]:
    """Peel leading global flags (`boost --debug install …`) off argv.

    Only flags *before* the command name are treated as global, so a
    subcommand keeps its own `--verbose`/`-q` (e.g. `boost lint --verbose`).
    """
    opts = {"verbose": False, "debug": False, "quiet": False}
    i = 0
    while i < len(argv) and argv[i] in _GLOBAL_FLAGS:
        opts[_GLOBAL_FLAGS[argv[i]]] = True
        i += 1
    return opts, argv[i:]


def main(argv: List[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out.harden_console_encoding()
    # Belt-and-suspenders fork safety: a host may fork() into `boost mcp
    # --stdio` without the no_proxy env boost injects at registration, leaving
    # the process one default getproxies() away from a macOS _scproxy SIGABRT.
    # Seed the guard for every invocation before any code path can trip it.
    nethttp.harden_fork_safety()
    opts, argv = _extract_globals(argv)
    logs.configure(verbose=opts["verbose"], debug=opts["debug"],
                   quiet=opts["quiet"])
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
    if name in _PLUMBING:
        # Before the _BY_NAME guard (it is not a command) and before
        # log_invocation: this runs on every TAB, and logging a line per
        # keystroke would bury the diagnostic log in completion noise.
        return _PLUMBING[name](rest)
    if name not in _BY_NAME:
        return _unknown(name)
    logs.log_invocation([name, *rest])
    start = time.perf_counter()
    rc = 70  # assume the worst until a handler proves otherwise
    try:
        rc = _dispatch(name, rest)
        return rc
    except BoostError as e:
        logs.get_logger().info("BoostError: %s", e.message)
        rc = 1
        out.err(e.message, hint=e.hint)
        return rc
    except KeyboardInterrupt:
        logs.get_logger().debug("interrupted by user")
        rc = 130
        print()
        return rc
    except BrokenPipeError:
        with contextlib.suppress(Exception):
            sys.stdout.close()
        rc = 0
        return rc
    except Exception as e:
        report = logs.write_crash_report(e, [name, *rest])
        if logs.is_debug():
            raise
        out.err("boost hit an unexpected error: %s: %s"
                % (type(e).__name__, e),
                hint=_crash_hint(report))
        return 70  # EX_SOFTWARE
    finally:
        # Bookend every invocation with its exit code + duration, even when the
        # --debug path re-raises the traceback above.
        logs.log_completion([name, *rest], rc,
                            (time.perf_counter() - start) * 1000)
