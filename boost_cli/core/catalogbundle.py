"""A portable catalogue bundle: everything `boost tap` produces, minus the clone.

WHY THIS EXISTS. `boost tap --defaults` is the slowest thing a new install does,
and almost none of the cost is the part anyone needs. Measured on a real
machine with **459 registries tapped**: the shallow clones are **12 GB**, while
the catalogue they produce — the JSON boost actually searches — is **101.1 MB**,
and **11.1 MB** gzipped. Search works from that catalogue with no clone present
at all.

So the expensive artifact is not the valuable one, and the valuable one fits in
an email. This module packs it.

WHAT IS DELIBERATELY NOT IN IT.

* The **derived indexes**. `rag_index.json`, `rag_postings.sqlite` and
  `rag_vectors.sqlite` are 3.8 GB of that machine's 3.9 GB cache directory, and
  they rebuild from the catalogue in seconds. Vectors additionally are only
  meaningful inside the embedding space that produced them, which is why
  `dense.export_shard` carries provider/model/dim/commit and `import_shard`
  refuses a mismatch. This format carries none of that and must not pretend to:
  shards are the reviewed path for vectors.
* The **repositories**. A bundle makes a catalogue searchable, not installable —
  `install` copies files out of a clone. Every tap's URL rides in the manifest
  precisely so the receiving machine can clone the one repo it ends up wanting,
  instead of all 459 up front.

The archive is a gzipped tar of `manifest.json` plus `catalog/<safe_name>.json`,
one per tap, byte-identical to what `catalog.build_cache` wrote.

SECURITY. A bundle is a file people send each other, which makes it untrusted
input in the most ordinary way there is, and tar member names are the classic
path-traversal vector. Extraction here never lets the archive choose a
destination: member names are validated, then the bytes are written to a path
this module builds from the basename. See `_safe_members`.
"""
from __future__ import annotations

import json
import tarfile
import time
from pathlib import Path

from ..errors import BoostError
from . import config, paths, registry

#: Bump when the layout changes incompatibly. An importer that cannot say what
#: it is looking at cannot refuse anything.
BUNDLE_FORMAT = 1

MANIFEST_NAME = "manifest.json"
#: Every catalogue file lives under this prefix; anything else is refused.
CATALOG_PREFIX = "catalog/"

#: Caps, so a hostile archive cannot exhaust the disk. Both are generous
#: against real data — the 459-tap export is 460 members and its largest
#: catalogue file is 14 MB — and both are monkeypatched low in the tests,
#: because a limit nothing ever reaches is a limit nothing has tested.
MAX_MEMBERS = 5000
MAX_MEMBER_BYTES = 256 * 1024 * 1024

