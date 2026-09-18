# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""boost bmad — the BMAD Method as a one-command, global autopilot.

There are two surfaces here, and the split is the whole design.

**The autopilot** is `boost bmad on`. One command, global by default, no Node
and no network: it writes the seven BMAD persona subagents into
`~/.claude/agents/`, and installs two hooks — a `SessionStart` briefing and a
`UserPromptSubmit` router. After that, every substantive prompt arrives already
carrying the persona that should lead it, the support personas to spawn
alongside, the BMAD skill for that track, and a definition of done read off the
repo in front of it (its test dir, its docs, its roadmap items, its gate
command). Trivial asks get no banner. All
of the thinking lives in :mod:`boost_cli.core.bmad`; this module is glue.

    boost bmad on                          # <- the one command. global.
    boost bmad off                         # remove hooks + boost-written personas
    boost bmad personas                    # the roster + whether installed, both scopes
    boost bmad route [PROMPT] [--plain]    # hook target; pipeable for debugging
    boost bmad on --host claude            # hooks for one host, not every one in use

**The full method** is `boost bmad install`, unchanged: it delegates to the
canonical `npx bmad-method install` (Node.js 20.12+) for the `bmad-*` workflow
skills and the per-project `_bmad/` runtime they read on activation.

    boost bmad install --scope project     # skills + _bmad/ runtime in this repo
    boost bmad install --scope global      # skills into ~/.claude/skills
    boost bmad init                        # add _bmad/ runtime to the current repo
    boost bmad startup on|off|status       # just the SessionStart briefing
    boost bmad disable / enable            # quarantine / restore skills (recoverable)
    boost bmad uninstall                   # delete skills + _bmad/ for a scope
    boost bmad doctor                      # what's installed where

The two compose: the autopilot routes at `bmad-build` and friends whether or
not they are installed, and says so — with the skills present you get BMAD's
full workflow, without them you get the persona's own playbook. Global installs
stage the installer in a temp dir and copy only the `bmad-*` skills into
~/.claude/skills, so $HOME never gets a stray `_bmad/`; the runtime is
per-project by design.

The **hooks fan out; the personas do not**, and the split is not arbitrary.

A subagent definition is a Claude Code contract, and BMAD's own installer takes
`--tools claude-code`, so personas stay in `~/.claude/agents/`. Copying them
into Gemini's `agents/` slot would also ship files its schema rejects — that
slot validates, and a Claude-dialect persona fails it.

The hooks are a different case, and an earlier version of this docstring got it
wrong by lumping them together: it claimed `SessionStart` and
`UserPromptSubmit` had "no equivalent in the other three agents", which stopped
being true when `core/hookhost.py` learned Gemini's vocabulary. They map to
`SessionStart` and `BeforeAgent`, so `bmad on` now installs them on every host
with evidence of use, translating the event names and the timeout units on the
way. Matchers are *not* translated — `hookhost` passes them through
host-native — so Claude's `startup|resume|clear` source matcher is applied only
on Claude.

What that buys on a second host is prompt shaping, not full parity. Gemini's
hooks pass `--host gemini`, so `route` and `orient` answer in the JSON Gemini
adds to the model's context and name the personas as roles rather than
subagents; `--host` on `on`/`startup` picks the hosts explicitly.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

from .. import cliparse
from ..core import bmad as core
from ..core import claude_settings as cs
from ..core import hookhost, journal, paths, util
from ..core import output as out
from ..errors import BoostError

DEFAULT_MODULES = "bmm"
HOOK_NAME = "bmad"
HOOK_MATCHER = "startup|resume|clear|compact"
ROUTE_HOOK_NAME = "bmad-route"

_ACTIONS = ("on", "off", "route", "personas", "install", "init", "startup",
            "orient", "uninstall", "disable", "enable", "doctor", "status")


