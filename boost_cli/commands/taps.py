# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Registry (taps) commands: tap, untap, taps, outdated."""
from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import suppress
from pathlib import Path

from .. import cliparse, spin
from ..core import (
    catalog,
    complete,
    config,
    gitutil,
    journal,
    lockfile,
    paths,
    registry,
    staleness,
    store,
    util,
)
from ..core import output as out
from ..errors import BoostError

_tilde = paths.tilde


def _tap_catalog(args) -> int:
    """Tap every registry in the filtered catalog selection."""
    selection = _catalog_selection(args)
    if not selection:
        out.warn("no catalog registries match that filter")
        return 1
    if args.dry_run:
        rows = [(e["name"], e["type"], e.get("category", ""),
                 "~%d" % (e.get("est_items") or 0),
                 out.role(e.get("focus", ""), "muted")) for e in selection]
        out.table(rows, headers=("NAME", "TYPE", "CATEGORY", "EST", "FOCUS"))
        print()
        out.dim("%d registries · ~%d items (dry run — nothing tapped)"
                % (len(selection), sum(e.get("est_items") or 0 for e in selection)))
        return 0
    focus = {str(e["name"]): e.get("focus", "") for e in selection}
    return _tap_all([str(e["url"]) for e in selection], jobs=args.jobs,
                    focus=focus)


def _print_dry_run(pairs: list[tuple[str, str]]) -> int:
    """Print what `--defaults`/SPEC would tap and return 0, tapping nothing.

    Shares the format of the `--catalog --dry-run` table above so the flag
    reads the same regardless of which branch of `cmd_tap` it modifies.
    """
    out.table(pairs, headers=("NAME", "URL"))
    print()
    out.dim("%d registries (dry run — nothing tapped)" % len(pairs))
    return 0


def _tap_all(urls: list[str], jobs: int | None,
             focus: dict[str, str] | None = None,
             pins: dict[str, str] | None = None,
             curated: bool = True) -> int:
    """Clone many registries at once, then scan each one that arrived.

    The split is the whole optimisation. Cloning is network latency — 1.6 s per
    registry whether one runs or twelve — so it goes wide; scanning is 3 ms per
    registry and writes a per-tap cache file, so it stays on this thread where
    its output can be printed in order and its errors belong to one tap.
    """
    focus = focus or {}
    results = registry.add_many(urls, curated=curated, pins=pins, jobs=jobs)
    rc = 0
    for res in results:
        name = res["name"]
        if res.get("skipped"):
            out.info(out.role("%s already tapped" % name, "muted"))
            continue
        if not res.get("ok"):
            out.warn("could not tap %s: %s" % (name, res.get("error", "")))
            rc = 1
            continue
        tap = res["tap"]
        try:
            entries = catalog.rebuild_tap(tap)
        except BoostError as err:
            out.warn("could not index %s: %s" % (name, err.message))
            rc = 1
            continue
        journal.log("tap", tap.name)
        note = focus.get(name) or ""
        out.ok("tapped %s (%d items)%s"
               % (tap.name, len(entries), " — %s" % note if note else ""))
    return rc


def _catalog_selection(args) -> list:
    """Filter the bundled registry catalog by --type/--category/--limit."""
    entries = config.load_registry_catalog()
    if args.type:
        entries = [e for e in entries
                   if e.get("type") == args.type or args.type in e.get("also_types", [])]
    if args.category:
        entries = [e for e in entries if e.get("category") == args.category]
    if not args.include_lists:
        entries = [e for e in entries if not e.get("list_only")]
    entries.sort(key=lambda e: (-int(e.get("est_items") or 0), e["name"].lower()))
    if args.limit:
        entries = entries[:args.limit]
    return entries


