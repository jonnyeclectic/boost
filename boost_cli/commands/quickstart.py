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
    bootstrap,
    catalog,
    complete,
    config,
    dense,
    journal,
    rag,
    registry,
    shards,
    util,
)
from ..core import output as out
from ..errors import BoostError


def _selection(catalog_scope: bool) -> list[dict]:
    """The registries quickstart will tap: the seven defaults, or all of them.

    `--catalog` exists because "search everything" is a real ask and the two
    costs that used to make it unreasonable are gone: tapping the whole
    catalogue measured 2 min 10 s (463 registries) once clones ran in
    parallel, and their vectors are a download rather than an hour of CPU.
    """
    if not catalog_scope:
        return [d.copy() for d in config.DEFAULT_TAPS]
    return [{"name": e["name"], "url": e["url"]}
            for e in config.load_registry_catalog()
            if not e.get("list_only") and e.get("name") and e.get("url")]


def _tap_defaults(selection: list[dict], pins: dict[str, dict],
                  dry_run: bool) -> tuple[list[str], bootstrap.SetupOutcome]:
    """Tap the selected registries, pinned to a shard's commit when one exists.

    Returns the selected tap names and what happened to each. The names are
    the *selection*, not the result — a registry whose clone failed is still
    in them — and they used to be all this returned, which is how seven failed
    clones ended in "✓ ready": nothing downstream could tell a working machine
    from an unreachable one. The outcome is the result; see
    `bootstrap.SetupOutcome`. A dry run changes nothing, so its outcome is
    empty.

    Pinning is the whole point: tapping HEAD and then fetching a shard is the
    ordering that produces a commit mismatch on every registry that moved since
    the last shard run.
    """
    names = [str(d["name"]) for d in selection]
    outcome = bootstrap.SetupOutcome()
    commits = {name: str(pins[name].get("commit")) for name in names
               if name in pins}
    if dry_run:
        existing = {t.name for t in registry.list_taps()}
        pending = [n for n in names if n not in existing]
        # Over the whole catalogue a line each is a wall of text, so past a handful
        # the dry run reports the shape instead of the list.
        if len(pending) > bootstrap.MAX_NAMED_REGISTRIES:
            out.info("would tap %d registries (%d pinned to a published "
                     "shard's commit)"
                     % (len(pending), sum(1 for n in pending if n in commits)))
            return names, outcome
        for name in names:
            if name in existing:
                out.info(out.role("%s already tapped" % name, "muted"))
                continue
            at = commits.get(name)
            out.info("would tap %s%s" % (name, " @ %s" % at[:7] if at else ""))
        return names, outcome
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
            outcome.already.append(name)
            continue
        if not res.get("ok"):
            out.warn("could not tap %s: %s" % (name, res.get("error", "")))
            outcome.failed.append(name)
            continue
        try:
            entries = catalog.rebuild_tap(res["tap"])
        except BoostError as exc:
            out.warn("could not index %s: %s" % (name, exc.message))
            # Not `failed`: the clone arrived and add_many has already written
            # it to the config, so the verdict must not send this user to
            # check a network that worked.
            outcome.unindexed.append(name)
            continue
        journal.log("tap", name)
        outcome.tapped.append(name)
        at = commits.get(name)
        out.ok("tapped %s (%d items)%s"
               % (name, len(entries), " @ %s" % at[:7] if at else ""))
    return names, outcome


def _report(results: list[dict]) -> None:
    """Say what each shard did, and name the remedy for what it did not do."""
    imported = [r for r in results if r["status"] == "imported"]
    current = [r for r in results if r["status"] == "current"]
    if imported:
        total = sum(int(r.get("chunks") or 0) for r in imported)
        out.ok("imported %d prebuilt shard%s (%s chunks) — no embedding needed"
               % (len(imported), "" if len(imported) == 1 else "s",
                  format(total, ",")))
    if current:
        # Nothing downloaded: the store already holds vectors for exactly the
        # commit the manifest publishes, which is the common case on a rerun.
        out.info(out.role("%d shard%s already up to date — nothing to fetch"
                          % (len(current), "" if len(current) == 1 else "s"),
                          "muted"))
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
    if any(r.get("commit_moved") for r in results):
        # A tap that moved past its vectors has a cheaper fix than embedding:
        # the manifest names the commit they describe, and `update --shards`
        # moves the tap there. A registry first tapped before quickstart
        # pinned anything lands here, and so does any tap once a week's
        # republish moves the manifest past it.
        out.info("taps that moved past their vectors: `boost update --shards`")
    left = [r["tap"] for r in results
            if r["status"] not in ("imported", "current")]
    if left:
        out.info("embed the rest locally when you want to: "
                 "`boost reindex --dense`")