def cmd_bmad(argv) -> int:
    p = cliparse.parser(
        prog="boost bmad",
        description="BMAD Method autopilot: personas, prompt routing, workflows")
    # metavar="ACTION": the auto-generated {on,off,...,status} metavar (13
    # entries) is one unbreakable token and overflowed the usage line up to
    # 100 columns wide. The full list still shows in `help=` below.
    p.add_argument("action", choices=_ACTIONS, metavar="ACTION",
                   help=" | ".join(_ACTIONS))
    p.add_argument("value", nargs="?",
                   help="startup: on | off | status · route: the prompt to classify")
    p.add_argument("-s", "--scope", choices=("project", "global"), default=None,
                   help="target scope (on/off default: global; personas and "
                        "status: both; others: project)")
    p.add_argument("--modules", default=DEFAULT_MODULES,
                   help="BMAD modules to install (default: %s)" % DEFAULT_MODULES)
    p.add_argument("-y", "--yes", action="store_true",
                   help="skip confirmation prompts")
    p.add_argument("--startup", action="store_true",
                   help="enable the startup toggle right after install")
    p.add_argument("--plain", action="store_true",
                   help="route: print the banner as text, not as hook JSON")
    p.add_argument("--host", metavar="H", default=None,
                   choices=(*hookhost.hosts(), "auto"),
                   help="on/startup: hosts to hook (%s; default auto: "
                        "claude + any in use) · route/orient: output format"
                        % " | ".join(hookhost.hosts()))
    args = p.parse_args(argv)

    if args.action == "on":
        return _autopilot_on(args.scope, args.host)
    if args.action == "off":
        return _autopilot_off(args.scope)
    if args.action == "route":
        return _route(args.value, args.plain, args.scope, _one_host(args.host))
    if args.action == "personas":
        return _personas(args.scope)
    if args.action == "install":
        return _install(args.scope, args.modules, args.startup)
    if args.action == "init":
        return _init(args.modules, args.startup)
    if args.action == "startup":
        return _startup(args.value or "status", args.scope, args.host)
    if args.action == "orient":
        return _orient(args.scope, _one_host(args.host))
    if args.action == "uninstall":
        return _uninstall(args.scope, args.yes)
    if args.action == "disable":
        return _disable(args.scope)
    if args.action == "enable":
        return _enable(args.scope)
    return _doctor()  # doctor | status


# ------------------------------------------------------------------- autopilot

def _on_off(value) -> str:
    """Render any truthy/falsy value as ``"on"``/``"off"``.

    `doctor` used to format some booleans as ``on``/``off`` and others as
    Python's ``True``/``False`` in the same block of output — "installed=False"
    printed right beside "autopilot=off". One helper keeps every boolean field
    in one vocabulary.
    """
    return "on" if value else "off"


def _agents_dir(scope) -> Path:
    """Where Claude Code reads subagent definitions for a scope."""
    base = paths.home() if scope == "global" else Path.cwd()
    return base / ".claude" / "agents"


def _never_fails(command: str) -> str:
    """Make a hook command structurally incapable of reporting failure.

    `_route` is careful to always exit 0 — but argparse never gets that far. The
    hook is installed against :func:`paths.launcher`, i.e. whatever `boost` is on
    PATH, which is not necessarily the build that wrote the hook: a stale pipx
    install, or a later downgrade, reaches `bmad route`, does not recognise the
    action, and exits **2**. On UserPromptSubmit exit 2 does not merely log — it
    blocks the prompt and erases it from the transcript, so every message the
    user typed would vanish until they found the hook.

    `|| true` closes that at the shell, outside any version of boost. The
    `# boost:<name>` ownership marker `claude_settings` appends still parses as a
    trailing comment.
    """
    return command + " || true"


def _one_host(host) -> str:
    """The host a hook runs under. Hooks written before `--host` are Claude's."""
    return hookhost.CLAUDE if host in (None, "auto") else host


def _hook_hosts(scope: str, requested=None) -> list[str]:
    """Hosts to write hooks into: Claude always, others on evidence of use.

    Claude is unconditional. It is boost's primary host and the behaviour every
    release before this one had, and the check cannot be `shutil.which` the way
    `boost mcp register`'s is: that command *shells out* to `claude mcp add` and
    genuinely cannot work without the binary, while this one only writes a
    settings.json. A user running inside Claude Code whose launcher is not on
    boost's PATH would otherwise silently get no hooks at all.

    A second host earns its hooks by evidence that it is actually in use —
    its CLI on PATH, or its dotdir already present. Writing into
    `~/.gemini/settings.json` for someone who has never run Gemini is litter in
    a file boost does not own. A host that appears later is picked up by the
    next `boost bmad on`, which is idempotent.

    ``requested`` (`--host`) overrides the rule: naming one host writes that
    host only, so Claude-only no longer means hand-editing Gemini's settings
    after every `on`.
    """
    if requested not in (None, "auto"):
        return [requested]
    chosen = [hookhost.CLAUDE]
    for host in hookhost.hosts():
        if host == hookhost.CLAUDE:
            continue
        dotdir = cs.settings_path(scope, host=host).parent
        if shutil.which(hookhost.cli(host)) or dotdir.is_dir():
            chosen.append(host)
    return chosen


