"""boost bmad — install & manage the BMAD Method, scope-aware and toggleable.

BMAD ships as Claude Code skills PLUS a per-project `_bmad/` config/runtime that
the skills read on activation. boost owns scope, the startup toggle, and teardown;
full provisioning is delegated to the canonical `npx bmad-method install`.

    boost bmad install --scope project     # skills + _bmad/ runtime in this repo
    boost bmad install --scope global      # skills into ~/.claude/skills (+ toggle)
    boost bmad init                        # add _bmad/ runtime to the current repo
    boost bmad startup on|off|status       # toggle the SessionStart orientation
                                           # (biases build/fix/change work to bmad-quick-dev)
    boost bmad disable / enable            # quarantine / restore skills (recoverable)
    boost bmad uninstall                   # delete skills + _bmad/ for a scope
    boost bmad doctor                      # what's installed where

Global installs stage the installer in a temp dir and copy only the `bmad-*`
skills into ~/.claude/skills, so $HOME never gets a stray `_bmad/`. The `_bmad/`
runtime is per-project (`boost bmad init`).
"""
from __future__ import annotations

import getpass
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path

from .. import cliparse
from ..core import claude_settings as cs
from ..core import journal, paths, util
from ..core import output as out
from ..errors import BoostError

DEFAULT_MODULES = "bmm"
HOOK_NAME = "bmad"
HOOK_MATCHER = "startup|resume|clear"

ORIENT = """[BMAD MODE ACTIVE — light orientation]
This environment has the BMAD Method installed as Claude Code skills. Be
BMAD-aware without hijacking simple requests: use the workflow when the user is
planning or building a feature; answer trivial one-off asks directly.

Entry point: invoke the `bmad-help` skill to assess state and recommend a step.

Persona agents (skills): bmad-agent-analyst (Mary, research/brief),
bmad-agent-pm (John, PRD), bmad-agent-architect (Winston, architecture),
bmad-agent-ux-designer (Sally), bmad-agent-dev (Amelia, implementation),
bmad-agent-tech-writer (Paige).

Phases: Analysis (bmad-brainstorming -> bmad-product-brief -> research) ->
Planning (bmad-prd -> bmad-architecture -> bmad-create-epics-and-stories) ->
Build (bmad-sprint-planning -> bmad-create-story -> bmad-dev-story ->
bmad-code-review -> bmad-qa-generate-e2e-tests -> bmad-retrospective).

Default bias: for a build, fix, change, or refactor request, go straight to the
`bmad-quick-dev` skill (clarify -> plan -> implement -> review) — skip the full
brief -> PRD -> architecture ceremony unless the user asks for full planning.

Full workflows need a per-project `_bmad/` runtime — run `boost bmad init` in a
repo if it isn't there yet. Turn this orientation off with `boost bmad startup off`."""

_ACTIONS = ("install", "init", "startup", "orient", "uninstall",
            "disable", "enable", "doctor", "status")


def cmd_bmad(argv) -> int:
    p = cliparse.parser(
        prog="boost bmad",
        description="Install & manage the BMAD Method (scope-aware, toggleable)")
    p.add_argument("action", choices=_ACTIONS, help=" | ".join(_ACTIONS))
    p.add_argument("value", nargs="?", help="for startup: on | off | status")
    p.add_argument("-s", "--scope", choices=("project", "global"), default=None,
                   help="target scope (default: project)")
    p.add_argument("--modules", default=DEFAULT_MODULES,
                   help="BMAD modules to install (default: %s)" % DEFAULT_MODULES)
    p.add_argument("-y", "--yes", action="store_true",
                   help="skip confirmation prompts")
    p.add_argument("--startup", action="store_true",
                   help="enable the startup toggle right after install")
    args = p.parse_args(argv)

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
    """SessionStart hook target: print orientation iff enabled (else silent)."""
    scope = scope or "project"
    with suppress(Exception):  # a hook must never break the session
        if _get_scope_state(scope).get("startup"):
            print(ORIENT)
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
    removed = _rm_skills(_skills_dir(scope))
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
    out.kv("npx", shutil.which("npx") or "MISSING")
    out.kv("node", shutil.which("node") or "MISSING")
    for scope in ("global", "project"):
        st = _get_scope_state(scope)
        n = _count_skills(_skills_dir(scope))
        hook = cs.has_hook(scope, "SessionStart", HOOK_NAME)
        out.kv(scope, "skills=%d  startup=%s  hook=%s  installed=%s"
               % (n, bool(st.get("startup")), hook, bool(st.get("installed"))))
    out.dim("  project = %s" % Path.cwd())
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