def cmd_tap(argv) -> int:
    """boost tap [SPEC] [--defaults] [--catalog] [--curated]"""
    p = cliparse.parser(
        prog="boost tap",
        description="Add a GitHub repo as a skill registry")
    p.add_argument("spec", nargs="*",
                   help="owner/repo, a git URL, or a local directory — several "
                        "at once clone in parallel")
    p.add_argument("--defaults", action="store_true",
                   help="tap the recommended public registries")
    p.add_argument("--catalog", action="store_true",
                   help="tap from the bundled curated registry catalog")
    p.add_argument("--type", choices=("skill", "rule", "workflow"),
                   help="with --catalog: restrict to one item type")
    p.add_argument("--category", help="with --catalog: restrict to one category")
    p.add_argument("--limit", type=int, metavar="N",
                   help="with --catalog: only the top N registries by est. size")
    p.add_argument("--include-lists", action="store_true",
                   help="with --catalog: also tap awesome-list/index repos")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would be tapped, tap nothing")
    p.add_argument("--curated", action="store_true",
                   help="mark the tap as curated (★ in listings)")
    p.add_argument("--at", metavar="SHA",
                   help="pin the clone to one 40-character commit, as a "
                        "published vector shard requires")
    p.add_argument("--jobs", type=int, metavar="N",
                   help="clone this many registries at once (default %d, max "
                        "%d)" % (registry.DEFAULT_TAP_JOBS,
                                 registry.MAX_TAP_JOBS))
    args = p.parse_args(argv)
    if args.at and len(args.spec) != 1:
        p.error("--at pins one registry, so it needs exactly one SPEC")
    if not args.spec and not args.defaults and not args.catalog:
        p.error("provide a SPEC, --defaults, or --catalog")

    rc = 0
    if args.catalog:
        rc |= _tap_catalog(args)
    if args.defaults:
        if args.dry_run:
            rc |= _print_dry_run([(str(d["name"]), str(d["url"]))
                                  for d in config.DEFAULT_TAPS])
        else:
            # "items", not "skills": the defaults now carry rules and
            # workflows, so a pure rules registry reported "257 skills"
            # immediately after the README promised three kinds. `_tap_all`
            # says items.
            rc |= _tap_all([str(d["url"]) for d in config.DEFAULT_TAPS],
                           jobs=args.jobs,
                           focus={str(d["name"]): str(d.get("focus", ""))
                                  for d in config.DEFAULT_TAPS})
    if args.spec and args.dry_run:
        rc |= _print_dry_run(registry.parse_specs(list(args.spec)))
    elif len(args.spec) == 1:
        with spin.Spinner("cloning %s" % args.spec[0]):
            tap = registry.add(args.spec[0], curated=args.curated, at=args.at)
            entries = catalog.rebuild_tap(tap)
        journal.log("tap", tap.name)
        pin = " @ %s" % args.at[:7] if args.at else ""
        out.ok("Tapped %s (%d items)%s" % (tap.name, len(entries), pin))
    elif args.spec:
        # Several specs clone through the same pool as --defaults/--catalog.
        # This is not only a convenience: `xargs boost_cli tap < list` hands
        # every line to ONE invocation, and rejecting the extras is how the
        # shards workflow tapped nothing — argparse errored, `|| true`
        # swallowed it, and the job died three steps later on "no taps
        # configured". A multi-spec surface makes the natural script correct.
        rc |= _tap_all(list(args.spec), jobs=args.jobs, curated=args.curated)
    # Refresh the TAB-completion name cache so `boost install <TAB>` sees
    # whatever this call just tapped instead of the pre-tap snapshot.
    complete.refresh_names()
    return rc


