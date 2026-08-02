"""Team & Collaboration commands: cohort, profile, protocol, pulse, replay, who."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import stat
import urllib.parse

from .. import cliparse
from ..core import (
    catalog,
    complete,
    journal,
    lockfile,
    paths,
    registry,
    store,
    util,
)
from ..core import output as out
from ..errors import BoostError

_tilde = paths.tilde


def _resolve_entry(name: str, prefer_tap: str | None = None):
    """Find a catalog entry by name, preferring a specific tap. None if absent."""
    matches = catalog.find(name)
    if not matches:
        return None
    if prefer_tap:
        tapped = [e for e in matches if e["tap"] == prefer_tap]
        if tapped:
            return tapped[0]
    return matches[0]


# ---------------------------------------------------------------- cohort

def _cohorts_path():
    return paths.state_dir() / "cohorts.json"


def _load_cohorts() -> dict:
    p = _cohorts_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cohorts(cohorts: dict) -> None:
    paths.ensure_dirs()
    _cohorts_path().write_text(json.dumps(cohorts, indent=2) + "\n", encoding="utf-8")


def _is_member(user: str, cohort_name: str, percent: int) -> bool:
    """Deterministic per user+cohort: stable across runs and machines."""
    digest = hashlib.sha256(("%s:%s" % (user, cohort_name)).encode()).hexdigest()
    return int(digest, 16) % 100 < percent


def cmd_cohort(argv) -> int:
    """boost cohort [list|create NAME --skills a,b --percent N|delete NAME|status|apply [NAME]]"""
    p = cliparse.parser(
        prog="boost cohort",
        description="Controlled skill rollouts & team A/B testing",
        epilog="Membership is a deterministic hash of user+cohort, so a 50%% "
               "rollout lands on the same half of the team every time. "
               "This machine evaluates its own membership locally.")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "create", "delete", "status", "apply"])
    p.add_argument("name", nargs="?", help="cohort name")
    p.add_argument("--skills", default="", help="comma-separated skill names")
    p.add_argument("--percent", type=int, default=100,
                   help="rollout percentage (default 100)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    cohorts = _load_cohorts()
    user = util.user()

    if args.action == "create":
        if not args.name:
            p.error("create needs a cohort NAME")
        if not 0 <= args.percent <= 100:
            p.error("--percent must be 0-100")
        skills = [s.strip() for s in args.skills.split(",") if s.strip()]
        if not skills:
            p.error("create needs --skills a,b,...")
        for s in skills:
            if not catalog.find(s):
                out.warn("skill %r not found in any tap (kept anyway)" % s)
        cohorts[args.name] = {"skills": skills, "percent": args.percent,
                              "created": util.now_iso(), "creator": user}
        _save_cohorts(cohorts)
        journal.log("cohort", args.name, op="create", percent=args.percent)
        member = _is_member(user, args.name, args.percent)
        out.ok("created cohort %s (%d%% rollout, %d skills) — you are %s"
               % (args.name, args.percent, len(skills),
                  "IN" if member else "OUT"))
        return 0

    if args.action == "delete":
        if not args.name:
            p.error("delete needs a cohort NAME")
        if args.name not in cohorts:
            raise BoostError("no cohort named %s" % args.name,
                            hint="list cohorts with `boost cohort list`")
        if not out.confirm("delete cohort %s?" % args.name):
            out.info("cancelled")
            return 1
        del cohorts[args.name]
        _save_cohorts(cohorts)
        journal.log("cohort", args.name, op="delete")
        out.ok("deleted cohort %s" % args.name)
        return 0

    if args.action == "apply":
        targets = [args.name] if args.name else sorted(cohorts)
        if args.name and args.name not in cohorts:
            raise BoostError("no cohort named %s" % args.name,
                            hint="list cohorts with `boost cohort list`")
        if not targets:
            out.info("no cohorts defined")
            return 0
        installed = lockfile.installed()
        applied = skipped = 0
        for cname in targets:
            spec = cohorts[cname]
            if not _is_member(user, cname, spec["percent"]):
                out.info(out.role("%s: not in the %d%% rollout — skipping"
                               % (cname, spec["percent"]), "muted"))
                continue
            out.heading("cohort %s" % cname)
            for skill in spec["skills"]:
                if skill in installed:
                    out.info(out.role("%s already installed" % skill, "muted"))
                    skipped += 1
                    continue
                entry = _resolve_entry(skill)
                if entry is None:
                    out.warn("%s not found in any tap — skipped" % skill)
                    continue
                res = store.install(entry)
                out.ok("installed %s → %s" % (skill, " · ".join(res.linked)))
                applied += 1
        out.info("applied: %d installed, %d already present" % (applied, skipped))
        return 0

    # list / status
    rows = []
    data = []
    for cname in sorted(cohorts):
        spec = cohorts[cname]
        member = _is_member(user, cname, spec["percent"])
        data.append({"name": cname, "skills": spec["skills"],
                     "percent": spec["percent"], "member": member,
                     "created": spec.get("created", "")})
        rows.append((cname, ", ".join(spec["skills"]),
                     "%d%%" % spec["percent"],
                     out.role("IN", "success") if member else out.role("out", "muted")))
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    if not rows:
        out.info("no cohorts defined")
        out.info(out.role("create one: `boost cohort create pilot --skills tdd-workflow --percent 50`", "muted"))
        return 0
    out.table(rows, headers=("COHORT", "SKILLS", "ROLLOUT", "YOU"))
    print()
    out.dim("membership = sha256(user:cohort) %% 100 < rollout · apply with `boost cohort apply`")
    return 0


# ---------------------------------------------------------------- profile

def _profile_path(name: str):
    return paths.profiles_dir() / (util.slugify(name) + ".json")


def _load_profile(name: str) -> dict:
    p = _profile_path(name)
    if not p.exists():
        raise BoostError("no profile named %s" % name,
                        hint="list profiles with `boost profile list`")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise BoostError("profile %s is unreadable: %s" % (name, e)) from e


def _profile_diff(profile: dict):
    """-> (missing, extras, changed): profile vs currently installed."""
    current = lockfile.installed()
    want = profile.get("skills", {})
    missing = sorted(n for n in want if n not in current)
    extras = sorted(n for n in current if n not in want)
    changed = sorted(n for n in want if n in current and
                     str(want[n].get("version")) != str(current[n].get("version")))
    return missing, extras, changed


def cmd_profile(argv) -> int:
    """boost profile [list|save NAME|use NAME [--prune]|show NAME|diff NAME|delete NAME]"""
    p = cliparse.parser(
        prog="boost profile",
        description="Named skill profiles for context switching")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "save", "use", "show", "diff", "delete"])
    p.add_argument("name", nargs="?", help="profile name")
    p.add_argument("--prune", action="store_true",
                   help="with `use`: fully uninstall skills not in the profile")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.action != "list" and not args.name:
        p.error("%s needs a profile NAME" % args.action)

    if args.action == "list":
        profiles = []
        for f in sorted(paths.profiles_dir().glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            profiles.append({"name": data.get("name", f.stem),
                             "skills": len(data.get("skills", {})),
                             "saved": data.get("saved", "?")})
        if args.json:
            print(json.dumps(profiles, indent=2))
            return 0
        if not profiles:
            out.info("no profiles saved")
            out.info(out.role("snapshot the current setup: `boost profile save daily`", "muted"))
            return 0
        rows = [(pr["name"], str(pr["skills"]), util.rel_time(pr["saved"]))
                for pr in profiles]
        out.table(rows, headers=("PROFILE", "SKILLS", "SAVED"))
        return 0

    if args.action == "save":
        installed = lockfile.installed()
        profile = {"name": args.name, "saved": util.now_iso(), "user": util.user(),
                   "skills": {n: {"tap": e.get("tap", "local"),
                                  "version": e.get("version", "0.0.0")}
                              for n, e in installed.items()}}
        paths.ensure_dirs()
        _profile_path(args.name).write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        journal.log("profile", args.name, op="save", skills=len(installed))
        out.ok("saved profile %s (%d skills)" % (args.name, len(installed)))
        return 0

    if args.action == "show":
        profile = _load_profile(args.name)
        if args.json:
            print(json.dumps(profile, indent=2))
            return 0
        out.heading("profile %s" % profile.get("name", args.name))
        out.kv("saved", "%s by %s" % (util.rel_time(profile.get("saved", "")),
                                      profile.get("user", "?")))
        rows = [(n, s.get("version", "?"), s.get("tap", "?"))
                for n, s in sorted(profile.get("skills", {}).items())]
        if rows:
            print()
            out.table(rows, headers=("SKILL", "VERSION", "TAP"))
        return 0

    if args.action == "diff":
        profile = _load_profile(args.name)
        missing, extras, changed = _profile_diff(profile)
        if args.json:
            print(json.dumps({"missing": missing, "extras": extras,
                              "changed": changed}, indent=2))
            return 0
        if not (missing or extras or changed):
            out.ok("current setup matches profile %s" % args.name)
            return 0
        for n in missing:
            out.info(out.role("+ %s" % n, "success") + out.role("  (in profile, not installed)", "muted"))
        for n in extras:
            out.info(out.role("- %s" % n, "danger") + out.role("  (installed, not in profile)", "muted"))
        for n in changed:
            out.info(out.role("~ %s" % n, "warn") + out.role("  (version differs)", "muted"))
        return 0

    if args.action == "delete":
        _load_profile(args.name)  # existence check
        if not out.confirm("delete profile %s?" % args.name):
            out.info("cancelled")
            return 1
        _profile_path(args.name).unlink()
        journal.log("profile", args.name, op="delete")
        out.ok("deleted profile %s" % args.name)
        return 0

    # use
    profile = _load_profile(args.name)
    missing, extras, _changed = _profile_diff(profile)
    want = profile.get("skills", {})
    for n in missing:
        entry = _resolve_entry(n, prefer_tap=want[n].get("tap"))
        if entry is None:
            out.warn("%s is in the profile but not in any tap — skipped" % n)
            continue
        res = store.install(entry)
        out.ok("installed %s → %s" % (n, " · ".join(res.linked)))
    for n in sorted(want):
        if lockfile.get_skill(n) and not (lockfile.get_skill(n) or {}).get("quarantined"):
            store.link_agents(n)
    if extras:
        if args.prune:
            if out.confirm("uninstall %d skill(s) not in the profile (%s)?"
                           % (len(extras), ", ".join(extras))):
                for n in extras:
                    store.uninstall(n)
                    out.ok("uninstalled %s" % n)
            else:
                out.info("kept extras installed")
        else:
            for n in extras:
                store.unlink_agents(n)
            out.info("sidelined %d skill(s) not in the profile (unlinked, still installed): %s"
                     % (len(extras), ", ".join(extras)))
    journal.log("profile", args.name, op="use")
    out.ok("switched to profile %s" % args.name)
    return 0


# ---------------------------------------------------------------- protocol

def _handler_script():
    return paths.state_dir() / "boost-protocol-handler.sh"


def _desktop_file():
    return paths.home() / ".local" / "share" / "applications" / "boost-protocol.desktop"


def _parse_boost_url(url: str):
    """boost://install/<skill> | boost://install/<tap>:<skill> | boost://tap/<owner>/<repo>
    -> (verb, argument)"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "boost":
        raise BoostError("not a boost:// URL: %s" % url,
                        hint="expected boost://install/<skill> or boost://tap/<owner>/<repo>")
    verb = parsed.netloc
    arg = urllib.parse.unquote(parsed.path.lstrip("/"))
    if verb not in ("install", "tap") or not arg:
        raise BoostError("cannot parse %s" % url,
                        hint="supported: boost://install/<skill>, "
                             "boost://install/<tap>:<skill>, boost://tap/<owner>/<repo>")
    return verb, arg


