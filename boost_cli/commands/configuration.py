"""Configuration commands: config, clean, create, policy, onboard,
completions, schedule, serve, mcp, self-update."""
from __future__ import annotations

import errno
import getpass
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import cliparse
from .. import __version__
from ..core import agents, catalog, config, frontmatter, gitutil, journal
from ..core import lockfile, mcp, paths, policy, rag, registry, store, util
from ..core import output as out
from ..errors import BoostError


def _tilde(p) -> str:
    """Contract $HOME to ~ in a path-ish string for display."""
    s = str(p)
    for h in {str(paths.home()), str(paths.home().resolve())}:
        if s == h:
            return "~"
        if s.startswith(h + os.sep):
            return "~" + s[len(h):]
    return s


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- config

def cmd_config(argv) -> int:
    """boost config [list|get KEY|set KEY VALUE|unset KEY] [--json]"""
    p = cliparse.parser(
        prog="boost config",
        description="Display or modify boost configuration")
    p.add_argument("action", nargs="?", default="list",
                   choices=("list", "get", "set", "unset"),
                   help="what to do (default: list)")
    p.add_argument("key", nargs="?", help="dotted key, e.g. ai.enabled")
    p.add_argument("value", nargs="?", help="new value (JSON or string)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output")
    args = p.parse_args(argv)
    if args.action in ("get", "set", "unset") and not args.key:
        raise BoostError("config %s requires a KEY" % args.action,
                        hint="e.g. `boost config %s ai.enabled`" % args.action)
    if args.action == "set" and args.value is None:
        raise BoostError("config set requires a VALUE",
                        hint="e.g. `boost config set ai.enabled false`")

    if args.action == "list":
        cfg = config.load()
        print(json.dumps(cfg, indent=2))
        if not args.json:
            out.dim("  " + _tilde(paths.config_path()))
        return 0

    if args.action == "get":
        missing = object()
        val = config.get(args.key, missing)
        if val is missing:
            raise BoostError("no config key %r" % args.key,
                            hint="see `boost config list`")
        if args.json:
            print(json.dumps(val))
        elif isinstance(val, str):
            print(val)
        else:
            print(json.dumps(val, indent=2))
        return 0

    if args.action == "set":
        try:
            config.set_value(args.key, args.value)
        except TypeError as e:
            raise BoostError(str(e),
                            hint="the parent key holds a plain value — "
                                 "`boost config unset` it first")
        val = config.get(args.key)
        journal.log("config", args.key, op="set")
        out.ok("set %s = %s"
               % (args.key, val if isinstance(val, str) else json.dumps(val)))
        return 0

    # unset
    if config.unset(args.key):
        journal.log("config", args.key, op="unset")
        out.ok("unset %s" % args.key)
    else:
        out.info("%s not set" % args.key)
    return 0


# ---------------------------------------------------------------- clean

def cmd_clean(argv) -> int:
    """boost clean [--dry-run] [--deep]"""
    p = cliparse.parser(
        prog="boost clean",
        description="Clear stale caches & broken symlinks")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be removed without touching anything")
    p.add_argument("--deep", action="store_true",
                   help="also remove snapshots older than 90 days")
    args = p.parse_args(argv)

    items = []  # (path, kind, bytes)
    for _agent, spec in agents.known_agents().items():
        adir = spec["dir"]
        if not adir.is_dir():
            continue
        for link in sorted(adir.iterdir()):
            if link.is_symlink() and not link.exists():
                items.append((link, "broken symlink", 0))

    configured = {t.safe_name for t in registry.list_taps()}
    if paths.cache_dir().is_dir():
        for f in sorted(paths.cache_dir().glob("*.json")):
            if f.stem not in configured:
                items.append((f, "stale tap cache", f.stat().st_size))

    if paths.lock_history_dir().is_dir():
        snaps = sorted(paths.lock_history_dir().glob("lock-*.json"))
        for old in snaps[:-50]:
            items.append((old, "old lock history", old.stat().st_size))

    if paths.store_dir().is_dir():
        for pth in sorted(paths.store_dir().rglob("*")):
            if pth.name == "__pycache__" and pth.is_dir():
                items.append((pth, "__pycache__", util.dir_size(pth)))
            elif pth.name == ".DS_Store" and pth.is_file():
                items.append((pth, ".DS_Store", pth.stat().st_size))

    if args.deep and paths.snapshots_dir().is_dir():
        cutoff = time.time() - 90 * 86400
        old_snaps = [s for s in sorted(paths.snapshots_dir().iterdir())
                     if s.lstat().st_mtime < cutoff]
        if old_snaps and not args.dry_run and not out.confirm(
                "remove %d snapshot(s) older than 90 days?" % len(old_snaps)):
            out.info("keeping old snapshots")
            old_snaps = []
        for s in old_snaps:
            size = util.dir_size(s) if s.is_dir() else s.lstat().st_size
            items.append((s, "old snapshot", size))

    if not items:
        out.ok("nothing to clean")
        return 0

    verb = "would remove" if args.dry_run else "removed"
    freed = 0
    for pth, kind, size in items:
        if not args.dry_run:
            try:
                if pth.is_symlink() or pth.is_file():
                    pth.unlink()
                elif pth.is_dir():
                    shutil.rmtree(pth)
            except OSError as e:
                out.warn("could not remove %s: %s" % (_tilde(pth), e))
                continue
        freed += size
        out.info("%s %s %s" % (verb, _tilde(pth), out.c("(%s)" % kind, out.DIM)))
    if args.dry_run:
        out.dim("  %d item(s) · %s would be freed" % (len(items), util.human_size(freed)))
    else:
        journal.log("clean", "%d items" % len(items), freed=util.human_size(freed))
        out.ok("cleaned %d item(s) · %s freed" % (len(items), util.human_size(freed)))
    return 0