#: (Claude event, hook name, matcher). The matcher is Claude's own
#: `SessionStart` source vocabulary, and `hookhost` deliberately does not
#: translate matchers — they pass through host-native — so it is applied only
#: on the host it was written for. Omitting it elsewhere means "every start",
#: which is what a session briefing wants anyway.
_ORIENT_HOOK = ("SessionStart", HOOK_NAME, HOOK_MATCHER)
_ROUTE_HOOK = ("UserPromptSubmit", ROUTE_HOOK_NAME, None)


def _host_command(host: str, command: str) -> str:
    """``command`` as ``host``'s hook runs it, made incapable of failing.

    Claude's bytes are what every earlier release wrote. Another host's hook
    names its host, so `route`/`orient` answer in the format that host reads,
    and drops stderr: Gemini shows stderr to the user when stdout is empty, so
    a launcher too old to know the action printed its usage error into the
    session despite `|| true`.
    """
    if host == hookhost.CLAUDE:
        return _never_fails(command)
    return _never_fails("%s --host %s 2>/dev/null" % (command, host))


def _add_hook_everywhere(scope: str, spec: tuple, command: str,
                         requested=None) -> list[str]:
    """Install one hook on every chosen host. Returns the hosts written."""
    event, name, matcher = spec
    written = []
    for host in _hook_hosts(scope, requested):
        target = hookhost.translate(host, event)
        if target is None:
            # Refused out loud rather than dropped: a hook the user asked for
            # and silently never got is worse than one that cannot exist.
            out.warn("%s has no counterpart for %s — skipped"
                     % (hookhost.label(host), event))
            continue
        cs.add_hook(scope, target, name, _host_command(host, command),
                    matcher=matcher if host == hookhost.CLAUDE else None,
                    host=host)
        written.append(host)
    return written


def _remove_hook_everywhere(scope: str, *specs: tuple) -> int:
    """Remove hooks from every host, installed or not. Returns how many were.

    Unlike install this does not filter on `shutil.which`: someone who removed
    an agent CLI still wants boost's hooks gone from its settings.json, and
    `remove_hook` against a file that was never written is a no-op — which is
    exactly why the count matters: a caller that hardcodes "both hooks" in its
    report is claiming work that a second, no-op `off` never did.
    """
    removed = 0
    for host in hookhost.hosts():
        for event, name, _matcher in specs:
            target = hookhost.translate(host, event)
            if target is not None:
                removed += cs.remove_hook(scope, target, name, host=host)
    return removed


def _autopilot_on(scope, requested_host=None) -> int:
    """The one command. Personas + orientation + router, in one idempotent pass.

    Global by default: the point of the autopilot is that a task arriving in
    *any* repo already knows which persona owns it, and per-project setup would
    make that a per-repo chore.
    """
    scope = scope or "global"
    agents = _agents_dir(scope)
    # Asked before writing: whether this run *creates* the directory decides
    # what running sessions can see (see the restart line below).
    fresh = not agents.is_dir()
    _written, skipped = core.write_personas(agents)
    # A skipped (edited) persona file is still on disk and Claude Code still
    # loads it — only the ones neither written nor present at all are truly
    # "not installed", so the reported count is managed + edited, not just
    # what this run happened to (re)write.
    present = len(core.present_personas(agents))

    launcher = shlex.quote(str(paths.launcher()))
    hosts = _add_hook_everywhere(
        scope, _ORIENT_HOOK, "%s bmad orient --scope %s" % (launcher, scope),
        requested_host)
    _add_hook_everywhere(scope, _ROUTE_HOOK,
                         "%s bmad route --scope %s" % (launcher, scope),
                         requested_host)
    _set_scope_state(scope, autopilot=True, startup=True, personas=present,
                     enabled_at=util.now_iso())
    journal.log("bmad-autopilot", "on", scope=scope, personas=present)

    out.ok("BMAD autopilot ON (%s) — %d persona subagent(s) + prompt router"
           % (scope, present))
    if skipped:
        out.warn("kept your edits to %d persona(s): %s"
                 % (len(skipped), ", ".join(skipped)))
        out.dim("  delete the file to let `boost bmad on` restore the stock version")
    out.dim("  personas → %s" % paths.tilde(agents))
    for host in hosts:
        out.dim("  hooks    → %s (%s + %s)"
                % (paths.tilde(cs.settings_path(scope, host=host)),
                   hookhost.translate(host, "SessionStart"),
                   hookhost.translate(host, "UserPromptSubmit")))
    out.dim("  every substantive prompt now names its lead persona and its "
            "definition of done; trivial asks are left alone")
    # Hook edits reach open sessions through the settings watcher, but Claude
    # Code only watches an agents dir that existed when the session started. So
    # a run that creates the dir starts banners before their personas can load;
    # one that finds it already there is picked up live and needs no restart.
    if fresh:
        out.info("routing banners can start in open sessions now; restart "
                 "them to use the new subagents")
    out.dim("  full BMAD workflow skills (needs Node): boost bmad install")
    return 0


