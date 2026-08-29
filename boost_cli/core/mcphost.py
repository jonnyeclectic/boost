# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Which agent CLIs can boost register itself with, and how.

``boost mcp register`` used to build one hardcoded ``claude mcp add …`` argv.
Claude Code is no longer the only host that speaks MCP — Gemini CLI does too —
and the two CLIs agree on the *concept* while disagreeing on almost every
detail of the grammar. This module is the table of those differences, kept pure
and I/O-free (like :mod:`boost_cli.core.mcpdecl`) so every branch is unit
testable and reachable by the mutation gate; the command layer does the
``shutil.which`` probing and the ``subprocess.run``.

The three ways the two grammars differ, all of them load-bearing:

* **Name position.** Both CLIs advertise the same usage string —
  ``[options] <name> <commandOrUrl> [args...]`` — so the shape is not the
  difference; the arity of ``-e`` is. Claude's is commander's variadic
  ``<env...>``, which keeps eating: a name placed *after* ``-e`` is swallowed
  as another env var ("Invalid environment variable format: boost"), so the
  name must lead. Gemini's is yargs with ``nargs: 1``, which takes exactly one
  value, so flags may precede the name safely.
* **The ``--`` separator.** Claude needs one to stop flag parsing before the
  server's own command. Gemini does not: its ``add`` sets yargs
  ``unknown-options-as-args``, so a bare ``--stdio`` already lands in
  ``[args...]`` as a literal. boost therefore omits it because it is
  *redundant* — not, as this note claimed until 2026-08-28, because Gemini
  would capture it and hand it to boost. It would not, and never would have:
  ``add`` also sets ``populate--`` and a middleware that appends ``argv["--"]``
  to the server args, both already present in the v0.46.0 source this file
  first cited. The argv was right; only the reason for it was wrong.
* **Unregister scope.** ``claude mcp remove`` finds the server in whichever
  scope holds it, without being told. ``gemini mcp remove`` defaults to
  ``--scope project`` and returns after logging "not found in project
  settings" — exit status 0, user-scope entry untouched — so the scope flag is
  mandatory on the way out, not just in. This is the one difference here with a
  silent-failure mode, which is why it is pinned twice.

Verified against the real CLIs — Claude Code 2.1.251 and Gemini CLI 0.57.0 — on
2026-08-28, by running every argv below against a throwaway ``HOME`` *and*
working directory (Gemini writes ``project`` scope to ``./.gemini``, so ``HOME``
alone does not sandbox it) and reading back the settings each one wrote, plus
the deliberate near-misses: the swallowed name above is a real 2.1.251 message,
not a remembered one. Gemini's yargs definitions were read from its installed
bundle as well, to pin *why* each argv works and not merely *that* it does.
Both are also pinned by tests, because an argv that is merely
*plausible* fails at the worst possible moment: silently, on someone else's
machine — and prose that is merely plausible fails the same way, one reader at
a time, which is what the ``--`` bullet above cost.
"""
from __future__ import annotations

# The MCP server name boost registers itself under. Deliberately free of
# underscores: Gemini CLI assigns every MCP tool the fully-qualified name
# ``mcp_{server}_{tool}`` and its policy parser splits on the first underscore
# after ``mcp_``, so an underscore in the server name makes wildcard policy
# rules silently mis-target.
SERVER_NAME = "boost"

# Env vars every host launches boost with. A host that fork()s into
# `boost mcp --stdio` on macOS can SIGABRT on the child side *pre-exec* if
# Obj-C is touched post-fork (CFPreferences / _scproxy proxy lookup). Disabling
# the fork-safety trap and short-circuiting proxy resolution keeps the host's
# fork into boost from aborting before our Python ever runs.
LAUNCH_ENV = {
    "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES",
    "no_proxy": "*",
}

CLAUDE = "claude"
GEMINI = "gemini"

# name -> {"cli": executable, "label": display name}. Order is the order hosts
# are tried and reported in.
HOSTS: dict[str, dict] = {
    CLAUDE: {"cli": "claude", "label": "Claude Code"},
    GEMINI: {"cli": "gemini", "label": "Gemini CLI"},
}


def hosts() -> list[str]:
    """Known host ids, in registration order."""
    return list(HOSTS)


def cli(host: str) -> str:
    """The executable name for ``host``. Raises KeyError if unknown."""
    return str(HOSTS[host]["cli"])


def label(host: str) -> str:
    """Display name for ``host`` (``gemini`` -> "Gemini CLI")."""
    return str(HOSTS[host]["label"])


def _env_flags(env: dict[str, str] | None) -> list[str]:
    """``-e KEY=VALUE`` pairs, sorted so the argv is deterministic."""
    if not env:
        return []
    out: list[str] = []
    for key in sorted(env):
        out += ["-e", "%s=%s" % (key, env[key])]
    return out


def register_argv(host: str, launcher: str, *, scope: str = "user",
                  name: str = SERVER_NAME,
                  env: dict[str, str] | None = None) -> list[str]:
    """The argv that registers boost as an MCP server with ``host``.

    ``launcher`` is the absolute path other processes should use to invoke
    boost (:func:`paths.launcher`). ``env`` defaults to :data:`LAUNCH_ENV`;
    pass ``{}`` for none. Raises KeyError for an unknown host.
    """
    exe = cli(host)
    flags = _env_flags(LAUNCH_ENV if env is None else env)
    if host == GEMINI:
        # [options] <name> <commandOrUrl> [args...]. No `--`: yargs
        # `unknown-options-as-args` already carries `--stdio` into [args...],
        # so a separator would be redundant rather than harmful.
        return ([exe, "mcp", "add", "--scope", scope, *flags,
                 name, launcher, "mcp", "--stdio"])
    # <name> [options] -- <command>: the name MUST precede the variadic -e.
    return ([exe, "mcp", "add", name, "--scope", scope, *flags,
             "--", launcher, "mcp", "--stdio"])


def unregister_argv(host: str, *, scope: str = "user",
                    name: str = SERVER_NAME) -> list[str]:
    """The argv that removes boost's MCP registration from ``host``.

    Gemini gets an explicit ``--scope`` because its ``remove`` defaults to
    ``project`` and would otherwise no-op against a user-scope registration.
    Claude's ``remove`` takes no scope flag.
    """
    exe = cli(host)
    if host == GEMINI:
        return [exe, "mcp", "remove", "--scope", scope, name]
    return [exe, "mcp", "remove", name]


def argv(host: str, action: str, launcher: str = "", *,
         scope: str = "user", name: str = SERVER_NAME) -> list[str]:
    """Dispatch to :func:`register_argv` / :func:`unregister_argv`.

    Raises ValueError for an action that is neither ``register`` nor
    ``unregister``, so a typo in the command layer fails loudly here rather
    than building a nonsense command line.
    """
    if action == "register":
        return register_argv(host, launcher, scope=scope, name=name)
    if action == "unregister":
        return unregister_argv(host, scope=scope, name=name)
    raise ValueError("unknown MCP host action %r" % action)


def resolve(requested: str | None) -> list[str]:
    """Which hosts a ``--host`` value selects, validated.

    ``None`` or ``"auto"`` means "every known host" — the command layer then
    skips the ones whose CLI is not installed. ``"all"`` is the same set but
    *without* that skip, for a user who wants the argv printed for a host they
    have not installed yet. Anything else must name exactly one known host.
    """
    if requested in (None, "", "auto", "all"):
        return hosts()
    if requested not in HOSTS:
        raise KeyError(requested)
    return [requested]
