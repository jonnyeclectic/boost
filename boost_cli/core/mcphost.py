# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which agent CLIs can boost register itself with, and how.

``boost mcp register`` used to build one hardcoded ``claude mcp add …`` argv.
Claude Code is no longer the only host that speaks MCP — Gemini CLI does too —
and the two CLIs agree on the *concept* while disagreeing on almost every
detail of the grammar. This module is the table of those differences, kept pure
and I/O-free (like :mod:`boost_cli.core.mcpdecl`) so every branch is unit
testable and reachable by the mutation gate; the command layer does the
``shutil.which`` probing and the ``subprocess.run``.

Antigravity CLI (``agy``) is the third host, and it is Gemini CLI's successor
rather than a variant of it: Gemini is being deprecated in its favour. Its
``add`` **upserts** where Claude's errors on a duplicate name, it has **no
scope** (one global file at ``~/.gemini/config/mcp_config.json`` — it inherited
Gemini's directory, so there is no ``~/.antigravity``), its off-switch is
``enable``/``disable`` rather than removal, and it has no per-server ``get``.
Its two argv rules come from its own help and both bite: **flags must precede
the name**, and **``--`` must precede a command whose args start with ``-``**,
or ``--stdio`` is eaten as an agy flag.

That upsert-vs-error asymmetry is also why `boost mcp register --host auto`
used to abort: Claude rejects the duplicate, and the sweep gave up before
reaching the next agent. Against agy alone it would never have surfaced.

The three ways the Claude and Gemini grammars differ, all of them
load-bearing:

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
* **Unregister scope.** ``gemini mcp remove`` defaults to ``--scope project``
  and returns after logging "not found in project settings" — exit status 0,
  user-scope entry untouched — so the scope flag is mandatory on the way out,
  not just in. This is the one difference here with a silent-failure mode,
  which is why it is pinned twice. ``claude mcp remove`` is the opposite and
  needs no flag: "if not specified, removes from whichever scope it exists
  in". boost passes ``--scope`` anyway, and that is a deliberate narrowing
  rather than belt-and-braces — see the next paragraph. Its ``local`` and
  ``user`` scopes both live in the configuration home, but ``project`` scope
  is ``<cwd>/.mcp.json``, which no ``HOME`` contains, so a scope-less remove
  can reach a committed file the guard below has not vouched for. boost only
  ever *registers* at user scope, so removing at user scope is the symmetric
  answer as well as the containable one.

**Where each host writes, and why boost refuses rather than redirects.**
A host CLI resolves its own configuration from the ambient environment, not
from the ``HOME`` boost is running under, so shelling out to ``claude mcp add``
from a run sandboxed with ``HOME=<tempdir>`` registered boost in the
developer's live ``~/.claude-personal/.claude.json``. :data:`CONFIG_HOME_ENV`
and :data:`USER_CONFIG_REL` name the file each host would touch, and the
command layer refuses when boost's own ``HOME`` does not contain it. Refusing
is the deliberate half: boost *could* set ``CLAUDE_CONFIG_DIR`` for the child
and redirect the write, but that re-points a user who set it on purpose and
reports success for a file their CLI never reads. ``--force`` is the way
through, and the refusal names the path and prints the argv.

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

import os.path
from collections.abc import Mapping

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
AGY = "agy"

# name -> {"cli": executable, "label": display name}. Order is the order hosts
# are tried and reported in; new hosts are appended so the existing order is
# untouched.
HOSTS: dict[str, dict] = {
    CLAUDE: {"cli": "claude", "label": "Claude Code"},
    GEMINI: {"cli": "gemini", "label": "Gemini CLI"},
    AGY: {"cli": "agy", "label": "Antigravity CLI"},
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


def has_scope(host: str) -> bool:
    """True when this host's registrations are scoped at all.

    Claude and Gemini keep local/user/project settings; agy keeps one global
    file. Reporting "(scope: user)" for agy would describe a distinction its
    CLI does not have — and would send anyone looking for a project-scoped
    entry after something that cannot exist.
    """
    return host != AGY


#: The environment variable a host resolves its configuration home from.
#: **Claude Code is the only one**, which is what makes the guard below small.
#: Verified on 2026-09-27 against the installed CLIs: Claude Code 2.1.283's own
#: strings describe ``CLAUDE_CONFIG_DIR`` as naming "the configuration home …
#: the HOME it defaults from"; Gemini CLI 0.57.0's ``GEMINI_DIR`` is a JS
#: constant ``".gemini"`` and not an environment variable at all (only
#: ``GEMINI_PROJECT_DIR`` exists, and it moves the *project* dir); and
#: Antigravity CLI exposes no config-dir variable, inheriting Gemini's tree.
#: A host absent from this table therefore keeps its files under ``$HOME``.
CONFIG_HOME_ENV: dict[str, str] = {
    CLAUDE: "CLAUDE_CONFIG_DIR",
}

#: Where each host keeps the user-scope registration ``mcp add`` writes,
#: relative to its configuration home. Claude's ``mcpServers`` live at the top
#: level of ``.claude.json``; Gemini's in ``.gemini/settings.json`` (the same
#: file :mod:`boost_cli.core.hookhost` writes hooks into); agy's in the global
#: ``.gemini/config/mcp_config.json`` it inherited, which is why it has no
#: scope. Components rather than a string so the join is native on Windows.
USER_CONFIG_REL: dict[str, tuple[str, ...]] = {
    CLAUDE: (".claude.json",),
    GEMINI: (".gemini", "settings.json"),
    AGY: (".gemini", "config", "mcp_config.json"),
}


def config_home_env(host: str) -> str | None:
    """The env var ``host`` reads its configuration home from, or ``None``.

    ``None`` is the common answer and means "this host is anchored at
    ``$HOME``". Raises KeyError for an unknown host, like the rest of this
    table.
    """
    if host not in HOSTS:
        raise KeyError(host)
    return CONFIG_HOME_ENV.get(host)


def config_home(host: str, env: Mapping[str, str], home: str) -> str:
    """Where ``host`` will look for its configuration, given ``env``.

    ``home`` is boost's own idea of the home directory (:func:`paths.home`),
    and is the answer unless the host has a configuration-home variable set to
    an **absolute** path. A relative value falls back to ``home`` because the
    CLI itself refuses it rather than resolving it: Claude Code 2.1.283 carries
    the literal message ``the configuration home (CLAUDE_CONFIG_DIR) is not an
    absolute path``. Treating it as a home would make boost report an escape
    for a config that writes nothing anywhere; falling back lets the CLI run
    and say so in its own words.
    """
    var = config_home_env(host)
    value = (env.get(var) or "").strip() if var else ""
    # `os.path.isabs`, not `Path(value).is_absolute()`. The two disagree only
    # on Windows, for a drive-less `/foo`: `ntpath.isabs` says True on 3.12 and
    # False on 3.13+, `PureWindowsPath` says False on both (the trap
    # `registry.py` documents for a tap spec), and the host CLI is a Node
    # program whose `path.win32.isAbsolute("/foo")` says True. Nothing models
    # all three, and nothing is written outside boost's $HOME either way —
    # this branch only decides whether boost or the CLI reports the refusal —
    # so switching would add a third answer and buy nothing.
    return value if value and os.path.isabs(value) else home  # noqa: FURB146


def user_config_path(host: str, env: Mapping[str, str], home: str) -> str:
    """The file ``host``'s user-scope ``mcp add``/``remove`` would write.

    Pure: the caller resolves and compares it (``scopes.contains``) against
    the home boost itself is running under. That comparison is the whole
    guard — an agent CLI resolves its own configuration from the ambient
    environment, not from the ``HOME`` boost was sandboxed with, so
    ``boost mcp register`` under ``HOME=<tempdir>`` really did write into a
    developer's live ``~/.claude-personal/.claude.json``.
    """
    return os.path.join(config_home(host, env, home), *USER_CONFIG_REL[host])


def escapes_home(host: str, env: Mapping[str, str], home,
                 *, force: bool = False) -> str | None:
    """The file ``host`` would write, when it is **outside** ``home``.

    ``None`` means the write is contained (or ``force`` was asked for) and the
    caller may shell out. This is the one function in this module that touches
    the filesystem — :func:`scopes.contains` resolves both sides, which is what
    makes it right on macOS, where a ``$HOME`` under ``/var/folders`` resolves
    to ``/private/var/...`` and comparing one resolved path against one nominal
    path never matches. It lives here rather than in the command layer anyway,
    because a guard the mutation gate cannot see is a guard that can rot: the
    gate runs ``tests/unit`` over ``boost_cli/core``, so a mutant flipping
    ``force`` or dropping the containment test has to be killed by a test
    rather than by a reviewer. Three call sites share it.
    """
    from . import scopes
    cfg = user_config_path(host, env, str(home))
    if force or scopes.contains(home, cfg):
        return None
    return cfg


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
    if host == AGY:
        # [flags] <name> <commandOrUrl> [args...], and both of its rules bite
        # here. Flags must come BEFORE the name — a flag after it is rejected —
        # and `--` must precede a command whose own args start with `-`, or
        # `--stdio` is eaten as an agy flag rather than passed to boost. There
        # is no scope: agy keeps one global file
        # (~/.gemini/config/mcp_config.json, inherited from Gemini CLI — there
        # is no ~/.antigravity), so passing `--scope` would be an error rather
        # than a no-op.
        return [exe, "mcp", "add", *flags, name,
                "--", launcher, "mcp", "--stdio"]
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
    Claude gets one for the opposite reason: without it, 2.1.283 "removes from
    whichever scope it exists in", and one of those scopes is
    ``<cwd>/.mcp.json`` — a committed file outside every ``HOME``, which
    :func:`escapes_home` therefore cannot vouch for. Passing the scope makes
    the argv match the file that was checked, and matches the register side,
    which only ever writes user scope. agy has no scopes at all.
    """
    exe = cli(host)
    if host == GEMINI:
        return [exe, "mcp", "remove", "--scope", scope, name]
    if host == AGY:
        # No scope flag: one global file. `agy mcp remove --help` on 1.1.22
        # gives `agy mcp remove <name> [flags]` with only `-h`/`--help` — so
        # the name is positional and there is no scope to pass, which is this
        # argv. (This note used to say `remove` was inferred from Claude's
        # shape because only `add`, `enable` and `disable` had been read off
        # agy's help. It has now been read: the guess was right, and it is no
        # longer a guess.)
        return [exe, "mcp", "remove", name]
    return [exe, "mcp", "remove", "--scope", scope, name]


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


def is_named(requested: str | None) -> bool:
    """True when ``requested`` names exactly one host — not unset/``auto``/``all``.

    A missing CLI is not an error under ``auto`` (most machines have one agent
    CLI, not all three) or ``all`` (deliberately shows every host's argv, installed
    or not — see :func:`resolve`'s docstring). Naming exactly one host and finding
    its CLI absent is a different situation: a script that ran
    ``boost mcp --host gemini`` and got exit 0 for a no-op cannot tell "it worked"
    from "gemini is not installed here" without parsing prose.
    """
    return requested not in (None, "", "auto", "all")


#: Substrings an agent CLI uses to say "this server is already registered" —
#: shared with :func:`classify_result`, register direction.
_ALREADY = ("already exists", "already registered", "already configured")

#: Substrings an agent CLI uses to say "no such server was registered" —
#: Gemini's own ``mcp remove --scope user boost`` prints
#: ``Server "boost" not found in user settings.`` on stderr and still exits 0,
#: so without this an unregister against nothing registered read as success.
_NOT_REGISTERED = ("not found",)


def classify_result(action: str, returncode: int, stdout: str, stderr: str) -> tuple[str, str]:
    """Classify a finished (un)register subprocess into ``(status, detail)``.

    Status is one of:

    * ``"ran"``            — the CLI ran and did what was asked;
    * ``"already"``        — register reported the server already exists,
      which is success worded differently;
    * ``"not_registered"`` — unregister reported there was nothing to remove,
      likewise success worded differently;
    * ``"failed"``         — a non-zero exit with none of the above markers.

    Pure over the text a finished child process produced — launching it and
    detecting a missing CLI (``shutil.which``) needs the filesystem and stays
    in the command layer, which is what makes every branch here reachable
    without a real ``claude``/``gemini``/``agy`` on PATH.
    """
    blob = (stderr + stdout).lower()
    if action == "unregister" and returncode == 0 and any(
            k in blob for k in _NOT_REGISTERED):
        return "not_registered", ""
    if returncode == 0:
        return "ran", ""
    if action == "register" and any(k in blob for k in _ALREADY):
        return "already", ""
    tail = stderr.strip().splitlines()
    return "failed", tail[-1] if tail else "unknown error"