def _autopilot_off(scope) -> int:
    scope = scope or "global"
    hooks_removed = _remove_hook_everywhere(scope, _ORIENT_HOOK, _ROUTE_HOOK)
    removed = core.remove_personas(_agents_dir(scope))
    _set_scope_state(scope, autopilot=False, startup=False, personas=0)
    journal.log("bmad-autopilot", "off", scope=scope, personas=len(removed))
    out.ok("BMAD autopilot OFF (%s) — removed %d persona(s) and %d hook(s)"
           % (scope, len(removed), hooks_removed))
    out.dim("  hand-edited personas were left in place")
    return 0


def _read_hook_stdin() -> dict:
    """Claude Code's UserPromptSubmit payload, or {} for anything unreadable.

    Accepts plain text too, so `echo "add tests for the scanner" | boost bmad
    route` works for a human debugging the routing table. (Give it a real
    prompt: anything under `core.MIN_WORDS` words classifies as trivial and
    prints nothing, which reads like a broken install.)
    """
    try:
        if sys.stdin.isatty():
            return {}       # interactive: don't block waiting for an EOF
        raw = sys.stdin.read().strip()
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"prompt": raw}
    return data if isinstance(data, dict) else {"prompt": raw}


def _route(prompt, plain, scope=None, host=hookhost.CLAUDE) -> int:
    """UserPromptSubmit hook target: classify, then emit the routing banner.

    This runs on every single prompt, so it has exactly one hard rule: **always
    exit 0**. On UserPromptSubmit an exit code of 2 blocks the prompt and erases
    it from the transcript — a crash here would eat the user's message. Every
    failure mode therefore degrades to silence.

    Run as a hook (no positional prompt, no ``--plain``) it speaks only while
    the autopilot is on, the same rule `_orient` applies. `off` works by
    deleting the hook, so without this any copy it missed kept routing: a
    committed `.claude/settings.json` in a second checkout, or a settings
    snapshot restored from boost's own history. A human asking what a prompt
    would route to gets the answer whatever the state.
    """
    try:
        payload = {} if prompt else _read_hook_stdin()
        text = prompt or str(payload.get("prompt") or "")
        cwd = payload.get("cwd")
        root = Path(cwd) if cwd else Path.cwd()
        if prompt or plain:
            banner = core.route_context(text, root, None, host)
        elif _autopilot_live(scope, root):
            banner = _session_banner(payload, text, root, host)
        else:
            return 0
    except Exception:                     # a hook must never break the session
        return 0
    if not banner:
        return 0
    if plain:
        print(banner)
        return 0
    print(hookhost.context_output(host, "UserPromptSubmit", banner))
    return 0


def _session_banner(payload: dict, text: str, root: Path,
                    host: str = hookhost.CLAUDE) -> str:
    """The hook's banner, or ``""`` when this session already holds it.

    Keyed by ``session_id``. Gemini's `BeforeAgent` carries one too, but its
    reference says hook context is appended "for this turn only", so a banner
    skipped there would simply be missing; the check applies to Claude alone.
    """
    session = str(payload.get("session_id") or "")
    if host != hookhost.CLAUDE or payload.get("hook_event_name") == "BeforeAgent":
        session = ""
    track = core.classify(text, root)
    if track == core.TRIVIAL:
        return ""
    sessions = _sessions_read() if session else {}
    if session and not core.banner_is_news(sessions.get(session), text, track,
                                           str(root)):
        return ""
    banner = core.route_context(
        text, root, (_agents_dir("global"), root / ".claude" / "agents"), host)
    if session and banner:
        sessions[session] = {"track": track, "root": str(root),
                             "at": util.now_iso()}
        # Best effort: a state dir that cannot be written (full disk, a
        # root-owned ~/.boost after one `sudo boost`) must cost one repeated
        # banner, not every banner — the write happens after the banner is
        # built, so an escaping OSError silenced the router outright.
        with suppress(OSError):
            _sessions_write(sessions)
    return banner