def cmd_protocol(argv) -> int:
    """boost protocol [status|register|unregister|open URL]"""
    p = cliparse.parser(
        prog="boost protocol",
        description="Manage the boost:// one-click-install handler")
    p.add_argument("action", nargs="?", default="status",
                   choices=["status", "register", "unregister", "open"])
    p.add_argument("url", nargs="?", help="a boost:// URL (for `open`)")
    args = p.parse_args(argv)
    system = platform.system()

    if args.action == "open":
        if not args.url:
            p.error("open needs a boost:// URL")
        verb, arg = _parse_boost_url(args.url)
        if verb == "install":
            entry = catalog.resolve_one(arg)
            if not out.confirm("install %s from %s?" % (entry["name"], entry["tap"])):
                out.info("cancelled")
                return 1
            res = store.install(entry)
            out.ok("copied to %s" % _tilde(res.dest))
            out.ok("linked → %s" % " · ".join(res.linked))
            out.ok("lock updated (.skill-lock.json)")
            return 0
        # tap
        if not out.confirm("tap %s?" % arg):
            out.info("cancelled")
            return 1
        tap = registry.add(arg)
        entries = catalog.rebuild_tap(tap)
        complete.refresh_names()
        journal.log("tap", tap.name, via="protocol")
        out.ok("tapped %s (%d skills)" % (tap.name, len(entries)))
        return 0

    if args.action == "register":
        paths.ensure_dirs()
        shim = paths.launcher()
        script = _handler_script()
        script.write_text("#!/usr/bin/env bash\n"
                          "# boost:// URL handler — invoked with the URL as $1\n"
                          'exec "%s" protocol open "$1"\n' % shim, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        out.ok("wrote handler script %s" % _tilde(script))
        if system == "Darwin":
            out.info("macOS routes URL schemes through app bundles, so one manual step remains:")
            out.info("  1. Automator → New → Application → 'Run Shell Script'")
            out.info('  2. script: %s "$1"   (pass input: as arguments)' % _tilde(script))
            out.info("  3. save as Boost.app, then add CFBundleURLTypes for 'boost' to its Info.plist")
            out.info(out.role("  (or: brew install duti && duti -s <bundle-id> boost)", "muted"))
        elif system == "Linux":
            desktop = _desktop_file()
            desktop.parent.mkdir(parents=True, exist_ok=True)
            desktop.write_text("[Desktop Entry]\nType=Application\nName=boost protocol handler\n"
                               "Exec=%s %%u\nMimeType=x-scheme-handler/boost;\nNoDisplay=true\n"
                               % script, encoding="utf-8")
            out.ok("wrote %s" % _tilde(desktop))
            if shutil.which("xdg-mime"):
                import subprocess
                proc = subprocess.run(["xdg-mime", "default", "boost-protocol.desktop",
                                       "x-scheme-handler/boost"], capture_output=True)
                if proc.returncode == 0:
                    out.ok("registered x-scheme-handler/boost via xdg-mime")
                else:
                    out.warn("xdg-mime registration failed — run it manually")
            else:
                out.warn("xdg-mime not found — handler written but not registered")
        else:
            out.warn("no automatic registration on %s — use the handler script directly" % system)
        journal.log("protocol", "register")
        return 0

    if args.action == "unregister":
        removed = 0
        for artifact in (_handler_script(), _desktop_file()):
            if artifact.exists():
                artifact.unlink()
                out.ok("removed %s" % _tilde(artifact))
                removed += 1
        if not removed:
            out.info("nothing registered")
        journal.log("protocol", "unregister")
        return 0

    # status
    out.kv("platform", system)
    out.kv("handler", _tilde(_handler_script())
           if _handler_script().exists() else "not registered")
    if system == "Linux":
        out.kv("desktop", _tilde(_desktop_file())
               if _desktop_file().exists() else "not registered")
    out.kv("URL forms", "boost://install/<skill> · boost://install/<tap>:<skill> "
                        "· boost://tap/<owner>/<repo>")
    out.dim("  try it: boost protocol open boost://install/brainstorming")
    return 0


# ---------------------------------------------------------------- pulse

_ACTION_ROLE = {"install": "success", "uninstall": "danger",
                "evolve": "warn", "edit": "warn"}


def cmd_pulse(argv) -> int:
    """boost pulse [-n N] [--all] [--action A] [--json]"""
    p = cliparse.parser(
        prog="boost pulse",
        description="Team activity feed of skill-management events")
    p.add_argument("-n", type=util.positive_int, default=20,
                   help="events to show (default 20)")
    p.add_argument("--all", action="store_true", help="show the whole journal")
    p.add_argument("--action", help="filter by action (install, tap, ...)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    events = journal.events(None if args.all else args.n, action=args.action)
    if args.json:
        print(json.dumps(events, indent=2))
        return 0
    if not events:
        out.info("no activity yet — events appear as you install and manage skills")
        return 0
    for e in events:
        action = e.get("action", "?")
        action_role = _ACTION_ROLE.get(action, "accent")
        extras = {k: v for k, v in e.items()
                  if k not in ("ts", "user", "action", "subject")}
        extra_s = ("  " + " ".join("%s=%s" % kv for kv in sorted(extras.items()))
                   if extras else "")
        print("  %s  %s  %s  %s%s" % (
            util.rel_time(e.get("ts", "")).rjust(7),
            out.role(e.get("user", "?").ljust(10), "accent"),
            out.role(action.ljust(11), action_role),
            out.c(e.get("subject", ""), out.BOLD),
            out.role(extra_s, "muted")))
    print()
    out.dim("local journal · share it with your team via `boost onboard`")
    return 0


# ---------------------------------------------------------------- replay

def cmd_replay(argv) -> int:
    """boost replay [list|show ID|rollback ID]"""
    p = cliparse.parser(
        prog="boost replay",
        description="View version history & roll back skills")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "show", "rollback"])
    p.add_argument("id", nargs="?", help="history entry id (from `boost replay list`)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.action == "list":
        history = lockfile.history_list()
        if args.json:
            print(json.dumps(history, indent=2))
            return 0
        if not history:
            out.info("no lock history yet — every install/uninstall snapshots the lock file")
            return 0
        rows = []
        prev_skills = None
        annotated = []
        for h in history:  # oldest -> newest
            try:
                skills = set(lockfile.history_read(h["id"]).get("skills", {}))
            except BoostError:
                skills = set()
            if prev_skills is None:
                delta = ""
            else:
                n_added, n_removed = (len(skills - prev_skills),
                                      len(prev_skills - skills))
                parts = ([("+%d" % n_added)] if n_added else []) + \
                        ([("-%d" % n_removed)] if n_removed else [])
                delta = " ".join(parts)
            annotated.append((h, delta))
            prev_skills = skills
        for h, delta in reversed(annotated):  # newest first
            rows.append((h["id"], util.rel_time(h["updated"]),
                         str(h["count"]), delta))
        out.table(rows, headers=("ID", "WHEN", "SKILLS", "Δ"))
        print()
        out.dim("inspect with `boost replay show <id>` · restore with `boost replay rollback <id>`")
        return 0

    if not args.id:
        p.error("%s needs a history ID" % args.action)
    snapshot = lockfile.history_read(args.id)
    snap_skills = snapshot.get("skills", {})
    current = lockfile.installed()
    added = sorted(n for n in current if n not in snap_skills)
    removed = sorted(n for n in snap_skills if n not in current)
    changed = sorted(n for n in current if n in snap_skills and
                     str(current[n].get("version")) != str(snap_skills[n].get("version")))

    if args.action == "show":
        if args.json:
            print(json.dumps({"id": args.id, "since_snapshot": {
                "added": added, "removed": removed, "changed": changed}}, indent=2))
            return 0
        out.heading("since %s (%s)" % (args.id,
                                       util.rel_time(snapshot.get("updated", ""))))
        if not (added or removed or changed):
            out.ok("current state matches this snapshot")
            return 0
        for n in added:
            out.info(out.role("+ %s" % n, "success") + out.role("  added since", "muted"))
        for n in removed:
            out.info(out.role("- %s" % n, "danger") + out.role("  removed since", "muted"))
        for n in changed:
            out.info(out.role("~ %s  %s → %s" % (n, snap_skills[n].get("version"),
                                              current[n].get("version")), "warn"))
        return 0

    # rollback
    if not (added or removed or changed):
        out.ok("already at this snapshot — nothing to do")
        return 0
    out.info("rollback to %s will: uninstall %d, install %d, revisit %d version change(s)"
             % (args.id, len(added), len(removed), len(changed)))
    if not out.confirm("proceed?"):
        out.info("cancelled")
        return 1
    for n in added:  # in current, not in snapshot
        store.uninstall(n)
        out.ok("uninstalled %s" % n)
    for n in removed:  # in snapshot, missing now
        want = snap_skills[n]
        entry = _resolve_entry(n, prefer_tap=want.get("tap"))
        if entry is None:
            out.warn("%s is gone from every tap — cannot restore" % n)
            continue
        res = store.install(entry, force=True)
        if str(entry.get("version")) != str(want.get("version")):
            out.warn("restored %s v%s from current tap state (snapshot had v%s)"
                     % (n, entry.get("version"), want.get("version")))
        else:
            out.ok("restored %s → %s" % (n, " · ".join(res.linked)))
    for n in changed:
        out.warn("%s version differs from snapshot (%s → %s) — taps only carry "
                 "their current state; `boost pin` prevents future drift"
                 % (n, snap_skills[n].get("version"), current[n].get("version")))
    journal.log("replay", args.id, op="rollback")
    out.ok("rollback to %s complete" % args.id)
    return 0


# ---------------------------------------------------------------- who

def cmd_who(argv) -> int:
    """boost who [SKILL] [--json]"""
    p = cliparse.parser(
        prog="boost who",
        description="Discover who on the team has skill expertise")
    p.add_argument("skill", nargs="?", help="focus on one skill")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    events = journal.events(subject=args.skill) if args.skill else journal.events()
    if not events:
        out.info("no journal activity yet — expertise builds as people install, "
                 "edit, and evolve skills")
        return 0

    if args.skill:
        lk = lockfile.get_skill(args.skill)
        expertise = ("install", "edit", "evolve", "distill", "tag")
        rows = [(util.rel_time(e.get("ts", "")), e.get("user", "?"),
                 e.get("action", "?"))
                for e in events if e.get("action") in expertise] or \
               [(util.rel_time(e.get("ts", "")), e.get("user", "?"),
                 e.get("action", "?")) for e in events]
        if args.json:
            print(json.dumps({"skill": args.skill, "installed": bool(lk),
                              "events": events}, indent=2))
            return 0
        out.heading(args.skill)
        if lk:
            out.kv("installed", "v%s from %s" % (lk.get("version"), lk.get("tap")))
        out.table(rows[:20], headers=("WHEN", "USER", "ACTION"))
        print()
        out.dim("based on the local journal — in a team setup, pulse feeds "
                "aggregate via `boost onboard`")
        return 0

    users: dict[str, dict] = {}
    for e in events:
        u = users.setdefault(e.get("user", "?"), {
            "events": 0, "skills": set(), "installs": 0, "last": e.get("ts", "")})
        u["events"] += 1
        if e.get("subject"):
            u["skills"].add(e["subject"])
        if e.get("action") == "install":
            u["installs"] += 1
        u["last"] = max(u["last"], e.get("ts", ""))
    if args.json:
        print(json.dumps({u: {"events": d["events"], "installs": d["installs"],
                              "skills": sorted(d["skills"]),
                              "last_active": d["last"]}
                          for u, d in users.items()}, indent=2))
        return 0
    board = [(u, str(d["events"]), str(len(d["skills"])), str(d["installs"]),
              util.rel_time(d["last"]))
             for u, d in sorted(users.items(), key=lambda kv: -kv[1]["events"])]
    out.table(board, headers=("USER", "EVENTS", "SKILLS", "INSTALLS", "LAST ACTIVE"))
    print()
    out.dim("based on the local journal — in a team setup, pulse feeds aggregate "
            "via `boost onboard`")
    return 0