def _muted(msg: str) -> None:
    """An indented muted line, wrapped to the pane.

    Wrap first, colour each line after: `out.role` brackets its argument with
    a start code and a reset, so colouring first and folding after leaves
    line 1 unterminated and the rest unstyled (CLAUDE.md's wrap rule). `- 2`
    pays for the indent `out.info` adds.
    """
    for line in out.wrap(msg, max(out.term_width() - 2, 20)):
        out.info(out.role(line, "muted"))


def _vectors_refused(outcome: bootstrap.SetupOutcome,
                     dry_run: bool = False) -> None:
    """Say once why the published vectors do not apply here, and the fix.

    Once, not per tap: `shards.sync` stamps the same machine-level detail on
    every row, so rendering its rows would print the reason seven times.
    """
    line, fix = outcome.vectors_note(dry_run)
    # Muted like every other zero-reason line: a missed upgrade, not a fault.
    _muted(line)
    _muted(fix)


def _sync_inputs(names: list[str], pins: dict[str, dict] | None = None
                 ) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """The (taps, commits, built) `shards.sync` is called with, for `names`.

    `_tap_commits`/`dense.tap_commits` are keyed by safe name; `sync` speaks
    tap names. The live run passes no `pins`: every tap is configured and at
    the commit its clone says. The dry run passes them, because a registry it
    has not tapped yet will be tapped at exactly that commit (`add_many`'s
    `pins=`), and that is the commit `sync` will then compare against.
    """
    safe = {t.name: t.safe_name for t in registry.list_taps()}
    have, stored = rag._tap_commits(), dense.tap_commits()
    commits = {n: have.get(s, "") for n, s in safe.items()}
    for name in names:
        if pins is not None and name not in safe and name in pins:
            safe[name] = registry.Tap(name=name, url="").safe_name
            commits[name] = str(pins[name].get("commit") or "")
    built = {n: stored.get(s, "") for n, s in safe.items()}
    return [n for n in names if n in safe], commits, built


def _fetch_phrase(steps: list[dict]) -> str:
    """"N shard(s)", with what they weigh when the manifest says.

    The dry run and the live run print this one phrase, so a preview cannot
    promise a count or a size the run then contradicts. The size is the
    manifest's own `bytes`; a row without one makes the sum a floor, and it
    is called one.
    """
    count = sum(1 for s in steps if s["status"] == "download")
    size, unsized = shards.download_bytes(steps)
    if not size:
        return "%d shard(s)" % count
    return "%d shard(s) (%s%s)" % (count, "at least " if unsized else "",
                                  util.human_size(size))


def _planned_rest(steps: list[dict]) -> bool:
    """Name what the dry run will not fetch, and why; True if it said anything.

    Once the preview counts only real downloads, its zero stops meaning "none
    published": a rerun whose vectors are all current plans nothing, and so
    does a tap that moved past its row. Both get the words the live run's
    `_report` gives them, so the preview does not blame the manifest.
    """
    current = sum(1 for s in steps if s["status"] == "current")
    moved = sum(1 for s in steps if s.get("commit_moved"))
    if current:
        _muted("%d shard%s already up to date — nothing to fetch"
               % (current, "" if current == 1 else "s"))
    if moved:
        _muted("%d tap(s) moved past their vectors, so their shards would be "
               "refused: `boost update --shards`" % moved)
    return bool(current or moved)