_PERSONA_STATE_LABEL = {
    "managed": "installed",
    "edited": "installed (edited)",
    "absent": "not installed",
}


def _personas(scope) -> int:
    """List personas: one scope if asked, otherwise both.

    This is a query, so with no ``--scope`` it reports BOTH — exactly what
    ``bmad status`` already does, and for the same reason. Picking one scope by
    default made the answer wrong whenever the personas lived in the other: it
    defaulted to global, so after `boost bmad on --scope project` it read
    ``~/.claude/agents``, found nothing, and reported seven personas sitting on
    disk as "not installed" — contradicting `boost bmad status` run a moment
    later in the same directory. Flipping the default to project would only
    move the false statement to the global install, which is the more common
    one; a query that inspects both places cannot be wrong about either.
    """
    for sc in (scope,) if scope else ("global", "project"):
        _personas_scope(sc)
    return 0


def _personas_scope(scope) -> None:
    """Report the persona roster for exactly one scope."""
    agents = _agents_dir(scope)
    states = core.persona_states(agents)
    out.heading("BMAD personas — %s" % scope)
    for p in core.PERSONAS:
        mark = _PERSONA_STATE_LABEL[states[p.slug]]
        # width 16: `bmad-architect` is exactly the default 14, which leaves no
        # gap between the key and the value.
        out.kv(p.slug, "%s, %s (%s) — %s"
               % (p.character, p.title, p.module, mark), width=16)
    out.dim("  → %s" % paths.tilde(agents))
    if all(state == "absent" for state in states.values()):
        out.dim("  install them with `boost bmad on`")


# ------------------------------------------------------------------- provisioning

def _require_npx() -> None:
    if not shutil.which("npx"):
        raise BoostError(
            "npx not found — BMAD is provisioned via `npx bmad-method install`",
            hint="install Node.js 20.12+ (e.g. `brew install node`), then retry")


def _run_installer(directory: Path, modules: str) -> subprocess.CompletedProcess:
    cmd = ["npx", "--yes", "bmad-method@%s" % core.BMAD_VERSION, "install",
           "--yes", "--directory", str(directory),
           "--tools", "claude-code", "--modules", modules,
           "--user-name", _whoami()]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise BoostError("bmad install failed: %s" % e,
                         hint="run it yourself: " + " ".join(cmd)) from e
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError(
            "bmad install failed: %s" % (tail[-1] if tail else "unknown error"),
            hint="run it yourself: " + " ".join(cmd))
    return proc


def _whoami() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "developer"


def _parse_version(text: str) -> str:
    m = re.search(r"v(\d+\.\d+\.\d+)", text)
    return m.group(1) if m else "unknown"


def _install(scope, modules, do_startup) -> int:
    scope = scope or "project"
    _require_npx()
    if scope == "global":
        before = _get_scope_state("global")
        ver, names = _copy_global_skills(modules)
        dropped = _drop_retired_skills(before, names, modules)
        _set_scope_state("global", installed=True, skills=len(names),
                         skill_list=names, version=ver,
                         modules=modules.split(","), installed_at=util.now_iso())
        out.ok("installed %d BMAD skill(s) globally → %s (v%s)"
               % (len(names), _skills_dir("global"), ver))
        if dropped:
            out.info("removed %d skill(s) this BMAD release no longer installs: %s"
                     % (len(dropped), ", ".join(dropped)))
        needs_runtime = [n for n in core.RUNTIME_SKILLS if n in names]
        if needs_runtime:
            out.warn("%s halt without a per-repo _bmad/ runtime — run "
                     "`boost bmad init` in each repo that uses them"
                     % " and ".join(needs_runtime))
        else:
            out.dim("  run `boost bmad init` in a project for its _bmad/ workflow runtime")
    else:
        ver, n = _install_project_runtime(modules)
        out.ok("installed BMAD in %s (%d skills, v%s)" % (Path.cwd(), n, ver))
    if do_startup:
        _startup("on", scope)
    return 0


def _init(modules, do_startup) -> int:
    _require_npx()
    ver, n = _install_project_runtime(modules)
    out.ok("BMAD runtime ready in %s (_bmad/, %d skills, v%s)"
           % (Path.cwd(), n, ver))
    if do_startup:
        _startup("on", "project")
    return 0


def _install_project_runtime(modules):
    target = Path.cwd()
    proc = _run_installer(target, modules)
    ver = _parse_version((proc.stdout or "") + (proc.stderr or ""))
    n = _count_skills(_skills_dir("project"))
    _set_scope_state("project", installed=True, skills=n, version=ver,
                     modules=modules.split(","), installed_at=util.now_iso())
    return ver, n


