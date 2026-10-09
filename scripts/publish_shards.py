#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Turn exported vector shards into something a stranger can download.

Four subcommands, matching the halves of publishing:

    publish_shards.py export --out DIR [--tap owner/repo ...]
        Export every tapped registry's vectors from THIS machine's store.
        Run it where the embeddings already exist — that is the whole point of
        a shard, and re-embedding to publish would defeat it.

    publish_shards.py export-keyword --out DIR [--tap owner/repo ...]
                                    [--skip FILE...]
        Export every tapped registry's KEYWORD (BM25) documents as
        `<tap>.keyword.json.gz`, built from its clone. Seconds per registry,
        so it runs before the embed pass and needs no backend.

    publish_shards.py unchanged --manifest-url URL --out FILE [--kind KIND]
        Which tapped registries are already published at the commit they are
        at now. Run it after tapping and BEFORE embedding: every registry it
        lists can be untapped, and the embed pass costs only what moved.
        `--kind keyword` asks the same of the keyword rows, whose one
        compatibility key is the index version rather than an embedding space.

    publish_shards.py manifest --shard-dir DIR --repo owner/repo [--tag TAG]
                              [--carry-forward PREV.json --unchanged FILE...]
                              [--keyword-unchanged FILE...] [--known FILE...]
        Digest the shards in DIR and write the manifest that `core.shards`
        reads: schema version, the embedding space they all share, and one row
        per shard with its registry commit, size, sha256 and download URL. With
        `--carry-forward`, rows from the previous manifest survive for the
        registries the build jobs reported unchanged — their assets are still
        on the release, byte for byte, so the old row is the right row — and
        for the registries no job reported on at all, which is a different
        thing (see below). Keyword shards in DIR (`*.keyword.json.gz`) become
        the manifest's `keyword` section, carried forward by the same rules.

WHAT SILENCE MEANS. The build matrix is `fail-fast: false`, so a job that dies
takes its ~10 registries' evidence with it: no fresh shard, no `unchanged` line,
nothing. A manifest rebuilt from the evidence alone therefore dropped them while
`--clobber` left their assets on the release — measured on the release of
2026-09-20 as 8 orphaned shards, 245.5 MB, one of them the 199 MB registry that
takes 2 h 07 m to rebuild — and every user of those registries went back to
embedding locally. So a run answers for a registry in one of four ways, and only
the third is silence worth carrying: **rebuilt** (a fresh shard here),
**unchanged** (a job said so, and its commit agrees with the row), **unreported**
(nobody said anything, and it is still in `--known`), **gone** (nobody said
anything and it has left the catalogue — dropped, so the index cannot grow
forever). The counts for the last two are printed, because a manifest that
shrinks quietly is the whole bug.

WHY THE MANIFEST IS GENERATED AND NOT WRITTEN BY HAND. Three of its fields are
load-bearing at import time and unguessable: `sha256` is what makes a download
verifiable, `commit` is what stops a stale shard being merged, and
`provider`/`model`/`dim` are what stop vectors from two different embedding
spaces being mixed into one store — a failure that does not raise, it just
returns nonsense rankings.

WHY CARRY FORWARD RATHER THAN RE-EXPORT. Every weekly run used to embed every
registry from scratch (~9 job-hours for the catalogue) although most registries
had not moved. The cheap alternative — import last week's shard and re-export
it — re-uploads ~300 MB of identical vectors a week. Carrying the row forward
uploads nothing: the asset is already on the release, and `--clobber` never
deletes what it does not replace.

WHICH EMBEDDING SPACE TO PUBLISH. The keyless one. `embed` resolves Voyage, then
OpenAI, then the local ONNX `BAAI/bge-small-en-v1.5` that ships with the `rag`
extra, so a shard built on a machine holding `VOYAGE_API_KEY` is 1024-d
`voyage-4` and can only be imported — and queried — by someone else holding that
key. Export refuses to mix spaces for that reason, and says which one it found.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import config, dense, gitutil, rag, registry, shards
from boost_cli.errors import BoostError