# ---------------------------------------------------------------- create

_CREATE_BODY = """# %(title)s

## When to use

TODO: describe the situations where this skill should activate.

## Instructions

1. TODO: first step the assistant should take
2. TODO: second step
3. TODO: third step

## Rules

- TODO: something the assistant must always do
- TODO: something the assistant must never do

## Examples

```text
TODO: a concrete input/output example
```
"""


def cmd_create(argv) -> int:
    """boost create NAME [--description D] [--dir DIR] [--install]"""
    p = cliparse.parser(
        prog="boost create",
        description="Scaffold a new skill from a template")
    p.add_argument("name", help="skill name (slugified)")
    p.add_argument("--description", default=None,
                   help="one-line trigger description for the frontmatter")
    p.add_argument("--dir", default=None,
                   help="parent directory (default: current directory)")
    p.add_argument("--install", action="store_true",
                   help="install the new skill immediately")
    args = p.parse_args(argv)

    name = util.slugify(args.name)
    parent = paths.expand(args.dir) if args.dir else Path.cwd()
    target = parent / name
    skill_md = target / "SKILL.md"
    if skill_md.exists():
        raise BoostError("%s already exists" % _tilde(skill_md),
                        hint="pick another name or --dir, or edit the existing file")

    meta = {
        "name": name,
        "description": args.description
        or "TODO: describe when this skill should trigger",
        "version": "0.1.0",
    }
    title = name.replace("-", " ").title()
    target.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(frontmatter.dump(meta) + "\n\n"
                        + _CREATE_BODY % {"title": title})
    journal.log("create", name, path=str(target))
    out.ok("created %s" % _tilde(skill_md))
    if args.install:
        res = store.install_from_path(target, name=name)
        out.ok("installed %s → %s" % (name, _tilde(res.dest)))
        if res.linked:
            out.info("linked: " + ", ".join(agents.display_name(a) for a in res.linked))
    else:
        out.dim("  next: edit it, then `boost import %s`" % _tilde(target))
    return 0


# ---------------------------------------------------------------- policy

