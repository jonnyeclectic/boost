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
import textwrap
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from .. import cliparse, spin
from ..core import (
    agents,
    ai,
    catalog,
    config,
    gitutil,
    journal,
    lockfile,
    paths,
    rag,
    registry,
    store,
    util,
)
from ..core import output as out
from ..core.stackprobe import detect_stack  # re-exported: shared with Quality
from ..errors import BoostError

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
    p.add_argument("--limit", type=util.positive_int, default=15,
                   help="max results (default 15)")
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
        hits, engine = rag.retrieve_any(query, k=max(60, args.limit * 4))
        scored = [(h["entry"], h["score"]) for h in (hits or [])]
    else:
        scored = catalog.search(query)
    if args.as_json:
        print(json.dumps([e | {"score": s} for e, s in scored[:args.limit]]))
        return 0
    if not scored:
        out.info("no matches for %r" % query)
        out.info(out.role("try `boost discover %s` to search all of GitHub" % query, "muted"))
        _hint_semantic_search(engine)
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
            out.warn(ai.fallback_note())
    shown = scored[:args.limit]
    # Cap the name column so one long name can't pad every row, and clip each
    # description to the remaining terminal width so results stay one line each.
    name_w = min(max(len(e["name"]) for e, _ in shown), 32)
    top = max((s for _e, s in shown), default=0) or 1
    cols = out.term_width()
    for e, sc in shown:
        # A relevance meter makes the ranking visible; tint it by magnitude.
        frac = sc / top
        hue = "cyan" if frac >= 0.66 else "violet" if frac >= 0.33 else "pink"
        bar = out.aurora(out.meter(frac), hue)
        tag = "  " + out.role("★ curated", "warn") if e.get("curated") else ""
        tag_w = len("  ★ curated") if e.get("curated") else 0
        desc_w = max(cols - 2 - 5 - name_w - 2 - tag_w, 8)  # 5 = meter + space
        name_cell = out.role(out.truncate(e["name"], name_w).ljust(name_w), "accent")
        out.info(bar + " " + name_cell + "  "
                 + out.truncate(e["description"] or "", desc_w) + tag)
    out.info(out.role("%d match%s · ranked by %s"
                   % (len(scored), "" if len(scored) == 1 else "es", ranker), "muted"))
    _hint_semantic_search(engine)
    return 0


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
    for line in textwrap.wrap(msg, max(out.term_width(), 20),
                              break_long_words=False, break_on_hyphens=False):
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
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    if args.export_shard or args.import_shard:
        return _shard_io(args)
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
        with spin.Spinner("embedding chunks into the dense store"):
            dense_stats = _reindex_dense(args.force)
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
            out.warn("dense index skipped — %s" % embed.fallback_note())
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
                out.ok("embedded %d passages (%s) into the dense vector store"
                       % (dense_stats["chunks"], dense_stats["provider"]))
    journal.log("reindex", "%d passages" % stats["docs"],
                entries=stats["entries"])
    return 0


def _reindex_dense(force):
    """Build the dense vector store; returns stats or None when unavailable."""
    # Local import: the dense/embedding engines are opt-in (`search --dense`),
    # so they stay out of startup for every other command in this module.
    from ..core import dense, embed
    if not dense.have_backend() or not embed.available():
        return None
    return dense.build(force=force)


def cmd_index(argv):
    """Build ~/.boost/cache/discovery.json via `gh api` code search."""
    p = cliparse.parser(
        prog="boost index",
        description="Build the discovery registry via GitHub Code Search")
    p.add_argument("--limit", type=util.positive_int, default=300,
                   help="max skill files to index (default 300)")
    args = p.parse_args(argv)
    if not shutil.which("gh"):
        raise BoostError("the GitHub CLI (gh) is required to build the index",
                        hint="brew install gh && gh auth login")
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
                 "search/code?q=filename:SKILL.md&per_page=100&page=%d" % page],
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
        {"generated": util.now_iso(), "github_total": total, "items": items},
        indent=1), encoding="utf-8")
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