DEFAULT_TAG = "shards-latest"

#: Suffix of a published keyword shard. Distinct from `.shard.json` so the
#: dense glob never picks one up, and gzip because the shard is JSON term
#: tables that compress several-fold.
KEYWORD_SUFFIX = ".keyword.json.gz"


def _safe(tap: str) -> str:
    return tap.replace("/", "__")


def _space(d: dict) -> dict:
    """The (provider, model, dim) triple, normalised so JSON and shard agree."""
    return {"provider": str(d.get("provider") or ""),
            "model": str(d.get("model") or ""),
            "dim": int(d.get("dim") or 0)}


def _fmt_space(space: dict) -> str:
    return "%s/%s/%sd" % (space["provider"], space["model"], space["dim"])


def cmd_export(args: argparse.Namespace) -> int:
    """Write one `<tap>.shard.json` per tap into `--out`."""
    taps = args.tap or [t.name for t in registry.list_taps()]
    if not taps:
        print("no taps configured on this machine", file=sys.stderr)
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for tap in taps:
        try:
            shard = dense.export_shard(tap)
        except BoostError as exc:
            print("skip %s: %s" % (tap, exc.message), file=sys.stderr)
            continue
        if not shard.get("chunks"):
            print("skip %s: no vectors" % tap, file=sys.stderr)
            continue
        dest = out_dir / (_safe(tap) + ".shard.json")
        dest.write_text(json.dumps(shard), encoding="utf-8")
        written += 1
        print("%s: %d chunks, %s @ %s"
              % (tap, len(shard["chunks"]), shard.get("model"),
                 str(shard.get("commit"))[:8]))
    print("wrote %d shard(s) to %s" % (written, out_dir))
    return 0 if written else 1


def keyword_bytes(shard: dict) -> bytes:
    """The published bytes of one keyword shard: canonical JSON, gzip'd.

    `sort_keys` and `mtime=0` make the bytes a function of the content alone,
    so re-exporting an unchanged registry produces the same sha256 instead of
    a new asset that differs only in a timestamp.
    """
    raw = json.dumps(shard, sort_keys=True, separators=(",", ":"))
    return gzip.compress(raw.encode("utf-8"), compresslevel=9, mtime=0)


def cmd_export_keyword(args: argparse.Namespace) -> int:
    """Write one `<tap>.keyword.json.gz` per tap into `--out`."""
    taps = args.tap or [t.name for t in registry.list_taps()]
    # The `tap commit` files `unchanged --kind keyword` writes: first field.
    skip = known_registries(args.skip)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for tap in taps:
        if tap in skip:
            print("%s: published index is current" % tap)
            continue
        try:
            shard = rag.export_shard(tap)
        except BoostError as exc:
            print("skip %s: %s" % (tap, exc.message), file=sys.stderr)
            continue
        if not shard["docs"]:
            print("skip %s: no documents" % tap, file=sys.stderr)
            continue
        data = keyword_bytes(shard)
        (out_dir / (_safe(tap) + KEYWORD_SUFFIX)).write_bytes(data)
        written += 1
        print("%s: %d documents, %d bytes @ %s"
              % (tap, len(shard["docs"]), len(data), shard["commit"][:8]))
    print("wrote %d keyword shard(s) to %s" % (written, out_dir))
    # Not a failure when nothing was written: a chunk whose every registry is
    # already published at its commit has nothing to export.
    return 0


