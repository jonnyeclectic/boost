# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Published dense-vector shards: the manifest, and fetching from it.

WHY. Embedding is the expensive half of the keyless tier — ~1.2 s/chunk on CPU,
so a corpus worth searching costs hours — while importing the same rows takes
0.12 s. ``core.dense`` has been able to export and import a shard since the
keyless work landed, but the two halves were only ever joined by hand: a user
had to know shards existed, find one in a workflow artifact (which needs a
GitHub token and expires at 90 days), download it, and pass the file to
``boost reindex --import-shard``. This module is the missing middle — a
manifest that says which shards exist, for which registry commit, in which
embedding space, and a verified download for one of them.

THE MANIFEST IS THE COMPATIBILITY CONTRACT. A vector only means anything
against others from the same embedding space, so ``dense.import_shard`` refuses
a shard whose provider/model/dim disagree with the store. Refusing is right, but
refusing *after* a 129 MB download is not, and the manifest exists so the answer
can be known before a byte moves: it carries the space at the top level, and
:func:`incompatible` reads it against what ``embed`` resolves here. That is also
why publishing keyless shards is the only useful choice — a shard embedded with
a paid provider's model can only be imported by someone holding that key, and
the query side would need it too.

STALENESS IS PER TAP, NOT PER MANIFEST. Each row pins the registry commit its
vectors were built from, because ``import_shard`` refuses a shard whose commit
does not match the tap on this machine — accepting it would let ``dense.build``
mark that tap "reused" and pin the user to stale vectors indefinitely. So a row
is only usable while the tap sits at that commit, which is what
``boost tap --at`` exists to arrange.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..errors import BoostError
from . import embed, paths, util

#: Where the published manifest lives. A rolling tag on boost's own repo, so
#: the URL is stable, anonymous (a workflow artifact is neither) and does not
#: move with a boost release — shards refresh on the *registries'* cadence.
DEFAULT_MANIFEST_URL = (
    "https://github.com/jonnyeclectic/boost/releases/download/"
    "shards-latest/manifest.json")

#: Env override, for testing against a local file:// or a fork's release.
MANIFEST_ENV = "BOOST_SHARD_MANIFEST"

#: Manifest schema version this build understands.
MANIFEST_VERSION = 1

#: Refuse a manifest larger than this. It is an index, not the payload: the
#: real ones are tens of KB, and an unbounded read of an attacker-controlled
#: URL is how a fetch becomes a memory exhaustion.
MAX_MANIFEST_BYTES = 8 * 1024 * 1024

#: Refuse a shard larger than this. The largest published to date is 129 MB
#: (78,095 chunks); the ceiling leaves room to grow without letting a bad
#: manifest fill a disk.
MAX_SHARD_BYTES = 2 * 1024 * 1024 * 1024

_CHUNK = 1024 * 256


def manifest_url() -> str:
    """The manifest URL in force, honouring the env override."""
    return os.environ.get(MANIFEST_ENV) or DEFAULT_MANIFEST_URL


def _open(url: str, timeout: float):
    """Open `url`, allowing only https and file:.

    ``file:`` is here for tests and for an air-gapped mirror; every other
    scheme is refused rather than handed to urllib, which speaks ftp and more.
    """
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("https", "file"):
        raise BoostError(
            "refusing to fetch a shard manifest over %r" % (scheme or "no scheme"),
            hint="shard URLs must be https (or file: for a local mirror)")
    try:
        return urllib.request.urlopen(url, timeout=timeout)  # noqa: S310  scheme checked above
    except (urllib.error.URLError, OSError) as exc:
        raise BoostError("cannot reach %s: %s" % (url, exc),
                         hint="shards are optional — `boost reindex --dense` "
                              "embeds locally instead") from exc