def cmd_discover(argv):
    """Browse/filter the GitHub-wide index built by `boost index`."""
    p = cliparse.parser(
        prog="boost discover",
        description="Browse & search the GitHub-wide skill discovery index")
    p.add_argument("query", nargs="*", help="filter terms (repo/path substring)")
    p.add_argument("--limit", type=util.positive_int, default=25,
                   help="max rows (default 25)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
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
        print(json.dumps(shown))
        return 0
    if not shown:
        out.info("no indexed skills match %r" % " ".join(args.query))
        out.info(out.role("the index holds %d entries — rebuild with `boost index`"
                       % len(all_items), "muted"))
        return 0
    out.table([(it.get("repo", "?"), it.get("path", ""),
                out.role(it.get("url", ""), "muted")) for it in shown],
              headers=("repo", "path", "url"))
    out.info(out.role("%d of %d indexed skills · GitHub reports ~%d total"
                   % (len(shown), len(all_items),
                      int(data.get("github_total") or 0)), "muted"))
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
    p.add_argument("--limit", type=util.positive_int, default=8,
                   help="max suggestions (default 8)")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output")
    args = p.parse_args(argv)
    target = paths.expand(args.path).resolve()
    if not target.is_dir():
        raise BoostError("no such directory: %s" % args.path)
    entries = catalog.all_entries()
    if not entries:
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


def _subseq(needle: str, hay: str) -> bool:
    """True when needle is a subsequence of hay (fuzzy filter)."""
    it = iter(hay)
    return all(ch in it for ch in needle)


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
    catalog (data/registries.json) — the only place "category" lives; catalog
    entries themselves carry no category, only their tap does."""
    return {e["name"]: e["category"] for e in config.load_registry_catalog()
            if e.get("category")}


_KIND_BADGE_KEYS = {"skill": "badge_skill", "rule": "badge_rule",
                    "workflow": "badge_workflow"}


def _kind_theme_key(kind: str) -> str:
    return _KIND_BADGE_KEYS.get(kind, "badge_skill")


def _row_badges(e: dict, categories: dict):
    """Ordered (text, theme-key) badges for a browse row: kind, version, tap,
    and — when the tap is one of the curated registries — its category.
    Most-important-first, so a narrow terminal drops from the tail without
    losing the essentials (kind and version survive; category goes first)."""
    badges = [("[%s]" % e.get("kind", "skill"),
               _kind_theme_key(e.get("kind", "skill"))),
              ("v" + e["version"], "version"),
              ("[%s]" % e["tap"], "tap")]
    category = categories.get(e["tap"])
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


def _match_positions(needle, hay):
    """Indices in hay consumed by a left-to-right subsequence match of needle.

    Drives fuzzy-match highlighting; returns [] when needle isn't a
    subsequence of hay (so nothing is highlighted).
    """
    positions, i = [], 0
    for j, ch in enumerate(hay):
        if i < len(needle) and ch == needle[i]:
            positions.append(j)
            i += 1
    return positions if i == len(needle) else []


def _scrollbar(total, rows, top):
    """(thumb_start, thumb_len) for a rows-tall scrollbar; None when all fits."""
    if rows <= 0 or total <= rows:
        return None
    thumb = max(1, rows * rows // total)
    max_top = total - rows
    start = round((rows - thumb) * top / max_top) if max_top else 0
    return (start, thumb)


def _grad_segments(width, n=3):
    """Split a width-wide rule into n near-equal [(start, length)] runs.

    Lets the browser paint a cyan -> violet -> pink gradient bar the same way
    out.gradient() lerps the wordmark.
    """
    if width <= 0:
        return []
    n = min(n, width)
    base, extra = divmod(width, n)
    segs, pos = [], 0
    for k in range(n):
        length = base + (1 if k < extra else 0)
        segs.append((pos, length))
        pos += length
    return segs


def _aurora_pairs(curses):
    """Allocate Aurora curses colour pairs; token-name -> attr int (0 if none)."""
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
    return pairs


def _aurora_theme(curses):
    """role -> curses attr. Monochrome baseline, upgraded to Aurora where able."""
    t = {"title": curses.A_BOLD, "prompt": curses.A_BOLD, "query": curses.A_BOLD,
         "count": curses.A_DIM, "help": curses.A_DIM, "star": curses.A_NORMAL,
         "name": curses.A_NORMAL, "sel_bar": curses.A_REVERSE,
         "sel_name": curses.A_BOLD, "match": curses.A_BOLD,
         "version": curses.A_DIM, "tap": curses.A_NORMAL,
         "rule": [curses.A_NORMAL, curses.A_NORMAL, curses.A_NORMAL],
         "scroll": curses.A_DIM, "detail_name": curses.A_BOLD,
         "detail_meta": curses.A_DIM, "detail_tag": curses.A_NORMAL,
         "dot_r": curses.A_NORMAL, "dot_y": curses.A_NORMAL,
         "dot_g": curses.A_NORMAL, "check": curses.A_BOLD,
         "badge_skill": curses.A_NORMAL, "badge_rule": curses.A_NORMAL,
         "badge_workflow": curses.A_NORMAL, "badge_category": curses.A_NORMAL,
         "desc": curses.A_DIM}
    if not hasattr(curses, "start_color"):
        return t
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        return t
    p = _aurora_pairs(curses)

    def P(nm, bold=False):
        a = p.get(nm, 0)
        return (a | curses.A_BOLD) if bold else a

    t.update({"title": P("cyan", True), "prompt": P("cyan", True),
              "star": P("yellow"), "sel_bar": P("cyan", True),
              "sel_name": P("cyan", True), "match": P("pink", True),
              "tap": P("violet"), "rule": [P("cyan"), P("violet"), P("pink")],
              "scroll": P("cyan"), "detail_name": P("cyan", True),
              "detail_tag": P("pink"), "dot_r": P("red"), "dot_y": P("yellow"),
              "dot_g": P("green"), "check": P("green", True),
              "badge_skill": P("cyan"), "badge_rule": P("violet"),
              "badge_workflow": P("pink"), "badge_category": P("yellow")})
    return t


_NAME_X = 4  # column the name (and everything under it) starts at


def _browse_tui(curses, entries):
    """Run the curses UI. Returns the list of entries picked for install
    (one or more, via multi-select), or None if the user quit without picking.
    """
    state: dict[str, Any] = {"picks": None}
    categories = _tap_categories()
    desc_cache: dict = {}
    loading: set = set()

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
        th = _aurora_theme(curses)

        def put(y, x, s, attr=0):  # clip-safe cell writer
            if 0 <= y < _h and 0 <= x < _w - 1 and s:
                with contextlib.suppress(curses.error):
                    scr.addnstr(y, x, s, _w - 1 - x, attr)

        filt, sel, detail = "", 0, False
        selected: set = set()
        while True:
            q = filt.lower()
            matches = [e for e in entries
                       if _subseq(q, (e["name"] + " " + e["tap"]).lower())]
            sel = max(0, min(sel, len(matches) - 1))
            _h, _w = scr.getmaxyx()
            pane = 6 if detail and matches else 0
            try:
                scr.erase()
                # titlebar: macOS traffic dots + wordmark + gradient rule
                put(0, 0, "●", th["dot_r"])
                put(0, 2, "●", th["dot_y"])
                put(0, 4, "●", th["dot_g"])
                title = " boost browse"
                put(0, 6, title, th["title"])
                rx = 6 + len(title) + 1
                # strict=False: a terminal narrower than the 3-color palette
                # yields fewer segments, and the extra attrs go unused.
                for (start, length), attr in zip(
                        _grad_segments(max(0, _w - 1 - rx)), th["rule"],
                        strict=False):
                    put(0, rx + start, "─" * length, attr)
                # prompt line: cyan chevron, query, cursor, right-aligned count
                put(1, 0, "❯", th["prompt"])
                put(1, 2, filt, th["query"])
                put(1, 2 + len(filt), "▏", th["prompt"])
                sel_txt = "%d selected · " % len(selected) if selected else ""
                count = "%s%d/%d" % (sel_txt, len(matches), len(entries))
                put(1, max(2 + len(filt) + 2, _w - 1 - len(count)), count,
                    th["count"])
                put(2, 0, "↑↓ move  space select  ↵ detail  i install  q quit",
                    th["help"])
                # each result is a two-row card: name/badges, then description
                avail = max(0, _h - 3 - pane)
                rows = max(1, avail // 2)
                top = max(0, sel - rows + 1)
                view = matches[top:top + rows]
                namew = min(max((len(e["name"]) for e in view), default=4),
                            max(8, _w - _NAME_X - 30))
                bar = _scrollbar(len(matches), rows, top)
                for i, e in enumerate(view):
                    y = 3 + i * 2
                    chosen = top + i == sel
                    checked = _desc_key(e) in selected
                    put(y, 0, "▎" if chosen else " ", th["sel_bar"])
                    put(y, 1, "✓" if checked else " ", th["check"])
                    put(y, 2, "★" if e.get("curated") else " ", th["star"])
                    nm = out.truncate(e["name"], namew)
                    put(y, _NAME_X, nm.ljust(namew),
                        th["sel_name"] if chosen else th["name"])
                    for pos in _match_positions(q, nm.lower()):
                        put(y, _NAME_X + pos, nm[pos], th["match"])
                    bx = _NAME_X + namew + 2
                    for text, tkey in _row_badges(e, categories):
                        if bx + len(text) > _w - 2:
                            break
                        put(y, bx, text, th[tkey])
                        bx += len(text) + 1
                    put(y + 1, _NAME_X, out.truncate(describe(e), _w - 1 - _NAME_X),
                        th["desc"])
                    if bar:
                        bstart, blen = bar
                        thumb = bstart <= i < bstart + blen
                        ch = "█" if thumb else "│"
                        put(y, _w - 2, ch, th["scroll"])
                        put(y + 1, _w - 2, ch, th["scroll"])
                if pane and matches:
                    e = matches[sel]
                    y0 = _h - pane
                    # strict=False: same narrow-terminal truncation as the
                    # titlebar rule above.
                    for (start, length), attr in zip(
                            _grad_segments(_w - 1), th["rule"],
                            strict=False):
                        put(y0, start, "─" * length, attr)
                    tags = "  ".join("#" + str(t) for t in
                                     (e.get("meta", {}).get("tags") or []))
                    put(y0 + 1, 1, "%s  v%s" % (e["name"], e["version"]),
                        th["detail_name"])
                    put(y0 + 2, 1, out.truncate(describe(e), _w - 3),
                        th["name"])
                    put(y0 + 3, 1, "tap %s   dir %s" % (e["tap"], e["rel_dir"]),
                        th["detail_meta"])
                    put(y0 + 4, 1, tags or "no tags", th["detail_tag"])
                scr.refresh()
            except curses.error:
                pass  # terminal too small mid-draw; retry on next key
            key = scr.getch()
            if key == -1:                                 # poll tick, no key
                continue
            if key in (ord("q"), 27):                    # q / ESC
                return
            if key == ord("i") and matches:
                state["picks"] = ([e for e in entries if _desc_key(e) in selected]
                                  if selected else [matches[sel]])
                return
            if key == ord(" ") and matches:
                k = _desc_key(matches[sel])
                if k in selected:
                    selected.discard(k)
                else:
                    selected.add(k)
            elif key == curses.KEY_UP:
                sel = max(0, sel - 1)
            elif key == curses.KEY_DOWN:
                sel = min(sel + 1, max(0, len(matches) - 1))
            elif key in (10, 13, curses.KEY_ENTER):
                detail = not detail
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                filt = filt[:-1]
            elif 33 <= key <= 126:                        # printable, not space
                filt += chr(key)

    curses.wrapper(ui)  # wrapper guards drawing with try/finally endwin()
    return state["picks"]


def cmd_browse(argv):
    """Full-screen fuzzy browser over every catalog entry."""
    p = cliparse.parser(
        prog="boost browse",
        description="Interactive full-screen TUI with fuzzy search")
    p.parse_args(argv)
    entries = sorted(catalog.all_entries(), key=operator.itemgetter("name"))
    if not entries:
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
    for entry in picked:
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
        out.kv("upstream", upstream)
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
              else " (%d skills · %d rules · %d workflows)"
              % (by_kind["skill"], by_kind["rule"], by_kind["workflow"]))
    summary = ("installed %d%s · available %d (across %d tap%s) · discovery index %s"
               % (installed_n, detail, available_n, taps_n,
                  "" if taps_n == 1 else "s",
                  discovery if discovery is not None else "not built"))
    print(out.panel(summary, title="inventory"))
    return 0