def cmd_unchanged(args: argparse.Namespace) -> int:
    """Write `tap commit` for every tap whose published shard is current.

    Exit 0 whatever happens: an empty list means "embed everything", which is
    the right outcome for a first run, an unreachable release, or a manifest in
    another embedding space — and a workflow that aborted on any of those would
    never publish the first shard.
    """
    lines: list[str] = []
    try:
        manifest = shards.fetch_manifest(args.manifest_url)
    except BoostError as exc:
        print("no usable manifest (%s) — embedding everything" % exc.message,
              file=sys.stderr)
        manifest = None
    keyword = getattr(args, "kind", "dense") == "keyword"
    if manifest is not None:
        why = (shards.keyword_incompatible(manifest) if keyword
               else shards.incompatible(manifest))
        if why:
            print("published shards are not usable by this run (%s) — "
                  "rebuilding everything" % why, file=sys.stderr)
        else:
            commits = {t.name: (gitutil.head_commit(t.path) if t.is_cloned
                                else "")
                       for t in registry.list_taps()}
            # The keyword rows are read through the same `unchanged`, by
            # handing it the section as if it were a manifest: one rule for
            # "is this row still the commit the tap is at", not two.
            view = ({"shards": shards.keyword_section(manifest).get("shards")}
                    if keyword else manifest)
            for tap, row in shards.unchanged(view, commits).items():
                lines.append("%s %s" % (tap, row["commit"]))
    text = "".join(line + "\n" for line in lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("%d registr%s unchanged since the last publish"
          % (len(lines), "y" if len(lines) == 1 else "ies"), file=sys.stderr)
    return 0


def _fresh_row(path: Path, repo: str, tag: str) -> tuple[dict, dict]:
    """One manifest row plus the embedding space its shard was built in."""
    raw = path.read_bytes()
    shard = json.loads(raw.decode("utf-8"))
    missing = [k for k in ("tap", "commit", "provider", "model", "dim")
               if not shard.get(k)]
    if missing:
        raise SystemExit("%s is missing %s" % (path.name, ", ".join(missing)))
    row = {
        "tap": shard["tap"],
        "commit": shard["commit"],
        "chunks": len(shard.get("chunks") or []),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "url": "https://github.com/%s/releases/download/%s/%s"
               % (repo, tag, path.name),
    }
    return row, _space(shard)


def known_registries(paths: list[str] | None) -> set[str]:
    """Which registries still count as registries, for carry-forward.

    ``None`` — no ``--known`` at all — means the bundled catalogue, a
    superset of the list ``shard_plan.py`` builds the run's matrix from (it
    skips ``list_only`` entries, which have no items to embed), so the
    publish job needs no extra plumbing to answer "has this registry left the
    catalogue?". A superset is the safe direction here: a registry that is
    known but never in the matrix is carried rather than dropped, and a
    carried row is still refused by ``dense.import_shard`` unless its commit
    matches. An explicit (possibly empty) list overrides it, which is what
    makes the decision testable and gives a scoped run an escape hatch.

    A file is one name per line; ``#`` comments and blank lines are skipped and
    anything after the first field is ignored, so the ``tap commit`` files the
    build jobs already write can be handed over unchanged.
    """
    if paths is None:
        names = {str(e.get("name") or "")
                 for e in config.load_registry_catalog()}
        names.discard("")
        if not names:
            print("the bundled registry catalogue is unreadable — carrying "
                  "nothing forward for unreported registries", file=sys.stderr)
        return names
    out: set[str] = set()
    for name in paths:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except OSError as exc:
            print("cannot read %s (%s) — its registries count as unknown, so "
                  "a row nobody reported on is dropped rather than carried"
                  % (name, exc), file=sys.stderr)
            continue
        for line in text.splitlines():
            fields = line.split("#", 1)[0].split()
            if fields:
                out.add(fields[0])
    return out


def _names(taps: list[str], cap: int = 8) -> str:
    """A log-sized rendering of a tap list: the first few, then a count."""
    shown = ", ".join(taps[:cap])
    return shown + ("" if len(taps) <= cap
                    else " and %d more" % (len(taps) - cap))


def _carried_rows(prev_path: str, unchanged_files: list[str],
                  fresh_taps: set[str], space: dict | None,
                  known: set[str]
                  ) -> tuple[list[dict], dict | None, dict]:
    """Rows from the previous manifest that this run has no better answer for.

    Returns ``(rows, previous_space, report)``, where `report` counts the two
    interesting populations for the log: ``silent`` (registries no job
    reported on, carried) and ``gone`` (registries no job reported on that
    have left the catalogue, dropped).

    FOUR STATES, ONE CARRY-FORWARD. A run reports on a registry by rebuilding
    it (a fresh shard) or by naming it in an ``unchanged-*.txt``. Anything else
    is silence, and silence has two causes that must not be treated alike: a
    build job that failed — ``fail-fast: false``, so ~10 registries vanish from
    the evidence while their assets stay on the release — and a registry that
    has left the catalogue. The first keeps last week's row; only the second is
    dropped.

    Every guard here still refuses rather than degrades, down both paths: an
    unreadable previous manifest and one in another embedding space carry
    nothing at all, and a row whose commit disagrees with the job that reported
    it is refused — and must not return through the silent path, because that
    registry *was* reported on.
    """
    try:
        prev = json.loads(Path(prev_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("previous manifest unreadable (%s) — carrying nothing forward"
              % exc, file=sys.stderr)
        return [], None, {}
    prev_space = _space(prev)
    if space is not None and prev_space != space:
        print("previous manifest is %s, this run is %s — carrying nothing "
              "forward" % (_fmt_space(prev_space), _fmt_space(space)),
              file=sys.stderr)
        return [], prev_space, {}
    out, report = _carry(shards.rows(prev), prev, unchanged_files, fresh_taps,
                         known)
    return out, prev_space, report


def _carry(index: dict[str, dict], prev: dict, unchanged_files: list[str],
           fresh_taps: set[str], known: set[str]) -> tuple[list[dict], dict]:
    """The four-state carry-forward over one set of published rows.

    `index` is the previous manifest's rows of one kind (dense, or the
    keyword section), already filtered by :func:`shards.rows`; `prev` is that
    kind's rows in manifest shape, for :func:`shards.unreported`.
    """
    wanted: dict[str, str] = {}
    for name in unchanged_files:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except OSError as exc:
            print("cannot read %s (%s) — its registries will be re-embedded "
                  "next run" % (name, exc), file=sys.stderr)
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2:
                wanted[parts[0]] = parts[1]
    out: list[dict] = []
    for tap, commit in sorted(wanted.items()):
        if tap in fresh_taps:
            continue
        row = index.get(tap)
        if row is None or str(row.get("commit")) != commit:
            # The job says one commit, the manifest another: someone is wrong,
            # and a row carried under those conditions could describe a tree
            # the registry is no longer at. Re-embedded next run.
            continue
        out.append(dict(row))
    # Everything above answers to evidence. What follows answers to its
    # absence: a registry named by no fresh shard and no unchanged file was
    # never reported on, so its published row stands — unless it has left the
    # catalogue, which is the one silence that means "gone".
    reported = set(fresh_taps) | set(wanted)
    silent = shards.unreported(prev, reported, known)
    # `dict(...)` on both carry paths, for the same reason the line above
    # copies: the rows come out of the previous manifest, and a later edit of
    # the new one must not reach back into it. Not observable from outside --
    # `prev` is parsed here and discarded -- so it is defensive symmetry
    # rather than a tested behaviour.
    out.extend(dict(silent[tap]) for tap in sorted(silent))
    gone = sorted(tap for tap in index
                  if tap not in reported and tap not in silent)
    return out, {"silent": sorted(silent), "gone": gone}


def _keyword_row(path: Path, repo: str, tag: str) -> tuple[dict, int]:
    """One keyword manifest row plus the index version its shard was built at."""
    raw = path.read_bytes()
    shard = json.loads(gzip.decompress(raw).decode("utf-8"))
    missing = [k for k in ("tap", "commit", "index_version", "docs")
               if not shard.get(k)]
    if missing:
        raise SystemExit("%s is missing %s" % (path.name, ", ".join(missing)))
    row = {
        "tap": shard["tap"],
        "commit": shard["commit"],
        "docs": len(shard["docs"]),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "url": "https://github.com/%s/releases/download/%s/%s"
               % (repo, tag, path.name),
    }
    return row, int(shard["index_version"])


def keyword_section(shard_dir: Path, args: argparse.Namespace,
                    known: set[str] | None) -> dict | None:
    """The manifest's `keyword` section: fresh shards plus carried rows.

    The dense rules, applied to a second kind of row. One index version per
    section, refused if the fresh shards disagree — `shards.keyword_
    incompatible` reads that one header to decide whether to download at all.
    A previous section at another version carries nothing: its rows were
    tokenized differently and every consumer would refuse them. Returns None
    when there is nothing to describe, so a manifest never carries an empty
    section that reads as "published, and covers no registry".
    """
    files = sorted(shard_dir.glob("*" + KEYWORD_SUFFIX))
    fresh: list[dict] = []
    versions: set[int] = set()
    for path in files:
        row, version = _keyword_row(path, args.repo, args.tag)
        fresh.append(row)
        versions.add(version)
    if len(versions) > 1:
        raise SystemExit("keyword shards span index versions %s — publish one "
                         "version per manifest" % sorted(versions))
    version = versions.pop() if versions else None
    carried: list[dict] = []
    if args.carry_forward:
        try:
            prev = json.loads(Path(args.carry_forward).read_text(
                encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
        sec = shards.keyword_section(prev) if isinstance(prev, dict) else {}
        prev_version = sec.get("index_version")
        if sec and version is not None and prev_version != version:
            print("previous keyword index is version %r, this run is %r — "
                  "carrying no keyword rows forward" % (prev_version, version),
                  file=sys.stderr)
        elif sec and isinstance(prev_version, int):
            view = {"shards": sec.get("shards")}
            carried, report = _carry(
                shards.rows(view), view, args.keyword_unchanged,
                {r["tap"] for r in fresh},
                known or set())
            version = prev_version
            print("keyword: %d fresh, %d carried (%d for registries no job "
                  "reported), %d dropped"
                  % (len(fresh), len(carried), len(report.get("silent") or []),
                     len(report.get("gone") or [])))
    rows = fresh + carried
    if not rows or version is None:
        return None
    return {"format": rag.SHARD_FORMAT, "index_version": version,
            "shards": sorted(rows, key=lambda r: r["tap"])}


def cmd_manifest(args: argparse.Namespace) -> int:
    """Digest a directory of shards (plus carried rows) into one manifest."""
    shard_dir = Path(args.shard_dir)
    files = sorted(shard_dir.glob("*.shard.json"))
    rows: list[dict] = []
    spaces: list[dict] = []
    for path in files:
        row, space = _fresh_row(path, args.repo, args.tag)
        rows.append(row)
        spaces.append(space)
    first = spaces[0] if spaces else None
    for path, space in zip(files, spaces, strict=True):
        if space != first:
            # Refuse rather than publish a manifest whose top-level space is a
            # lie for some of its rows: `core.shards.incompatible` reads that
            # one header to decide whether to download anything at all.
            raise SystemExit(
                "%s is %s but the others are %s — publish one embedding space "
                "per manifest" % (path.name, _fmt_space(space),
                                  _fmt_space(first or {})))
    carried = 0
    report: dict = {}
    known = known_registries(args.known) if args.carry_forward else None
    if args.carry_forward:
        old, prev_space, report = _carried_rows(
            args.carry_forward, args.unchanged, {r["tap"] for r in rows},
            first, known if known is not None else set())
        rows.extend(old)
        carried = len(old)
        if first is None and old:
            # A quiet week: nothing moved, nothing fresh, and the manifest is
            # still due. Its space is the previous manifest's.
            first = prev_space
    if not rows or first is None:
        print("nothing to publish: no *.shard.json under %s and nothing "
              "carried forward" % shard_dir, file=sys.stderr)
        return 1
    manifest = {
        "version": 1,
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": first["provider"],
        "model": first["model"],
        "dim": first["dim"],
        "shards": sorted(rows, key=lambda r: r["tap"]),
    }
    keyword = keyword_section(shard_dir, args, known)
    if keyword is not None:
        manifest[shards.KEYWORD_SECTION] = keyword
    dest = Path(args.out)
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(int(r.get("chunks") or 0) for r in rows)
    silent = report.get("silent") or []
    gone = report.get("gone") or []
    # Both directions, always, because a silently shrinking manifest is the
    # failure this reporting exists to make visible: how many rows were kept
    # for jobs that never reported, and how many were let go.
    print("manifest: %d shard(s) (%d fresh, %d carried unchanged, %d carried "
          "for registries no job reported), %s chunks, %s -> %s"
          % (len(rows), len(rows) - carried, carried - len(silent),
             len(silent), format(total, ","), _fmt_space(first), dest))
    if silent:
        print("::warning::no build job reported on %d registr%s — their job "
              "failed or never ran, so last week's published row was carried "
              "forward: %s"
              % (len(silent), "y" if len(silent) == 1 else "ies",
                 _names(silent)))
    if gone:
        print("dropped %d published row(s) for registr%s no longer in the "
              "catalogue: %s" % (len(gone), "y" if len(gone) == 1 else "ies",
                                 _names(gone)))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("export", help="export this machine's vectors")
    ex.add_argument("--out", required=True, metavar="DIR")
    ex.add_argument("--tap", action="append", metavar="OWNER/REPO",
                    help="only this tap (repeatable); default is every tap")
    ex.set_defaults(func=cmd_export)

    un = sub.add_parser("unchanged",
                        help="list tapped registries already published at "
                             "their current commit")
    un.add_argument("--manifest-url", metavar="URL",
                    help="the published manifest (default: boost's own)")
    un.add_argument("--out", metavar="FILE",
                    help="write `tap commit` lines here instead of stdout")
    un.add_argument("--kind", choices=("dense", "keyword"), default="dense",
                    help="which published rows to compare (default: dense)")
    un.set_defaults(func=cmd_unchanged)

    kw = sub.add_parser("export-keyword",
                        help="export this machine's keyword (BM25) documents")
    kw.add_argument("--out", required=True, metavar="DIR")
    kw.add_argument("--tap", action="append", metavar="OWNER/REPO",
                    help="only this tap (repeatable); default is every tap")
    kw.add_argument("--skip", nargs="*", default=[], metavar="FILE",
                    help="`tap commit` files (from `unchanged --kind "
                         "keyword`) naming registries not to export")
    kw.set_defaults(func=cmd_export_keyword)

    mf = sub.add_parser("manifest", help="write manifest.json for a shard dir")
    mf.add_argument("--shard-dir", required=True, metavar="DIR")
    mf.add_argument("--repo", required=True, metavar="OWNER/REPO",
                    help="repo whose release hosts the assets")
    mf.add_argument("--tag", default=DEFAULT_TAG,
                    help="release tag hosting the assets (default: %(default)s)")
    mf.add_argument("--out", default="manifest.json", metavar="FILE")
    mf.add_argument("--carry-forward", metavar="PREV.json",
                    help="the previous manifest; its rows survive for "
                         "registries listed in --unchanged files")
    mf.add_argument("--unchanged", nargs="*", default=[], metavar="FILE",
                    help="`tap commit` files written by "
                         "`publish_shards.py unchanged` in the build jobs")
    mf.add_argument("--keyword-unchanged", nargs="*", default=[],
                    metavar="FILE",
                    help="`tap commit` files written by `unchanged --kind "
                         "keyword`; carries those keyword rows forward")
    mf.add_argument("--known", nargs="*", default=None, metavar="FILE",
                    help="registries that still exist, one name per line "
                         "(default: the bundled catalogue). A published row "
                         "survives a run that never reported on it only for "
                         "these; `--known` with no file carries none.")
    mf.set_defaults(func=cmd_manifest)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