def _copy_global_skills(modules) -> tuple[str, list[str]]:
    """Stage the installer in a temp dir; copy only bmad-* skills into ~/.claude.

    Returns ``(version, skill names copied)``. The names are recorded so the
    next global install knows which skills are boost's to retire.
    """
    stage = Path(tempfile.mkdtemp(prefix="boost-bmad-"))
    try:
        proc = _run_installer(stage, modules)
        ver = _parse_version((proc.stdout or "") + (proc.stderr or ""))
        src = stage / ".claude" / "skills"
        dest = _skills_dir("global")
        dest.mkdir(parents=True, exist_ok=True)
        names = []
        for d in sorted(src.glob("bmad-*")):
            if not d.is_dir():
                continue
            t = dest / d.name
            if t.exists():
                util.rmtree(t)
            shutil.copytree(d, t)
            names.append(d.name)
        return ver, names
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _drop_retired_skills(before: dict, installed: list[str],
                         modules: str) -> list[str]:
    """Remove skills the last global install recorded and this one did not ship.

    The copy only replaces directories the new stage has, and upstream's own
    cleanup runs inside the empty stage, never against `~/.claude/skills` — so
    a skill a release retired (`bmad-document-project` in 6.12.0) survived
    every reinstall. Only *recorded* names go: another `bmad-*` directory may
    be the user's own.

    **A narrower module set retires nothing.** `--modules` defaults to `bmm` on
    every run, so `boost bmad install --scope global` after an earlier
    `--modules bmm,cis` stages only bmm — and every cis skill would read as
    "retired by the release" and be deleted. A run can only retire within the
    modules it actually installed.
    """
    previous = before.get("skill_list")
    if not isinstance(previous, list):
        return []
    had = before.get("modules")
    if isinstance(had, list) and set(had) - set(modules.split(",")):
        return []
    dest = _skills_dir("global")
    dropped = []
    for name in sorted({n for n in previous if isinstance(n, str)} - set(installed)):
        # A hand-edited state file must not steer the delete out of the dir.
        if not (name.startswith("bmad-") and Path(name).name == name):
            continue
        if (dest / name).is_dir():
            util.rmtree(dest / name)
            dropped.append(name)
    return dropped


# ----------------------------------------------------------------------- toggle

def _startup(value, scope, requested_host=None) -> int:
    scope = scope or "project"
    if value == "on":
        cmd = "%s bmad orient --scope %s" % (
            shlex.quote(str(paths.launcher())), scope)
        started = _add_hook_everywhere(scope, _ORIENT_HOOK, cmd, requested_host)
        _set_scope_state(scope, startup=True)
        journal.log("bmad-startup", "on", scope=scope)
        out.ok("BMAD startup ON (%s) — new sessions get orientation" % scope)
        for host in started:
            out.dim("  hook → %s" % cs.settings_path(scope, host=host))
        return 0
    if value == "off":
        _remove_hook_everywhere(scope, _ORIENT_HOOK)
        _set_scope_state(scope, startup=False)
        journal.log("bmad-startup", "off", scope=scope)
        out.ok("BMAD startup OFF (%s) — skills stay installed" % scope)
        return 0
    if value == "status":
        return _status(scope)
    raise BoostError("unknown startup value %r" % value,
                     hint="use 'on', 'off' or 'status'")


def _orient(scope, host=hookhost.CLAUDE) -> int:
    """SessionStart hook target: print the briefing iff enabled (else silent).

    On `clear` and `compact` it also forgets the session's last routing banner:
    the conversation that held it is gone, so the next routed prompt needs it
    again rather than being skipped as a repeat.
    """
    scope = scope or "project"
    with suppress(Exception):  # a hook must never break the session
        payload = _read_hook_stdin()
        session = str(payload.get("session_id") or "")
        if session and payload.get("source") in ("clear", "compact"):
            sessions = _sessions_read()
            if sessions.pop(session, None) is not None:
                _sessions_write(sessions)
    with suppress(Exception):
        if _get_scope_state(scope).get("startup"):
            print(hookhost.context_output(host, "SessionStart",
                                          core.orientation(host)))
    return 0


def _status(scope) -> int:
    st = _get_scope_state(scope)
    hosts = _hosts_with(scope, "SessionStart", HOOK_NAME)
    n = _count_skills(_skills_dir(scope))
    out.heading("BMAD startup — %s" % scope)
    out.kv("enabled", str(bool(st.get("startup"))))
    out.kv("hook", "present (%s)" % ", ".join(hosts) if hosts else "absent")
    out.kv("skills", str(n))
    out.kv("installed", str(bool(st.get("installed"))))
    return 0


