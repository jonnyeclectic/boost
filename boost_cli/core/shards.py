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
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import suppress
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


def _read_capped(resp, cap: int) -> bytes:
    """Read the whole response, stopping once it exceeds `cap` bytes.

    THE LOOP IS THE POINT. ``HTTPResponse.read(amt)`` returns *up to* `amt`
    bytes, not `amt` bytes, and over a real connection it routinely returns
    less — one read of the live 166 KB manifest came back with 131,072 bytes
    on one run and 146,547 on the next. A single ``resp.read(cap + 1)``
    therefore handed a truncated document to ``json.loads``, which reported it
    as "not valid JSON": a network artefact wearing the costume of a corrupt
    publish, on every command that reads the manifest.

    The unit suite could not see it, and still cannot without help: its
    fixtures are ``file:`` URLs, where one read does return the whole file.
    ``tests/unit/test_shards.py`` covers this with a response that short-reads
    on purpose.

    Reading `cap + 1` in total keeps the size check that follows honest — one
    byte over the ceiling is enough to fail it, and nothing larger is buffered.
    """
    chunks: list[bytes] = []
    total = 0
    while total <= cap:
        buf = resp.read(min(_CHUNK, cap + 1 - total))
        if not buf:
            break
        chunks.append(buf)
        total += len(buf)
    return b"".join(chunks)


def _verify_complete(resp, raw: bytes, url: str) -> None:
    """Refuse a body that arrived shorter than the server said it would.

    ``read(amt)`` performs no length check — that is done only by ``read()``
    with no argument — so a connection cut mid-stream returns a short body and
    then a clean EOF. The truncated document reaches ``json.loads``, which
    calls it "not valid JSON", and the user goes looking for a corrupt publish
    that does not exist. Observed here against the live 166,210-byte manifest:
    a read returned 146,547 bytes and the next returned nothing.

    The Content-Encoding guard is not defensive padding. ``Content-Length``
    describes the bytes ON THE WIRE, so against a gzipping proxy it is the
    compressed size while `raw` is the decoded body — comparing the two would
    manufacture a truncation failure, which is the same class of bug this
    function exists to remove. A missing or unparseable header means the
    question cannot be answered and is left alone.
    """
    enc = (resp.headers.get("Content-Encoding") or "").strip().lower()
    if enc and enc != "identity":
        return
    try:
        want = int(resp.headers.get("Content-Length"))
    except (TypeError, ValueError):
        return
    if len(raw) < want:
        raise BoostError(
            "shard manifest download from %s was truncated (%d of %d bytes)"
            % (url, len(raw), want),
            hint="a proxy or a dropped connection cut the stream — retry")


def fetch_manifest(url: str | None = None, timeout: float = 30.0) -> dict:
    """Download and validate the shard manifest.

    Validation is not politeness: every field below is later used to decide
    whether a download is worth making or a shard is safe to import, and a
    manifest that omits one would fail at whichever later step first noticed —
    after the download, in the worst case.
    """
    url = url or manifest_url()
    with _open(url, timeout) as resp:
        raw = _read_capped(resp, MAX_MANIFEST_BYTES)
        # Size ceiling first, completeness second: a manifest larger than the
        # cap is also "shorter than declared", and reporting that one as a
        # truncated download would name the wrong problem.
        if len(raw) > MAX_MANIFEST_BYTES:
            raise BoostError("shard manifest at %s is implausibly large" % url)
        _verify_complete(resp, raw, url)
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