def _parse_policy_value(key: str, raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    if isinstance(policy.DEFAULTS.get(key), list):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return raw


def cmd_policy(argv) -> int:
    """boost policy [list|set KEY VALUE|unset KEY|check] [--json]"""
    p = cliparse.parser(
        prog="boost policy",
        description="Manage & enforce skill governance policies")
    p.add_argument("action", nargs="?", default="list",
                   choices=("list", "set", "unset", "check"),
                   help="what to do (default: list)")
    p.add_argument("key", nargs="?", help="policy key, e.g. min_quality_score")
    p.add_argument("value", nargs="?", help="new value (JSON, comma list, or string)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output")
    args = p.parse_args(argv)

    if args.action in ("set", "unset"):
        if not args.key:
            raise BoostError("policy %s requires a KEY" % args.action,
                            hint="keys: " + ", ".join(sorted(policy.DEFAULTS)))
        if args.key not in policy.DEFAULTS:
            raise BoostError("unknown policy key %r" % args.key,
                            hint="keys: " + ", ".join(sorted(policy.DEFAULTS)))

    if args.action == "list":
        pol = policy.load()
        print(json.dumps(pol, indent=2))
        if not args.json:
            diff = sorted(k for k in policy.DEFAULTS
                          if pol.get(k) != policy.DEFAULTS[k])
            out.dim("  modified from defaults: %s" % ", ".join(diff)
                    if diff else "  all values at defaults")
        return 0

    if args.action == "set":
        if args.value is None:
            raise BoostError("policy set requires a VALUE",
                            hint="e.g. `boost policy set min_quality_score 60`")
        pol = policy.load()
        pol[args.key] = _parse_policy_value(args.key, args.value)
        policy.save(pol)
        journal.log("policy", args.key, op="set")
        out.ok("set %s = %s" % (args.key, json.dumps(pol[args.key])))
        return 0

    if args.action == "unset":
        pol = policy.load()
        pol[args.key] = policy.DEFAULTS[args.key]
        policy.save(pol)
        journal.log("policy", args.key, op="unset")
        out.ok("reset %s to default (%s)"
               % (args.key, json.dumps(policy.DEFAULTS[args.key])))
        return 0

    # check
    pol = policy.load()
    installed = lockfile.installed()
    min_score = int(pol.get("min_quality_score") or 0)
    violations = []  # (skill, problem)
    for name, entry in sorted(installed.items()):
        tap = entry.get("tap", "local")
        if name in pol["blocked_skills"]:
            violations.append((name, "on the blocklist"))
        if tap in pol["blocked_taps"]:
            violations.append((name, "tap %s is blocked" % tap))
        if pol["allowed_taps"] and tap not in pol["allowed_taps"] and tap != "local":
            violations.append((name, "tap %s is not on the allowlist" % tap))
        if min_score:
            score, _notes = util.score_skill(store.skill_store_dir(name))
            if score < min_score:
                violations.append(
                    (name, "quality score %d < required %d" % (score, min_score)))
    unpinned = sorted(n for n, e in installed.items() if not e.get("pinned"))

    if args.json:
        print(json.dumps({
            "skills": len(installed),
            "violations": [{"skill": s, "violation": v} for s, v in violations],
            "pin_only": bool(pol["pin_only"]),
            "unpinned": unpinned if pol["pin_only"] else [],
        }, indent=2))
        return 1 if violations else 0

    if pol["pin_only"]:
        out.info("pin-only mode is on — installs/updates are frozen"
                 + (" (%d unpinned skill(s): %s)"
                    % (len(unpinned), ", ".join(unpinned)) if unpinned else ""))
    if violations:
        out.table(violations, headers=("SKILL", "VIOLATION"))
        print()
        out.err("%d policy violation(s) across %d installed skill(s)"
                % (len(violations), len(installed)),
                hint="adjust with `boost policy set` or remove the offenders")
        return 1
    out.ok("policy check passed (%d skills)" % len(installed))
    return 0


# ---------------------------------------------------------------- onboard

_WORKFLOW_REL = ".github/workflows/boost-skill-inventory.yml"
_TELEMETRY_REL = ".boost/telemetry.json"

_WORKFLOW_YML = """\
# generated by `boost onboard` — publishes this repo's AI-skill inventory
name: boost skill inventory

on:
  push:
    branches: [main]
  workflow_dispatch: {}

jobs:
  inventory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Report skill count
        if: ${{ hashFiles('.skill-lock.json') != '' }}
        run: |
          python3 -c "import json; d = json.load(open('.skill-lock.json')); print(len(d.get('skills', {})), 'skills tracked')"
      - name: Upload skill inventory
        if: ${{ hashFiles('.skill-lock.json') != '' }}
        uses: actions/upload-artifact@v4
        with:
          name: skill-lock
          path: .skill-lock.json
"""


def cmd_onboard(argv) -> int:
    """boost onboard [--repo DIR] [--pr] [--dry-run]"""
    p = cliparse.parser(
        prog="boost onboard",
        description="Add skill-tracker telemetry to a repo & open a PR")
    p.add_argument("--repo", default=".", help="repository directory (default: .)")
    p.add_argument("--pr", action="store_true",
                   help="commit on a branch and open a PR with `gh`")
    p.add_argument("--dry-run", action="store_true",
                   help="preview the files without writing anything")
    args = p.parse_args(argv)

    repo = paths.expand(args.repo).resolve()
    if not repo.is_dir():
        raise BoostError("%s is not a directory" % _tilde(repo),
                        hint="point --repo at a checked-out repository")

    telemetry = json.dumps({
        "enabled": True,
        "share_pulse": True,
        "created": util.now_iso(),
        "by": _user(),
    }, indent=2) + "\n"
    files = [(_TELEMETRY_REL, telemetry), (_WORKFLOW_REL, _WORKFLOW_YML)]
    if repo != paths.store_dir().resolve():
        files.append((".skill-lock.json",
                      json.dumps(lockfile.read(), indent=2, sort_keys=True) + "\n"))

    if args.dry_run:
        for rel, content in files:
            out.heading("would write %s" % _tilde(repo / rel))
            for line in content.splitlines()[:24]:
                out.dim("    " + line)
        return 0

    if args.pr:  # check preconditions FIRST so we never leave the repo mid-state
        if not gitutil.is_repo(repo):
            raise BoostError("%s is not a git repository" % _tilde(repo),
                            hint="--pr needs a git checkout with a GitHub remote")
        if gitutil.run(["-C", str(repo), "status", "--porcelain"]).stdout.strip():
            raise BoostError("working tree at %s is not clean" % _tilde(repo),
                            hint="commit or stash your changes first")
        if not shutil.which("gh"):
            raise BoostError("the `gh` CLI is required for --pr",
                            hint="brew install gh, or rerun without --pr")

    for rel, content in files:
        fp = repo / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        out.ok("created %s" % _tilde(fp))
    journal.log("onboard", _tilde(repo), pr=args.pr or None)

    if args.pr:
        branch = "boost/onboard-skill-tracker"
        gitutil.run(["-C", str(repo), "checkout", "-b", branch])
        gitutil.run(["-C", str(repo), "add"] + [rel for rel, _ in files])
        gitutil.run(["-C", str(repo), "commit", "-m",
                     "chore: add boost skill tracking (boost onboard)"])
        try:
            proc = subprocess.run(["gh", "pr", "create", "--fill"],
                                  cwd=str(repo), capture_output=True,
                                  text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as e:
            raise BoostError("gh pr create failed: %s" % e,
                            hint="branch %s is committed — push it and open the PR manually" % branch)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise BoostError("gh pr create failed: %s" % (tail[-1] if tail else "unknown error"),
                            hint="branch %s is committed — push it and run `gh pr create --fill`" % branch)
        url = (proc.stdout or "").strip().splitlines()
        out.ok("opened PR%s" % ((" " + url[-1]) if url else ""))
    return 0


# ---------------------------------------------------------------- completions

def _sq(s: str) -> str:
    """Escape a string for a POSIX/zsh single-quoted context."""
    return s.replace("'", "'\\''")


def cmd_completions(argv) -> int:
    """boost completions [bash|zsh|fish]"""
    p = cliparse.parser(
        prog="boost completions",
        description="Generate shell tab-completion scripts")
    p.add_argument("shell", nargs="?", choices=("bash", "zsh", "fish"),
                   default=None, help="target shell (default: from $SHELL)")
    args = p.parse_args(argv)
    from ..cli import COMMANDS

    shell = args.shell or Path(os.environ.get("SHELL", "")).name
    if shell not in ("bash", "zsh", "fish"):
        shell = "bash"

    names = [n for n, _g, _m, _s in COMMANDS]
    if shell == "bash":
        lines = ["# boost bash completion",
                 'complete -W "%s" boost' % " ".join(names)]
        hint = "boost completions bash >> ~/.bashrc"
    elif shell == "zsh":
        lines = ["#compdef boost", "", "_boost() {", "  local -a _boost_commands",
                 "  _boost_commands=("]
        lines += ["    '%s:%s'" % (n, _sq(s)) for n, _g, _m, s in COMMANDS]
        lines += ["  )", "  if (( CURRENT == 2 )); then",
                  "    _describe -t commands 'boost command' _boost_commands",
                  "  else", "    _files", "  fi", "}", "", '_boost "$@"']
        hint = "boost completions zsh > ~/.zfunc/_boost   (with fpath+=~/.zfunc before compinit)"
    else:
        lines = ["# boost fish completion"]
        lines += ["complete -c boost -n __fish_use_subcommand -a %s -d '%s'"
                  % (n, s.replace("\\", "\\\\").replace("'", "\\'"))
                  for n, _g, _m, s in COMMANDS]
        hint = "boost completions fish > ~/.config/fish/completions/boost.fish"
    print("\n".join(lines))
    out.dim("# install: " + hint)
    return 0


# ---------------------------------------------------------------- schedule

_INTERVALS = {"6h": 21600, "12h": 43200, "daily": 86400}
_CRON_SPECS = {"6h": "0 */6 * * *", "12h": "0 */12 * * *", "daily": "0 6 * * *"}
_PLIST_LABEL = "com.boost.sync"
_CRON_MARK = "# boost-sync"


def _plist_path() -> Path:
    return paths.home() / "Library" / "LaunchAgents" / (_PLIST_LABEL + ".plist")


def _plist_body(shim: Path, seconds: int) -> str:
    log = paths.logs_dir() / "schedule.log"
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>%s</string>
  <key>ProgramArguments</key>
  <array>
    <string>%s</string>
    <string>update</string>
  </array>
  <key>StartInterval</key><integer>%d</integer>
  <key>StandardOutPath</key><string>%s</string>
  <key>StandardErrorPath</key><string>%s</string>
</dict>
</plist>
""" % (_PLIST_LABEL, shim, seconds, log, log)


def _crontab_lines():
    """Current crontab lines, [] when empty, None when crontab is unusable."""
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return []  # "no crontab for user"
    return proc.stdout.splitlines()


def _cron_field_ok(field: str, val: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        try:
            return val % int(field[2:]) == 0
        except (ValueError, ZeroDivisionError):
            return False
    try:
        return val == int(field)
    except ValueError:
        return False


def _cron_next_run(spec: str):
    """Best-effort next fire time for a `M H * * *`-shaped cron spec."""
    parts = spec.split()
    if len(parts) < 2:
        return None
    t = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(2 * 24 * 60):
        if _cron_field_ok(parts[0], t.minute) and _cron_field_ok(parts[1], t.hour):
            return t
        t += timedelta(minutes=1)
    return None


def _interval_label(seconds) -> str:
    for label, secs in _INTERVALS.items():
        if secs == seconds:
            return label
    return "%ss" % seconds


def cmd_schedule(argv) -> int:
    """boost schedule [status|enable [--interval 6h|12h|daily]|disable]"""
    p = cliparse.parser(
        prog="boost schedule",
        description="Manage automatic skill-sync scheduling")
    p.add_argument("action", nargs="?", default="status",
                   choices=("status", "enable", "disable"),
                   help="what to do (default: status)")
    p.add_argument("--interval", choices=tuple(_INTERVALS), default="6h",
                   help="how often to run `boost update` (default: 6h)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output (status only)")
    args = p.parse_args(argv)

    darwin = sys.platform == "darwin"
    shim = paths.launcher()

    if args.action == "status":
        present, interval, next_run = False, None, None
        if darwin:
            plist = _plist_path()
            if plist.exists():
                present = True
                m = re.search(r"<key>StartInterval</key>\s*<integer>(\d+)</integer>",
                              plist.read_text())
                if m:
                    secs = int(m.group(1))
                    interval = _interval_label(secs)
                    nxt = datetime.fromtimestamp(plist.stat().st_mtime + secs)
                    while nxt < datetime.now():
                        nxt += timedelta(seconds=secs)
                    next_run = nxt
        else:
            lines = _crontab_lines() or []
            job = next((ln for ln in lines if ln.rstrip().endswith(_CRON_MARK)), None)
            if job:
                present = True
                spec = " ".join(job.split()[:5])
                interval = next((lbl for lbl, s in _CRON_SPECS.items() if s == spec),
                                spec)
                next_run = _cron_next_run(spec)
        if args.json:
            print(json.dumps({
                "platform": sys.platform,
                "backend": "launchd" if darwin else "cron",
                "scheduled": present,
                "interval": interval,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M") if next_run else None,
            }, indent=2))
            return 0
        out.kv("platform", "%s (%s)" % (sys.platform, "launchd" if darwin else "cron"))
        out.kv("scheduled", "yes" if present else "no")
        if present:
            out.kv("interval", "every %s" % interval)
            out.kv("next run", next_run.strftime("%Y-%m-%d %H:%M (approx)")
                   if next_run else "unknown")
        else:
            out.dim("  enable with `boost schedule enable --interval 6h|12h|daily`")
        return 0

    if args.action == "enable":
        seconds = _INTERVALS[args.interval]
        paths.ensure_dirs()
        if darwin:
            plist = _plist_path()
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_text(_plist_body(shim, seconds))
            out.ok("wrote %s" % _tilde(plist))
            try:
                subprocess.run(["launchctl", "unload", str(plist)],
                               capture_output=True, text=True, timeout=30)
                proc = subprocess.run(["launchctl", "load", "-w", str(plist)],
                                      capture_output=True, text=True, timeout=30)
                if proc.returncode != 0:
                    tail = (proc.stderr or "").strip().splitlines()
                    out.warn("launchctl load failed: %s"
                             % (tail[-1] if tail else "unknown error"))
                    out.dim("  load it manually: launchctl load -w %s" % _tilde(plist))
                else:
                    out.ok("`boost update` scheduled every %s" % args.interval)
            except (OSError, subprocess.TimeoutExpired):
                out.warn("launchctl unavailable — the agent loads at next login")
        else:
            lines = _crontab_lines()
            entry = "%s %s update >> %s 2>&1 %s" % (
                _CRON_SPECS[args.interval], shim,
                paths.logs_dir() / "schedule.log", _CRON_MARK)
            if lines is None:
                out.warn("crontab is not available — add this line yourself:")
                out.info(entry)
            else:
                kept = [ln for ln in lines if not ln.rstrip().endswith(_CRON_MARK)]
                try:
                    proc = subprocess.run(["crontab", "-"],
                                          input="\n".join(kept + [entry]) + "\n",
                                          capture_output=True, text=True, timeout=30)
                except (OSError, subprocess.TimeoutExpired):
                    proc = None
                if proc is None or proc.returncode != 0:
                    out.warn("could not write crontab — add this line yourself:")
                    out.info(entry)
                else:
                    out.ok("`boost update` scheduled every %s via cron" % args.interval)
        journal.log("schedule", "enable", interval=args.interval)
        return 0

    # disable
    removed = False
    if darwin:
        plist = _plist_path()
        if plist.exists():
            try:
                subprocess.run(["launchctl", "unload", "-w", str(plist)],
                               capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                out.warn("launchctl unavailable — removed the plist only")
            plist.unlink()
            removed = True
    else:
        lines = _crontab_lines()
        if lines:
            kept = [ln for ln in lines if not ln.rstrip().endswith(_CRON_MARK)]
            if len(kept) != len(lines):
                try:
                    proc = subprocess.run(["crontab", "-"],
                                          input="\n".join(kept) + ("\n" if kept else ""),
                                          capture_output=True, text=True, timeout=30)
                    removed = proc.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if not removed:
                    out.warn("could not rewrite crontab — remove the %s line yourself"
                             % _CRON_MARK)
    if removed:
        journal.log("schedule", "disable")
        out.ok("automatic sync disabled")
    else:
        out.info("no schedule was configured")
    return 0


# ---------------------------------------------------------------- serve

_PAGE_CSS = ("body{background:#111;color:#ddd;font-family:ui-monospace,SFMono-Regular,"
             "Menlo,monospace;max-width:720px;margin:2rem auto;padding:0 1rem}"
             "h1{color:#fff;font-size:1.3rem}a{color:#7dc4ff;text-decoration:none}"
             "a:hover{text-decoration:underline}table{border-collapse:collapse;width:100%}"
             "th,td{text-align:left;padding:.3rem .8rem .3rem 0;"
             "border-bottom:1px solid #2a2a2a}.dim{color:#777}")


def _serve_page() -> str:
    installed = lockfile.installed()
    entries = catalog.all_entries()
    taps = registry.list_taps()
    rows = "".join(
        '<tr><td><a href="/skill/%s">%s</a></td><td>%s</td><td>%s</td></tr>'
        % (urllib.parse.quote(n), html.escape(n),
           html.escape(str(e.get("version", "?"))),
           html.escape(str(e.get("tap", "?"))))
        for n, e in sorted(installed.items()))
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>boost — skill catalog</title><style>%s</style></head><body>"
            "<h1>⚡ boost <span class='dim'>v%s</span></h1>"
            "<p class='dim'>%d installed · %d available across %d taps</p>"
            "<table><tr><th>skill</th><th>version</th><th>tap</th></tr>%s</table>"
            "<p><a href='/installed.json'>installed.json</a> · "
            "<a href='/catalog.json'>catalog.json</a></p></body></html>"
            % (_PAGE_CSS, __version__, len(installed), len(entries), len(taps),
               rows or "<tr><td colspan='3' class='dim'>nothing installed</td></tr>"))


def _skill_text(name: str):
    """SKILL.md text for an installed skill, else from a tap. None if unknown."""
    if not re.match(r"^[A-Za-z0-9._-]+$", name):
        return None
    fp = store.skill_store_dir(name) / "SKILL.md"
    if fp.is_file():
        return fp.read_text(encoding="utf-8", errors="replace")
    for e in catalog.find(name):
        try:
            fp = registry.get(e["tap"]).path / e["skill_md"]
        except BoostError:
            continue
        if fp.is_file():
            return fp.read_text(encoding="utf-8", errors="replace")
    return None


class _CatalogHandler(BaseHTTPRequestHandler):
    server_version = "boost/" + __version__

    def log_message(self, fmt, *args):  # logged in _send instead
        pass

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        out.dim("  %s %s → %d" % (self.command, self.path, status))

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        try:
            if path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", _serve_page().encode())
            elif path == "/catalog.json":
                self._send(200, "application/json",
                           json.dumps(catalog.all_entries(), indent=2).encode())
            elif path == "/installed.json":
                self._send(200, "application/json",
                           json.dumps(lockfile.read(), indent=2).encode())
            elif path.startswith("/skill/"):
                name = path[len("/skill/"):].strip("/")
                text = _skill_text(name)
                if text is None:
                    self._send(404, "application/json",
                               json.dumps({"error": "no skill named %r" % name}).encode())
                else:
                    self._send(200, "text/plain; charset=utf-8", text.encode())
            else:
                self._send(404, "application/json",
                           json.dumps({"error": "not found"}).encode())
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001 — keep the server alive
            try:
                self._send(500, "application/json",
                           json.dumps({"error": str(e)}).encode())
            except Exception:
                pass


def cmd_serve(argv) -> int:
    """boost serve [--port N] [--host H]"""
    p = cliparse.parser(
        prog="boost serve",
        description="Serve the skill catalog over HTTP (port 8787)")
    p.add_argument("--port", type=int,
                   default=int(config.get("serve.port", 8787) or 8787),
                   help="port to listen on (default: config serve.port)")
    p.add_argument("--host", default="127.0.0.1",
                   help="address to bind (default: 127.0.0.1)")
    args = p.parse_args(argv)

    try:
        httpd = ThreadingHTTPServer((args.host, args.port), _CatalogHandler)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            raise BoostError("port %d is already in use" % args.port,
                            hint="pick another with --port")
        raise BoostError("cannot bind %s:%d — %s" % (args.host, args.port, e),
                        hint="check --host and --port")
    out.info("⚡ serving skill catalog on http://%s:%d %s"
             % (args.host, args.port, out.c("(ctrl-c to stop)", out.DIM)))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        out.ok("server stopped")
    finally:
        httpd.server_close()
    return 0


# ---------------------------------------------------------------- mcp

# The MCP tool surface is an extensible registry (core/mcp.py): each handler is
# a small `fn(args) -> (text, is_error)` that self-registers its JSON spec, so a
# new capability is one REGISTRY.register(...) call — no dispatcher edits. This
# is the Phase-3 "MCP as a hub" seam (docs/rag-architecture.md §8).

REGISTRY = mcp.Registry()


def _tool_search(args: dict):
    query = str(args.get("query", ""))
    rag_result = rag.search(query, limit=10)
    if rag_result is not None:  # full-content index is built
        hits, _ranker = rag_result
        if not hits:
            return "no skills match %r" % query, False
        return "\n".join(
            "%s — %s (%s)" % (h["entry"]["name"],
                              h["entry"].get("description", ""),
                              h["entry"]["tap"])
            for h in hits), False
    # no index yet -> keep today's frontmatter search so nothing regresses
    scored = catalog.search(query)[:10]
    if not scored:
        return "no skills match %r" % query, False
    return "\n".join("%s — %s (%s)" % (e["name"], e["description"], e["tap"])
                     for e, _score in scored), False


def _tool_list(args: dict):
    skills = lockfile.installed()
    if not skills:
        return "no skills installed", False
    return "\n".join("%s v%s (%s)%s"
                     % (n, e.get("version", "?"), e.get("tap", "?"),
                        " [pinned]" if e.get("pinned") else "")
                     for n, e in sorted(skills.items())), False


def _tool_info(args: dict):
    name = str(args.get("name", ""))
    entry = lockfile.get_skill(name)
    matches = catalog.find(name)
    if not entry and not matches:
        return "no skill named %r (installed or in any tap)" % name, True
    src = matches[0] if matches else {}
    lines = ["name: " + name,
             "version: %s" % (entry or src).get("version", "?"),
             "tap: %s" % (entry or src).get("tap", "?")]
    if src.get("description"):
        lines.append("description: %s" % src["description"])
    if entry:
        lines.append("installed: yes (%s)" % entry.get("installed_at", "?"))
        lines.append("agents: %s" % (", ".join(entry.get("agents") or []) or "none"))
        if entry.get("pinned"):
            lines.append("pinned: yes")
    else:
        lines.append("installed: no")
    return "\n".join(lines), False


def _tool_install(args: dict):
    entry = catalog.resolve_one(str(args.get("name", "")))
    res = store.install(entry)
    lines = ["installed %s v%s from %s → %s"
             % (res.name, entry.get("version", "?"), entry["tap"], res.dest),
             "linked agents: %s" % (", ".join(res.linked) or "none"),
             "quality score: %d/100" % res.score]
    if res.conflicts:
        lines.append("conflicts (left in place): %s" % ", ".join(res.conflicts))
    return "\n".join(lines), False


def _tool_doctor(args: dict):
    plan = store.sync_plan()
    issues = sum(len(v) for v in plan.values())
    taps = registry.list_taps()
    lines = ["installed skills: %d" % len(lockfile.installed()),
             "taps: %d (%d skills available)" % (len(taps), len(catalog.all_entries()))]
    for key, vals in plan.items():
        if vals:
            lines.append("%s: %s" % (key, ", ".join(str(v) for v in vals)))
    lines.append("healthy — no issues found" if issues == 0
                 else "%d issue(s) — run `boost sync` to fix" % issues)
    return "\n".join(lines), issues > 0


def _tool_discover_github(args: dict):
    """Grow the corpus: GitHub code-search for SKILL.md repos (needs `gh`).

    A Phase-3 reach-out tool. Degrades the ``core/ai.py`` way — if `gh` is absent
    or the search fails, it returns a short helpful message instead of raising,
    so the MCP server never dies on a missing external dependency.
    """
    from . import discovery
    if not shutil.which("gh"):
        return ("GitHub discovery needs the `gh` CLI — install it with "
                "`brew install gh && gh auth login`, then retry."), True
    query = str(args.get("query", ""))
    raw = args.get("limit")
    limit = int(raw) if isinstance(raw, (int, float)) and int(raw) > 0 else 20
    limit = min(limit, 100)
    hits = discovery.github_skill_search(query, limit)
    if hits is None:
        return ("GitHub code search failed — check `gh auth status` and retry."), True
    if not hits:
        return ("no SKILL.md repositories found on GitHub for %r"
                % (query.strip() or "any query")), False
    return "\n".join("%s — %s" % (h["repo"], h.get("description") or h.get("path", ""))
                     for h in hits), False


REGISTRY.register(
    "boost_search",
    "Search AI coding skills across the configured tap registries",
    {"type": "object",
     "properties": {"query": {"type": "string", "description": "search terms"}},
     "required": ["query"]},
    _tool_search)
REGISTRY.register(
    "boost_list",
    "List the skills currently installed by boost",
    {"type": "object", "properties": {}},
    _tool_list)
REGISTRY.register(
    "boost_info",
    "Show detailed information about one skill",
    {"type": "object",
     "properties": {"name": {"type": "string", "description": "skill name"}},
     "required": ["name"]},
    _tool_info)
REGISTRY.register(
    "boost_install",
    "Install a skill from a configured tap registry",
    {"type": "object",
     "properties": {"name": {"type": "string", "description": "skill name"}},
     "required": ["name"]},
    _tool_install)
REGISTRY.register(
    "boost_doctor",
    "Health summary of the boost skill environment",
    {"type": "object", "properties": {}},
    _tool_doctor)
REGISTRY.register(
    "boost_discover_github",
    "Discover new SKILL.md repositories on GitHub to grow the corpus (needs the "
    "`gh` CLI; degrades to a hint when unavailable)",
    {"type": "object",
     "properties": {
         "query": {"type": "string",
                   "description": "optional extra search terms (topic, language)"},
         "limit": {"type": "integer",
                   "description": "max repositories to return (default 20)"}}},
    _tool_discover_github)

# Back-compat shims: the JSON-RPC server and tests reference these names.
_MCP_TOOLS = REGISTRY.specs()


def _mcp_tool(tool: str, args: dict):
    """Run one MCP tool -> (text, is_error). (None, _) for unknown tools."""
    return REGISTRY.call(tool, args)


def _mcp_send(msg: dict) -> bool:
    try:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
        return True
    except (BrokenPipeError, OSError):
        return False


def _mcp_serve_stdio() -> int:
    """Newline-delimited JSON-RPC 2.0 MCP server on stdin/stdout."""
    while True:
        try:
            line = sys.stdin.readline()
        except (KeyboardInterrupt, OSError):
            return 0
        if not line:  # EOF
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            if not _mcp_send({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": "parse error"}}):
                return 0
            continue
        method = str(req.get("method", ""))
        if "id" not in req:  # notification (e.g. notifications/initialized)
            continue
        resp = {"jsonrpc": "2.0", "id": req.get("id")}
        if method == "initialize":
            resp["result"] = {"protocolVersion": "2024-11-05",
                              "capabilities": {"tools": {}},
                              "serverInfo": {"name": "boost", "version": __version__}}
        elif method == "ping":
            resp["result"] = {}
        elif method == "tools/list":
            resp["result"] = {"tools": _MCP_TOOLS}
        elif method == "tools/call":
            params = req.get("params") or {}
            tool = str(params.get("name", ""))
            try:
                text, is_err = _mcp_tool(tool, params.get("arguments") or {})
            except BoostError as e:
                text = "Error: %s" % e.message + ("\nhint: %s" % e.hint if e.hint else "")
                is_err = True
            except Exception as e:  # noqa: BLE001 — server must not die
                text, is_err = "Error: %s" % e, True
            if text is None:
                resp["error"] = {"code": -32602, "message": "unknown tool %r" % tool}
            else:
                resp["result"] = {"content": [{"type": "text", "text": text}]}
                if is_err:
                    resp["result"]["isError"] = True
        else:
            resp["error"] = {"code": -32601, "message": "method not found: %s" % method}
        if not _mcp_send(resp):
            return 0


def cmd_mcp(argv) -> int:
    """boost mcp [register|unregister] [--stdio]"""
    p = cliparse.parser(
        prog="boost mcp",
        description="Register boost as an MCP server for Claude Code")
    p.add_argument("action", nargs="?", default="register",
                   choices=("register", "unregister"),
                   help="what to do (default: register)")
    p.add_argument("--stdio", action="store_true",
                   help="run the MCP server on stdin/stdout (used by Claude Code)")
    args = p.parse_args(argv)

    if args.stdio:
        return _mcp_serve_stdio()

    shim = paths.launcher()
    if args.action == "register":
        cmd = ["claude", "mcp", "add", "--scope", "user", "boost", "--",
               str(shim), "mcp", "--stdio"]
    else:
        cmd = ["claude", "mcp", "remove", "boost"]

    if shutil.which("claude"):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BoostError("claude mcp %s failed: %s" % (args.action, e),
                            hint="run it yourself: " + " ".join(cmd))
        for ln in (proc.stdout or "").strip().splitlines():
            out.info(ln)
        if proc.returncode != 0:
            tail = (proc.stderr or "").strip().splitlines()
            raise BoostError("claude mcp %s failed: %s"
                            % (args.action, tail[-1] if tail else "unknown error"),
                            hint="run it yourself: " + " ".join(cmd))
        out.ok("%sed boost as an MCP server (scope: user)"
               % ("register" if args.action == "register" else "unregister"))
    else:
        out.warn("`claude` CLI not found — run this yourself:")
        out.info(" ".join(cmd))
    journal.log("mcp", args.action)
    return 0


# ---------------------------------------------------------------- self-update

def cmd_self_update(argv) -> int:
    """boost self-update"""
    p = cliparse.parser(
        prog="boost self-update",
        description="Update boost itself to the latest version")
    p.parse_args(argv)

    root = paths.repo_root()
    if not gitutil.is_repo(root):
        raise BoostError("boost is not running from a git checkout",
                        hint="git clone the boost repo and symlink bin")
    old = __version__
    before = gitutil.head_commit(root)
    gitutil.run(["-C", str(root), "pull", "--ff-only"], timeout=120)
    after = gitutil.head_commit(root)
    # The version is setuptools-scm derived — there is no `__version__ = "…"`
    # literal to grep, and the build-time _version.py / installed metadata are
    # stale until a reinstall. Ask git for the freshly-pulled version directly
    # (mirrors boost_cli._detect_version()'s git-checkout fallback), and treat a
    # moved HEAD as the unambiguous "an update landed" signal — independent of
    # how the two version strings happen to be formatted.
    new = gitutil.run(
        ["-C", str(root), "describe", "--tags", "--always", "--dirty"],
        check=False, timeout=10).stdout.strip().lstrip("v") or old
    updated = bool(after) and after != before
    journal.log("self-update", new if updated else old, previous=old)
    if updated:
        out.ok("boost v%s → v%s" % (old, new))
    else:
        out.ok("already up to date (v%s)" % old)
    return 0