def _progress(total: int):
    """An `on_event` for `shards.sync`: one short line per download.

    Muted and numbered, so 459 of them read as a counter rather than a wall,
    and silent for every other status — `_report` says what each shard did
    once the loop is over, and repeating it per tap here said it twice.
    """
    done = [0]

    def event(tap: str, status: str, detail: str) -> None:
        if status != "downloading":
            return
        done[0] += 1
        out.info(out.role("fetching %s%s (%d/%d)"
                          % (tap, " %s" % detail if detail else "",
                             done[0], total), "muted"))
    return event


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
    # Fetched first because it decides how the taps are pinned — and fetched
    # without the extra too. Pinning is config, not embedding, and the line a
    # machine without the extra ends on promises that installing it and
    # rerunning brings the vectors. A rerun cannot keep that promise alone:
    # `add_many` skips a tap already configured, so a registry first tapped at
    # HEAD stays at HEAD, and `sync` refuses every shard built for a commit it
    # is not at. Only `--no-vectors` opts out, and it leaves the taps
    # unpinned, so `boost update` keeps moving them. A failure here is not
    # fatal: keyword search is the documented default and works without a
    # single vector.
    if not args.no_vectors:
        try:
            with spin.Spinner("reading the shard manifest"):
                manifest = shards.fetch_manifest()
            pins = shards.rows(manifest)
        except BoostError as exc:
            # "no published shards" named the wrong cause — the project's
            # shards are fine; this machine could not read the manifest (a
            # proxy, a dropped connection, a BOOST_SHARD_MANIFEST typo, an
            # air-gapped mirror). And the hint was the actionable half: every
            # transport-shaped failure raised here carries one.
            out.warn("could not read the shard manifest: %s" % exc.message,
                     wrap=True)
            # Without the extra the manifest was read for its pins alone, and
            # losing them is the whole cost. The transport hint offers
            # `boost reindex --dense`, which needs the very extra this machine
            # lacks, and the run already ends naming how to install it. Every
            # other hint (https only, retry, self-update) still applies.
            if exc.hint and (want_vectors or exc.hint != shards.LOCAL_EMBED_HINT):
                _muted(exc.hint)
            manifest = None

    selection = _selection(args.catalog)
    names, outcome = _tap_defaults(selection, pins, args.dry_run)
    # Judged once, from the manifest alone, and read by both runs below. The
    # live run used to learn it only inside `shards.sync`, whose seven
    # `incompatible` rows it then rendered none of — while the dry run, which
    # never asked, promised every published shard.
    # Only with the extra: without it the manifest was read for its pins, and
    # the missing extra is the reason no vector loads, said in its own words.
    usable = (want_vectors and manifest is not None
              and outcome.judge_vectors(manifest))
    if args.dry_run:
        steps: list[dict] = []
        if usable and manifest is not None:
            taps, commits, built = _sync_inputs(names, pins)
            steps = shards.plan(taps, commits, manifest, built)
        planned = [s for s in steps if s["status"] == "download"]
        out.info("would build the keyword index, then import %s"
                 % _fetch_phrase(steps))
        said = _planned_rest(steps)
        # "0 shard(s)" reads as "none are published" when the real cause is
        # local, and --dry-run is exactly what a cautious new user runs first.
        # The live path already explains both cases; without this the preview
        # is the one surface that reports the symptom and withholds the reason.
        if not planned and not said:
            if args.no_vectors:
                out.info(out.role("(0 because --no-vectors was asked for)",
                                  "muted"))
            elif not dense.have_backend():
                out.info("0 because semantic search needs the extra: `%s` — "
                         "keyword search works without it"
                         % dense.install_extra(), wrap=True)
            elif manifest is None:
                _muted("(0 because the shard manifest could not be read — "
                       "keyword search is unaffected)")
            elif outcome.vectors_refused:
                # Before "none published": `sync` refuses the space before it
                # looks at a single row, so this is the zero the live run hits.
                _vectors_refused(outcome, dry_run=True)
            else:
                _muted("(0 because none of these registries have a "
                       "published shard yet)")
        return 0

    with spin.Spinner("building the keyword index"):
        stats = rag.build()
    outcome.entries = int(stats.get("entries", 0))
    # A tick on "indexed 0 items" is half of the contradiction this command
    # used to print; the other half is the "ready" line below. Both turn on
    # the same fact, so they cannot disagree.
    (out.ok if outcome.searchable else out.warn)(
        "indexed %s items for keyword search" % format(outcome.entries, ","))

    if usable and manifest is not None:
        taps, commits, built = _sync_inputs(names)
        # Said before the first byte moves, in the words the dry run used:
        # the download is the one step here that can take minutes, and it
        # used to run without a line until it was over.
        steps = shards.plan(taps, commits, manifest, built)
        fetch = sum(1 for s in steps if s["status"] == "download")
        if fetch:
            _muted("fetching %s" % _fetch_phrase(steps))
        results = shards.sync(taps, commits, manifest=manifest, built=built,
                              on_event=_progress(fetch))
        _report(results)
    elif outcome.vectors_refused:
        _vectors_refused(outcome)
    elif args.no_vectors:
        out.info(out.role("skipped vectors as asked", "muted"))
    elif not dense.have_backend():
        out.info("semantic search needs the extra: `%s`, then `boost "
                 "quickstart` again" % dense.install_extra(), wrap=True)
    elif want_vectors:
        # The whole vector step was skipped, and the only word about it was a
        # warning many screens back. Without this the run ends "✓ ready" as
        # though vectors had been imported.
        _muted("no vectors imported — the shard manifest could not be read; "
               "`boost update --shards` retries it, and `boost reindex "
               "--dense` builds them locally")

    complete.refresh_names()
    note = outcome.failure_note()
    if note:
        out.warn(note, wrap=True)
    message, hint = outcome.verdict()
    if outcome.ok:
        out.ok(message)
        return 0
    # Raised rather than returned so the failure wears the same `Error:`/`hint:`
    # shape as `boost search`'s own "no taps configured" — the command a user
    # runs next, and the one README's install snippet runs next.
    raise BoostError(message, hint=hint)