def unchanged(manifest: dict, commits: dict[str, str]) -> dict[str, dict]:
    """Manifest rows that already describe the commit each tap is at now.

    This is what lets a weekly shard run skip most of its own work. Every run
    used to embed every registry from scratch — ~9 job-hours for the catalogue
    — on ephemeral runners with no memory of last week, and registries move
    slowly, so most of that bought the same vectors again. The manifest pins
    the commit each shard was built from, so "has this one moved?" is one
    comparison, and a registry that has not keeps last week's row.

    Same rule that makes a shard importable at all: reuse only for the EXACT
    commit the row describes. An empty local commit is a tap whose clone
    failed, not a match — that registry is embedded, never skipped. The
    embedding-space check is the caller's (:func:`incompatible`), because a
    manifest from another space reuses nothing however fresh its commits.
    """
    index = rows(manifest)
    out: dict[str, dict] = {}
    for tap, commit in commits.items():
        row = index.get(tap)
        if row is None or not commit:
            continue
        if str(row.get("commit")) == commit:
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
#: "imported" (vectors landed), "current" (store already holds this exact
#: commit's vectors, nothing downloaded), "unpublished" (no row for this tap),
#: "refused" (row existed, import said no — commit or space mismatch),
#: "failed" (download or verification error).
def sync(taps: list[str], commits: dict[str, str],
         manifest: dict | None = None, cache_dir: Path | None = None,
         on_event=None, built: dict[str, str] | None = None) -> list[dict]:
    """Download and import a published shard for each of `taps`.

    `commits` maps tap name -> the commit this machine has it at, which is what
    ``dense.import_shard`` validates against. Passing it in rather than reading
    it here keeps this function testable without a tap on disk, and keeps the
    "which commit" question answered in exactly one place per caller.

    `built` maps tap name -> the commit the vector store already holds for it
    (``dense.tap_commits()``), same triple-equality short-circuit as
    :func:`ingest`: a tap already at the manifest row's commit *with vectors
    already built there* skips the download entirely and reports "current".
    Omit it (the default) to keep the old always-download behaviour — the
    right choice for a caller like `pkg._resync_vectors` where the tap just
    moved and a fresh shard is exactly what is wanted.

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
    built = built or {}
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
        want = str(row.get("commit") or "")
        if want and local == want == built.get(tap, ""):
            results.append({"tap": tap, "status": "current"})
            _emit(on_event, tap, "current", "")
            continue
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
    if any(r["status"] == "imported" for r in results):
        # Stamped here as well as in `ingest`, because this is the path a new
        # machine takes: `boost quickstart` imports through `sync`, so without
        # this the marker stays unset for exactly the users the staleness hint
        # is written for, and the one surface that teaches `boost update
        # --shards` exists would never fire on the onboarding path.
        mark_synced()
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


#: How long published vectors may go un-ingested before `boost search` says so.
#: The publish cadence is weekly, so this is two missed runs — a hint that fires
#: the morning after every run is one users learn to read past, and the remedy
#: it names moves taps, which is not a thing to nag anyone into hourly.
STALE_SHARDS_DAYS = 14


def mark_synced() -> None:
    """Stamp "published vectors were ingested just now"; never fails a run."""
    with suppress(OSError):
        paths.ensure_dirs()
        paths.shard_sync_marker().write_text("", encoding="utf-8")


def sync_age_days() -> float | None:
    """Days since published vectors were last ingested, or None if never.

    None is not zero and not infinity, the same distinction
    ``registry.refresh_age_days`` draws: a machine that embedded everything
    locally has never ingested a shard and must not be nagged about the age of
    something it does not use.
    """
    try:
        age = time.time() - paths.shard_sync_marker().stat().st_mtime
    except OSError:
        return None
    return max(0.0, age / 86400.0)


def ingest(taps: list[str], commits: dict[str, str],
           built: dict[str, str] | None = None, manifest: dict | None = None,
           cache_dir: Path | None = None, on_event=None,
           retarget=None) -> list[dict]:
    """Bring `taps` to the state the published manifest describes.

    WHICH SIDE IS AUTHORITATIVE is the whole difference from :func:`sync`.
    `sync` takes this machine's commits as given and asks whether a published
    shard happens to match. That is right on the day a machine is set up, and
    wrong a week later: the weekly run republishes against whatever the
    registries have moved to, so for most taps the answer becomes "no", and the
    user is told their vectors are stale with no way to act on it but hours of
    local CPU. `ingest` reads the manifest as the *target*: a row for a tap this
    machine holds at another commit is a reason to move the tap, because the
    commit was pinned to match the vectors in the first place.

    `built` maps tap name -> the commit this machine's vector store holds for
    it (``dense.tap_commits``), and it is what makes the weekly case free: a tap
    already at the row's commit *with vectors already built there* is skipped
    without downloading anything. Passing only `commits` would re-download a
    store's own rows every week.

    ORDER IS LOAD-BEARING: download and verify the bytes, and only then move the
    tap. Moving first and failing the download leaves the clone on a commit
    whose vectors are stale but still present — the failure that looks like
    nothing at all, and the one this module exists to refuse. `retarget` is
    injected so the ordering can be tested without a git remote; it defaults to
    ``registry.retarget``.

    Never raises for one tap. A registry that dropped out of the manifest is
    reported "unpublished" and left pinned exactly where it sits — falling back
    to moving it to HEAD would be inventing a target no vectors describe.
    """
    from . import dense
    manifest = manifest if manifest is not None else fetch_manifest()
    why = incompatible(manifest)
    if why:
        return [{"tap": t, "status": "incompatible", "detail": why,
                 "moved": False} for t in taps]
    if retarget is None:
        from . import registry
        retarget = registry.retarget
    index = rows(manifest)
    cache_dir = cache_dir or (paths.cache_dir() / "shards")
    built = built or {}
    results: list[dict] = []
    for tap in taps:
        row = index.get(tap)
        if row is None:
            results.append({"tap": tap, "status": "unpublished", "moved": False})
            _emit(on_event, tap, "unpublished", "")
            continue
        want = str(row.get("commit") or "")
        local = commits.get(tap, "")
        if want and local == want == built.get(tap, ""):
            results.append({"tap": tap, "status": "current", "moved": False})
            _emit(on_event, tap, "current", "")
            continue
        dest = cache_dir / (tap.replace("/", "__") + ".shard.json")
        moved = False
        try:
            _emit(on_event, tap, "downloading", _size_label(row))
            download(row, dest, manifest)
            shard = json.loads(dest.read_text(encoding="utf-8"))
            if local != want:
                _emit(on_event, tap, "moving", want[:7])
                retarget(tap, want)
                moved = True
            ok, reason = dense.import_shard(shard, commit=want)
        except BoostError as exc:
            results.append({"tap": tap, "status": "failed", "moved": moved,
                            "detail": exc.message})
            _emit(on_event, tap, "failed", exc.message)
            continue
        except (OSError, json.JSONDecodeError) as exc:
            results.append({"tap": tap, "status": "failed", "moved": moved,
                            "detail": str(exc)})
            _emit(on_event, tap, "failed", str(exc))
            continue
        finally:
            # The shard is a transfer format, not a cache — see `sync`.
            dest.unlink(missing_ok=True)
        status = "imported" if ok else "failed"
        results.append({"tap": tap, "status": status, "detail": reason,
                        "moved": moved, "chunks": int(row.get("chunks") or 0)})
        _emit(on_event, tap, status, reason)
    if any(r["status"] in ("imported", "current") for r in results):
        # Stamped for "the manifest was read and acted on", not for "something
        # changed": a run where every tap was already current is the successful
        # weekly case, and leaving the marker cold would make search nag about
        # vectors refreshed this morning.
        mark_synced()
    return results