# ------------------------------------------------------------------- teardown

def _uninstall(scope, yes) -> int:
    scope = scope or "project"
    if not (yes or out.confirm(
            "Remove BMAD (%s)? deletes bmad-* skills%s" % (
                scope, " + _bmad/, _bmad-output/" if scope == "project" else ""))):
        out.info("aborted")
        return 1
    _remove_hook_everywhere(scope, _ORIENT_HOOK, _ROUTE_HOOK)
    removed = _rm_skills(_skills_dir(scope))
    removed += len(core.remove_personas(_agents_dir(scope)))
    if scope == "project":
        for extra in ("_bmad", "_bmad-output"):
            pth = Path.cwd() / extra
            if pth.exists():
                shutil.rmtree(pth, ignore_errors=True)
                removed += 1
    _clear_scope_state(scope)
    journal.log("bmad-uninstall", scope, count=removed)
    out.ok("removed BMAD (%s): %d item(s)" % (scope, removed))
    return 0


def _disable(scope) -> int:
    """Quarantine: turn startup off and move skills aside (recoverable)."""
    scope = scope or "project"
    _remove_hook_everywhere(scope, _ORIENT_HOOK)
    qdir = _quarantine_dir(scope)
    qdir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for d in sorted(_skills_dir(scope).glob("bmad-*")):
        target = qdir / d.name
        if target.exists():
            util.rmtree(target)
        shutil.move(str(d), str(target))
        moved += 1
    _set_scope_state(scope, startup=False, disabled=True)
    journal.log("bmad-disable", scope, count=moved)
    out.ok("quarantined %d BMAD skill(s) (%s)" % (moved, scope))
    out.dim("  restore with `boost bmad enable --scope %s`" % scope)
    return 0


def _enable(scope) -> int:
    scope = scope or "project"
    qdir = _quarantine_dir(scope)
    restored = 0
    if qdir.exists():
        dest = _skills_dir(scope)
        dest.mkdir(parents=True, exist_ok=True)
        for d in sorted(qdir.glob("bmad-*")):
            target = dest / d.name
            if target.exists():
                util.rmtree(target)
            shutil.move(str(d), str(target))
            restored += 1
    _set_scope_state(scope, disabled=False)
    if restored:
        journal.log("bmad-enable", scope, count=restored)
        out.ok("restored %d BMAD skill(s) (%s)" % (restored, scope))
    else:
        out.warn("nothing quarantined for %s scope" % scope)
    return 0


def _doctor() -> int:
    out.heading("BMAD status")
    # Node is only needed by `install`/`init`; the autopilot never shells out,
    # so MISSING here is a limitation, not a fault.
    out.kv("npx", shutil.which("npx") or "MISSING (only `install` needs it)")
    out.kv("node", shutil.which("node") or "MISSING (only `install` needs it)")
    for scope in ("global", "project"):
        st = _get_scope_state(scope)
        agents = _agents_dir(scope)
        # managed + edited: an edited persona file is still on disk and
        # Claude Code still loads it, same as core.present_personas().
        personas = len(core.present_personas(agents))
        router_hosts = _hosts_with(scope, "UserPromptSubmit", ROUTE_HOOK_NAME)
        briefing_hosts = _hosts_with(scope, "SessionStart", HOOK_NAME)
        router = bool(router_hosts)
        live = bool(st.get("autopilot")) and router
        briefing = _where(briefing_hosts)
        if briefing_hosts and _stale_matcher(scope):
            # The matcher lives in the user's settings.json from whenever they
            # last ran `on`, while the code that depends on it ships with the
            # binary — so an old install silently misses newer sources.
            briefing += " (stale matcher: re-run `boost bmad on`)"
        out.kv(scope, "autopilot=%s  %d personas  router=%s  briefing=%s"
               % (_on_off(live), personas, _where(router_hosts), briefing))
        out.kv("  workflows", "skills=%d  installed=%s"
               % (_count_skills(_skills_dir(scope)), _on_off(st.get("installed"))))
    out.dim("  project = %s" % Path.cwd())
    if not any(_get_scope_state(s).get("autopilot") for s in ("global", "project")):
        out.dim("  turn it on with `boost bmad on`")
    return 0


# -------------------------------------------------------------------- helpers

