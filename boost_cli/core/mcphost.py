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
One argv rule of its own bites: **flags must precede the name**. The ``--``
boost also emits is agy's documented separator and, measured on 1.1.22, inert
— see :func:`add_argv`.

That upsert-vs-error asymmetry is also why `boost mcp register --host auto`
used to abort: Claude rejects the duplicate, and the sweep gave up before
reaching the next agent. Against agy alone it would never have surfaced.

Codex CLI is the fourth host, and it was a skills and rules target here before
it was an MCP one. Its grammar agrees with none of the other three outright:
``--env`` is **long-form only** (``-e`` is "unexpected argument '-e' found",
exit 2), flags are accepted on *either* side of the name, and ``--`` is
load-bearing rather than decorative — with it, a command that begins with a
dash is stored verbatim, where agy rejects the same thing outright. Like agy it
has **no scope** (one global ``$CODEX_HOME/config.toml``) and its ``add``
upserts, replacing the whole entry rather than erroring. Two things about
*where* it writes are its own, and both are in :func:`config_home`: the default
is ``$HOME/.codex/``, a subdirectory rather than ``$HOME`` itself, and a
**relative** ``CODEX_HOME`` is honoured against the current directory — the
exact opposite of Claude Code, which refuses one. Measured against codex-cli
0.156.1 on 2026-09-27.

The three ways the Claude and Gemini grammars differ, all of them
load-bearing:

* **Name position.** Both CLIs advertise the same usage string —
  ``[options] <name> <commandOrUrl> [args...]`` — so the shape is not the
  difference; the arity of ``-e`` is. Claude's is commander's variadic
  ``<env...>``, which keeps eating: a name placed *after* ``-e`` is swallowed
  as another env var ("Invalid environment variable format: boost"), so the
  name must lead. Gemini's is yargs with ``nargs: 1``, which takes exactly one
  value, so flags may precede the name safely.
* **The ``--`` separator, and where it goes.** Both need one; only Claude
  takes it *before* the command. Gemini takes it after —
  ``add <name> <command> -- <args...>`` — and rejects Claude's placement
  outright ("Not enough non-option arguments: got 1, need at least 2"),
  because yargs has then seen one non-option argument where it needs two.
  This note said for a long time that Gemini needed no separator at all,
  reasoning from ``unknown-options-as-args``; that setting rescues only
  options Gemini does **not** know, and ``mcp add`` knows ten of them
  (``-d``, ``-s``, ``-t``, ``-e``, ``-H``, ``--timeout``, ``--trust``,
  ``--description``, ``--include-tools``, ``--exclude-tools``). The claim held
  for as long as the only tail boost ever passed was its own ``mcp --stdio``,
  which Gemini does not know. It stopped holding the moment
  :func:`add_argv` began building arbitrary *skill-declared* command lines:
  the canonical GitHub server's ``-e GITHUB_PERSONAL_ACCESS_TOKEN`` was eaten
  by Gemini's own ``--env``, and the container launched with no token, exit 0.
  Measured on 0.61.0. (``populate--`` and the middleware that appends
  ``argv["--"]`` to the server args are both real and are what make the
  trailing separator work, including with an empty tail.)
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
CODEX = "codex"