def export_bundle(dest: Path) -> dict:
    """Pack every tapped registry's catalogue into ``dest``. Returns stats.

    Driven by the **tap list**, not by a scan of the cache directory, and that
    is what keeps the derived indexes out rather than any filename filter: a
    file only becomes a candidate by being named ``<safe_name>.json`` for a
    configured tap, so ``rag_vectors.sqlite`` is never considered in the first
    place. It also means a stale catalogue left behind by an untapped registry
    is not exported. An earlier revision carried an ``_is_catalogue_file``
    predicate for this and never called it — dead code that made the
    accompanying test pass for a reason that had nothing to do with the filter.

    A configured tap with no cache file yet is **skipped, not fatal**: taps are
    built one at a time, and refusing to export the other 458 because one is
    mid-build would make this unusable exactly when it is most wanted. The
    skipped names come back in the stats so the caller can say so.

    Exporting nothing raises instead, because an empty bundle is
    indistinguishable from a working one until someone imports it.
    """
    dest = Path(dest)
    taps = registry.list_taps()
    packed: list[dict] = []
    skipped: list[str] = []
    entries = 0

    for tap in taps:
        cache_file = paths.cache_dir() / ("%s.json" % tap.safe_name)
        if not cache_file.is_file():
            skipped.append(tap.name)
            continue
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(tap.name)
            continue
        count = len(data.get("skills") or [])
        entries += count
        packed.append({"name": tap.name, "url": tap.url,
                       "curated": tap.curated,
                       "commit": str(data.get("commit") or ""),
                       "entries": count,
                       "file": "%s.json" % tap.safe_name})

    if not packed:
        raise BoostError(
            "nothing to export — no tapped registry has a built catalogue",
            hint="tap a registry first, e.g. `boost tap --defaults`")

    manifest = {
        "format": BUNDLE_FORMAT,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "taps": packed,
        "entries": entries,
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(dest, "w:gz") as tar:
            _add_bytes(tar, MANIFEST_NAME,
                       json.dumps(manifest, indent=1).encode("utf-8"))
            for row in packed:
                src = paths.cache_dir() / row["file"]
                tar.add(str(src), arcname=CATALOG_PREFIX + row["file"])
    except OSError as exc:
        raise BoostError("cannot write bundle %s: %s" % (dest, exc)) from exc

    return {"path": str(dest), "taps": len(packed), "entries": entries,
            "skipped": skipped, "bytes": dest.stat().st_size}


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    """Add an in-memory file to ``tar`` (used for the manifest)."""
    import io
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0          # reproducible: same catalogue, same bytes
    tar.addfile(info, io.BytesIO(data))


def read_manifest(src: Path) -> dict:
    """The manifest of ``src``, without extracting anything else."""
    src = Path(src)
    if not src.is_file():
        raise BoostError("no such bundle: %s" % src)
    try:
        with tarfile.open(src, "r:gz") as tar:
            member = tar.getmember(MANIFEST_NAME)
            if not member.isfile():
                raise BoostError("bundle manifest is not a file: %s" % src)
            handle = tar.extractfile(member)
            if handle is None:
                raise BoostError("bundle manifest is unreadable: %s" % src)
            return json.loads(handle.read().decode("utf-8"))
    except KeyError as exc:
        raise BoostError(
            "%s is not a boost catalogue bundle (no %s)" % (src, MANIFEST_NAME),
            hint="create one with `boost catalog --export <file>`") from exc
    except (tarfile.TarError, OSError) as exc:
        raise BoostError("cannot read bundle %s: %s" % (src, exc)) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BoostError("bundle manifest is malformed: %s" % exc) from exc


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """The catalogue members of ``tar``, or raise naming what was rejected.

    The archive never chooses a destination. A member is accepted only when it
    is a regular file directly under ``catalog/`` whose name is a plain
    basename — no separators, no ``..``, no leading ``/``, no symlink or device
    entry — and the caller then writes it to a path built from that basename.
    Validating the name and *also* discarding it is deliberate: a check that
    feeds its input forward is one refactor away from being decorative.
    """
    members = tar.getmembers()
    if len(members) > MAX_MEMBERS:
        raise BoostError(
            "bundle has %d members, over the %d cap"
            % (len(members), MAX_MEMBERS),
            hint="this is not a catalogue export — check where it came from")

    picked: list[tarfile.TarInfo] = []
    for member in members:
        if member.name == MANIFEST_NAME:
            continue
        if not member.isfile():
            # Symlinks and hardlinks are how an archive writes outside its own
            # tree without any name containing "..".
            raise BoostError(
                "bundle contains a non-regular entry: %s" % member.name,
                hint="a catalogue bundle holds only JSON files")
        if not member.name.startswith(CATALOG_PREFIX):
            raise BoostError(
                "bundle contains an entry outside %s: %s"
                % (CATALOG_PREFIX, member.name))
        leaf = member.name[len(CATALOG_PREFIX):]
        if (not leaf or leaf != Path(leaf).name or leaf.startswith(".")
                or "/" in leaf or "\\" in leaf or not leaf.endswith(".json")):
            raise BoostError(
                "bundle contains an unsafe member name: %s" % member.name)
        if member.size > MAX_MEMBER_BYTES:
            raise BoostError(
                "bundle member %s is %d bytes, over the %d cap"
                % (member.name, member.size, MAX_MEMBER_BYTES))
        picked.append(member)
    return picked


def import_bundle(src: Path) -> dict:
    """Restore a catalogue bundle into this machine. Returns stats.

    **Merges, never replaces.** The receiving machine may already have taps of
    its own, and silently dropping them would be a worse outcome than the slow
    tap this feature exists to avoid. A tap already configured keeps its
    existing entry; its catalogue file is overwritten, which is the point.
    """
    src = Path(src)
    manifest = read_manifest(src)

    fmt = manifest.get("format")
    if fmt != BUNDLE_FORMAT:
        raise BoostError(
            "bundle format %r is not supported (this boost reads %d)"
            % (fmt, BUNDLE_FORMAT),
            hint="upgrade boost, or re-export the bundle with this version")

    paths.ensure_dirs()
    written = 0
    try:
        with tarfile.open(src, "r:gz") as tar:
            members = _safe_members(tar)
            for member in members:
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                leaf = Path(member.name).name
                # The destination is built here, from the basename, so the
                # archive cannot influence it even if a check above is wrong.
                target = paths.cache_dir() / leaf
                target.write_bytes(handle.read(MAX_MEMBER_BYTES + 1))
                written += 1
    except (tarfile.TarError, OSError) as exc:
        raise BoostError("cannot read bundle %s: %s" % (src, exc)) from exc

    cfg = config.load()
    existing = cfg.get("taps") or []
    if not isinstance(existing, list):
        existing = []
    known = {t.get("name") for t in existing if isinstance(t, dict)}
    added = 0
    for row in manifest.get("taps") or []:
        name = row.get("name")
        if not name or name in known:
            continue
        existing.append({"name": name, "url": row.get("url", ""),
                         "curated": bool(row.get("curated"))})
        known.add(name)
        added += 1
    cfg["taps"] = existing
    config.save(cfg)

    return {"path": str(src), "taps": len(manifest.get("taps") or []),
            "added": added, "files": written,
            "entries": int(manifest.get("entries") or 0),
            "generated": manifest.get("generated", "")}
