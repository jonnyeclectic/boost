"""boost bmad — the BMAD Method as a one-command, global autopilot.

There are two surfaces here, and the split is the whole design.

**The autopilot** is `boost bmad on`. One command, global by default, no Node
and no network: it writes the seven BMAD persona subagents into
`~/.claude/agents/`, and installs two hooks — a `SessionStart` briefing and a
`UserPromptSubmit` router. After that, every substantive prompt arrives already
carrying the persona that should lead it, the support personas to spawn
alongside, the BMAD skill for that track, and a definition of done read off the
repo in front of it (its test dir, its docs, its roadmap items, its gate
command). Trivial asks get nothing, so the router costs a question nothing. All
of the thinking lives in :mod:`boost_cli.core.bmad`; this module is glue.

    boost bmad on                          # <- the one command. global.
    boost bmad off                         # remove hooks + boost-written personas
    boost bmad personas                    # the roster, and whether it is installed
    boost bmad route [PROMPT] [--plain]    # hook target; pipeable for debugging

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

Both surfaces are **Claude Code only**, and deliberately so: subagent
definitions and `SessionStart`/`UserPromptSubmit` hooks are Claude Code
contracts with no equivalent in the other three agents boost targets, and BMAD's
own installer likewise takes `--tools claude-code`. This is the one part of
boost that does not fan out over `agents.enabled_agents()`.
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
from ..core import journal, paths, util
from ..core import output as out
from ..errors import BoostError

DEFAULT_MODULES = "bmm"
HOOK_NAME = "bmad"
HOOK_MATCHER = "startup|resume|clear"
ROUTE_HOOK_NAME = "bmad-route"

_ACTIONS = ("on", "off", "route", "personas", "install", "init", "startup",
            "orient", "uninstall", "disable", "enable", "doctor", "status")


def cmd_bmad(argv) -> int:
    p = cliparse.parser(
        prog="boost bmad",
        description="BMAD Method autopilot: personas, prompt routing, workflows")
    p.add_argument("action", choices=_ACTIONS, help=" | ".join(_ACTIONS))
    p.add_argument("value", nargs="?",
                   help="startup: on | off | status · route: the prompt to classify")
    p.add_argument("-s", "--scope", choices=("project", "global"), default=None,
                   help="target scope (on/off default: global; others: project)")
    p.add_argument("--modules", default=DEFAULT_MODULES,
                   help="BMAD modules to install (default: %s)" % DEFAULT_MODULES)
    p.add_argument("-y", "--yes", action="store_true",
                   help="skip confirmation prompts")
    p.add_argument("--startup", action="store_true",
                   help="enable the startup toggle right after install")
    p.add_argument("--plain", action="store_true",
                   help="route: print the banner as text, not as hook JSON")
    args = p.parse_args(argv)

    if args.action == "on":
        return _autopilot_on(args.scope)
    if args.action == "off":
        return _autopilot_off(args.scope)
    if args.action == "route":
        return _route(args.value, args.plain)
    if args.action == "personas":
        return _personas(args.scope)
    if args.action == "install":
        return _install(args.scope, args.modules, args.startup)
    if args.action == "init":
        return _init(args.modules, args.startup)
    if args.action == "startup":
        return _startup(args.value or "status", args.scope)
    if args.action == "orient":
        return _orient(args.scope)
    if args.action == "uninstall":
        return _uninstall(args.scope, args.yes)
    if args.action == "disable":
        return _disable(args.scope)
    if args.action == "enable":
        return _enable(args.scope)
    return _doctor()  # doctor | status


# ------------------------------------------------------------------- autopilot

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


def _autopilot_on(scope) -> int:
    """The one command. Personas + orientation + router, in one idempotent pass.

    Global by default: the point of the autopilot is that a task arriving in
    *any* repo already knows which persona owns it, and per-project setup would
    make that a per-repo chore.
    """
    scope = scope or "global"
    agents = _agents_dir(scope)
    slugs, skipped = core.write_personas(agents)

    launcher = shlex.quote(str(paths.launcher()))
    cs.add_hook(scope, "SessionStart", HOOK_NAME,
                _never_fails("%s bmad orient --scope %s" % (launcher, scope)),
                matcher=HOOK_MATCHER)
    cs.add_hook(scope, "UserPromptSubmit", ROUTE_HOOK_NAME,
                _never_fails("%s bmad route" % launcher))
    _set_scope_state(scope, autopilot=True, startup=True, personas=len(slugs),
                     enabled_at=util.now_iso())
    journal.log("bmad-autopilot", "on", scope=scope, personas=len(slugs))

    out.ok("BMAD autopilot ON (%s) — %d persona subagent(s) + prompt router"
           % (scope, len(slugs)))
    if skipped:
        out.warn("kept your edits to %d persona(s): %s"
                 % (len(skipped), ", ".join(skipped)))
        out.dim("  delete the file to let `boost bmad on` restore the stock version")
    out.dim("  personas → %s" % paths.tilde(agents))
    out.dim("  hooks    → %s (SessionStart + UserPromptSubmit)"
            % paths.tilde(cs.settings_path(scope)))
    out.dim("  every substantive prompt now names its lead persona and its "
            "definition of done; trivial asks are left alone")
    # Claude Code only watches an agents dir that existed when the session
    # started, so a first-ever install is invisible until the next launch.
    out.info("restart your agent session to pick up the new subagents")
    out.dim("  full BMAD workflow skills (needs Node): boost bmad install")
    return 0


def _autopilot_off(scope) -> int:
    scope = scope or "global"
    cs.remove_hook(scope, "SessionStart", HOOK_NAME)
    cs.remove_hook(scope, "UserPromptSubmit", ROUTE_HOOK_NAME)
    removed = core.remove_personas(_agents_dir(scope))
    _set_scope_state(scope, autopilot=False, startup=False, personas=0)
    journal.log("bmad-autopilot", "off", scope=scope, personas=len(removed))
    out.ok("BMAD autopilot OFF (%s) — removed %d persona(s) and both hooks"
           % (scope, len(removed)))
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


def _route(prompt, plain) -> int:
    """UserPromptSubmit hook target: classify, then emit the routing banner.

    This runs on every single prompt, so it has exactly one hard rule: **always
    exit 0**. On UserPromptSubmit an exit code of 2 blocks the prompt and erases
    it from the transcript — a crash here would eat the user's message. Every
    failure mode therefore degrades to silence.
    """
    try:
        payload = {} if prompt else _read_hook_stdin()
        text = prompt or str(payload.get("prompt") or "")
        cwd = payload.get("cwd")
        root = Path(cwd) if cwd else Path.cwd()
        banner = core.route_context(text, root)
    except Exception:                     # a hook must never break the session
        return 0
    if not banner:
        return 0
    if plain:
        print(banner)
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": banner,
    }}))
    return 0


def _personas(scope) -> int:
    scope = scope or "global"
    agents = _agents_dir(scope)
    live = set(core.installed_personas(agents))
    out.heading("BMAD personas — %s" % scope)
    for p in core.PERSONAS:
        mark = "installed" if p.slug in live else "not installed"
        # width 16: `bmad-architect` is exactly the default 14, which leaves no
        # gap between the key and the value.
        out.kv(p.slug, "%s, %s (%s) — %s"
               % (p.character, p.title, p.module, mark), width=16)
    out.dim("  → %s" % paths.tilde(agents))
    if not live:
        out.dim("  install them with `boost bmad on`")
    return 0


# ------------------------------------------------------------------- provisioning

def _require_npx() -> None:
    if not shutil.which("npx"):
        raise BoostError(
            "npx not found — BMAD is provisioned via `npx bmad-method install`",
            hint="install Node.js 20.12+ (e.g. `brew install node`), then retry")


def _run_installer(directory: Path, modules: str) -> subprocess.CompletedProcess:
    cmd = ["npx", "--yes", "bmad-method@latest", "install",
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
        n = _copy_global_skills(modules)
        _set_scope_state("global", installed=True, skills=n,
                         modules=modules.split(","), installed_at=util.now_iso())
        out.ok("installed %d BMAD skill(s) globally → %s"
               % (n, _skills_dir("global")))
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


def _copy_global_skills(modules) -> int:
    """Stage the installer in a temp dir; copy only bmad-* skills into ~/.claude."""
    stage = Path(tempfile.mkdtemp(prefix="boost-bmad-"))
    try:
        _run_installer(stage, modules)
        src = stage / ".claude" / "skills"
        dest = _skills_dir("global")
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        for d in sorted(src.glob("bmad-*")):
            if not d.is_dir():
                continue
            t = dest / d.name
            if t.exists():
                util.rmtree(t)
            shutil.copytree(d, t)
            n += 1
        return n
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ----------------------------------------------------------------------- toggle

def _startup(value, scope) -> int:
    scope = scope or "project"
    if value == "on":
        cmd = "%s bmad orient --scope %s" % (
            shlex.quote(str(paths.launcher())), scope)
        cs.add_hook(scope, "SessionStart", HOOK_NAME, cmd, matcher=HOOK_MATCHER)
        _set_scope_state(scope, startup=True)
        journal.log("bmad-startup", "on", scope=scope)
        out.ok("BMAD startup ON (%s) — new sessions get orientation" % scope)
        out.dim("  hook → %s" % cs.settings_path(scope))
        return 0
    if value == "off":
        cs.remove_hook(scope, "SessionStart", HOOK_NAME)
        _set_scope_state(scope, startup=False)
        journal.log("bmad-startup", "off", scope=scope)
        out.ok("BMAD startup OFF (%s) — skills stay installed" % scope)
        return 0
    return _status(scope)


def _orient(scope) -> int:
    """SessionStart hook target: print the briefing iff enabled (else silent)."""
    scope = scope or "project"
    with suppress(Exception):  # a hook must never break the session
        if _get_scope_state(scope).get("startup"):
            print(core.orientation())
    return 0


def _status(scope) -> int:
    st = _get_scope_state(scope)
    hook = cs.has_hook(scope, "SessionStart", HOOK_NAME)
    n = _count_skills(_skills_dir(scope))
    out.heading("BMAD startup — %s" % scope)
    out.kv("enabled", str(bool(st.get("startup"))))
    out.kv("hook", "present" if hook else "absent")
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
        return 0
    cs.remove_hook(scope, "SessionStart", HOOK_NAME)
    cs.remove_hook(scope, "UserPromptSubmit", ROUTE_HOOK_NAME)
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
    cs.remove_hook(scope, "SessionStart", HOOK_NAME)
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
        personas = len(core.installed_personas(agents))
        router = cs.has_hook(scope, "UserPromptSubmit", ROUTE_HOOK_NAME)
        live = bool(st.get("autopilot")) and router
        out.kv(scope, "autopilot=%s  %d personas  router=%s  briefing=%s"
               % ("on" if live else "off", personas,
                  "on" if router else "off",
                  "on" if cs.has_hook(scope, "SessionStart", HOOK_NAME) else "off"))
        out.kv("  workflows", "skills=%d  installed=%s"
               % (_count_skills(_skills_dir(scope)), bool(st.get("installed"))))
    out.dim("  project = %s" % Path.cwd())
    if not any(_get_scope_state(s).get("autopilot") for s in ("global", "project")):
        out.dim("  turn it on with `boost bmad on`")
    return 0


# -------------------------------------------------------------------- helpers

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


def _proj_key() -> str:
    return str(Path.cwd().resolve())


def _get_scope_state(scope) -> dict:
    d = _state_read()
    if scope == "global":
        return d["global"]
    return d["projects"].get(_proj_key(), {})


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
