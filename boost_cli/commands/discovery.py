# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Discovery & Search commands: search, discover, recommend, browse,
index, trending, stats, count.

Also exports detect_stack(), shared with the Quality commands.
"""
from __future__ import annotations

import contextlib
import json
import operator
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from .. import cliparse, spin
from ..core import (
    agents,
    ai,
    browse,
    catalog,
    config,
    gitutil,
    journal,
    lockfile,
    paths,
    rag,
    registry,
    rules,
    store,
    util,
)
from ..core import output as out
from ..core.stackprobe import detect_stack  # re-exported: shared with Quality
from ..errors import BoostError
from ._common import _s

__all__ = ["detect_stack"]


_tilde = paths.tilde


def _json_array(text):
    """Best-effort extraction of the first JSON array in an AI reply."""
    m = re.search(r"\[.*\]", text or "", re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _discovery_path() -> Path:
    return paths.cache_dir() / "discovery.json"


def _ai_rank(query: str, scored):
    """Ask Claude to reorder the top hits. Returns a new scored list or None."""
    top = scored[:15]
    listing = "\n".join("- %s: %s" % (e["name"], e["description"])
                        for e, _ in top)
    reply = ai.ask(
        "Query: %s\n\nSkills:\n%s\n\nOrder these skill names best-match-first "
        "for the query. Reply with ONLY a JSON array of names."
        % (query, listing),
        system="You rank AI coding skills by relevance to a search query.",
        max_tokens=400)
    order = _json_array(reply)
    if not order:
        return None
    by_name = {e["name"]: (e, s) for e, s in scored}
    names = [str(n) for n in order if str(n) in by_name]
    rest = [t for t in scored if t[0]["name"] not in set(names)]
    return [by_name[n] for n in names] + rest


_ENGINE_LABEL = {"BM25 full-content": "full-content BM25"}


def cmd_search(argv):
    """Search the tap catalogs, optionally AI-reranked with --smart."""
    p = cliparse.parser(
        prog="boost search",
        description="Search skills across tap registries (AI-ranked)")
    p.add_argument("query", nargs="+", help="search terms")
    p.add_argument("--smart", action="store_true",
                   help="rerank the top hits with Claude")
    p.add_argument("--category", default="",
                   help="only show entries whose category matches (case-insensitive)")
    p.add_argument("--limit", type=util.positive_int, default=15,
                   help="max results (default 15)")
    p.add_argument("--collapse-near-duplicates", action="store_true",
                   dest="collapse_dupes",
                   help="collapse near-identical entries (translations, "
                        "paraphrases) via dense embeddings — opt-in, needs a "
                        "built dense index; threshold not yet validated "
                        "against a real corpus, see the roadmap")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    query = " ".join(args.query)
    if not registry.list_taps():
        raise BoostError("no taps configured — nothing to search",
                        hint="add the recommended registries with `boost tap --defaults`")
    # Full-content (RAG) search is the default: build the index on first use so
    # every user gets BM25 ranking without having to know about `boost reindex`.
    # rag.ensure() is incremental, offline, and degrades to frontmatter search
    # if the build fails — so a search never hard-fails on an indexing problem.
    #
    # `and not rag.stale()`, not a bare `rag.ready()`: ready() only asks whether
    # an index exists, so once one did, `boost tap X` followed by a search
    # answered "no matches" for a skill `boost info X` could describe from the
    # same machine — and pointed the user at `boost discover` to go searching
    # GitHub for something already on disk.
    fresh = rag.ready() and not rag.stale()
    use_rag = fresh
    if not fresh:
        # Name which one it is: a first build and a refresh cost the user the
        # same pause, and only one of them is explained by "first run".
        with spin.Spinner("refreshing the search index (taps changed)"
                          if rag.ready() else
                          "building the search index (first run)"):
            use_rag = rag.ensure()
    engine = ""
    if use_rag:
        # retrieve_any, not retrieve: this picks the dense backend when one is
        # built and floors to BM25 otherwise, so the CLI and the MCP server
        # answer from the same engine instead of the CLI being BM25-only.
        hits, engine = rag.retrieve_any(
            query, k=max(60, args.limit * 4),
            collapse_near_duplicates=args.collapse_dupes)
        scored = [(h["entry"], h["score"]) for h in (hits or [])]
    else:
        scored = catalog.search(query)
    if args.category:
        scored = [(e, s) for e, s in scored
                 if catalog.matches_category(e, args.category)]
    if args.as_json:
        print(json.dumps([e | {"score": s} for e, s in scored[:args.limit]]))
        return 0
    if not scored:
        # The standardized ○/→ empty state, so "nothing here" reads the same
        # as every other command's; both wordings are pinned by tests.
        print(out.empty_state(
            "no matches for %r" % query,
            "try `boost discover %s` to search all of GitHub" % query))
        _hint_semantic_search(engine)
        # Especially here: "no matches" is exactly the answer an out-of-date
        # tap set produces, and the user has no other way to suspect it.
        _hint_stale_taps()
        return 0
    # The CLI's long-standing wording for the BM25 engine differs from the label
    # rag/eval use ("BM25 full-content"), and both are load-bearing: the latter
    # is pinned in tests/eval/baseline.json. Map instead of moving either.
    ranker = _ENGINE_LABEL.get(engine, engine) if use_rag else "heuristic relevance"
    if args.smart:
        if ai.available():
            with spin.Spinner("ranking %d matches with Claude" % len(scored)):
                reranked = _ai_rank(query, scored)
            if reranked:
                scored, ranker = reranked, "Claude Haiku relevance"
        else:
            out.warn(ai.fallback_note(), wrap=True)
    shown = scored[:args.limit]
    # The dot marks "a skill by this name is installed" — a name match, with
    # the known homonym caveat (13 real skills share `code-reviewer`). A lock
    # problem must never take search down with it.
    installed: set[str] = set()
    with contextlib.suppress(Exception):
        installed = set(store.installed())
    top = max((s for _e, s in shown), default=0) or 1
    # One column plan for the whole screen (name, kind, tap, description with
    # a stated drop order), one assembler per row — both pure and unit-tested
    # in core.output, so this loop only feeds and prints.
    lay = out.search_layout(out.term_width(),
                            [e["name"] for e, _ in shown],
                            [str(e.get("kind") or "skill") for e, _ in shown],
                            [str(e.get("tap") or "") for e, _ in shown])
    for e, sc in shown:
        out.info(out.format_search_row(
            e["name"], e.get("description") or "",
            str(e.get("kind") or "skill"), str(e.get("tap") or ""), sc / top,
            curated=bool(e.get("curated")),
            installed=e["name"] in installed, lay=lay))
    out.info(out.role("%d match%s · ranked by %s"
                   % (len(scored), "" if len(scored) == 1 else "es", ranker), "muted"))
    if use_rag:
        _note_stem_expansions(query)
    _hint_semantic_search(engine)
    _hint_stale_taps()
    return 0


def _note_stem_expansions(query: str) -> None:
    """Say when a query term was widened to the word actually indexed.

    Staying quiet would be a worse answer than the old empty one: the user
    asked for `brainstorm` and is looking at results for `brainstorming`, and
    only one of those is a word they typed.
    """
    subs = rag.stem_expansions(rag.tokenize(query))
    if not subs:
        return
    said = ", ".join("%r" % term for term in subs)
    shown = ", ".join("%r" % term for term in subs.values())
    out.info(out.role(out.truncate(
        "no exact match for %s — showing %s" % (said, shown),
        max(0, out.term_width() - 2)), "muted"))


def _hint_stale_taps() -> None:
    """Mention old tap clones. One `stat`, and never a network call.

    Search deliberately does not refresh the taps themselves. A refresh is a
    `git fetch` per tap — ~1.6 s each, minutes across a real install — so doing
    it inline would turn a sub-second command into a wait, and doing it in the
    background would mean unannounced network egress plus writes to the very
    caches the search is reading. Worse, a tap's commit is load-bearing for
    dense vectors, so a silent update would strand imported shards as stale.

    So: say it, do not do it. The marker's mtime answers "how long ago" for the
    price of one stat, and a machine that has never refreshed says nothing at
    all rather than inventing an age.
    """
    if _hint_stale_shards():
        return
    age = registry.refresh_age_days()
    if age is None or age < registry.STALE_TAPS_DAYS:
        return
    out.info(out.role(
        "taps last refreshed %d days ago — `boost update --taps-only`"
        % int(age), "muted"))


def _hint_stale_shards() -> bool:
    """Mention un-ingested published vectors. One `stat`, and never a network call.

    The published manifest is ~170 KB, so checking it inline would be cheap —
    and cheapness is not the argument. Acting on the answer means moving taps
    and downloading hundreds of megabytes, which cannot happen inside a
    sub-second search, so the most an inline check could ever produce is this
    one line: the same line, for the price of a network round trip on every
    query and unannounced egress at that. The marker's mtime answers it for
    free, and a machine that has never ingested a shard says nothing rather
    than inventing an age.

    Returns True when it printed, so the tap-age hint stays quiet. The remedy
    named here moves the taps as well, and two staleness lines under one set of
    results is how a hint turns into noise.
    """
    from ..core import shards
    age = shards.sync_age_days()
    if age is None or age < shards.STALE_SHARDS_DAYS:
        return False
    from ..core import dense
    if not dense.status().get("ready"):
        # Vectors that are not serving queries cannot be stale in a way the
        # user can act on; `_hint_semantic_search` owns that conversation.
        return False
    out.info(out.role(
        "prebuilt vectors last refreshed %d days ago — `boost update --shards`"
        % int(age), "muted"))
    return True


def _hint_semantic_search(engine: str) -> None:
    """Say that a better engine exists, when BM25 answered alone.

    `boost search` reported which engine *ran* and never that a better one was
    available, so a user who installed the extra but never reindexed had no way
    to learn the semantic search they think they enabled has never once run.
    That is the silent half of the three-things-must-line-up problem, and
    `boost doctor` was the only surface that said anything about it.

    Deliberately quiet: one muted line, only when dense contributed nothing, and
    naming the ONE next action rather than the whole setup. The remedy comes
    from core.dense.fix_hint — the same table doctor reads — so the two surfaces
    can never disagree about whether an API key is needed.
    """
    if engine != "BM25 full-content":
        # Anything else either already used vectors ("dense vectors", "hybrid
        # RRF") or is the frontmatter fallback, where the BM25 index failed to
        # build — a louder problem that this hint would only paper over.
        return
    from ..core import dense
    st = dense.status()
    if st.get("ready"):
        return
    # Wrap to the pane like every other row here: at COLUMNS=60 the longest
    # remedy is 82 characters and would be the one line in this output that
    # blows the terminal width. `break_long_words=False` keeps the shell command
    # runnable — a copy-pasteable `pip install ...` matters more than a hard
    # clamp, and _FIX is tested to hold no token long enough to overflow.
    msg = "semantic search is off — %s" % dense.fix_hint(st.get("reason", ""), st)
    # `- 2` pays for the indent `out.info` adds: wrapping to the full width and
    # then indenting is what put this hint one column over the pane. Wrap
    # first, colour each line after — `out.role` brackets its argument with a
    # start code and a reset, so colouring first and splitting after leaves the
    # first line unterminated and the second uncoloured.
    for line in out.wrap(msg, max(out.term_width() - 2, 20)):
        out.info(out.role(line, "muted"))


def _shard_io(args) -> int:
    """`--export-shard` / `--import-shard`, the two halves of a prebuilt shard.

    Embedding is ~1.2 s/chunk on CPU — 74 minutes for 743 entries — so without
    a way to move vectors between machines the keyless tier is available in
    principle and unreachable in practice. Import validates rather than trusts;
    see `dense.import_shard` for why a mismatched shard must be refused instead
    of merged.
    """
    from ..core import dense
    if args.export_shard:
        shard = dense.export_shard(args.export_shard)
        if not shard.get("chunks"):
            raise BoostError("no vectors for %r" % args.export_shard,
                            hint="build them first with `boost reindex --dense`")
        print(json.dumps(shard))
        return 0
    path = Path(args.import_shard)
    try:
        shard = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoostError("cannot read shard %s: %s" % (path, exc)) from exc
    tap = str(shard.get("tap") or "")
    commit = rag._tap_commits().get(tap.replace("/", "__"), "")
    ok, reason = dense.import_shard(shard, commit=commit)
    if not ok:
        raise BoostError("shard refused — %s" % reason,
                        hint="`boost reindex --dense` embeds it locally instead")
    out.ok("%s: %s" % (tap, reason))
    return 0


def _fetch_shards(args) -> int:
    """`--fetch-shards`: the published half of the keyless tier, on demand.

    Separate from `boost quickstart` because the two answer different
    questions. Quickstart sets a machine up; this refreshes vectors on one that
    is already tapped, including taps quickstart never touches.
    """
    from ..core import dense, shards
    if not registry.list_taps():
        raise BoostError("no taps configured — nothing to fetch",
                        hint="`boost quickstart` taps the defaults and fetches "
                             "their vectors in one pass")
    manifest = shards.fetch_manifest()
    why = shards.incompatible(manifest)
    if why:
        raise BoostError("published shards cannot serve this machine — %s" % why,
                        hint=dense.fix_hint(dense.status().get("reason", "")))
    commits = rag._tap_commits()
    stored = dense.tap_commits()
    by_name = {t.name: commits.get(t.safe_name, "") for t in registry.list_taps()}
    built = {t.name: stored.get(t.safe_name, "") for t in registry.list_taps()}
    results = shards.sync(
        list(by_name), by_name, manifest=manifest, built=built,
        # Progress goes to stdout, and so does the JSON: emitting both left
        # `--json` printing "fetching ..." lines ahead of the document, which
        # no parser can read past.
        on_event=None if args.as_json else _shard_event)
    if args.as_json:
        print(json.dumps({"shards": results}, indent=2))
        return 0
    got = [r for r in results if r["status"] == "imported"]
    current = [r for r in results if r["status"] == "current"]
    total = sum(int(r.get("chunks") or 0) for r in got)
    if got:
        out.ok("imported %d shard(s), %s chunks — no embedding needed"
               % (len(got), format(total, ",")))
    if current:
        # Nothing to download: the store already holds vectors for exactly
        # the commit the manifest publishes. Reported alongside `got` rather
        # than instead of it — a run that imports some shards and finds the
        # rest already current has two things to say, and an `elif` here said
        # only the first.
        out.info(out.role("%d shard(s) already up to date — nothing to fetch"
                          % len(current), "muted"))
    if not got and not current:
        # Not a success line. Nothing landed, and saying "imported 0" with a
        # tick reads as a job well done to the one user who most needs to know
        # their vectors are still missing.
        out.warn("no published vectors matched your taps")
    missing = [r["tap"] for r in results
               if r["status"] not in ("imported", "current")]
    if missing:
        out.info(out.role("%d tap(s) without usable vectors: %s"
                          % (len(missing), ", ".join(missing[:5])
                             + (" …" if len(missing) > 5 else "")), "muted"))
        if any(r["status"] == "refused" for r in results):
            # A refusal here is almost always "the tap has moved past the
            # commit these vectors describe", which local embedding is the
            # expensive answer to and `--shards` is the cheap one: it moves the
            # tap back onto a published commit instead.
            out.info("taps that moved past their vectors: `boost update --shards`")
        out.info("embed those locally with `boost reindex --dense`")
    return 0


def _shard_event(tap: str, status: str, detail: str) -> None:
    """Progress for one shard, quiet enough to run over forty taps."""
    if status == "downloading":
        out.info(out.role("fetching %s %s" % (tap, detail), "muted"))
    elif status in ("failed", "refused"):
        out.info(out.role("%s: %s%s" % (tap, status,
                                        " (%s)" % detail if detail else ""),
                          "muted"))


def cmd_reindex(argv):
    """Build/refresh the full-content (RAG) search index over tapped items."""
    p = cliparse.parser(
        prog="boost reindex",
        description="Build or refresh the full-content search index")
    p.add_argument("--force", action="store_true",
                   help="reindex every tap, ignoring cached commits")
    p.add_argument("--dense", action="store_true",
                   help="also embed chunks into the opt-in dense vector store "
                        "(needs the `rag` extra; no API key required)")
    p.add_argument("--export-shard", metavar="TAP",
                   help="write TAP's prebuilt vectors to stdout as JSON, for "
                        "publishing so others need not re-embed them")
    p.add_argument("--import-shard", metavar="FILE",
                   help="merge a prebuilt vector shard, skipping the embed "
                        "cost; refused unless it matches this store's backend "
                        "and the tap's current commit")
    p.add_argument("--fetch-shards", action="store_true",
                   help="download and import published vectors for every tap "
                        "that has them, instead of embedding locally")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    if args.export_shard or args.import_shard:
        return _shard_io(args)
    if args.fetch_shards:
        return _fetch_shards(args)
    if not registry.list_taps():
        raise BoostError("no taps configured — nothing to index",
                        hint="add the recommended registries with `boost tap --defaults`")
    with spin.Spinner("building full-content index"):
        stats = rag.build(force=args.force)
    dense_stats = None
    if args.dense:
        # Imported lazily (only on `--dense`) so the optional dense/embedding
        # stack never loads for the common offline commands this module also
        # holds — count, stats, trending, plain search. See the import-budget
        # gate (scripts/import_budget.py).
        from ..core import embed
        with spin.Spinner("embedding chunks into the dense store") as sp:
            dense_stats = _reindex_dense(args.force, spinner=sp)
    if args.as_json:
        print(json.dumps({"bm25": stats, "dense": dense_stats}
                         if args.dense else stats))
        return 0
    out.ok("indexed %d passages across %d items from %d tap%s"
           % (stats["docs"], stats["entries"], stats["taps"],
              "" if stats["taps"] == 1 else "s"))
    if stats["reused"]:
        out.info(out.role("reused %d unchanged tap%s; reindexed: %s"
                       % (len(stats["reused"]),
                          "" if len(stats["reused"]) == 1 else "s",
                          ", ".join(stats["reindexed"]) or "none"), "muted"))
    if args.dense:
        if dense_stats is None:
            out.warn("dense index skipped — %s" % embed.fallback_note(),
                     wrap=True)
        else:
            failed = dense_stats.get("failed") or []
            if failed:
                out.warn("embedding failed for %d tap(s) — %d passages stored. "
                         "The provider rejected those batches (rate limit, "
                         "quota, or oversized input); their commits were not "
                         "recorded, so a rerun retries them."
                         % (len(failed), dense_stats["chunks"]))
            elif not dense_stats["chunks"]:
                # Reporting success with an empty store sent a real user chasing
                # the wrong cause: a stale run can mark every tap "built", so the
                # reuse path skips everything and stores nothing.
                out.warn("the dense vector store is empty — %d tap(s) were "
                         "reused as already-built. Rebuild with "
                         "`boost reindex --dense --force`."
                         % len(dense_stats["reused"]))
            else:
                # `chunks` is the store TOTAL, not this run's work, so on an
                # incremental run "embedded 657,587 passages" described an
                # afternoon of CPU that did not happen. `added` is what this
                # run actually paid for.
                added = dense_stats.get("added", dense_stats["chunks"])
                out.ok("embedded %d passage%s (%s) — the dense store holds %d"
                       % (added, "" if added == 1 else "s",
                          dense_stats["provider"], dense_stats["chunks"]))
                # The saving the tap-level line cannot show: a tap appears in
                # `reindexed` the moment its commit moves, so a run that reused
                # every entry inside three moved taps otherwise reads as three
                # taps fully re-embedded.
                kept = dense_stats.get("reused_entries") or 0
                if kept:
                    out.info(out.role(
                        "reused %d unchanged item%s inside %d moved tap%s — "
                        "only %d item%s changed"
                        % (kept, "" if kept == 1 else "s",
                           len(dense_stats["reindexed"]),
                           "" if len(dense_stats["reindexed"]) == 1 else "s",
                           dense_stats.get("embedded_entries") or 0,
                           "" if dense_stats.get("embedded_entries") == 1
                           else "s"), "muted"))
            if dense_stats.get("quantized"):
                out.ok("quantized %d existing vectors — dense search no longer "
                       "scans the whole store on every query"
                       % dense_stats["quantized"])
            if dense_stats.get("deduplicated"):
                out.ok("reclaimed %d duplicate vector%s — registries paste the "
                       "same text, and the store now holds one copy of each"
                       % (dense_stats["deduplicated"],
                          "" if dense_stats["deduplicated"] == 1 else "s"))
    journal.log("reindex", "%d passages" % stats["docs"],
                entries=stats["entries"])
    return 0


def _embed_progress(spinner):
    """A callback that rewrites the spinner's label with real numbers.

    Embedding is the longest thing boost does — tens of thousands of distinct
    chunks at roughly a second each for a full catalogue — and it ran under a
    fixed label for hours. "embedding chunks into the dense store" is
    indistinguishable from a hang, which is exactly how it was reported.

    The rate comes from this run rather than a constant, because the two
    backends differ by an order of magnitude and a local model's throughput
    depends on the machine. Until a batch has finished there is nothing to
    estimate from, so it says the total and nothing else rather than guessing.
    """
    started = time.monotonic()

    def report(done: int, total: int) -> None:
        if spinner is None or not total:
            return
        pct = 100.0 * done / total
        # The bar first, because it is the part that answers the question the
        # user actually has — "is this moving?" — at a glance, before any of
        # the digits are read. `spin.bar` is the same determinate bar the rest
        # of the CLI draws, so this looks like boost rather than like a
        # second progress convention.
        label = "embedding %s %d%% · %s/%s chunks" % (
            spin.bar(done, total, width=16), int(pct),
            format(done, ","), format(total, ","))
        elapsed = time.monotonic() - started
        if done and elapsed > 1:
            remaining = (total - done) * (elapsed / done)
            if remaining >= 1:
                label += " · ~%s left" % util.human_duration(remaining)
        spinner.label = label

    return report


def _reindex_dense(force, spinner=None):
    """Build the dense vector store; returns stats or None when unavailable."""
    # Local import: the dense/embedding engines are opt-in (`search --dense`),
    # so they stay out of startup for every other command in this module.
    from ..core import dense, embed
    if not dense.have_backend() or not embed.available():
        return None
    # Convert a pre-quantization store first, so a user who reindexes gets the
    # speedup without having to know the word "quantize". It re-encodes vectors
    # already on disk — no provider call, no cost — and `build` below then adds
    # only what changed. Doing it after would quantize, then write float32 rows
    # into a store that no longer has a float32 table.
    migrated = dense.quantize()
    # Then collapse the byte-identical copies, in that order and not the other:
    # `quantize` moves vectors out of `vec_chunks` one rowid at a time and
    # would refuse a store whose vector rows no longer match its chunk rows,
    # which is exactly what deduplicating first produces. Both are offline and
    # free — they re-encode and re-key what is already on disk — so a user gets
    # the disk back without having to know either word.
    collapsed = dense.deduplicate()
    stats = dense.build(force=force, on_progress=_embed_progress(spinner))
    if migrated and isinstance(stats, dict):
        stats = stats | {"quantized": migrated["chunks"]}
    if collapsed and isinstance(stats, dict) and collapsed["freed"]:
        stats = stats | {"deduplicated": collapsed["freed"]}
    return stats


def cmd_index(argv):
    """Build ~/.boost/cache/discovery.json via `gh api` code search."""
    p = cliparse.parser(
        prog="boost index",
        description="Build the discovery registry via GitHub Code Search")
    p.add_argument("query", nargs="*",
                   help="narrow the sample to these terms (default: any SKILL.md)")
    p.add_argument("--limit", type=util.positive_int, default=300,
                   help="max skill files to index (default 300)")
    args = p.parse_args(argv)
    if not shutil.which("gh"):
        raise BoostError("the GitHub CLI (gh) is required to build the index",
                        hint="brew install gh && gh auth login")
    query = " ".join(t for t in args.query if t.strip())
    # Unqueried, this samples whatever code search happens to rank first, so an
    # untargeted build is a lucky draw rather than a corpus. Callers who know
    # what they are after can now aim it.
    q = "filename:SKILL.md" + ((" " + query) if query else "")
    items: list[dict] = []
    total = 0
    pages = min((max(1, args.limit) + 99) // 100, 10)  # code search caps at 1000
    for page in range(1, pages + 1):
        spin.progress(page, pages, "searching GitHub for SKILL.md")
        if page > 1:
            time.sleep(1)  # stay under the code-search rate limit
        try:
            proc = subprocess.run(
                ["gh", "api", "-H", "Accept: application/vnd.github+json",
                 "search/code?q=%s&per_page=100&page=%d"
                 % (urllib.parse.quote(q, safe=":"), page)],
                capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as e:
            raise BoostError("gh api timed out on page %d" % page, hint=str(e)) from e
        if proc.returncode != 0:
            tail = "\n".join((proc.stderr or proc.stdout or "").strip()
                             .splitlines()[-3:])
            if not items:
                raise BoostError("GitHub code search failed",
                                hint=tail or "check `gh auth status`")
            out.warn("page %d failed — keeping the %d items fetched so far"
                     % (page, len(items)))
            break
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise BoostError("gh api returned unparseable JSON",
                            hint="try `boost index` again, or `gh auth status`") from None
        if page == 1:
            total = int(data.get("total_count") or 0)
        batch = data.get("items") or []
        for it in batch:
            repo = it.get("repository") or {}
            items.append({
                "repo": repo.get("full_name", "?"),
                "path": it.get("path", ""),
                "url": it.get("html_url", ""),
                "description": repo.get("description") or "",
            })
            if len(items) >= args.limit:
                break
        if len(items) >= args.limit or len(batch) < 100:
            break
    paths.ensure_dirs()
    _discovery_path().write_text(json.dumps(
        {"generated": util.now_iso(), "github_total": total, "query": query,
         "items": items}, indent=1), encoding="utf-8")
    repos = len({it["repo"] for it in items})
    out.ok("indexed %d skill files across %d repos (GitHub reports %d total)"
           % (len(items), repos, total))
    journal.log("index", "%d skill files" % len(items), total=total)
    return 0


def github_skill_search(query="", limit=20):
    """One-shot GitHub code search for SKILL.md repos (Phase-3 MCP reach-out).

    Returns a list of ``{repo, path, url, description}`` dicts, or ``None`` when
    the `gh` CLI is unavailable or the search fails — so callers degrade
    gracefully instead of raising. Unlike :func:`cmd_index` this fetches a single
    page and writes no cache: it is sized for an interactive MCP call, not a full
    corpus build.
    """
    if not shutil.which("gh"):
        return None
    q = "filename:SKILL.md"
    if query and query.strip():
        q += " " + query.strip()
    per_page = max(1, min(int(limit), 100))
    try:
        proc = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github+json",
             "search/code?q=%s&per_page=%d&page=1"
             % (urllib.parse.quote(q, safe=":"), per_page)],
            capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    items = []
    for it in (data.get("items") or [])[:per_page]:
        repo = it.get("repository") or {}
        items.append({
            "repo": repo.get("full_name", "?"),
            "path": it.get("path", ""),
            "url": it.get("html_url", ""),
            "description": repo.get("description") or "",
        })
    return items


def _by_repo(hits):
    """Collapse per-file code-search hits into one row per repository.

    Code search returns a row per matching SKILL.md, so a repo carrying several
    skills — or mirroring them into per-agent plugin directories — can fill the
    whole limit with itself. What `discover` is for is naming a repo worth
    tapping, so the repo is the unit that belongs on screen.
    """
    rows: dict[str, dict] = {}
    for h in hits:
        row = rows.get(h["repo"])
        if row is None:
            rows[h["repo"]] = h | {"files": 1}
            continue
        row["files"] += 1
        if not row.get("description"):
            row["description"] = h.get("description") or ""
        # Show the shallowest copy: `skills/x` is the one a registry means,
        # and the per-agent mirrors below it are the same skill again.
        if (str(h.get("path", "")).count("/")
                < str(row.get("path", "")).count("/")):
            row["path"], row["url"] = h.get("path", ""), h.get("url", "")
    return list(rows.values())


# Code search caps a page at 100, and the whole page is what we want. `--limit`
# counts ROWS, and a row is a repo — but code search ranks per *file* with no
# per-repo cap, so one large registry routinely owns the top 25 hits. Spending
# the budget on files and collapsing afterwards returned a single row for
# `--limit 25`.
_GH_PAGE = 100


def _fall_back(why: str, hint: str) -> None:
    """Explain the fall-through to the local index, then return None.

    On stderr, so it survives ``--json``: suppressing it was the defect. A
    script piping stdout still gets clean JSON, and nobody is left unable to
    tell "GitHub has no matches" from "GitHub was never searched".
    """
    out.warn("%s — falling back to the local index" % why, stream=sys.stderr)
    out.info(out.role(hint, "muted"), stream=sys.stderr)
    return None


def _discover_live(args, tokens):
    """Search GitHub itself — the same reach-out the MCP tool makes.

    Returns an exit code, or None to fall through to the cached index.
    """
    if not shutil.which("gh"):
        return _fall_back("GitHub search needs the `gh` CLI",
                          "install it with `brew install gh && gh auth login` "
                          "to search GitHub itself")
    hits = github_skill_search(" ".join(tokens), _GH_PAGE)
    if hits is None:
        return _fall_back("GitHub code search failed", "check `gh auth status`")
    rows = _by_repo(hits)[:args.limit]
    if args.as_json:
        # `source` on every row, in both paths, because the fall-through above
        # switches corpus *and* row shape. Without it a script cannot tell
        # "GitHub has no matches" from "GitHub was never searched".
        print(json.dumps([r | {"source": "github"} for r in rows]))
        return 0
    if not rows:
        out.info("no SKILL.md repositories on GitHub match %r"
                 % " ".join(tokens))
        out.info(out.role("try broader terms, or `boost search` for the "
                          "registries already tapped", "muted"))
        return 0
    # The count rides the repo column, which is short: appended to the path it
    # was the first thing a narrow terminal truncated away. out.plain because
    # every field here is a GitHub string — a repo name or path carrying a
    # cursor-movement escape would rewrite the rows printed above it.
    out.table([(out.plain(it.get("repo", "?"))
                + (" (%d)" % it["files"] if it.get("files", 1) > 1 else ""),
                out.plain(it.get("path", "")),
                out.role(out.plain(it.get("url", "")), "muted")) for it in rows],
              headers=("repo", "path", "url"))
    # "(N)" counts files in THIS page, not the repo's skills — say so, rather
    # than letting a capped sample read as a total.
    out.info(out.role("%d repo(s) across the top %d code-search hits · live "
                      "GitHub Code Search" % (len(rows), len(hits)), "muted"))
    out.info(out.role("add one with `boost tap <repo>`, then `boost install "
                      "<skill>`", "muted"))
    return 0


def cmd_discover(argv):
    """Search GitHub for SKILL.md repos to tap — live, no index required."""
    p = cliparse.parser(
        prog="boost discover",
        description="Search GitHub for skill repositories you have not tapped yet")
    p.add_argument("query", nargs="*", help="search terms (topic, language, name)")
    p.add_argument("--limit", type=util.positive_int, default=25,
                   help="max rows (default 25)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    p.add_argument("--local", action="store_true",
                   help="search only the cached index, never the network")
    args = p.parse_args(argv)
    tokens = [t for t in args.query if t.strip()]
    # A query is a question about GitHub, not about whatever `boost index`
    # happened to sample — so ask GitHub. The cached index stays the answer for
    # bare browsing and for --local, where being offline is the point.
    if tokens and not args.local:
        code = _discover_live(args, tokens)
        if code is not None:
            return code
    dpath = _discovery_path()
    if not dpath.exists():
        if args.as_json:
            print(json.dumps([]))
            return 0
        out.info("the discovery index has not been built yet")
        if shutil.which("gh"):
            out.info("build it with `boost index` (GitHub Code Search)")
        else:
            out.info("install the GitHub CLI first (`brew install gh && "
                     "gh auth login`), then run `boost index`")
        return 0
    try:
        data = json.loads(dpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise BoostError("the discovery index is corrupt",
                        hint="rebuild it with `boost index`") from None
    all_items = data.get("items") or []
    tokens = [t.lower() for t in args.query if t.strip()]
    items = [it for it in all_items
             if all(t in ("%s %s %s" % (it.get("repo", ""), it.get("path", ""),
                                        it.get("description", ""))).lower()
                    for t in tokens)]
    shown = items[:args.limit]
    if args.as_json:
        # Tagged like the live rows above: this is the branch a script reaches
        # after a silent fall-through, and the two row shapes differ.
        print(json.dumps([it | {"source": "local-index"} for it in shown]))
        return 0
    if not shown:
        out.info("no locally indexed skills match %r" % " ".join(args.query))
        # Say what was actually consulted. The old wording read as a verdict on
        # GitHub when it was only ever a verdict on this cache. The next line
        # depends on WHY we are here: told to stay local, or fell through after
        # GitHub was unreachable. "drop --local" to someone who never typed it
        # is advice they cannot act on, contradicting the warning just printed.
        out.info(out.role(
            ("this searched a local sample of %d entries, not GitHub — drop "
             "--local to search GitHub itself" % len(all_items))
            if args.local else
            ("this searched a local sample of %d entries because GitHub could "
             "not be reached" % len(all_items)), "muted"))
        return 0
    # out.plain: these rows came from GitHub too, by way of `boost index`.
    out.table([(out.plain(it.get("repo", "?")), out.plain(it.get("path", "")),
                out.role(out.plain(it.get("url", "")), "muted")) for it in shown],
              headers=("repo", "path", "url"))
    # `github_total` is the match count for the query `boost index` was built
    # with, which since that command took a query is not "all of GitHub".
    scope = (" matching %r" % data["query"]) if data.get("query") else ""
    out.info(out.role("%d of %d indexed skills · GitHub reported ~%d total%s "
                      "when this index was built"
                      % (len(shown), len(all_items),
                         int(data.get("github_total") or 0), scope), "muted"))
    return 0


def _ai_picks(stack: dict, cands):
    """Ask Claude for its top-5 picks with reasons. Returns list or None."""
    listing = "\n".join("- %s: %s" % (e["name"], e["description"])
                        for e in cands)
    reply = ai.ask(
        "Project stack: %s\n\nCandidate skills:\n%s\n\nPick the 5 best skills "
        "for this project. Reply with ONLY a JSON array like "
        '[{"name": "...", "reason": "one short line"}].'
        % (json.dumps(stack), listing),
        system="You recommend AI coding skills for a software project.",
        max_tokens=500)
    picks = _json_array(reply)
    if not picks:
        return None
    return [pk for pk in picks if isinstance(pk, dict) and pk.get("name")][:5]


def cmd_recommend(argv):
    """Match the detected tech stack against the catalog."""
    p = cliparse.parser(
        prog="boost recommend",
        description="Suggest skills based on your project's tech stack")
    p.add_argument("--path", default=".", help="project directory (default: cwd)")
    p.add_argument("--category", default="",
                   help="only recommend entries whose category matches (case-insensitive)")
    p.add_argument("--limit", type=util.positive_int, default=8,
                   help="max suggestions (default 8)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    target = paths.expand(args.path).resolve()
    if not target.is_dir():
        raise BoostError("no such directory: %s" % args.path)
    entries = catalog.all_entries()
    if args.category:
        entries = catalog.filter_by_category(entries, args.category)
        if not entries:
            raise BoostError("no entries in category %r" % args.category,
                            hint="try `boost recommend` with no --category")
    elif not entries:
        raise BoostError("no skills in any tap to recommend from",
                        hint="add registries with `boost tap --defaults`")
    stack = detect_stack(target)
    agg: dict[str, dict[str, Any]] = {}
    for kw in stack["keywords"]:
        for e, s in catalog.search(kw, entries):
            rec = agg.setdefault(e["name"], {"entry": e, "score": 0,
                                             "because": set()})
            rec["score"] += s
            rec["because"].add(kw)
    for rec in agg.values():
        if rec["entry"].get("curated"):
            rec["score"] += 10
    ranked = sorted(agg.values(),
                    key=lambda r: (-r["score"], r["entry"]["name"]))
    if args.as_json:
        print(json.dumps({"stack": stack, "recommendations": [
            r["entry"] | {"score": r["score"], "because": sorted(r["because"])}
            for r in ranked[:args.limit]]}))
        return 0
    line = "stack: " + (", ".join(stack["languages"]) or "unknown")
    if stack["frameworks"]:
        line += " · frameworks: " + ", ".join(stack["frameworks"])
    out.info(out.role("%s  (%s)" % (line, _tilde(target)), "muted"))
    shown: list[dict[str, Any]] = ranked[:args.limit]
    if not shown:
        # Annotated rather than inlined: an unannotated literal of mixed value
        # types infers dict[str, object], which then makes every r["entry"][…]
        # read below an error about indexing `object`.
        curated: list[dict[str, Any]] = [
            {"entry": e, "score": 0, "because": {"curated"}}
            for e in entries if e.get("curated")]
        shown = curated[:args.limit]
        if not shown:
            out.info("no recommendations for this stack — try `boost search <keyword>`")
            return 0
        out.info("no stack-specific matches — curated picks instead:")
    width = min(max(len(r["entry"]["name"]) for r in shown), 32)
    cols = out.term_width()
    for r in shown:
        e = r["entry"]
        because = "because: %s" % ", ".join(sorted(r["because"]))
        desc_w = max(cols - 2 - width - 2 - (len(because) + 2), 8)
        name_cell = out.role(out.truncate(e["name"], width).ljust(width), "accent")
        out.info(name_cell + "  " + out.truncate(e["description"] or "", desc_w)
                 + "  " + out.role(because, "muted"))
    if ai.available():
        picks = _ai_picks(stack, [r["entry"] for r in ranked[:20]])
        if picks:
            out.heading("AI picks")
            for pk in picks:
                out.info(out.role(str(pk.get("name", "?")), "accent") + "  "
                         + str(pk.get("reason", "")))
    return 0


def _browse_plain(entries, why: str):
    out.warn(why + " — showing the full catalog")
    out.table([(e["name"], "v" + e["version"], e["tap"],
                "★" if e.get("curated") else "") for e in entries],
              headers=("name", "version", "tap", ""))
    out.info(out.role("%d skills · install with `boost install <name>`"
                   % len(entries), "muted"))
    return 0


def _tap_categories() -> dict:
    """tap name ('owner/repo') -> curated category, from the bundled registry
    catalog (data/registries.json). Fallback only: a catalog entry's own
    stamped `category` (`catalog.CACHE_FORMAT` 2+) is preferred wherever one is
    available; this is what `_row_badges` falls back to for a cache written
    before that field existed."""
    return config.registry_categories()


_KIND_BADGE_KEYS = {"skill": "badge_skill", "rule": "badge_rule",
                    "workflow": "badge_workflow"}


def _kind_theme_key(kind: str) -> str:
    return _KIND_BADGE_KEYS.get(kind, "badge_skill")


def _row_badges(e: dict, categories: dict):
    """Ordered (text, theme-key) badges for a browse row: kind, version, tap,
    and the item's category, when one is known. Most-important-first, so a
    narrow terminal drops from the tail without losing the essentials (kind
    and version survive; category goes first).

    The entry's own stamped `category` (`catalog.CACHE_FORMAT` 2+) is used
    first — it covers un-bundled taps too, which the old tap-level lookup
    never could. `categories` (`_tap_categories`) is the fallback for a cache
    written before that field existed, so an un-rescanned tap doesn't lose its
    badge outright."""
    badges = [(out.kind_label(e.get("kind", "skill")),
               _kind_theme_key(e.get("kind", "skill"))),
              ("v" + e["version"], "version"),
              ("[%s]" % e["tap"], "tap")]
    category = e.get("category") or categories.get(e["tap"])
    if category:
        badges.append(("[%s]" % category, "badge_category"))
    return badges


def _desc_key(e: dict):
    return (e.get("tap", ""), e["name"])


def _entry_source_path(e: dict):
    """On-disk path of the file backing a catalog entry, or None when its tap
    isn't cloned/known — used to fall back to a `boost explain`-style summary
    for entries whose frontmatter has no description."""
    try:
        tap = registry.get(e["tap"])
    except BoostError:
        return None
    path = tap.path / e.get("skill_md", "")
    return path if path.is_file() else None


def _lazy_description(e: dict) -> str:
    """A one-line fallback description for an entry with no frontmatter
    description — the `boost explain` idea, sized for a picker row. Meant to
    run off the UI thread since it may shell out to `claude`/the Anthropic API."""
    path = _entry_source_path(e)
    text = ""
    if path is not None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    if text and ai.available():
        reply = ai.ask(
            "In ONE short plain sentence (max 18 words, no markdown), describe "
            "what this %s named %r does, based on its file:\n\n%s"
            % (e.get("kind", "skill"), e["name"], text[:4000]),
            system="You summarize AI coding skills, rules, and workflows in "
                   "one plain sentence for a picker UI.",
            max_tokens=60)
        if reply:
            return reply.strip().splitlines()[0][:200]
    return "no description available"


# --- Aurora palette for the curses browser -----------------------------------
# The full-screen browser paints itself in the same Aurora tokens as the rest
# of the CLI. curses can't reuse the ANSI escapes from core.output, so these
# helpers translate the single-source palette (out.TOKENS) into curses colour
# pairs, degrading to the 8 base colours — then to monochrome — when a terminal
# (or the test fake) can't do better.

def _curses_rgb1000():
    """out.TOKENS scaled from 0..255 to curses' 0..1000 RGB range.

    Parity-locked to the web palette: whatever style/boost.css defines, the
    browser renders, so the TUI can never drift from the design system.
    """
    return {name: tuple(round(c / 255 * 1000) for c in rgb)
            for name, rgb in out.TOKENS.items()}


def _nearest_base(curses):
    """Each Aurora token mapped to its closest of the 8 base curses colours.

    Used when the terminal can't redefine colours (mirrors the 16-colour
    fallback in core.output._AURORA).
    """
    return {"cyan": curses.COLOR_CYAN, "violet": curses.COLOR_MAGENTA,
            "pink": curses.COLOR_MAGENTA, "green": curses.COLOR_GREEN,
            "yellow": curses.COLOR_YELLOW}


# Geometry that used to live here moved into core.browse, under the mutation
# gate; the thin aliases keep the draw code (and its pinned tests) reading the
# same while making "both panes share one implementation" provable by `is`.
_scrollbar = browse.scrollbar
_grad_segments = browse.rule_segments


def _aurora_pairs(curses):
    """Allocate Aurora curses colour pairs.

    Returns ``(pairs, custom)``: token-name -> attr int (0 if none), and
    whether true custom colours were achieved — the theme needs to know,
    because the gradient rule is only honest when its three stops are the
    real Aurora hues (on the 8/16-colour fallback violet and pink both map to
    magenta, and cyan/magenta/magenta reads as confetti, not a gradient).
    """
    names = ("cyan", "violet", "pink", "green", "yellow")
    try:
        custom = curses.can_change_color() and 16 + len(names) <= curses.COLORS
    except curses.error:
        custom = False
    fg = dict(_nearest_base(curses))
    if custom:
        rgb = _curses_rgb1000()
        for idx, nm in enumerate(names):
            slot = 16 + idx
            try:
                curses.init_color(slot, *rgb[nm])
                fg[nm] = slot
            except curses.error:
                pass
    fg["red"] = curses.COLOR_RED
    pairs = {}
    for i, nm in enumerate(("cyan", "violet", "pink", "green", "yellow", "red"),
                           start=1):
        try:
            curses.init_pair(i, fg[nm], -1)
            pairs[nm] = curses.color_pair(i)
        except curses.error:
            pairs[nm] = 0
    return pairs, custom


_NAME_X = 4  # column the name (and everything under it) starts at


def _browse_theme(curses):
    """Role -> curses attr for the browser, built grayscale-first.

    The browser used six hues at once — cyan kinds, violet taps, pink matches,
    yellow categories, green states — and read as confetti rather than as one
    surface. Refactoring UI's rule is the fix: hierarchy comes from weight, and
    colour is added last, for meaning only.

    So the tiers are BOLD / normal / DIM, and the palette is one accent plus two
    semantics that earn their place:

      accent (cyan)   focus, selection, section heads — the one brand colour
      ok (green)      installed; the only "this succeeded" signal
      warn (yellow)   curated star, and a failed install
      everything else BOLD for primary, plain for values, DIM for labels,
                      badges, descriptions and chrome

    Monochrome terminals keep the whole hierarchy, because the tiers are
    attributes rather than colours.
    """
    B, D, N, R = curses.A_BOLD, curses.A_DIM, curses.A_NORMAL, curses.A_REVERSE
    t = {
        # structural tiers
        "primary": B, "value": N, "muted": D,
        "accent": B, "accent_dim": N,
        "ok": B, "warn": N, "err": B,
        # chrome
        "border": D, "border_focus": B, "title": B, "help": D,
        "prompt": B, "query": B, "count": D,
        "row_sel": R, "scroll": D,
        # rows
        "name": B, "desc": D, "match": B, "star": N, "check": B, "state": N,
        "version": D, "tap": D,
        "badge_skill": D, "badge_rule": D, "badge_workflow": D,
        "badge_category": D,
        # detail pane
        "detail_name": B, "head": B, "field": N, "label": D,
        "busy": B, "failed": B,
        "dot_r": N, "dot_y": N, "dot_g": N,
        "rule": [D, D, D],
    }
    if not hasattr(curses, "start_color"):
        return t
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        return t
    p, custom = _aurora_pairs(curses)

    def P(nm, bold=False):
        a = p.get(nm, 0)
        return (a | curses.A_BOLD) if bold else a

    # Colour is layered ON the tiers, never instead of them: every role below
    # keeps the weight it had, so removing colour changes nothing structural.
    t.update({
        "accent": P("cyan", True), "accent_dim": P("cyan"),
        "ok": P("green", True), "warn": P("yellow"), "err": P("red", True),
        "title": P("cyan", True), "prompt": P("cyan", True),
        "border": P("cyan"), "border_focus": P("cyan", True),
        "row_sel": P("cyan", True) | curses.A_REVERSE,
        "scroll": P("cyan"),
        "match": P("cyan", True), "star": P("yellow"), "check": P("green", True),
        "state": P("green"), "detail_name": P("cyan", True),
        "head": P("cyan", True), "busy": P("cyan", True),
        "ok_line": P("green", True), "failed": P("yellow", True),
        "dot_r": P("red"), "dot_y": P("yellow"), "dot_g": P("green"),
        # The browser's one gradient moment: the top rule runs cyan → violet
        # → pink, but only when the terminal can render the real Aurora hues.
        # The 8/16-colour fallback keeps a single-hue rule (mirroring
        # out.gradient's basic-level behaviour) rather than the cyan/magenta/
        # magenta confetti the base palette would produce.
        "rule": ([P("cyan"), P("violet"), P("pink")] if custom
                 else [P("cyan")] * 3),
    })
    return t


def _browse_tui(curses, entries, install=None):
    """Run the curses UI. Returns the list of entries picked for install
    (one or more, via multi-select), or None if the user quit without picking.

    Layout is a single framed surface: title bar, query, scope radios, then a
    list pane and a detail pane divided by a rule. All of the geometry and all
    of the matching come from :mod:`core.browse`, which is where they can be
    tested — this function only draws and dispatches keys.
    """
    state: dict[str, Any] = {"picks": None}
    categories = _tap_categories()
    desc_cache: dict = {}
    loading: set = set()
    installed_names = set(store.installed())
    do_install = install or store.install
    # Collapse rows that say the same thing. A registry renders one skill into
    # .claude/, .cursor/, .gemini/ and a plugin root, so 37% of a real 60,047
    # entry catalogue is a duplicate of another row. Kept as (entry, copies) so
    # the count can be shown — hiding rows silently is worse than showing them.
    deduped = browse.dedupe(entries)
    copies = {id(e): n for e, n in deduped}
    unique_entries = [e for e, _n in deduped]
    hidden = len(entries) - len(unique_entries)
    # name -> (state, message). Item 1: an install runs without leaving the
    # browser, and the detail pane reports it. Threaded so the draw loop keeps
    # answering keys while files are written — an install that freezes the UI
    # reads as a crash.
    status: dict[str, tuple[str, str]] = {}
    done: list = []
    workers: list = []
    queue: list = []
    queue_lock = threading.Lock()
    # What Enter will touch, by kind — stated in the detail pane before it is
    # pressed (a rule edits a file the user reads every session, which is the
    # highest-stakes of the three). Built once: the paths cannot change
    # mid-session, and browse.install_target stays pure by receiving them.
    link_names = ", ".join(agents.display_name(a)
                           for a in agents.linking_agents()) or "no agents"
    context_files = " · ".join(sorted(
        _tilde(d / rules.CONTEXT_FILES[a][0])
        for a, d in agents.enabled_agents().items()
        if a in rules.CONTEXT_FILES))
    targets = {
        "skill": "%s · linked to %s" % (_tilde(paths.store_dir()), link_names),
        "rule": context_files or "each agent's rules directory",
        "workflow": "each agent's commands dir (TOML for gemini)",
    }

    def start_install(entry):
        """Queue an install. Installs run one at a time, in a single worker.

        Serial on purpose. Running them in parallel threads was a lost update:
        every `store.install` does a read-modify-write of `.skill-lock.json`, so
        two at once raced and one entry vanished from the lock — a Tab-select of
        two skills installed both to disk and recorded one. It showed up as a
        test that passed alone and failed 3 runs in 5 in the suite.

        One background worker still keeps the draw loop answering keys, which is
        the property that actually mattered.
        """
        name = entry["name"]
        with queue_lock:
            if status.get(name, ("", ""))[0] in (browse.BUSY, browse.OK):
                return
            status[name] = (browse.BUSY, "")
            queue.append(entry)
            if any(t.is_alive() for t in workers):
                return                                  # a worker is draining

        def worker():
            while True:
                with queue_lock:
                    if not queue:
                        return
                    item = queue.pop(0)
                nm = item["name"]
                try:
                    res = do_install(item)
                except BoostError as e:
                    status[nm] = (browse.FAILED, e.message)
                except Exception as e:                  # never kill the TUI
                    status[nm] = (browse.FAILED, str(e))
                else:
                    installed_names.add(nm)
                    done.append(item)
                    status[nm] = (browse.OK, _tilde(getattr(res, "dest", "")))

        t = threading.Thread(target=worker, daemon=True)
        workers.append(t)
        t.start()

    def describe(e):
        """Description text for a row, kicking off a background lazy-load
        (the `boost explain` fallback) the first time an entry with no
        frontmatter description is shown — never blocks the draw loop."""
        if e.get("description"):
            return e["description"]
        key = _desc_key(e)
        if key in desc_cache:
            return desc_cache[key]
        if key not in loading:
            loading.add(key)

            def worker(entry=e, cache_key=key):
                desc_cache[cache_key] = _lazy_description(entry)
                loading.discard(cache_key)

            threading.Thread(target=worker, daemon=True).start()
        return "loading description…"

    def ui(scr):
        with contextlib.suppress(curses.error):
            curses.curs_set(0)
        scr.timeout(80)  # short poll so a finished lazy-load redraws promptly
        th = _browse_theme(curses)

        def put(y, x, s, attr=0):  # clip-safe cell writer
            # `x < _w`, not `_w - 1`: the right-hand border lives in the last
            # column, and the old bound made it unwritable — the frame drew
            # with three sides. Writing the very last cell can make curses
            # scroll, which is what the suppressed error covers.
            if 0 <= y < _h and 0 <= x < _w and s:
                with contextlib.suppress(curses.error):
                    scr.addnstr(y, x, s, _w - x, attr)

        filt, sel, detail = "", 0, True
        focus, scope, dscroll = "list", browse.SCOPES[0], 0
        collapse = True
        selected: set = set()
        # One haystack per entry per scope, built on first use and reused for
        # every keystroke: re-deriving it inside the filter cost 125 ms per key
        # over 71,700 entries, which is slower than the draw poll.
        index: dict = {}
        while True:
            _h, _w = scr.getmaxyx()
            pool = unique_entries if collapse else entries
            key = (scope, collapse)
            if key not in index:
                index[key] = browse.index_entries(pool, scope)
            found = browse.matches_indexed(index[key], filt)
            sel = max(0, min(sel, len(found) - 1))
            lay = browse.layout(_w, _h, detail=detail)
            try:
                scr.erase()
                # status.copy(): the worker thread owns the mapping; a shallow
                # copy keeps the fold safe from a mid-iteration mutation.
                _draw_frame(put, th, lay, focus,
                            browse.session_summary(status.copy()))
                _draw_query(put, th, lay, filt, focus, len(found), len(pool),
                            len(selected), hidden if collapse else 0)
                _draw_scopes(put, th, lay, scope, focus)
                rows = _draw_rows(put, th, lay, found, sel, selected, filt,
                                  focus, describe, categories, installed_names,
                                  copies if collapse else None, status,
                                  scope, hidden if collapse else 0)
                if lay.has_detail and found:
                    dscroll = _draw_detail(
                        put, th, lay, found[sel], dscroll, focus,
                        installed_names, status,
                        browse.install_target(found[sel], targets))
                scr.refresh()
            except curses.error:
                pass  # terminal too small mid-draw; retry on next key
                rows = 1
            key = scr.getch()
            if key == -1:                                 # poll tick, no key
                continue
            if key == 9 and found:                        # TAB: multi-select
                selected.symmetric_difference_update({_desc_key(found[sel])})
                continue
            if key == 27:                                 # ESC: quit
                return
            if key in (10, 13, curses.KEY_ENTER) and found:
                # Enter confirms, the way every other picker does. `i` used to
                # install and `q` used to quit; both are printable, and once
                # space types into the query every printable key has to.
                #
                # It installs in place rather than exiting: the browser is for
                # finding several things, and dropping to a shell after the
                # first one makes the user re-run and re-type to get the next.
                for e in ([e for e in entries if _desc_key(e) in selected]
                          if selected else [found[sel]]):
                    start_install(e)
                selected.clear()
                continue
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT) and \
                    browse.scope_step(focus, "left" if key == curses.KEY_LEFT
                                      else "right"):
                # Item 2: on the toggle row the horizontal arrows pick a scope.
                scope = browse.next_scope(
                    scope, browse.scope_step(
                        focus, "left" if key == curses.KEY_LEFT else "right"))
                sel, dscroll = 0, 0
                continue
            if key == curses.KEY_UP:
                focus, sel = browse.move_focus(focus, "up", sel, len(found),
                                               lay.has_detail)
                if focus == "detail":
                    dscroll -= 1
            elif key == curses.KEY_DOWN:
                focus, sel = browse.move_focus(focus, "down", sel, len(found),
                                               lay.has_detail)
                if focus == "detail":
                    dscroll += 1
            elif key == curses.KEY_RIGHT:
                focus, sel = browse.move_focus(focus, "right", sel, len(found),
                                               lay.has_detail)
            elif key == curses.KEY_LEFT:
                focus, sel = browse.move_focus(focus, "left", sel, len(found),
                                               lay.has_detail)
            elif key == curses.KEY_NPAGE:
                sel = min(sel + max(1, rows), max(0, len(found) - 1))
            elif key == curses.KEY_PPAGE:
                sel = max(0, sel - max(1, rows))
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                filt, sel, dscroll = filt[:-1], 0, 0
            elif key == 20:                               # ^T: cycle scope
                scope, sel = browse.next_scope(scope), 0
            elif key == 4:                                # ^D: show duplicates
                collapse, sel, dscroll = not collapse, 0, 0
            elif 32 <= key <= 126:
                # 32 is SPACE, and it belongs to the query: the range used to
                # start at 33 with space bound to select, so two words could
                # never be searched for at once. Selection moved to TAB.
                filt, sel, dscroll = filt + chr(key), 0, 0
                focus = "search" if focus == "search" else focus

    curses.wrapper(ui)  # wrapper guards drawing with try/finally endwin()
    # Join before returning. The workers are daemons so the draw loop can exit
    # promptly, but a daemon dies with the process — quitting right after Enter
    # would abandon an install mid-write. `store.install` stages atomically, so
    # the store survives either way; what would not survive is the user's
    # belief that it finished.
    for t in workers:
        t.join(timeout=60)
    # Installs already happened in-loop; hand back what landed so the caller
    # can print a summary rather than repeating the work.
    return done or state["picks"]


def _draw_frame(put, th, lay, focus, summary=None):
    """Outer box, column divider, and the title sitting in the top rule.

    ``summary`` is the session's install chip from
    :func:`browse.session_summary` — set into the bottom rule when present,
    so what happened this session is visible even with the detail pane
    closed or parked elsewhere.
    """
    w, h = lay.w, lay.h
    if w < 4 or h < 6:
        return
    inner = w - 2
    put(0, 0, "╭" + "─" * inner + "╮", th["border"])
    # Dots grouped rather than dash-separated: spaced out they read as part of
    # the rule instead of as a cluster of window controls.
    put(0, 2, " ", th["border"])
    put(0, 3, "●", th["dot_r"])
    put(0, 4, "●", th["dot_y"])
    put(0, 5, "●", th["dot_g"])
    title = "  boost browse  "
    put(0, 6, title, th["title"])
    # The one gradient moment: the rest of the top rule runs cyan → violet →
    # pink (glyphs unchanged — repainted in place, so monochrome loses
    # nothing). The theme decides whether the stops are real Aurora hues or
    # collapse to a single accent; see _browse_theme.
    grad_x = 6 + len(title)
    # Tolerate a theme without the stop list (the draw loop never raises on a
    # frame): anything short falls back to the plain border attr.
    stops = th["rule"] if isinstance(th["rule"], (list, tuple)) else ()
    for i, (start, length) in enumerate(browse.rule_segments(
            max(0, w - 1 - grad_x))):
        put(0, grad_x + start, "─" * length,
            stops[i] if i < len(stops) else th["border"])
    # Item 1: the focused pane is obvious. Its border brightens and it gets a
    # caption in the divider — a scrollable pane with no focus affordance is a
    # pane the user cannot tell they are driving.
    list_edge = th["border_focus"] if focus in ("list", "search", "scopes") \
        else th["border"]
    detail_edge = th["border_focus"] if focus == "detail" else th["border"]
    for y in range(1, h - 1):
        put(y, 0, "│", list_edge if y >= lay.body_y else th["border"])
        put(y, w - 1, "│",
            detail_edge if lay.has_detail and y >= lay.body_y else th["border"])
    # rule between the chrome and the body, tee'd where the divider lands
    sep = lay.body_y - 1
    put(sep, 0, "├" + "─" * inner + "┤", th["border"])
    if lay.has_detail:
        put(sep, lay.detail_x - 1, "┬", th["border"])
        for y in range(lay.body_y, h - 1):
            put(y, lay.detail_x - 1, "│", detail_edge)
        cap = " details " if focus != "detail" else " details · ↑↓ scroll "
        if lay.detail_w > len(cap) + 2:
            put(sep, lay.detail_x + 1, cap,
                th["accent"] if focus == "detail" else th["muted"])
    put(h - 1, 0, "╰" + "─" * inner + "╯", th["border"])
    if lay.has_detail:
        put(h - 1, lay.detail_x - 1, "┴", th["border"])
    if summary:
        # Clipped to end before the divider tee (or the corner), so the frame
        # glyphs survive any message length. Absent, the idle rule is
        # byte-identical to a summary-less frame.
        role, text = summary
        boundary = lay.detail_x - 1 if lay.has_detail else w - 1
        room = boundary - 3
        if room > 4:
            put(h - 1, 2, (" " + text + " ")[:room],
                th.get(role) or th.get("ok") or 0)
    # The hint used to live in the bottom rule, where the column divider's
    # tee landed on top of it and turned "esc quit" into "┴sc quit". It has
    # its own row now, above the rule that separates chrome from body.
    # Two hints, not one truncated: clipping the long one mid-word ends the
    # line on "esc", which reads as a key rather than as a cut-off phrase.
    hint = ("↑↓ move  ⇥ select  → detail  ^T scope  ^D dupes  "
            "↵ install  esc quit")
    if len(hint) > inner - 2:
        hint = "↑↓ move  ⇥ select  ↵ install  esc quit"
    if len(hint) > inner - 2:
        hint = "↑↓  ⇥ sel  ↵ add  esc"
    put(lay.body_y - 2, 2, hint[:max(0, inner - 2)], th["help"])


def _draw_query(put, th, lay, filt, focus, n_found, n_all, n_sel, hidden=0):
    """The query row: chevron, text, cursor when focused, right-aligned count.

    ``hidden`` is stated, never implied: a browser that quietly drops a third of
    the catalogue and shows a smaller total is indistinguishable from one with a
    broken filter.
    """
    active = focus == "search"
    put(1, 2, "❯", th["prompt"] if active else th["border"])
    put(1, 4, filt or "type to filter…",
        th["query"] if filt else th["help"])
    if active:
        put(1, 4 + len(filt), "▏", th["prompt"])
    tail = browse.count_tail(n_found, n_all, n_sel, hidden)
    put(1, max(4 + len(filt) + 2, lay.w - 2 - len(tail)), tail, th["count"])


def _draw_scopes(put, th, lay, scope, focus):
    """Radio row — which field the query is matched against.

    Item 2: reachable by arrow. When the row holds focus it says so and shows
    that left/right pick, rather than leaving ^T as the only way in.
    """
    active = focus == "scopes"
    x = 2
    put(2, x, "match", th["accent"] if active else th["help"])
    x += 6
    for name in browse.SCOPES:
        on = name == scope
        if on:
            mark, attr = "(●)", th["accent"]
        else:
            mark, attr = "( )", th["muted"]
        put(2, x, mark, attr)
        label = browse.scope_label(name)
        # The active toggle is underlined while the row is focused, so "which
        # one is selected" and "which pane am I in" stay separate signals.
        put(2, x + 4, label, attr | (4 if active and on else 0))
        x += 5 + len(label)
        if x > lay.w - 6:
            break
    if active and x + 12 < lay.w - 2:
        put(2, x + 1, "← → pick", th["help"])


def _draw_rows(put, th, lay, found, sel, selected, filt, focus,
               describe, categories, installed_names, copies=None,
               status=None, scope="all", hidden=0):
    """The result list. Returns how many rows fit, for page-up/down."""
    rows = max(1, lay.body_h // 2)
    lw = lay.list_w
    if not found:
        # A silent void is indistinguishable from a hung draw; the pane says
        # what happened and which keys widen the net (see browse.empty_lines).
        for i, (role, text) in enumerate(browse.empty_lines(filt, scope,
                                                            hidden)):
            y = lay.body_y + 1 + i
            if y >= lay.h - 1:
                break
            put(y, lay.list_x + 2, text[:max(0, lw - 4)], th[role])
        return rows
    top = max(0, min(sel - rows + 1, max(0, len(found) - rows)))
    if sel < top:
        top = sel
    view = found[top:top + rows]
    has_bar = len(found) > rows
    # The rail keeps a one-column gutter to the pane edge, plus the scrollbar
    # column when the list overflows.
    railw = lw - (2 if has_bar else 1)
    for i, e in enumerate(view):
        y = lay.body_y + i * 2
        if y + 1 >= lay.h - 1:
            break
        chosen = top + i == sel
        # Item 5: the whole row highlights, not just its marker. Painting the
        # full span first means the badges and description inherit it too.
        row_attr = th["row_sel"] if chosen else 0
        if chosen:
            put(y, lay.list_x, " " * lw, row_attr)
            put(y + 1, lay.list_x, " " * lw, row_attr)
        x = lay.list_x + 1
        put(y, x, "✓" if _desc_key(e) in selected else " ",
            row_attr or th["check"])
        put(y, x + 1, "★" if e.get("curated") else " ", row_attr or th["star"])
        # The third mark carries the whole install lifecycle (◐ / ✗ / ●),
        # from the same glyph table the detail pane reports with.
        st = (status or {}).get(e["name"], (None, ""))[0]
        glyph, role = browse.state_glyph(st, e["name"] in installed_names)
        put(y, x + 2, glyph, row_attr or th[role])
        nx = x + 4
        namew = max(4, min(len(e["name"]), lw - 6))
        nm = out.truncate(e["name"], namew)
        put(y, nx, nm, row_attr or th["name"])
        if not chosen:
            for pos in browse.highlight_positions(filt, nm):
                if pos < len(nm):
                    put(y, nx + pos, nm[pos], th["match"])
        # The badge rail right-aligns to the pane edge so kind/version/tap
        # stop wandering with every name length. A collapsed row's ×N count
        # leads the rail and is the last badge to drop — copies are accounted
        # for, never disappeared.
        rail = []
        n_copies = (copies or {}).get(id(e), 1)
        if n_copies > 1:
            rail.append(("×%d" % n_copies, "accent_dim"))
        rail += _row_badges(e, categories)
        name_end = (nx - lay.list_x) + len(nm) + 2
        for bx, text, tkey in browse.badge_positions(name_end, rail, railw):
            put(y, lay.list_x + bx, text, row_attr or th[tkey])
        put(y + 1, nx, out.truncate(describe(e),
                                    max(4, lw - (7 if has_bar else 6))),
            row_attr or th["desc"])
    if has_bar:
        # The detail pane always had one; a 70,000-row list deserves to know
        # where it is too. Same track/thumb vocabulary as the detail edge.
        bar = browse.scrollbar(len(found), rows, top)
        if bar:
            bstart, blen = bar
            attr = th["border_focus"] if focus == "list" else th["border"]
            bx = lay.list_x + lw - 1
            for j in range(rows):
                thumb = bstart <= j < bstart + blen
                for dy in (0, 1):
                    y = lay.body_y + j * 2 + dy
                    if y >= lay.h - 1:
                        break
                    put(y, bx, "█" if thumb else "│", attr)
    return rows


def _draw_detail(put, th, lay, entry, dscroll, focus, installed_names,
                 status=None, install_to=None):
    """The right-hand panel. Returns the clamped scroll offset."""
    st, msg = (status or {}).get(entry["name"], (None, ""))
    # -3, not -2: one column of left padding, and one on the right reserved for
    # the scrollbar. At -2 a wrapped sentence ran into the thumb.
    lines = browse.detail_lines(entry, width=max(8, lay.detail_w - 3),
                               installed=entry["name"] in installed_names,
                               state=st, message=msg, install_to=install_to)
    visible = max(0, lay.body_h)
    dscroll = browse.clamp_scroll(dscroll, len(lines), visible)
    active = focus == "detail"
    for i, (role, text) in enumerate(lines[dscroll:dscroll + visible]):
        y = lay.body_y + i
        if y >= lay.h - 1:
            break
        if role == "rule":
            put(y, lay.detail_x, "─" * max(0, lay.detail_w), th["border"])
            continue
        attr = {"title": th["detail_name"], "head": th["head"],
                "desc": th["value"], "state": th["state"],
                "ok": th.get("ok_line", th["ok"]), "busy": th["busy"],
                "failed": th["failed"], "muted": th["muted"],
                "field": th["field"]}.get(role, th["field"])
        put(y, lay.detail_x + 1, text, attr)
    if len(lines) > visible and visible > 0:
        bar = _scrollbar(len(lines), visible, dscroll)
        if bar:
            bstart, blen = bar
            for i in range(visible):
                y = lay.body_y + i
                if y >= lay.h - 1:
                    break
                thumb = bstart <= i < bstart + blen
                put(y, lay.detail_x + lay.detail_w - 1,
                    "█" if thumb else "│",
                    th["border_focus"] if active else th["border"])
    return dscroll


def cmd_browse(argv):
    """Full-screen fuzzy browser over every catalog entry."""
    p = cliparse.parser(
        prog="boost browse",
        description="Interactive full-screen TUI with fuzzy search")
    p.add_argument("--category", default="",
                   help="only browse entries whose category matches (case-insensitive)")
    args = p.parse_args(argv)
    entries = sorted(catalog.all_entries(), key=operator.itemgetter("name"))
    if args.category:
        entries = catalog.filter_by_category(entries, args.category)
        if not entries:
            raise BoostError("no entries in category %r" % args.category,
                            hint="try `boost browse` with no --category to see them all")
    elif not entries:
        raise BoostError("no skills available to browse",
                        hint="add registries with `boost tap --defaults`")
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _browse_plain(entries, "interactive mode needs a TTY")
    try:
        import curses
    except ImportError:
        return _browse_plain(entries, "curses is unavailable on this Python")
    picked = _browse_tui(curses, entries)
    if not picked:
        return 0
    # The browser installs in place now, so anything it hands back is usually
    # already on disk. Install only what still needs it — that keeps this path
    # correct whether the TUI did the work or merely picked.
    settled = set(store.installed())
    staged = [e for e in picked if e["name"] in settled]
    for entry in staged:
        out.ok("installed %s v%s" % (entry["name"], entry.get("version", "?")))
    for entry in [e for e in picked if e["name"] not in settled]:
        try:
            res = store.install(entry)
        except BoostError as e:
            # browse lists every catalog kind (skills, rules, workflows), but
            # only skills install; a rule/workflow pick — or an already-
            # installed/pinned skill — must not abort the rest of the batch.
            out.warn(e.message)
            if e.hint:
                out.info(out.c(e.hint, out.DIM))
            continue
        out.ok("installed %s v%s → %s"
               % (entry["name"], entry["version"], _tilde(res.dest)))
        if res.linked:
            out.info("linked into: "
                     + ", ".join(agents.display_name(a) for a in res.linked))
        for conflict in res.conflicts:
            out.warn("conflict: %s exists and is not a symlink" % _tilde(conflict))
    return 0


def cmd_trending(argv):
    """Rank skills by local install events from the journal."""
    p = cliparse.parser(
        prog="boost trending",
        description="Show trending skills by install count")
    p.add_argument("--limit", type=util.positive_int, default=10,
                   help="max rows (default 10)")
    args = p.parse_args(argv)
    evs = journal.events(action="install")
    by_name = {e["name"]: e for e in catalog.all_entries()}
    if not evs:
        out.heading("curated picks (no local install data yet)")
        curated = [e for e in by_name.values() if e.get("curated")]
        if not curated:
            out.info("no curated skills available — add taps with `boost tap --defaults`")
            return 0
        descw = max(out.term_width() - 24, 24)  # reserve name + version columns
        out.table([(e["name"], "v" + e["version"],
                    out.truncate(e["description"], descw))
                   for e in sorted(curated, key=operator.itemgetter("name"))[:args.limit]])
        return 0
    agg: dict[str, Any] = {}
    for ev in evs:  # most-recent-first, so first ts per subject is the latest
        name = ev.get("subject") or "?"
        rec = agg.setdefault(name, {"count": 0, "last": ev.get("ts", "")})
        rec["count"] += 1
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    descw = max(out.term_width() - 44, 24)  # reserve name/installs/last columns
    out.table([(name, str(rec["count"]), util.rel_time(rec["last"]),
                out.truncate(by_name.get(name, {}).get("description", ""), descw))
               for name, rec in ranked[:args.limit]],
              headers=("name", "installs", "last", "description"))
    out.info(out.role("based on local install activity", "muted"))
    return 0


def cmd_stats(argv):
    """Lock-file, journal, and upstream stats for one skill."""
    p = cliparse.parser(
        prog="boost stats",
        description="Install statistics & trend for a single skill")
    p.add_argument("name", help="skill name")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    name = args.name
    # find_any: a rule's lock facts are the answer, not "no skill named X".
    found = lockfile.find_any(name)
    kind, lock = found if found is not None else ("skill", None)
    matches = catalog.find(name)
    cat = matches[0] if matches else None
    if not lock and not cat:
        raise BoostError("no skill named %r installed or in any tap" % name,
                        hint="try `boost search %s`" % name)
    acts = {a: len(journal.events(action=a, subject=name))
            for a in ("install", "update", "uninstall")}
    if lock is not None and kind != "skill":
        # Materialized kinds have no store dir or agent symlinks; the lock
        # facts and journal activity are their whole stats surface.
        if args.as_json:
            print(json.dumps({"name": name, "kind": kind, "installed": True,
                              "lock": lock, "activity": acts}))
            return 0
        out.heading("%s (%s)" % (name, kind))
        out.kv("version", lock.get("version", "?"))
        out.kv("tap", lock.get("tap", "?"))
        out.kv("installed", util.rel_time(lock.get("installed_at", "")))
        out.kv("updated", util.rel_time(lock.get("updated_at", "")))
        out.kv("agents", ", ".join(sorted(
            {m.get("agent", "?") for m in lock.get("materializations") or []}))
            or "none")
        out.kv("pinned", "yes" if lock.get("pinned") else "no")
        if lock.get("quarantined"):
            out.kv("quarantined", "yes")
        out.kv("sha256", str(lock.get("sha256", ""))[:12])
        out.kv("activity", "%d installs · %d updates · %d uninstalls"
               % (acts["install"], acts["update"], acts["uninstall"]))
        return 0
    latest = cat["version"] if cat else None
    upstream = None
    if cat:
        with contextlib.suppress(BoostError):
            tap = registry.get(cat["tap"])
            if tap.is_cloned:
                lines = gitutil.log_for_path(tap.path, cat["rel_dir"], n=1)
                upstream = lines[0] if lines else None
    sdir = store.skill_store_dir(name)
    size = util.dir_size(sdir) if lock and sdir.is_dir() else None
    if args.as_json:
        print(json.dumps({
            "name": name, "installed": bool(lock), "lock": lock, "size": size,
            "activity": acts,
            "catalog": ({"latest": latest, "tap": cat["tap"],
                         "description": cat["description"],
                         "upstream": upstream} if cat else None)}))
        return 0
    out.heading(name)
    if lock:
        out.kv("version", lock.get("version", "?"))
        out.kv("tap", lock.get("tap", "?"))
        out.kv("installed", util.rel_time(lock.get("installed_at", "")))
        out.kv("updated", util.rel_time(lock.get("updated_at", "")))
        out.kv("agents", ", ".join(lock.get("agents") or []) or "none")
        out.kv("pinned", "yes" if lock.get("pinned") else "no")
        out.kv("sha256", str(lock.get("sha256", ""))[:12])
        if size is not None:
            out.kv("size", util.human_size(size))
    elif cat:   # no lock means the guard above found a catalog entry
        out.kv("version", cat["version"])
        out.kv("tap", cat["tap"])
        out.kv("description", cat["description"])
        out.info(out.role("not installed — `boost install %s`" % name, "muted"))
    out.kv("activity", "%d installs · %d updates · %d uninstalls"
           % (acts["install"], acts["update"], acts["uninstall"]))
    if lock and latest:
        if util.semver_gt(latest, lock.get("version", "0")):
            out.kv("latest", "%s %s" % (latest, out.role("(update available)", "warn")))
        else:
            out.kv("latest", "%s %s" % (latest, out.role("(up to date)", "muted")))
    if upstream:
        out.kv("upstream", upstream, wrap=True)
    return 0


def cmd_count(argv):
    """One-line inventory: installed / available / taps / discovery index."""
    p = cliparse.parser(
        prog="boost count",
        description="Quick summary of installed / available / taps")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    by_kind = {kind: len(section)
               for kind, section in lockfile.all_installed().items()}
    installed_n = sum(by_kind.values())
    taps_n = len(registry.list_taps())
    available_n = len(catalog.all_entries())
    discovery = None
    dpath = _discovery_path()
    if dpath.exists():
        try:
            discovery = len(json.loads(dpath.read_text(encoding="utf-8")).get("items") or [])
        except (json.JSONDecodeError, OSError):
            discovery = None
    if args.as_json:
        print(json.dumps({"installed": installed_n,
                          "skills": by_kind["skill"], "rules": by_kind["rule"],
                          "workflows": by_kind["workflow"],
                          "available": available_n,
                          "taps": taps_n, "discovery": discovery}))
        return 0
    # The breakdown appears exactly when it carries information: with only
    # skills installed, "installed 2" already means two skills.
    detail = ("" if not (by_kind["rule"] or by_kind["workflow"])
              else " (%d skill%s · %d rule%s · %d workflow%s)"
              % (by_kind["skill"], _s(by_kind["skill"]),
                 by_kind["rule"], _s(by_kind["rule"]),
                 by_kind["workflow"], _s(by_kind["workflow"])))
    summary = ("installed %d%s · available %d (across %d tap%s) · discovery index %s"
               % (installed_n, detail, available_n, taps_n,
                  "" if taps_n == 1 else "s",
                  discovery if discovery is not None else "not built"))
    print(out.panel(summary, title="inventory"))
    return 0
