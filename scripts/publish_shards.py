#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Turn exported vector shards into something a stranger can download.

Two subcommands, matching the two halves of publishing:

    publish_shards.py export --out DIR [--tap owner/repo ...]
        Export every tapped registry's vectors from THIS machine's store.
        Run it where the embeddings already exist — that is the whole point of
        a shard, and re-embedding to publish would defeat it.

    publish_shards.py manifest --shard-dir DIR --repo owner/repo [--tag TAG]
        Digest the shards in DIR and write the manifest that `core.shards`
        reads: schema version, the embedding space they all share, and one row
        per shard with its registry commit, size, sha256 and download URL.

WHY THE MANIFEST IS GENERATED AND NOT WRITTEN BY HAND. Three of its fields are
load-bearing at import time and unguessable: `sha256` is what makes a download
verifiable, `commit` is what stops a stale shard being merged, and
`provider`/`model`/`dim` are what stop vectors from two different embedding
spaces being mixed into one store — a failure that does not raise, it just
returns nonsense rankings.

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

from boost_cli.core import dense, registry
from boost_cli.errors import BoostError

DEFAULT_TAG = "shards-latest"


def _safe(tap: str) -> str:
    return tap.replace("/", "__")


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


def _row(path: Path, repo: str, tag: str) -> tuple[dict, dict]:
    """One manifest row plus the embedding space its shard was built in."""
    raw = path.read_bytes()
    shard = json.loads(raw.decode("utf-8"))
    missing = [k for k in ("tap", "commit", "provider", "model", "dim")
               if not shard.get(k)]
    if missing:
        raise SystemExit("%s is missing %s" % (path.name, ", ".join(missing)))
    space = {k: shard[k] for k in ("provider", "model", "dim")}
    row = {
        "tap": shard["tap"],
        "commit": shard["commit"],
        "chunks": len(shard.get("chunks") or []),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "url": "https://github.com/%s/releases/download/%s/%s"
               % (repo, tag, path.name),
    }
    return row, space


def cmd_manifest(args: argparse.Namespace) -> int:
    """Digest a directory of shards into one manifest.json."""
    shard_dir = Path(args.shard_dir)
    paths = sorted(shard_dir.glob("*.shard.json"))
    if not paths:
        print("no *.shard.json under %s" % shard_dir, file=sys.stderr)
        return 1
    rows, spaces = [], []
    for path in paths:
        row, space = _row(path, args.repo, args.tag)
        rows.append(row)
        spaces.append(space)
    first = spaces[0]
    for path, space in zip(paths, spaces, strict=True):
        if space != first:
            # Refuse rather than publish a manifest whose top-level space is a
            # lie for some of its rows: `core.shards.incompatible` reads that
            # one header to decide whether to download anything at all.
            raise SystemExit(
                "%s is %s/%s/%sd but the others are %s/%s/%sd — publish one "
                "embedding space per manifest"
                % (path.name, space["provider"], space["model"], space["dim"],
                   first["provider"], first["model"], first["dim"]))
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
    total = sum(r["chunks"] for r in rows)
    print("manifest: %d shard(s), %s chunks, %s/%s/%sd -> %s"
          % (len(rows), format(total, ","), first["provider"], first["model"],
             first["dim"], dest))
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

    mf = sub.add_parser("manifest", help="write manifest.json for a shard dir")
    mf.add_argument("--shard-dir", required=True, metavar="DIR")
    mf.add_argument("--repo", required=True, metavar="OWNER/REPO",
                    help="repo whose release hosts the assets")
    mf.add_argument("--tag", default=DEFAULT_TAG,
                    help="release tag hosting the assets (default: %(default)s)")
    mf.add_argument("--out", default="manifest.json", metavar="FILE")
    mf.set_defaults(func=cmd_manifest)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
