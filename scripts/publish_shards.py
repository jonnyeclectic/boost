#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Turn exported vector shards into something a stranger can download.

The subcommands, in the order a publish runs them:

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
        `--keyword-tag` names the release their URLs point at (default: --tag).

    publish_shards.py splice | verify | prune | capacity
        The release bookkeeping `shards.yml` runs around the uploads — see
        TWO RELEASES below, and each subcommand's --help.

TWO RELEASES, BECAUSE ONE HOLDS 1,000 ASSETS. GitHub refuses the 1,001st asset
on a release ("file_count limited to 1000 assets per release"), and one asset
per registry per kind is ~2 x 512 against that. `shards-latest` reached 999 and
every run after 2026-10-11 failed its upload with HTTP 422 — and because
`--clobber` deletes before it uploads, each failed run also left rows in the
still-live 2026-10-11 manifest describing assets that had since been replaced
(162 dense, 145 keyword by size) or deleted outright (4). So the keyword
shards live on a second rolling prerelease, `KEYWORD_TAG`, and the manifest
stays on `shards-latest`, where every boost in the field already looks.

Every boost that reads the keyword section accepts the move unchanged:
`core.shards.download` refuses a URL off the manifest's own *host*
(`_same_origin` compares scheme and netloc, nothing else), and both tags are
on github.com.

The publish job's order is what keeps a client from reading a manifest that
names a missing asset (bar `--clobber`'s own delete-then-upload, which
`shards.yml` describes): upload keyword shards to their release; publish an
interim manifest (last week's dense rows plus this week's keyword section,
each checked by `verify` against the release listings); `prune` only as many
now-unnamed keyword assets off `shards-latest` as this run's new dense shards
need room for; upload the dense shards; `verify` and publish the final
manifest; then prune what it does not name — every keyword asset left on
`shards-latest`, and, `--bounded` by MAX_DROP_FRACTION, the orphaned dense
shards and the keyword release's own orphans. `capacity` runs in
the plan job, before any build job spends an hour, and fails if either
release's projected count would pass `RELEASE_ASSET_LIMIT` less
`RELEASE_ASSET_HEADROOM`.

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
import os
import sys
import tempfile
import urllib.parse
import zlib
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

#: Suffix of a published dense shard.
DENSE_SUFFIX = ".shard.json"

#: The asset name the manifest is published under, on `DEFAULT_TAG`.
MANIFEST_ASSET = "manifest.json"

#: The second rolling prerelease, which hosts the keyword shards. Created
#: exactly like `shards-latest` — prerelease, `--latest=false` — and spelled
#: with the same prefix and no digit, so release-drafter, the README's shields
#: badge and setuptools-scm's `v[0-9]*` tag match all keep ignoring it.
KEYWORD_TAG = "shards-keyword-latest"

#: GitHub's per-release asset ceiling. Not a tunable: the upload of asset
#: 1,001 is refused with HTTP 422.
RELEASE_ASSET_LIMIT = 1000

#: How far under `RELEASE_ASSET_LIMIT` the plan job's projection must stay.
#: Each registry costs one asset per release, and the catalogue grew from 464
#: shardable registries on 2026-10-11 to 512 on 2026-11-04, so this is about
#: seven weeks of growth between the check failing and the release filling.
RELEASE_ASSET_HEADROOM = 100

#: Slack `prune --room-for` keeps under the hard limit, so a count that is a
#: few assets stale by the time the upload runs cannot cost the run.
ROOM_MARGIN = 10

#: `verify` refuses to write a manifest that would lose more than this share of
#: a section's rows, and `prune --bounded` to delete more than this share of a
#: release's assets of one kind. Dropping a row whose asset is gone or replaced
#: is right — no client can use it — but a listing that came back wrong would
#: drop the good rows with it, and the cost of that lands next week, as a
#: re-embed. The worst breakage measured on a live release sits under it: the
#: 2026-10-11 manifest has 162 of its 458 dense rows (35%) naming an asset that
#: a failed run's `--clobber` replaced (every one `updated_at` 2026-11-01).
MAX_DROP_FRACTION = 0.5


