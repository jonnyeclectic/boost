# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost quickstart` — one command from empty machine to working search.

WHY A COMMAND AND NOT A DOC. The setup a new user needs is four steps that each
fail quietly when skipped: tap something, build the BM25 index, install the
`rag` extra, and embed the catalogue. The last one is the wall — ~1.2 s/chunk on
CPU, hours for a corpus worth searching — and it is why the keyless semantic
tier was reachable in principle and not in practice. Published shards remove it,
but only if the tap sits at the commit its vectors were built from, so tapping
and fetching cannot be two commands a user is trusted to order correctly.

WHAT IT WILL NOT DO. It never embeds as a side effect. A user who runs a
"quickstart" and gets an unannounced multi-hour CPU job has been ambushed; the
taps without a published shard are named, with the one command that would embed
them, and left alone.
"""
from __future__ import annotations

from .. import cliparse, spin
from ..core import (
    catalog,
    complete,
    config,
    dense,
    journal,
    rag,
    registry,
    shards,
)
from ..core import output as out
from ..errors import BoostError


def _selection(catalog_scope: bool) -> list[dict]:
    """The registries quickstart will tap: the seven defaults, or all of them.

    `--catalog` exists because "search everything" is a real ask and the two
    costs that used to make it unreasonable are gone: tapping 463 registries is
    2 min 10 s now that clones run in parallel, and their vectors are a
    download rather than an hour of CPU.
    """
    if not catalog_scope:
        return [d.copy() for d in config.DEFAULT_TAPS]
    return [{"name": e["name"], "url": e["url"]}
            for e in config.load_registry_catalog()
            if not e.get("list_only") and e.get("name") and e.get("url")]


def _tap_defaults(selection: list[dict], pins: dict[str, dict],
                  dry_run: bool) -> list[str]:
    """Tap the selected registries, pinned to a shard's commit when one exists.

    Returns the tap names that are configured afterwards, tapped here or not.
    Pinning is the whole point: tapping HEAD and then fetching a shard is the
    ordering that produces a commit mismatch on every registry that moved since
    the last shard run.
    """
    names = [str(d["name"]) for d in selection]
    commits = {name: str(pins[name].get("commit")) for name in names
               if name in pins}
    if dry_run:
        existing = {t.name for t in registry.list_taps()}
        pending = [n for n in names if n not in existing]
        # Over 463 registries a line each is a wall of text, so past a handful
        # the dry run reports the shape instead of the list.
        if len(pending) > 12:
            out.info("would tap %d registries (%d pinned to a published "
                     "shard's commit)"
                     % (len(pending), sum(1 for n in pending if n in commits)))
            return names
        for name in names:
            if name in existing:
                out.info(out.role("%s already tapped" % name, "muted"))
                continue
            at = commits.get(name)
            out.info("would tap %s%s" % (name, " @ %s" % at[:7] if at else ""))
        return names
    # One pool, one config write: seven sequential clones is ~11 s of waiting
    # for work that takes ~2 s done together, and the first thing a new user
    # sees should not be a progress bar.
    with spin.Spinner("tapping %d registries" % len(names)):
        results = registry.add_many([str(d["url"]) for d in selection],
                                    curated=True, pins=commits)
    for res in results:
        name = res["name"]
        if res.get("skipped"):
            out.info(out.role("%s already tapped" % name, "muted"))
            continue
        if not res.get("ok"):
            out.warn("could not tap %s: %s" % (name, res.get("error", "")))
            continue
        try:
            entries = catalog.rebuild_tap(res["tap"])
        except BoostError as exc:
            out.warn("could not index %s: %s" % (name, exc.message))
            continue
        journal.log("tap", name)
        at = commits.get(name)
        out.ok("tapped %s (%d items)%s"
               % (name, len(entries), " @ %s" % at[:7] if at else ""))
    return names


def _report(results: list[dict]) -> None:
    """Say what each shard did, and name the remedy for what it did not do."""
    imported = [r for r in results if r["status"] == "imported"]
    if imported:
        total = sum(int(r.get("chunks") or 0) for r in imported)
        out.ok("imported %d prebuilt shard%s (%s chunks) — no embedding needed"
               % (len(imported), "" if len(imported) == 1 else "s",
                  format(total, ",")))
    for kind, label in (("unpublished", "no published shard"),
                        ("refused", "shard refused"),
                        ("failed", "shard failed")):
        rows = [r for r in results if r["status"] == kind]
        if not rows:
            continue
        for r in rows:
            detail = r.get("detail") or ""
            out.info(out.role("%s: %s%s" % (r["tap"], label,
                                            " (%s)" % detail if detail else ""),
                              "muted"))
    left = [r["tap"] for r in results if r["status"] != "imported"]
    if left:
        out.info("embed the rest locally when you want to: "
                 "`boost reindex --dense`")


def cmd_quickstart(argv) -> int:
    """boost quickstart [--catalog] [--no-vectors] [--dry-run]"""
    p = cliparse.parser(
        prog="boost quickstart",
        description="Tap the starter registries and load prebuilt vectors")
    p.add_argument("--catalog", action="store_true",
                   help="tap every catalogued registry, not just the 7 "
                        "starters, and fetch vectors for all of them")
    p.add_argument("--no-vectors", action="store_true",
                   help="set up taps and keyword search only, skip shards")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would happen, change nothing")
    args = p.parse_args(argv)

    manifest = None
    pins: dict[str, dict] = {}
    want_vectors = not args.no_vectors and dense.have_backend()
    if want_vectors:
        # Fetched first because it decides how the taps are pinned. A failure
        # here is not fatal: keyword search is the documented default and works
        # without a single vector.
        try:
            with spin.Spinner("reading the shard manifest"):
                manifest = shards.fetch_manifest()
            pins = shards.rows(manifest)
        except BoostError as exc:
            out.warn("no published shards: %s" % exc.message)
            manifest = None

    selection = _selection(args.catalog)
    names = _tap_defaults(selection, pins, args.dry_run)
    if args.dry_run:
        planned = [n for n in names if n in pins] if manifest else []
        out.info("would build the keyword index, then import %d shard(s)"
                 % len(planned))
        # "0 shard(s)" reads as "none are published" when the real cause is
        # local, and --dry-run is exactly what a cautious new user runs first.
        # The live path already explains both cases; without this the preview
        # is the one surface that reports the symptom and withholds the reason.
        if not planned:
            if args.no_vectors:
                out.info(out.role("(0 because --no-vectors was asked for)",
                                  "muted"))
            elif not dense.have_backend():
                out.info("0 because semantic search needs the extra: "
                         "`pipx inject boost-skill-cli "
                         "\"boost-skill-cli[rag]\"` — keyword search works "
                         "without it", wrap=True)
            elif manifest is None:
                out.info(out.role("(0 because the shard manifest could not be "
                                  "read — keyword search is unaffected)",
                                  "muted"), wrap=True)
            else:
                out.info(out.role("(0 because none of these registries have a "
                                  "published shard yet)", "muted"), wrap=True)
        return 0

    with spin.Spinner("building the keyword index"):
        stats = rag.build()
    out.ok("indexed %s items for keyword search" % format(
        int(stats.get("entries", 0)), ","))

    if manifest is not None:
        commits = rag._tap_commits()
        # `_tap_commits` is keyed by safe name; `sync` speaks tap names.
        by_name = {t.name: commits.get(t.safe_name, "")
                   for t in registry.list_taps()}
        results = shards.sync([n for n in names if n in by_name], by_name,
                              manifest=manifest)
        _report(results)
    elif args.no_vectors:
        out.info(out.role("skipped vectors as asked", "muted"))
    elif not dense.have_backend():
        out.info("semantic search needs the extra: "
                 "`pipx inject boost-skill-cli \"boost-skill-cli[rag]\"`, "
                 "then `boost quickstart` again")

    complete.refresh_names()
    out.ok("ready — try `boost search brainstorming`")
    return 0
