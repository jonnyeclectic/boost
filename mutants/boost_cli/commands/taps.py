"""Registry (taps) commands: tap, untap, taps, outdated."""
from __future__ import annotations

import argparse
import json
import os

from ..core import catalog, config, gitutil, journal, lockfile, paths, registry, store, util
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


def cmd_tap(argv) -> int:
    """boost tap [SPEC] [--defaults] [--curated]"""
    p = argparse.ArgumentParser(
        prog="boost tap",
        description="Add a GitHub repo as a skill registry")
    p.add_argument("spec", nargs="?",
                   help="owner/repo, a git URL, or a local directory")
    p.add_argument("--defaults", action="store_true",
                   help="tap the recommended public registries")
    p.add_argument("--curated", action="store_true",
                   help="mark the tap as curated (★ in listings)")
    args = p.parse_args(argv)
    if not args.spec and not args.defaults:
        p.error("provide a SPEC or --defaults")

    rc = 0
    if args.defaults:
        existing = {t.name for t in registry.list_taps()}
        for default in config.DEFAULT_TAPS:
            if default["name"] in existing:
                out.info(out.c("%s already tapped" % default["name"], out.DIM))
                continue
            try:
                tap = registry.add(default["url"], curated=True)
                entries = catalog.rebuild_tap(tap)
            except BoostError as e:
                out.warn("could not tap %s: %s" % (default["name"], e.message))
                rc = 1
                continue
            journal.log("tap", tap.name)
            out.ok("tapped %s (%d skills) — %s"
                   % (tap.name, len(entries), default.get("focus", "")))
    if args.spec:
        tap = registry.add(args.spec, curated=args.curated)
        entries = catalog.rebuild_tap(tap)
        journal.log("tap", tap.name)
        out.ok("Tapped %s (%d skills)" % (tap.name, len(entries)))
    return rc


def cmd_untap(argv) -> int:
    """boost untap NAME [--force]"""
    p = argparse.ArgumentParser(
        prog="boost untap",
        description="Remove a registry tap")
    p.add_argument("name", help="tap name (owner/repo or short alias)")
    p.add_argument("-f", "--force", action="store_true",
                   help="skip the confirmation prompt")
    p.add_argument("-y", "--yes", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    tap = registry.get(args.name)
    dependent = sorted(n for n, e in lockfile.installed().items()
                       if e.get("tap") == tap.name)
    if dependent:
        out.warn("%d skill(s) installed from %s: %s"
                 % (len(dependent), tap.name, ", ".join(dependent)))
        out.warn("installed skills keep working but lose their update source")
        if not (args.force or args.yes) and not out.confirm(
                "untap %s anyway?" % tap.name):
            out.info("cancelled")
            return 1
    registry.remove(tap.name)
    journal.log("untap", tap.name)
    out.ok("untapped %s" % tap.name)
    return 0


def _tap_updated(tap: "registry.Tap") -> str:
    """Last-commit date of a tap clone, else the cache's generated age."""
    if tap.is_cloned:
        try:
            # --date=short --format=%cd == %cs, but works on git < 2.21 too
            proc = gitutil.run(["-C", str(tap.path), "log", "-1",
                                "--date=short", "--format=%cd"], check=False)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except BoostError:
            pass
    try:
        data = json.loads(tap.cache_file.read_text())
        return util.rel_time(data.get("generated", ""))
    except (OSError, ValueError):
        return "?"


def cmd_taps(argv) -> int:
    """boost taps [--json]"""
    p = argparse.ArgumentParser(
        prog="boost taps",
        description="List all configured registry taps")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output")
    args = p.parse_args(argv)

    taps = []
    total = 0
    for tap in registry.list_taps():
        skills = catalog.load_tap(tap)
        total += len(skills)
        taps.append({"name": tap.name, "url": tap.url, "curated": tap.curated,
                     "skills": len(skills), "updated": _tap_updated(tap)})
    if args.json:
        print(json.dumps(taps, indent=2))
        return 0
    if not taps:
        out.info("no taps configured")
        out.info(out.c("add the recommended registries with `boost tap --defaults`",
                       out.DIM))
        return 0
    rows = [(t["name"], str(t["skills"]), t["updated"],
             "★" if t["curated"] else "", out.c(_tilde(t["url"]), out.DIM))
            for t in taps]
    out.table(rows, headers=("NAME", "SKILLS", "UPDATED", "", "URL"))
    print()
    out.dim("%d taps · %d skills" % (len(taps), total))
    return 0


def cmd_outdated(argv) -> int:
    """boost outdated [--json]"""
    p = argparse.ArgumentParser(
        prog="boost outdated",
        description="Show skills with available updates")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output")
    args = p.parse_args(argv)

    results = []
    heads = {}  # tap name -> HEAD commit ("" when unknown)
    for name, lk in sorted(lockfile.installed().items()):
        tap_name = lk.get("tap", "local")
        if tap_name == "local":
            continue
        matches = [e for e in catalog.find(name) if e["tap"] == tap_name]
        if not matches:
            continue
        entry = matches[0]
        latest = str(entry.get("version") or "0.0.0")
        installed_v = str(lk.get("version") or "0.0.0")
        stale, latest_disp = False, latest
        if util.semver_gt(latest, installed_v):
            stale = True
        else:
            if tap_name not in heads:
                try:
                    tap = registry.get(tap_name)
                    heads[tap_name] = (gitutil.head_commit(tap.path)
                                       if tap.is_cloned else "")
                except BoostError:
                    heads[tap_name] = ""
            head = heads[tap_name]
            if head and head != lk.get("commit"):
                try:
                    src = store.source_dir_for(entry)
                except BoostError:
                    stale, latest_disp = True, "source missing"
                else:
                    if util.sha256_dir(src) != lk.get("sha256"):
                        stale = True
                        latest_disp = "%s (%s)" % (latest, head[:7])
        if stale:
            results.append({"name": name, "installed": installed_v,
                            "latest": latest_disp, "tap": tap_name,
                            "pinned": bool(lk.get("pinned"))})

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        out.ok("everything up to date")
        return 0
    rows = [(r["name"],
             r["installed"] + (" (pinned)" if r["pinned"] else ""),
             r["latest"], r["tap"]) for r in results]
    out.table(rows, headers=("NAME", "INSTALLED", "LATEST", "TAP"))
    print()
    out.dim("%d outdated · `boost update` upgrades (pinned skills stay put)"
            % len(results))
    return 0