def _safe(tap: str) -> str:
    return tap.replace("/", "__")


def dense_asset_name(tap: str) -> str:
    """The name `shards.yml` uploads `tap`'s dense shard under.

    One underscore, not two: the export step names the file with
    ``tr '/' '__'``, and `tr` maps each `/` to the FIRST character of its
    second set. Mirrored here rather than shared, so the test that runs `tr`
    is what keeps the two from drifting.
    """
    return tap.replace("/", "_") + DENSE_SUFFIX


def keyword_asset_name(tap: str) -> str:
    """The name `export-keyword` writes `tap`'s keyword shard under."""
    return _safe(tap) + KEYWORD_SUFFIX


def release_url(repo: str, tag: str, name: str) -> str:
    """The anonymous download URL of asset `name` on release `tag`."""
    return "https://github.com/%s/releases/download/%s/%s" % (repo, tag, name)


def asset_location(url: object) -> tuple[str, str] | None:
    """``(tag, asset name)`` for a release-download URL, else None.

    Read off the path's last three segments, `download/<tag>/<name>`, so it
    answers for any repo and for a `file:` mirror laid out the same way.
    """
    if not isinstance(url, str):
        return None
    parts = urllib.parse.urlparse(url).path.split("/")
    if len(parts) < 4 or parts[-3] != "download" or parts[-4] != "releases":
        return None
    tag, name = parts[-2], parts[-1]
    if not tag or not name:
        return None
    return tag, name


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


