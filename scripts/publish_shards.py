#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Turn exported vector shards into something a stranger can download.

Three subcommands, matching the three halves of publishing:

    publish_shards.py export --out DIR [--tap owner/repo ...]
        Export every tapped registry's vectors from THIS machine's store.
        Run it where the embeddings already exist — that is the whole point of
        a shard, and re-embedding to publish would defeat it.

    publish_shards.py unchanged --manifest-url URL --out FILE
        Which tapped registries are already published at the commit they are
        at now. Run it after tapping and BEFORE embedding: every registry it
        lists can be untapped, and the embed pass costs only what moved.

    publish_shards.py manifest --shard-dir DIR --repo owner/repo [--tag TAG]
                              [--carry-forward PREV.json --unchanged FILE...]
        Digest the shards in DIR and write the manifest that `core.shards`
        reads: schema version, the embedding space they all share, and one row
        per shard with its registry commit, size, sha256 and download URL. With
        `--carry-forward`, rows from the previous manifest survive for the
        registries the build jobs reported unchanged — their assets are still
        on the release, byte for byte, so the old row is the right row.

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
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import dense, gitutil, registry, shards
from boost_cli.errors import BoostError

DEFAULT_TAG = "shards-latest"


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
    if manifest is not None:
        why = shards.incompatible(manifest)
        if why:
            print("published shards are not in this run's space (%s) — "
                  "embedding everything" % why, file=sys.stderr)
        else:
            commits = {t.name: (gitutil.head_commit(t.path) if t.is_cloned
                                else "")
                       for t in registry.list_taps()}
            for tap, row in shards.unchanged(manifest, commits).items():
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


def _carried_rows(prev_path: str, unchanged_files: list[str],
                  fresh_taps: set[str], space: dict | None
                  ) -> tuple[list[dict], dict | None]:
    """Rows from the previous manifest for registries reported unchanged.

    Returns ``(rows, previous_space)``. Every guard here refuses rather than
    degrades: a row is carried only for the exact commit the job saw, only
    when the previous manifest is in this run's embedding space, and never
    for a registry a fresh shard already describes.
    """
    try:
        prev = json.loads(Path(prev_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("previous manifest unreadable (%s) — carrying nothing forward"
              % exc, file=sys.stderr)
        return [], None
    prev_space = _space(prev)
    if space is not None and prev_space != space:
        print("previous manifest is %s, this run is %s — carrying nothing "
              "forward" % (_fmt_space(prev_space), _fmt_space(space)),
              file=sys.stderr)
        return [], prev_space
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
    index = shards.rows(prev)
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
    return out, prev_space


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
    if args.carry_forward:
        old, prev_space = _carried_rows(args.carry_forward, args.unchanged,
                                        {r["tap"] for r in rows}, first)
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
    dest = Path(args.out)
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(int(r.get("chunks") or 0) for r in rows)
    print("manifest: %d shard(s) (%d fresh, %d carried forward), %s chunks, "
          "%s -> %s" % (len(rows), len(rows) - carried, carried,
                        format(total, ","), _fmt_space(first), dest))
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
    un.set_defaults(func=cmd_unchanged)

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
    mf.set_defaults(func=cmd_manifest)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