def _stale_matcher(scope) -> bool:
    """True when the installed briefing hook predates the current matcher.

    `_orient` forgets a session's last banner on `clear` and `compact`, and
    `compact` only reaches it if the hook was written with today's matcher.
    """
    rows = [r for r in cs.list_hooks(scope)
            if r["event"] == "SessionStart" and r["name"] == HOOK_NAME]
    return any(r.get("matcher") != HOOK_MATCHER for r in rows)


def _hosts_with(scope, event: str, name: str) -> list[str]:
    """Which hosts carry this boost hook, in report order.

    `--host gemini` makes a Claude-less autopilot reachable for the first time,
    and a report that asks only Claude called that install absent — `doctor`
    said `autopilot=off router=off` about a router that was about to run.
    """
    found = []
    for host in hookhost.hosts():
        target = hookhost.translate(host, event)
        if target is not None and cs.has_hook(scope, target, name, host=host):
            found.append(host)
    return found


def _where(hosts: list[str]) -> str:
    """``off``, ``on`` (Claude only) or ``on (gemini)`` — who has the hook."""
    if not hosts:
        return "off"
    if hosts == [hookhost.CLAUDE]:
        return "on"
    return "on (%s)" % ", ".join(hosts)


def _skills_dir(scope) -> Path:
    base = paths.home() if scope == "global" else Path.cwd()
    return base / ".claude" / "skills"


def _count_skills(skills_dir: Path) -> int:
    if not skills_dir.exists():
        return 0
    return sum(1 for d in skills_dir.glob("bmad-*") if d.is_dir())


def _rm_skills(skills_dir: Path) -> int:
    n = 0
    if skills_dir.exists():
        for d in sorted(skills_dir.glob("bmad-*")):
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return n


def _quarantine_dir(scope) -> Path:
    key = "global" if scope == "global" else _fs_slug(str(Path.cwd().resolve()))
    return paths.state_dir() / "bmad-quarantine" / key


def _fs_slug(p: str) -> str:
    return p.replace(os.sep, "__").strip("_") or "root"


# ---------------------------------------------------------------------- state

def _state_path() -> Path:
    return paths.state_dir() / "bmad.json"


def _state_read() -> dict:
    p = _state_path()
    if not p.exists():
        return {"global": {}, "projects": {}}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"global": {}, "projects": {}}
    d.setdefault("global", {})
    d.setdefault("projects", {})
    return d


def _state_write(d: dict) -> None:
    paths.ensure_dirs()
    _state_path().write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")


SESSIONS_KEPT = 200
"""Session records kept; the oldest go first. A lost one costs one banner."""


def _sessions_path() -> Path:
    return paths.state_dir() / "bmad-sessions.json"


def _sessions_read() -> dict:
    """``{session_id: {track, root, at}}``; anything unreadable reads as empty."""
    try:
        data = json.loads(_sessions_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _sessions_write(sessions: dict) -> None:
    """Atomically, and bounded: every routed prompt in every session writes it."""
    def at(item):
        record = item[1]
        return str(record.get("at", "")) if isinstance(record, dict) else ""

    kept = dict(sorted(sessions.items(), key=at)[-SESSIONS_KEPT:])
    util.atomic_write_text(_sessions_path(), json.dumps(kept, indent=1) + "\n")


def _proj_key(project=None) -> str:
    return str(Path(project or Path.cwd()).resolve())


def _get_scope_state(scope, project=None) -> dict:
    d = _state_read()
    if scope == "global":
        return d["global"]
    return d["projects"].get(_proj_key(project), {})


def _autopilot_live(scope, root) -> bool:
    """Whether the router hook for ``scope`` may speak in the repo at ``root``.

    Project state is keyed by the exact checkout path, the key `_orient` uses. A
    nearest-parent lookup would route in a worktree nested under the repo while
    the briefing stayed silent — the disagreement this check exists to end. A
    hook with no ``--scope`` (every install before this one wrote it that way)
    accepts either scope until the next `boost bmad on` rewrites it.
    """
    scopes = (scope,) if scope else ("global", "project")
    return any(_get_scope_state(sc, root).get("autopilot") for sc in scopes)


def _set_scope_state(scope, **patch) -> None:
    d = _state_read()
    if scope == "global":
        d["global"].update(patch)
    else:
        d["projects"].setdefault(_proj_key(), {}).update(patch)
    _state_write(d)


def _clear_scope_state(scope) -> None:
    d = _state_read()
    if scope == "global":
        d["global"] = {}
    else:
        d["projects"].pop(_proj_key(), None)
    _state_write(d)