def _write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to `path` so the path never holds a partial file.

    A job killed mid-write (OOM, timeout) used to leave a truncated
    `.keyword.json.gz` that the publish job then globbed and choked on. The
    temp name ends `.tmp`, so neither the artifact upload nor the manifest
    glob (`*.keyword.json.gz`) ever matches a half-written one.
    """
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
        _write_atomic(out_dir / (_safe(tap) + KEYWORD_SUFFIX), data)
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
            hosted_on = getattr(args, "hosted_on", None)
            if hosted_on:
                # A row whose asset sits on another release is not "already
                # published" for a run that publishes to this one: listing it
                # would carry the old URL forward and keep the asset pinned
                # where it is. Unlisted, the registry is re-exported here —
                # seconds for a keyword shard — and its old asset becomes
                # unnamed, which is what lets the publish job prune it.
                kept = [r for r in view.get("shards") or []
                        if isinstance(r, dict)
                        and (asset_location(r.get("url")) or ("",))[0]
                        == hosted_on]
                view = {"shards": kept}
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
        "url": release_url(repo, tag, path.name),
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


def _keyword_row(path: Path, repo: str, tag: str) -> tuple[dict, int] | None:
    """One keyword manifest row plus the index version its shard was built at.

    None for a file that does not inflate to a JSON object — a truncated or
    corrupt gzip. That tap is then simply unreported, so its previous row
    carries forward; raising here would abort the whole manifest step and
    take the dense rows down with it.
    """
    raw = path.read_bytes()
    try:
        shard = json.loads(gzip.decompress(raw).decode("utf-8"))
    except (OSError, EOFError, zlib.error, ValueError):
        shard = None
    if not isinstance(shard, dict):
        return None
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
        "url": release_url(repo, tag, path.name),
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
    # The release these rows' assets are uploaded to. Defaults to the dense
    # tag, so a one-release fork publishes exactly as before; `shards.yml`
    # passes KEYWORD_TAG.
    tag = getattr(args, "keyword_tag", None) or args.tag
    for path in files:
        got = _keyword_row(path, args.repo, tag)
        if got is None:
            print("::warning::%s is not a readable keyword shard — treating "
                  "its registry as unreported" % path.name, file=sys.stderr)
            # Delete it, or the upload step's `--clobber` replaces the good
            # asset of the same name that the carried row still points at.
            path.unlink(missing_ok=True)
            continue
        row, version = got
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


# ------------------------------------------------------------ release upkeep


def _read_json(path: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("cannot read %s: %s" % (path, exc)) from exc


def release_assets(release: object) -> dict[str, dict]:
    """``{name: {"id", "size"}}`` from a REST release object.

    The shape `gh api repos/OWNER/REPO/releases/tags/TAG` prints, which
    carries every asset inline (measured: all 999 on `shards-latest`). A
    document with no `assets` list is an error rather than an empty release,
    for every caller: `verify` and `prune` act on what this says is *absent*,
    so an error page read as "no assets" would drop every row, and `capacity`
    acts on what it says is *present*, so the same page would pass a full
    release. A release that does not exist yet is the shell's to decide — on
    an HTTP 404 and nothing else — and it writes ``{"assets": []}`` for one.
    """
    assets = release.get("assets") if isinstance(release, dict) else None
    if not isinstance(assets, list):
        raise SystemExit("release listing has no `assets` list — refusing "
                         "to decide what is or is not on the release")
    out: dict[str, dict] = {}
    for a in assets:
        if isinstance(a, dict) and isinstance(a.get("name"), str):
            out[a["name"]] = {"id": a.get("id"), "size": a.get("size")}
    return out


def _release_args(values: list[str] | None) -> dict[str, dict[str, dict]]:
    """``--release TAG=FILE`` pairs, each read with :func:`release_assets`."""
    out: dict[str, dict[str, dict]] = {}
    for value in values or []:
        tag, sep, path = value.partition("=")
        if not sep or not tag or not path:
            raise SystemExit("--release wants TAG=FILE, got %r" % value)
        out[tag] = release_assets(_read_json(path))
    return out


def _sections(manifest: dict) -> list[tuple[str, list]]:
    """``(label, rows)`` for the dense rows and, if present, the keyword rows."""
    out = [("dense", manifest.get("shards") or [])]
    sec = manifest.get(shards.KEYWORD_SECTION)
    if isinstance(sec, dict):
        out.append(("keyword", sec.get("shards") or []))
    return out


def row_problem(row: object, releases: dict[str, dict[str, dict]]
                ) -> str | None:
    """Why `row` names no asset a client could download, or None if it does.

    Checked against the listing, not by downloading: presence, and the size
    the row records. A size is not a digest — an asset replaced by one of the
    same length passes here and is refused by the client's sha256 instead —
    but it catches every replacement the failed runs actually made.
    """
    if not isinstance(row, dict):
        return "is not an object"
    loc = asset_location(row.get("url"))
    if loc is None:
        return "has no release-download URL"
    tag, name = loc
    if tag not in releases:
        return "is on release %s, which this run did not list" % tag
    asset = releases[tag].get(name)
    if asset is None:
        return "names %s, which is not on %s" % (name, tag)
    want = row.get("bytes")
    if isinstance(want, int) and asset.get("size") != want:
        return ("names %s, which is %s bytes on %s; the row says %d"
                % (name, asset.get("size"), tag, want))
    return None


def verify_manifest(manifest: dict, releases: dict[str, dict[str, dict]],
                    only: str | None = None
                    ) -> tuple[dict, dict[str, list[tuple[str, str]]]]:
    """`manifest` without the rows whose asset is missing or replaced.

    Returns ``(manifest, dropped)``, `dropped` mapping each checked section
    to its ``(tap, reason)`` pairs. Dropping is the right answer for such a
    row, rather than failing the publish: a client would refuse it anyway,
    on sha256 or on a 404, and a registry with no row is simply re-embedded
    next week, because `unchanged` finds nothing to keep for it. A keyword
    section left with no rows is removed, as `keyword_section` never writes
    an empty one. `only` names the one section to check; the other passes
    through untouched.
    """
    out = dict(manifest)
    dropped: dict[str, list[tuple[str, str]]] = {}
    for label, rows in _sections(manifest):
        if only is not None and label != only:
            continue
        kept: list = []
        lost: list[tuple[str, str]] = []
        for row in rows:
            why = row_problem(row, releases)
            if why is None:
                kept.append(row)
            else:
                tap = str(row.get("tap") if isinstance(row, dict) else row)
                lost.append((tap, why))
        dropped[label] = lost
        if label == "dense":
            out["shards"] = kept
        elif kept:
            out[shards.KEYWORD_SECTION] = dict(
                manifest[shards.KEYWORD_SECTION], shards=kept)
        else:
            out.pop(shards.KEYWORD_SECTION, None)
    return out, dropped


def cmd_verify(args: argparse.Namespace) -> int:
    """Drop the rows a release listing cannot vouch for; refuse a rout."""
    manifest = _read_json(args.manifest)
    if not isinstance(manifest, dict):
        raise SystemExit("%s is not a manifest" % args.manifest)
    releases = _release_args(args.release)
    if not releases:
        raise SystemExit("verify needs at least one --release TAG=FILE")
    checked, dropped = verify_manifest(manifest, releases, args.only)
    refused = False
    for label, rows in _sections(manifest):
        if label not in dropped:
            continue
        lost = dropped[label]
        print("%s: %d row(s), %d verified, %d dropped"
              % (label, len(rows), len(rows) - len(lost), len(lost)))
        if lost:
            print("::warning::%d %s row(s) name an asset that is missing or "
                  "was replaced since: %s"
                  % (len(lost), label, _names(["%s (%s)" % (t, why)
                                               for t, why in lost], cap=4)))
        if rows and len(lost) > MAX_DROP_FRACTION * len(rows):
            print("refusing: %d of %d %s rows would go — more than %d%% "
                  "means the listing is wrong, not the release"
                  % (len(lost), len(rows), label, MAX_DROP_FRACTION * 100),
                  file=sys.stderr)
            refused = True
    if refused:
        return 1
    Path(args.out or args.manifest).write_text(
        json.dumps(checked, indent=2) + "\n", encoding="utf-8")
    return 0


def splice(dense_from: dict, keyword_from: dict) -> dict:
    """`dense_from`'s dense rows with `keyword_from`'s keyword section.

    The interim manifest: last week's dense rows, whose assets are all
    still on `shards-latest` because no dense shard has been uploaded yet,
    and this week's keyword section, whose assets are already on their own
    release. Publishing it is what makes every keyword asset on
    `shards-latest` unnamed BEFORE the dense upload needs the room.
    """
    out = {k: v for k, v in dense_from.items()
           if k != shards.KEYWORD_SECTION and not k.startswith("_")}
    sec = keyword_from.get(shards.KEYWORD_SECTION)
    if isinstance(sec, dict) and sec.get("shards"):
        out[shards.KEYWORD_SECTION] = sec
    if keyword_from.get("generated"):
        out["generated"] = keyword_from["generated"]
    return out


def cmd_splice(args: argparse.Namespace) -> int:
    dense_from = _read_json(args.dense)
    keyword_from = _read_json(args.keyword)
    if (not isinstance(dense_from, dict)
            or dense_from.get("version") != shards.MANIFEST_VERSION
            or not isinstance(dense_from.get("shards"), list)):
        print("%s is not a version-%d manifest — no interim manifest"
              % (args.dense, shards.MANIFEST_VERSION), file=sys.stderr)
        return 1
    if not isinstance(keyword_from, dict):
        raise SystemExit("%s is not a manifest" % args.keyword)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(splice(dense_from, keyword_from), indent=2)
                   + "\n", encoding="utf-8")
    return 0


def named_assets(manifest: dict, tag: str) -> set[str]:
    """Asset names on release `tag` that any row of `manifest` points at.

    Every row with a URL counts, malformed or not: this is the set `prune`
    must never touch, and erring towards keeping an asset costs one slot.
    """
    out: set[str] = set()
    for _label, rows in _sections(manifest):
        for row in rows:
            if not isinstance(row, dict):
                continue
            loc = asset_location(row.get("url"))
            if loc and loc[0] == tag:
                out.add(loc[1])
    return out


def prune_candidates(manifest: dict, tag: str, assets: dict[str, dict],
                     suffix: str) -> list[tuple[str, str]]:
    """``(id, name)`` of every `suffix` asset on `tag` the manifest does not name.

    Only ever called with the manifest that is already PUBLISHED, so nothing
    returned here is reachable by a client that reads it.
    """
    keep = named_assets(manifest, tag)
    return [(str(assets[name].get("id")), name) for name in sorted(assets)
            if name.endswith(suffix) and name not in keep
            and assets[name].get("id") is not None]


def new_names(assets: dict[str, dict], uploading: list[str]) -> set[str]:
    """The names in `uploading` the release does not already hold.

    A file whose name is already there replaces it (`--clobber` deletes, then
    uploads), so only these change the count.
    """
    return {Path(f).name for f in uploading} - set(assets)


def room_needed(assets: dict[str, dict], uploading: list[str]) -> int:
    """How many assets must go before `uploading` fits under the limit."""
    return max(0, len(assets) + len(new_names(assets, uploading))
               - (RELEASE_ASSET_LIMIT - ROOM_MARGIN))


def cmd_prune(args: argparse.Namespace) -> int:
    """List `id name` for the assets the published manifest leaves unnamed."""
    manifest = _read_json(args.manifest)
    if not isinstance(manifest, dict):
        raise SystemExit("%s is not a manifest" % args.manifest)
    assets = release_assets(_read_json(args.release_json))
    victims = prune_candidates(manifest, args.tag, assets, args.suffix)
    if args.room_for is not None:
        need = room_needed(assets, args.room_for)
        if need > len(victims):
            print("::error::%s holds %d assets and this upload adds %d new "
                  "names; %d must go but only %d unnamed %s asset(s) can"
                  % (args.tag, len(assets),
                     len(new_names(assets, args.room_for)), need,
                     len(victims), args.suffix))
            return 1
        victims = victims[:need]
    elif args.bounded:
        # The guard for the passes where a wrong manifest costs rebuilds —
        # above all the dense one, whose shards are the expensive kind. A
        # manifest that names far fewer rows than the release holds is a
        # wrong manifest, not a release full of orphans: "build the manifest"
        # reads a failed fetch of last week's as a first run and carries
        # nothing forward, and pruning against that would delete every
        # dense shard it left out.
        held = sum(1 for name in assets if name.endswith(args.suffix))
        if len(victims) > MAX_DROP_FRACTION * held:
            print("::error::refusing to prune %d of the %d %s asset(s) on %s "
                  "— more than %d%% means the manifest is wrong, not the "
                  "release" % (len(victims), held, args.suffix, args.tag,
                               MAX_DROP_FRACTION * 100))
            if args.out:
                Path(args.out).write_text("", encoding="utf-8")
            return 1
    text = "".join("%s %s\n" % v for v in victims)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("%s: %d of %d asset(s) to prune" % (args.tag, len(victims),
                                             len(assets)), file=sys.stderr)
    return 0


def carried_keyword_assets(live: dict | None, tag: str, taps: list[str]
                           ) -> set[str]:
    """Keyword assets on `tag` the live manifest names for a registry not in
    `taps` — rows the next manifest carries forward as they are.

    A registry this run does not rebuild is unreported, so its keyword row
    survives with its URL, and the asset it names stays where it is: on
    `shards-latest`, if the row predates the split. A row with no `tap`
    counts too, since `prune` keeps whatever any row names. So does a row
    for a registry that has left the catalogue, which the manifest drops
    instead (11 of the live manifest's keyword rows on 2026-11-04): an
    overcount, which is the direction a ceiling check can afford.
    """
    run = set(taps)
    out: set[str] = set()
    for _label, rows in _sections(live or {}):
        for row in rows:
            if not isinstance(row, dict) or row.get("tap") in run:
                continue
            loc = asset_location(row.get("url"))
            if loc and loc[0] == tag and loc[1].endswith(KEYWORD_SUFFIX):
                out.add(loc[1])
    return out


def project_assets(taps: list[str], existing: dict[str, dict[str, dict]],
                   dense_tag: str = DEFAULT_TAG,
                   keyword_tag: str = KEYWORD_TAG,
                   live: dict | None = None) -> dict[str, int]:
    """Each release's asset count once a run over `taps` has published.

    An upload adds a name or replaces one, so a release holds the union of
    what it holds now and what the run uploads. That is an upper bound, and
    deliberately: the final prune then removes what the published manifest
    leaves unnamed, so the union overcounts by at most one run's orphans.

    Two corrections on `shards-latest`. The manifest is always there. And
    its keyword assets go, because the publish job prunes each one the
    manifest stops naming — except those `live` (the published manifest)
    names for a registry outside this run, which stay with their carried
    rows (:func:`carried_keyword_assets`). One population this cannot see
    from the plan job: a registry in this run whose build job or keyword
    export then fails is carried the same way. `RELEASE_ASSET_HEADROOM`
    absorbs those, and `prune --room-for` refuses at publish time if it
    cannot.
    """
    held = existing.get(dense_tag, {})
    dense = {n for n in held if not n.endswith(KEYWORD_SUFFIX)}
    dense |= {dense_asset_name(t) for t in taps} | {MANIFEST_ASSET}
    dense |= carried_keyword_assets(live, dense_tag, taps) & set(held)
    keyword = set(existing.get(keyword_tag, {}))
    keyword |= {keyword_asset_name(t) for t in taps}
    return {dense_tag: len(dense), keyword_tag: len(keyword)}


def live_manifest(path: str | None, assets: dict[str, dict]) -> dict | None:
    """The published manifest, if the release listing says there is one.

    The listing is the authority, not the download: no `manifest.json` on
    the release means no manifest yet (the first run), and the file is not
    read. One listed but unreadable is an error, because reading it as "no
    manifest" would drop every carried row from the projection — the same
    fail-open as reading a failed listing as an empty release.
    """
    if MANIFEST_ASSET not in assets:
        return None
    if not path:
        raise SystemExit("the release holds %s but no --live-manifest was "
                         "given" % MANIFEST_ASSET)
    manifest = _read_json(path)
    if not isinstance(manifest, dict):
        raise SystemExit("%s is not a manifest" % path)
    return manifest


def matrix_taps(matrix: str) -> list[str]:
    """The registries a plan job's matrix JSON names, in order."""
    try:
        entries = json.loads(matrix)
    except json.JSONDecodeError as exc:
        raise SystemExit("--matrix is not JSON: %s" % exc) from exc
    if not isinstance(entries, list):
        raise SystemExit("--matrix is not a list")
    return [t for entry in entries for t in str(entry).split()]


def cmd_capacity(args: argparse.Namespace) -> int:
    """Fail before any build job runs if a release would pass its ceiling."""
    taps = matrix_taps(args.matrix)
    existing = _release_args(args.release)
    live = live_manifest(args.live_manifest,
                         existing.get(args.dense_tag, {}))
    budget = RELEASE_ASSET_LIMIT - RELEASE_ASSET_HEADROOM
    projected = project_assets(taps, existing, args.dense_tag,
                               args.keyword_tag, live)
    over = []
    for tag, count in projected.items():
        print("%s: %d asset(s) after this run, of %d allowed (GitHub's %d "
              "less RELEASE_ASSET_HEADROOM %d)"
              % (tag, count, budget, RELEASE_ASSET_LIMIT,
                 RELEASE_ASSET_HEADROOM))
        if count > budget:
            over.append((tag, count))
    if over:
        for tag, count in over:
            print("::error::%s would hold %d assets, over the %d this repo "
                  "allows a release (GitHub refuses past %d). Split the "
                  "release again, or prune assets no manifest row names."
                  % (tag, count, budget, RELEASE_ASSET_LIMIT))
        return 1
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
    un.add_argument("--hosted-on", metavar="TAG", default=None,
                    help="only rows whose asset is on this release tag count "
                         "as unchanged (default: any)")
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
    mf.add_argument("--keyword-tag", default=None, metavar="TAG",
                    help="release tag hosting the keyword shards (default: "
                         "--tag; shards.yml passes %s)" % KEYWORD_TAG)
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

    sp = sub.add_parser("splice",
                        help="an interim manifest: one manifest's dense rows "
                             "with another's keyword section")
    sp.add_argument("--dense", required=True, metavar="PREV.json",
                    help="the manifest whose dense rows to keep (the live one)")
    sp.add_argument("--keyword", required=True, metavar="NEW.json",
                    help="the manifest whose keyword section to take")
    sp.add_argument("--out", required=True, metavar="FILE")
    sp.set_defaults(func=cmd_splice)

    vf = sub.add_parser("verify",
                        help="drop rows whose asset a release listing does "
                             "not hold at the recorded size")
    vf.add_argument("--manifest", required=True, metavar="FILE")
    vf.add_argument("--release", action="append", metavar="TAG=FILE",
                    help="a `gh api repos/O/R/releases/tags/TAG` document "
                         "(repeatable); a row on an unlisted tag is dropped")
    vf.add_argument("--out", metavar="FILE",
                    help="where to write the result (default: in place)")
    vf.add_argument("--only", choices=("dense", "keyword"), default=None,
                    help="check one section and pass the other through — "
                         "the interim manifest re-publishes the live dense "
                         "rows, so only its keyword section is new")
    vf.set_defaults(func=cmd_verify)

    pr = sub.add_parser("prune",
                        help="list `id name` of assets the published manifest "
                             "does not name")
    pr.add_argument("--manifest", required=True, metavar="FILE",
                    help="the manifest as PUBLISHED")
    pr.add_argument("--tag", required=True, help="the release to prune")
    pr.add_argument("--release-json", required=True, metavar="FILE",
                    help="`gh api repos/O/R/releases/tags/TAG` for --tag")
    pr.add_argument("--suffix", required=True,
                    help="only assets ending in this, e.g. %s" % KEYWORD_SUFFIX)
    pr.add_argument("--room-for", nargs="*", default=None, metavar="FILE",
                    help="list only enough for these uploads to fit under "
                         "the asset limit (fails if that is not possible)")
    pr.add_argument("--bounded", action="store_true",
                    help="refuse, listing nothing, if over MAX_DROP_FRACTION "
                         "(%d%%%%) of the release's --suffix assets are "
                         "unnamed" % (MAX_DROP_FRACTION * 100))
    pr.add_argument("--out", metavar="FILE",
                    help="write the list here instead of stdout")
    pr.set_defaults(func=cmd_prune)

    cp = sub.add_parser("capacity",
                        help="fail if a planned run would overfill a release")
    cp.add_argument("--matrix", required=True, metavar="JSON",
                    help="the plan job's matrix: a JSON list of "
                         "space-separated registry lists")
    cp.add_argument("--release", action="append", metavar="TAG=FILE",
                    help="what a release holds now (repeatable); a "
                         "release that does not exist yet is "
                         "'{\"assets\": []}', and anything without an "
                         "`assets` list is refused")
    cp.add_argument("--live-manifest", metavar="FILE", default=None,
                    help="the published manifest; required when the "
                         "--dense-tag listing holds %s" % MANIFEST_ASSET)
    cp.add_argument("--dense-tag", default=DEFAULT_TAG)
    cp.add_argument("--keyword-tag", default=KEYWORD_TAG)
    cp.set_defaults(func=cmd_capacity)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