def cmd_untap(argv) -> int:
    """boost untap NAME [--force]"""
    p = cliparse.parser(
        prog="boost untap",
        description="Remove a registry tap")
    p.add_argument("name", help="tap name (owner/repo or short alias)")
    p.add_argument("-f", "--force", action="store_true",
                   help="skip the confirmation prompt")
    p.add_argument("-y", "--yes", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    tap = registry.get(args.name)
    # All three lock sections: untapping the source of a live CLAUDE.md rule
    # deserves the same warning as untapping the source of a skill.
    dependent = [(kind, n)
                 for kind, section in lockfile.all_installed().items()
                 for n, e in sorted(section.items())
                 if e.get("tap") == tap.name]
    if dependent:
        labels = [n if kind == "skill" else "%s (%s)" % (n, kind)
                  for kind, n in dependent]
        out.warn("%d installed item(s) from %s: %s"
                 % (len(dependent), tap.name, ", ".join(labels)))
        out.warn("installed items keep working but lose their update source")
        if not (args.force or args.yes) and not out.confirm(
                "untap %s anyway?" % tap.name):
            out.info("cancelled")
            return 1
    registry.remove(tap.name)
    complete.refresh_names()
    journal.log("untap", tap.name)
    out.ok("untapped %s" % tap.name)
    return 0


def _tap_updated(tap: registry.Tap) -> str:
    """Last-commit date of a tap clone, else the cache's generated age."""
    if tap.is_cloned:
        with suppress(BoostError):
            # --date=short --format=%cd == %cs, but works on git < 2.21 too
            proc = gitutil.run(["-C", str(tap.path), "log", "-1",
                                "--date=short", "--format=%cd"], check=False)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
    try:
        data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
        return util.rel_time(data.get("generated", ""))
    except (OSError, ValueError):
        return "?"


def cmd_taps(argv) -> int:
    """boost taps [--json]"""
    p = cliparse.parser(
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
                     "skills": len(skills), "updated": _tap_updated(tap),
                     "pin": tap.pin})
    if args.json:
        print(json.dumps(taps, indent=2))
        return 0
    if not taps:
        out.info("no taps configured")
        out.info(out.role("add the recommended registries with `boost tap --defaults`", "muted"))
        return 0
    # A pinned tap reads as its commit rather than its date: the date of a
    # clone held still is not what the user needs to know about it, and a tap
    # that `boost update` deliberately skips should say why on the line the
    # user is already reading.
    rows = [(t["name"], str(t["skills"]),
             "@%s" % str(t["pin"])[:7] if t["pin"] else t["updated"],
             "★" if t["curated"] else "", out.role(_tilde(t["url"]), "muted"))
            for t in taps]
    out.table(rows, headers=("NAME", "SKILLS", "UPDATED", "", "URL"))
    print()
    out.dim("%d taps · %d skills" % (len(taps), total))
    return 0