def fetch_manifest(url: str | None = None, timeout: float = 30.0) -> dict:
    """Download and validate the shard manifest.

    Validation is not politeness: every field below is later used to decide
    whether a download is worth making or a shard is safe to import, and a
    manifest that omits one would fail at whichever later step first noticed —
    after the download, in the worst case.
    """
    url = url or manifest_url()
    with _open(url, timeout) as resp:
        raw = resp.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise BoostError("shard manifest at %s is implausibly large" % url)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoostError("shard manifest at %s is not valid JSON: %s"
                         % (url, exc)) from exc
    if not isinstance(data, dict):
        raise BoostError("shard manifest at %s is not an object" % url)
    version = data.get("version")
    if version != MANIFEST_VERSION:
        raise BoostError(
            "shard manifest is version %r, this boost speaks %d"
            % (version, MANIFEST_VERSION),
            hint="`boost self-update` — a newer manifest needs a newer boost")
    for field in ("provider", "model", "dim"):
        if not data.get(field):
            raise BoostError("shard manifest is missing %s" % field)
    if not isinstance(data.get("shards"), list):
        raise BoostError("shard manifest has no shards list")
    data["_url"] = url
    return data


def incompatible(manifest: dict) -> str | None:
    """Why these shards cannot serve this machine, or None if they can.

    Answered from the manifest alone, before any download. The comparison is
    against what :mod:`embed` resolves *now* — not against the store — because
    the store may not exist yet, and it is the query that has to be embedded in
    the same space for the vectors to mean anything.
    """
    prov, mdl, dim = embed.provider(), embed.model(), embed.dimension()
    if prov is None:
        # No backend at all: the extra is missing. That is a different remedy
        # from a space mismatch, and `dense.fix_hint` owns the wording.
        return "no embedding backend on this machine"
    if manifest.get("provider") != prov:
        return ("published shards are %s, this machine embeds with %s"
                % (manifest.get("provider"), prov))
    if manifest.get("model") != mdl:
        return ("published shards are %s, this machine embeds with %s"
                % (manifest.get("model"), mdl))
    if int(manifest.get("dim") or 0) != int(dim or 0):
        return ("published shards are %s-dimensional, this machine embeds at %s"
                % (manifest.get("dim"), dim))
    return None


def rows(manifest: dict) -> dict[str, dict]:
    """Manifest shard rows keyed by tap name, skipping malformed ones.

    Skipping rather than raising: one bad row in a published index must not
    deny a user the other forty. A row is usable only with all four fields —
    without ``sha256`` the download cannot be verified, and without ``commit``
    the import would be refused anyway.
    """
    out: dict[str, dict] = {}
    for row in manifest.get("shards") or []:
        if not isinstance(row, dict):
            continue
        tap = str(row.get("tap") or "")
        if not tap or not all(row.get(f) for f in ("commit", "url", "sha256")):
            continue
        out[tap] = row
    return out


def _same_origin(a: str, b: str) -> bool:
    """True when two URLs share scheme+host+port.

    A manifest names the URLs boost will download, so a hostile or compromised
    manifest could otherwise point the fetch anywhere. Pinning shard URLs to
    the manifest's own origin keeps trust where the user put it — on the
    manifest URL they configured — rather than letting the document widen it.
    """
    pa, pb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    return (pa.scheme.lower(), pa.netloc.lower()) == (pb.scheme.lower(),
                                                      pb.netloc.lower())


def download(row: dict, dest: Path, manifest: dict,
             timeout: float = 300.0) -> Path:
    """Fetch one shard to `dest`, verifying its digest before returning.

    The digest is checked over the bytes actually written, and a mismatch
    deletes the file. A shard that fails verification is not "probably fine":
    it is either corrupt — in which case importing it writes nonsense vectors
    that fail silently, as wrong rankings — or substituted.
    """
    url = str(row.get("url") or "")
    origin = str(manifest.get("_url") or manifest_url())
    if not _same_origin(url, origin):
        raise BoostError(
            "shard URL %s is not on the manifest's own host" % url,
            hint="the manifest may be tampered with; fetch it from %s" % origin)
    want = str(row.get("sha256") or "").lower()
    digest = hashlib.sha256()
    size = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with _open(url, timeout) as resp, tmp.open("wb") as fh:
            while True:
                buf = resp.read(_CHUNK)
                if not buf:
                    break
                size += len(buf)
                if size > MAX_SHARD_BYTES:
                    raise BoostError("shard %s exceeds %d bytes"
                                     % (row.get("tap"), MAX_SHARD_BYTES))
                digest.update(buf)
                fh.write(buf)
        got = digest.hexdigest()
        if got != want:
            raise BoostError(
                "shard %s failed verification" % row.get("tap"),
                hint="expected sha256 %s, got %s — refusing to import it"
                     % (want[:16], got[:16]))
        tmp.replace(dest)
    finally:
        # Never leave a half-written or rejected shard where a later run could
        # mistake it for a good one.
        tmp.unlink(missing_ok=True)
    return dest