# name -> {"cli": executable, "label": display name}. Order is the order hosts
# are tried and reported in; new hosts are appended so the existing order is
# untouched.
HOSTS: dict[str, dict] = {
    CLAUDE: {"cli": "claude", "label": "Claude Code"},
    GEMINI: {"cli": "gemini", "label": "Gemini CLI"},
    AGY: {"cli": "agy", "label": "Antigravity CLI"},
    CODEX: {"cli": "codex", "label": "Codex CLI"},
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


#: Hosts whose registrations are not scoped at all — one global file each,
#: so there is no local/user/project distinction to report or to pass.
_NO_SCOPE = frozenset({AGY, CODEX})


def has_scope(host: str) -> bool:
    """True when this host's registrations are scoped at all.

    Claude and Gemini keep local/user/project settings; agy and Codex each
    keep one global file. Reporting "(scope: user)" for those two would
    describe a distinction their CLIs do not have — and would send anyone
    looking for a project-scoped entry after something that cannot exist.
    """
    return host not in _NO_SCOPE


#: The environment variable a host resolves its configuration home from.
#: **Two of the four have one**, which is what keeps the guard below small.
#: Verified on 2026-09-27 against the installed CLIs: Claude Code 2.1.283's own
#: strings describe ``CLAUDE_CONFIG_DIR`` as naming "the configuration home …
#: the HOME it defaults from"; codex-cli 0.156.1 honours ``CODEX_HOME`` and
#: says so in its own error ("CODEX_HOME points to … but that path does not
#: exist"); Gemini CLI 0.57.0's ``GEMINI_DIR`` is a JS constant ``".gemini"``
#: and not an environment variable at all (only ``GEMINI_PROJECT_DIR`` exists,
#: and it moves the *project* dir); and Antigravity CLI exposes no config-dir
#: variable, inheriting Gemini's tree. A host absent from this table therefore
#: keeps its files under ``$HOME``.
CONFIG_HOME_ENV: dict[str, str] = {
    CLAUDE: "CLAUDE_CONFIG_DIR",
    CODEX: "CODEX_HOME",
}

#: Where a host's configuration home sits *inside* ``$HOME`` when its variable
#: is unset. Empty for three of the four: Claude's ``.claude.json`` and the two
#: Gemini-family files carry their own directory in :data:`USER_CONFIG_REL`,
#: so their home *is* ``$HOME``. Codex is the exception — ``CODEX_HOME``
#: defaults to ``$HOME/.codex`` and the file inside it is a bare
#: ``config.toml``, so the directory cannot ride along in the relative tail:
#: it applies in the unset branch only, and a ``CODEX_HOME`` that *is* set
#: names the directory itself. Measured: ``HOME=<tmp> codex mcp add …`` writes
#: ``<tmp>/.codex/config.toml``, and ``CODEX_HOME=<dir>`` writes
#: ``<dir>/config.toml``.
CONFIG_HOME_DEFAULT_REL: dict[str, tuple[str, ...]] = {
    CODEX: (".codex",),
}

#: Hosts that honour a **relative** configuration-home value by resolving it
#: against the current directory. Codex is the only one, and it is the exact
#: opposite of Claude Code, which refuses a relative ``CLAUDE_CONFIG_DIR``
#: outright — so the two cannot share a branch. It matters because the guard
#: is about *where the bytes land*: measured on 0.156.1, ``cd <dir> &&
#: CODEX_HOME=relprobe codex mcp add …`` wrote ``<dir>/relprobe/config.toml``,
#: which is a path no ``$HOME`` need contain. Falling back to ``home`` for it,
#: as Claude's branch does, would report the write contained when it is not.
RELATIVE_CONFIG_HOME_CWD = frozenset({CODEX})

#: Where each host keeps the user-scope registration ``mcp add`` writes,
#: relative to its configuration home. Claude's ``mcpServers`` live at the top
#: level of ``.claude.json``; Gemini's in ``.gemini/settings.json`` (the same
#: file :mod:`boost_cli.core.hookhost` writes hooks into); agy's in the global
#: ``.gemini/config/mcp_config.json`` it inherited, which is why it has no
#: scope; and Codex's ``[mcp_servers.<name>]`` tables in the ``config.toml``
#: at the root of its configuration home — a bare filename here because the
#: ``.codex`` directory is the *home*, supplied by
#: :data:`CONFIG_HOME_DEFAULT_REL` when ``CODEX_HOME`` is unset.
#: Components rather than a string so the join is native on Windows.
USER_CONFIG_REL: dict[str, tuple[str, ...]] = {
    CLAUDE: (".claude.json",),
    GEMINI: (".gemini", "settings.json"),
    AGY: (".gemini", "config", "mcp_config.json"),
    CODEX: ("config.toml",),
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


def config_home(host: str, env: Mapping[str, str], home: str,
                cwd: str | None = None) -> str:
    """Where ``host`` will look for its configuration, given ``env``.

    ``home`` is boost's own idea of the home directory (:func:`paths.home`),
    and is the answer — joined with :data:`CONFIG_HOME_DEFAULT_REL`, which is
    empty for every host but Codex — unless the host has a configuration-home
    variable set.

    An **absolute** value is that home. A **relative** one splits the hosts,
    and the split is measured rather than assumed:

    * Claude Code refuses it. 2.1.283 carries the literal message ``the
      configuration home (CLAUDE_CONFIG_DIR) is not an absolute path``, so
      boost falls back to ``home``. Treating it as a home would make boost
      report an escape for a config that writes nothing anywhere; falling back
      lets the CLI run and say so in its own words.
    * Codex honours it, against the **current directory** — measured on
      0.156.1, ``cd <dir> && CODEX_HOME=relprobe codex mcp add …`` wrote
      ``<dir>/relprobe/config.toml``. Falling back would call that write
      contained when ``<dir>`` need not be under ``$HOME`` at all.

    ``cwd`` defaults to :func:`os.getcwd`, and exists so the resolution is
    testable without chdir'ing the test process. It is read only for a host in
    :data:`RELATIVE_CONFIG_HOME_CWD` with a relative value set, so the common
    path stays free of ambient state.
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
    if value and os.path.isabs(value):  # noqa: FURB146
        return value
    if value and host in RELATIVE_CONFIG_HOME_CWD:
        here = os.getcwd() if cwd is None else cwd  # noqa: FURB104
        return os.path.join(here, value)
    return os.path.join(home, *CONFIG_HOME_DEFAULT_REL.get(host, ()))


def user_config_path(host: str, env: Mapping[str, str], home: str,
                     cwd: str | None = None) -> str:
    """The file ``host``'s user-scope ``mcp add``/``remove`` would write.

    Pure: the caller resolves and compares it (``scopes.contains``) against
    the home boost itself is running under. That comparison is the whole
    guard — an agent CLI resolves its own configuration from the ambient
    environment, not from the ``HOME`` boost was sandboxed with, so
    ``boost mcp register`` under ``HOME=<tempdir>`` really did write into a
    developer's live ``~/.claude-personal/.claude.json``.
    """
    return os.path.join(config_home(host, env, home, cwd),
                        *USER_CONFIG_REL[host])


def escapes_home(host: str, env: Mapping[str, str], home,
                 *, force: bool = False, cwd: str | None = None) -> str | None:
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
    cfg = user_config_path(host, env, str(home), cwd)
    if force or scopes.contains(home, cfg):
        return None
    return cfg


#: The flag each host spells "set this environment variable" with. ``-e`` for
#: three of them; Codex has **no short form** — ``codex mcp add x -e A=1 …``
#: exits 2 with "unexpected argument '-e' found", and its own tip ("to pass
#: '-e' as a value, use '-- -e'") is about the command, not the option. So the
#: spelling is per host rather than one constant.
ENV_FLAG: dict[str, str] = {CODEX: "--env"}


def _env_flags(env: dict[str, str] | None, flag: str = "-e") -> list[str]:
    """``<flag> KEY=VALUE`` pairs, sorted so the argv is deterministic."""
    if not env:
        return []
    out: list[str] = []
    for key in sorted(env):
        out += [flag, "%s=%s" % (key, env[key])]
    return out


def add_argv(host: str, name: str, command: str, tail: list[str], *,
             scope: str = "user",
             env: dict[str, str] | None = None) -> list[str]:
    """``<host> mcp add`` for *any* server — the one copy of that grammar.

    ``command`` plus ``tail`` is the server's own command line. There is one
    copy because there are two callers: :func:`register_argv` registers boost
    itself, and :func:`boost_cli.core.mcpdecl.register_argv` registers a server
    a skill declares. Those built the argv separately, and the second grew a
    Gemini branch and a Claude fallthrough while agy — the one host whose
    grammar rejects Claude's shape — fell through to Claude's, so every
    ``boost install`` of an MCP-declaring skill on a machine with agy on PATH
    failed. A shared builder makes that divergence unrepresentable rather than
    merely fixed.

    Raises KeyError for an unknown host, and ValueError for a known host with
    no grammar here — see the tail of this function for why that matters.
    """
    exe = cli(host)
    flags = _env_flags(env, ENV_FLAG.get(host, "-e"))
    if host == CODEX:
        # [OPTIONS] <NAME> (--url <URL> | -- <COMMAND>...), and of the four
        # hosts this is the most forgiving shape: flags are accepted on either
        # side of the name (unlike agy, which rejects one after it) and the
        # `--` may be dropped when the command does not begin with a dash
        # (`add nosep /bin/echo mcp --stdio` stores args ["mcp", "--stdio"]).
        #
        # It is emitted anyway, and here that is not decoration: Codex's usage
        # string names it, and with it a command that *does* begin with a dash
        # is stored verbatim (`add dashy -- -weird arg` -> command "-weird"),
        # where agy rejects the same thing outright. The one rule with no give
        # is the flag spelling — see ENV_FLAG.
        #
        # No `--scope`: Codex keeps one global $CODEX_HOME/config.toml and
        # says so in its own output ("Added global MCP server 'boost'.").
        # Measured on codex-cli 0.156.1.
        return [exe, "mcp", "add", *flags, name, "--", command, *tail]
    if host == AGY:
        # [flags] <name> <commandOrUrl> [args...]. Flags must come BEFORE the
        # name — a flag after it is rejected — and there is no scope: agy keeps
        # one global file (~/.gemini/config/mcp_config.json, inherited from
        # Gemini CLI — there is no ~/.antigravity), so `--scope` would be an
        # error rather than a no-op.
        #
        # The `--` is agy's documented separator ("Use -- before the command to
        # pass a command or args that begin with '-'") and, measured on 1.1.22,
        # it is inert: agy never consumes an argument that *follows* the
        # command, not even one of its own flags (`add I npx -t http` stores
        # ["-t", "http"]), and a command that itself begins with a dash is
        # rejected with or without it ("invalid command \"-weird\": flags must
        # come before the server name"). So it is emitted because agy's help
        # says to and it costs nothing — not because a case here needs it.
        return [exe, "mcp", "add", *flags, name, "--", command, *tail]
    if host == GEMINI:
        # [options] <name> <commandOrUrl> [args...], and the separator goes
        # AFTER the command — the one host where it does. Before it, Claude's
        # way, yargs counts one non-option argument and fails ("Not enough
        # non-option arguments: got 1, need at least 2").
        #
        # It is not optional. `unknown-options-as-args` rescues only options
        # gemini does *not* know, and `gemini mcp add` knows ten: -d/--debug,
        # -s/--scope, -t/--transport/--type, -e/--env, -H/--header, --timeout,
        # --trust, --description, --include-tools, --exclude-tools. A skill
        # declaring the canonical GitHub server — `docker run -i --rm -e
        # GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/…` — had its `-e` pair claimed
        # by gemini's own `--env` (`nargs: 1`, so it takes the name as its one
        # value) and the container launched without the token, exit 0, no
        # warning. The `-e KEY=value` spelling is not dropped but *relocated*:
        # it lands in gemini's own `env` map, out of the args docker reads, so
        # the container is just as tokenless. `-t http` is worse: the entry is
        # rewritten as {"url": "npx", "type": "http"}. Measured on 0.61.0.
        #
        # Unconditional, including for an empty tail: `add x npx --` is
        # accepted and stores `args: []`.
        return [exe, "mcp", "add", "--scope", scope, *flags,
                name, command, "--", *tail]
    if host == CLAUDE:
        # <name> [options] -- <command>: the name MUST precede the variadic -e.
        return [exe, "mcp", "add", name, "--scope", scope, *flags,
                "--", command, *tail]
    # A row in HOSTS with no branch above. Claude's shape used to be the
    # fallthrough, which is how agy came to be handed an argv its CLI rejects;
    # a host is added to the table and to this function or not at all.
    raise ValueError("no `mcp add` grammar for host %r" % host)


def register_argv(host: str, launcher: str, *, scope: str = "user",
                  name: str = SERVER_NAME,
                  env: dict[str, str] | None = None) -> list[str]:
    """The argv that registers boost as an MCP server with ``host``.

    ``launcher`` is the absolute path other processes should use to invoke
    boost (:func:`paths.launcher`). ``env`` defaults to :data:`LAUNCH_ENV`;
    pass ``{}`` for none. Raises KeyError for an unknown host.
    """
    return add_argv(host, name, launcher, ["mcp", "--stdio"], scope=scope,
                    env=LAUNCH_ENV if env is None else env)


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
    if host == CODEX:
        # `codex mcp remove <NAME>`: one global file, so no scope, and it is
        # idempotent — removing a name that is not there exits 0 with "No MCP
        # server named 'x' found." (`get` is the one that exits 1, which is
        # why a presence probe would have to use `get`). That wording is why
        # _NOT_REGISTERED carries a second marker.
        return [exe, "mcp", "remove", name]
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
#: ``"not found"`` catches Claude and Gemini. Codex needs its own: 0.156.1
#: prints ``No MCP server named 'boost' found.`` and exits 0, which contains
#: "found" but never "not found" — so without this marker an unregister
#: against nothing registered would be reported as a removal that happened.
_NOT_REGISTERED = ("not found", "no mcp server named")


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