def cmd_outdated(argv) -> int:
    """boost outdated [--json]"""
    p = cliparse.parser(
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
        head, src_sha, src_missing = "", None, False
        if not util.semver_gt(latest, installed_v):
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
                    src_sha = util.sha256_dir(store.source_dir_for(entry))
                except BoostError:
                    src_missing = True
        if src_missing:
            stale, latest_disp = True, "source missing"
        else:
            reason = staleness.upstream_reason(
                installed_v, latest, lk.get("commit", ""), head,
                lk.get("sha256", ""), src_sha)
            if reason == staleness.VERSION:
                stale = True
            elif reason == staleness.CONTENT:
                stale, latest_disp = True, "%s (%s)" % (latest, head[:7])
        if stale:
            results.append({"name": name, "kind": "skill",
                            "installed": installed_v,
                            "latest": latest_disp, "tap": tap_name,
                            "pinned": bool(lk.get("pinned"))})

    # Rules/workflows have no store dir — their staleness signal is the lock's
    # source sha256 against the tap's current source file (the comparison
    # `boost update` itself uses before re-materializing).
    for kind, section in (("rule", lockfile.installed_rules()),
                          ("workflow", lockfile.installed_workflows())):
        for name, lk in sorted(section.items()):
            tap_name = lk.get("tap", "local")
            if tap_name == "local":
                continue
            installed_v = str(lk.get("version") or "0.0.0")
            try:
                raw = (registry.get(tap_name).path / lk.get("source_file", "")
                       ).read_text(encoding="utf-8", errors="replace")
            except (OSError, BoostError):
                results.append({"name": name, "kind": kind,
                                "installed": installed_v,
                                "latest": "source missing", "tap": tap_name,
                                "pinned": bool(lk.get("pinned"))})
                continue
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() == lk.get("sha256"):
                continue
            matches = [e for e in catalog.find(name)
                       if e["tap"] == tap_name
                       and e.get("kind", "skill") == kind]
            latest = str(matches[0].get("version") or "?") if matches else "?"
            if not util.semver_gt(latest, installed_v):
                latest = "%s (content changed)" % latest
            results.append({"name": name, "kind": kind,
                            "installed": installed_v, "latest": latest,
                            "tap": tap_name, "pinned": bool(lk.get("pinned"))})

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        out.ok("everything up to date")
        return 0
    rows = [(r["name"] + ("" if r["kind"] == "skill" else " (%s)" % r["kind"]),
             r["installed"] + (" (pinned)" if r["pinned"] else ""),
             r["latest"], r["tap"]) for r in results]
    out.table(rows, headers=("NAME", "INSTALLED", "LATEST", "TAP"))
    print()
    out.dim("%d outdated · `boost update` upgrades (pinned items stay put)"
            % len(results))
    return 0


#: `--show` prints a table, not the full manifest — `--json` already carries
#: every row, so this exists to keep the table on a screen, not to hide data.
_SHOW_ROW_CAP = 20


def cmd_catalog(argv) -> int:
    """boost catalog --export FILE | --import FILE [--json]"""
    p = cliparse.parser(
        prog="boost catalog",
        description="Share the tapped catalogue so others skip the clone")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", metavar="FILE",
                      help="write every tapped registry's catalogue to FILE")
    mode.add_argument("--import", metavar="FILE", dest="import_",
                      help="merge a catalogue bundle into this machine")
    mode.add_argument("--show", metavar="FILE",
                      help="describe a bundle without importing it")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)

    from ..core import catalogbundle

    if args.show:
        manifest = catalogbundle.read_manifest(Path(args.show))
        if args.as_json:
            print(json.dumps(manifest, indent=2))
            return 0
        out.heading("catalogue bundle %s" % args.show)
        out.info("built %s · %d taps · %s entries"
                 % (manifest.get("generated", "?"),
                    len(manifest.get("taps") or []),
                    "{:,}".format(int(manifest.get("entries") or 0))))
        manifest_taps = manifest.get("taps") or []
        rows = [(t.get("name", "?"), str(t.get("entries", "?")),
                 (t.get("commit") or "")[:7])
                for t in manifest_taps[:_SHOW_ROW_CAP]]
        if rows:
            out.table(rows, headers=("TAP", "ENTRIES", "COMMIT"))
        if len(manifest_taps) > _SHOW_ROW_CAP:
            out.dim("… and %d more (use --json for the full list)"
                    % (len(manifest_taps) - _SHOW_ROW_CAP))
        return 0

    if args.export:
        stats = catalogbundle.export_bundle(Path(args.export))
        if args.as_json:
            print(json.dumps(stats, indent=2))
            return 0
        out.ok("packed %d taps · %s entries · %.1f MB → %s"
               % (stats["taps"], "{:,}".format(stats["entries"]),
                  stats["bytes"] / 1e6, stats["path"]))
        if stats["skipped"]:
            # Configured but not yet built. Named rather than counted: the
            # reader needs to know WHICH registry the receiver will not get.
            out.warn("skipped %d tap(s) with no built catalogue: %s"
                     % (len(stats["skipped"]), ", ".join(stats["skipped"][:5])))
        out.dim("the receiver runs `boost catalog --import <file>` — no clone, "
                "no re-tap")
        return 0

    stats = catalogbundle.import_bundle(Path(args.import_))
    if args.as_json:
        print(json.dumps(stats, indent=2))
        return 0
    out.ok("imported %d catalogue file(s) · %s entries · %d new tap(s)"
           % (stats["files"], "{:,}".format(stats["entries"]), stats["added"]))
    local_added = stats.get("local_added") or []
    if local_added:
        # These clone fine right now — the catalogue is already on disk — but
        # `boost update`/`--force` on one of them will fail the moment the
        # exporting machine's directory is gone, and there is nothing in a
        # local path to warn the receiver of that on its own.
        out.warn("%d tap(s) point at a directory on the exporting machine, "
                 "not a clonable URL: %s — `boost update` on these will fail "
                 "once that path is gone"
                 % (len(local_added), ", ".join(local_added[:5])))
    out.dim("`boost search` works now; `boost install` clones just the one "
            "registry it needs")
    return 0