#: One shard's outcome. `status` is the vocabulary both callers render:
#: "imported" (vectors landed), "unpublished" (no row for this tap),
#: "refused" (row existed, import said no — commit or space mismatch),
#: "failed" (download or verification error).
def sync(taps: list[str], commits: dict[str, str],
         manifest: dict | None = None, cache_dir: Path | None = None,
         on_event=None) -> list[dict]:
    """Download and import a published shard for each of `taps`.

    `commits` maps tap name -> the commit this machine has it at, which is what
    ``dense.import_shard`` validates against. Passing it in rather than reading
    it here keeps this function testable without a tap on disk, and keeps the
    "which commit" question answered in exactly one place per caller.

    Never raises for one tap's failure. A shard is an optimisation over local
    embedding, so the useful behaviour when one is missing, stale or corrupt is
    to say so and leave that tap to `reindex --dense` — not to abandon the
    forty that worked.
    """
    from . import dense
    manifest = manifest if manifest is not None else fetch_manifest()
    why = incompatible(manifest)
    if why:
        return [{"tap": t, "status": "incompatible", "detail": why}
                for t in taps]
    index = rows(manifest)
    cache_dir = cache_dir or (paths.cache_dir() / "shards")
    # Annotated because the rows are not uniform: only an imported shard
    # carries `chunks`, and inference from the first append would fix the value
    # type as `str`.
    results: list[dict] = []
    for tap in taps:
        row = index.get(tap)
        if row is None:
            results.append({"tap": tap, "status": "unpublished"})
            _emit(on_event, tap, "unpublished", "")
            continue
        local = commits.get(tap, "")
        if local and str(row.get("commit")) != local:
            # Caught here as well as in `import_shard` so the download is
            # skipped rather than paid for and then thrown away.
            results.append({"tap": tap, "status": "refused",
                            "detail": "tap is at %s, shard is for %s"
                                      % (local[:7], str(row["commit"])[:7])})
            _emit(on_event, tap, "refused", "commit moved")
            continue
        dest = cache_dir / (tap.replace("/", "__") + ".shard.json")
        try:
            _emit(on_event, tap, "downloading", _size_label(row))
            download(row, dest, manifest)
            shard = json.loads(dest.read_text(encoding="utf-8"))
            ok, reason = dense.import_shard(shard, commit=local)
        except BoostError as exc:
            results.append({"tap": tap, "status": "failed",
                            "detail": exc.message})
            _emit(on_event, tap, "failed", exc.message)
            continue
        except (OSError, json.JSONDecodeError) as exc:
            results.append({"tap": tap, "status": "failed",
                            "detail": str(exc)})
            _emit(on_event, tap, "failed", str(exc))
            continue
        finally:
            # The shard is a transfer format, not a cache: once its rows are in
            # the store the JSON is dead weight, and these run to hundreds of
            # megabytes.
            dest.unlink(missing_ok=True)
        status = "imported" if ok else "refused"
        results.append({"tap": tap, "status": status, "detail": reason,
                        "chunks": int(row.get("chunks") or 0)})
        _emit(on_event, tap, status, reason)
    return results


def _emit(on_event, tap: str, status: str, detail: str) -> None:
    """Report progress if the caller asked to hear about it."""
    if on_event is not None:
        on_event(tap, status, detail)


def _size_label(row: dict) -> str:
    """Human size for a shard row, or "" when the manifest omits it."""
    size = row.get("bytes")
    if not isinstance(size, int) or size <= 0:
        return ""
    return util.human_size(size)
