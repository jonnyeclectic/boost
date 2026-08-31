# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Published shards: the manifest contract, and refusing rather than degrading.

A shard moves vectors between machines, so every check in `core.shards` exists
because the alternative failure is silent. Mixing two embedding spaces does not
raise — it returns wrong rankings. Importing a shard for a commit the tap has
moved past does not raise either — it makes `dense.build` mark that tap
"reused" and pins the user to stale vectors. A corrupt download imports as
noise. So the tests here are mostly about what is *refused*, and where: the
space and commit checks have to happen before the download, or a user pays 129
MB to be told no.

The fixtures are plain dicts and `file:` URLs. `download` is exercised for
real — it is the function with a digest, a size ceiling and an origin check in
it, and mocking urlopen would test none of them.
"""
import contextlib
import json
import sqlite3

import pytest

from boost_cli.core import shards
from boost_cli.errors import BoostError

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}


def _shard_file(tmp_path, tap, commit):
    """A shard on disk, and the manifest row that describes it."""
    body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                       "chunks": [{"name": "x", "tap": tap, "path": "p",
                                   "kind": "skill", "cix": 0, "snip": "s",
                                   "embedding": "AAAA"}]})
    path = tmp_path / (tap.replace("/", "__") + ".shard.json")
    path.write_text(body, encoding="utf-8")
    import hashlib
    return path, {"tap": tap, "commit": commit, "chunks": 1,
                  "bytes": len(body.encode()),
                  "sha256": hashlib.sha256(body.encode()).hexdigest(),
                  "url": path.as_uri()}


def _manifest(tmp_path, rows, **over):
    data = {"version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
            "shards": rows}
    data.update(over)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestFetchManifest:
    """Every field validated here is load-bearing at import time."""

    def test_reads_a_well_formed_manifest(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        path = _manifest(tmp_path, [row])
        got = shards.fetch_manifest(path.as_uri())
        assert got["provider"] == "local"
        assert got["dim"] == 384
        assert got["_url"] == path.as_uri()

    def test_a_future_schema_is_refused_by_version(self, tmp_path):
        path = _manifest(tmp_path, [], version=99)
        with pytest.raises(BoostError, match="version"):
            shards.fetch_manifest(path.as_uri())

    @pytest.mark.parametrize("field", ["provider", "model", "dim"])
    def test_a_manifest_without_its_space_is_refused(self, tmp_path, field):
        # Without these three nothing downstream can tell whether the vectors
        # are comparable with this machine's, and `incompatible` would compare
        # against None and wave everything through.
        path = _manifest(tmp_path, [], **{field: None})
        with pytest.raises(BoostError, match=field):
            shards.fetch_manifest(path.as_uri())

    def test_missing_shards_list_is_refused(self, tmp_path):
        path = _manifest(tmp_path, [])
        path.write_text(json.dumps({"version": 1, **SPACE}), encoding="utf-8")
        with pytest.raises(BoostError, match="shards"):
            shards.fetch_manifest(path.as_uri())

    def test_non_json_is_a_boost_error_not_a_traceback(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text("<html>404</html>", encoding="utf-8")
        with pytest.raises(BoostError, match="valid JSON"):
            shards.fetch_manifest(path.as_uri())

    def test_a_non_https_url_is_refused_before_urllib_sees_it(self):
        with pytest.raises(BoostError, match="refusing to fetch"):
            shards.fetch_manifest("ftp://example.com/manifest.json")

    def test_the_env_override_wins(self, monkeypatch):
        monkeypatch.setenv(shards.MANIFEST_ENV, "https://example.test/m.json")
        assert shards.manifest_url() == "https://example.test/m.json"

    def test_the_default_url_is_https_and_anonymous(self, monkeypatch):
        monkeypatch.delenv(shards.MANIFEST_ENV, raising=False)
        # A workflow artifact URL needs a token; a release asset does not. If
        # this ever points at /actions/artifacts the quickstart is broken for
        # everyone who is not logged in.
        assert shards.manifest_url().startswith("https://")
        assert "/releases/download/" in shards.manifest_url()


class TestIncompatible:
    """The pre-download gate. Answered from the manifest, never from bytes."""

    def test_matching_space_is_compatible(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        assert shards.incompatible({**SPACE}) is None

    def test_no_backend_names_the_backend_not_the_model(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: None)
        assert "backend" in shards.incompatible({**SPACE})

    def test_a_paid_provider_cannot_use_keyless_shards(self, monkeypatch):
        # The case that decides what is worth publishing: a machine holding a
        # Voyage key embeds queries at 1024-d, so 384-d keyless vectors are
        # unusable there — and it must be told before a download, not after.
        monkeypatch.setattr(shards.embed, "provider", lambda: "voyage")
        monkeypatch.setattr(shards.embed, "model", lambda: "voyage-4")
        monkeypatch.setattr(shards.embed, "dimension", lambda: 1024)
        why = shards.incompatible({**SPACE})
        assert "voyage" in why

    def test_same_provider_different_model_is_refused(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: "other/model")
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        assert "other/model" in shards.incompatible({**SPACE})

    def test_same_model_different_dim_is_refused(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 768)
        assert "768" in shards.incompatible({**SPACE})


class TestRows:
    """One malformed row must not deny a user the other forty."""

    def test_keys_by_tap(self, tmp_path):
        _, a = _shard_file(tmp_path, "a/b", "1" * 40)
        _, c = _shard_file(tmp_path, "c/d", "2" * 40)
        assert sorted(shards.rows({"shards": [a, c]})) == ["a/b", "c/d"]

    @pytest.mark.parametrize("drop", ["commit", "url", "sha256", "tap"])
    def test_a_row_missing_a_required_field_is_skipped(self, tmp_path, drop):
        _, a = _shard_file(tmp_path, "a/b", "1" * 40)
        _, c = _shard_file(tmp_path, "c/d", "2" * 40)
        del a[drop]
        assert list(shards.rows({"shards": [a, c]})) == ["c/d"]

    def test_a_non_dict_row_is_skipped(self):
        assert shards.rows({"shards": ["nonsense", None]}) == {}

    def test_no_shards_key_is_empty_not_an_error(self):
        assert shards.rows({}) == {}


class TestDownload:
    """Verification, origin pinning, and leaving nothing behind on refusal."""

    def test_a_verified_shard_lands_at_dest(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        mpath = _manifest(tmp_path, [row])
        manifest = shards.fetch_manifest(mpath.as_uri())
        dest = tmp_path / "out" / "a__b.shard.json"
        shards.download(row, dest, manifest)
        assert json.loads(dest.read_text())["tap"] == "a/b"

    def test_a_bad_digest_is_refused_and_deleted(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        manifest = shards.fetch_manifest(_manifest(tmp_path, [row]).as_uri())
        row = {**row, "sha256": "0" * 64}
        dest = tmp_path / "out" / "a__b.shard.json"
        with pytest.raises(BoostError, match="verification"):
            shards.download(row, dest, manifest)
        # Nothing partial survives: a later run must not mistake it for good.
        assert not dest.exists()
        assert not dest.with_suffix(dest.suffix + ".part").exists()

    def test_a_url_off_the_manifests_host_is_refused(self, tmp_path):
        _, row = _shard_file(tmp_path, "a/b", "1" * 40)
        mpath = _manifest(tmp_path, [row])
        manifest = shards.fetch_manifest(mpath.as_uri())
        # A manifest names the URLs boost fetches, so a tampered one must not
        # be able to widen where the fetch goes.
        row = {**row, "url": "https://evil.example/a.json"}
        with pytest.raises(BoostError, match="not on the manifest"):
            shards.download(row, tmp_path / "x.json", manifest)

    def test_size_label_reads_bytes_and_tolerates_its_absence(self):
        assert shards._size_label({"bytes": 2 * 1024 * 1024}).endswith("MB")
        assert shards._size_label({}) == ""
        assert shards._size_label({"bytes": "big"}) == ""


@pytest.mark.usefixtures("sandbox")
class TestSync:
    """Per-tap outcomes: one failure never costs another tap its vectors.

    ``sandbox`` because a successful import stamps the shard-sync marker under
    ``$HOME`` — the mtime `boost search` reads — and a test suite must not write
    into the developer's real ``~/.boost/state`` to find that out.
    """

    def _manifest_for(self, tmp_path, taps):
        rows = [_shard_file(tmp_path, tap, commit)[1] for tap, commit in taps]
        path = _manifest(tmp_path, rows)
        return shards.fetch_manifest(path.as_uri())

    @pytest.fixture(autouse=True)
    def _keyless(self, monkeypatch):
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)

    def test_imports_and_reports_chunks(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "1 chunk"))
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res == [{"tap": "a/b", "status": "imported",
                        "detail": "1 chunk", "chunks": 1}]

    def test_a_moved_tap_is_refused_without_downloading(self, tmp_path,
                                                        monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        called = []
        monkeypatch.setattr(shards, "download",
                            lambda *a, **k: called.append(1))
        res = shards.sync(["a/b"], {"a/b": "9" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res[0]["status"] == "refused"
        # The point of checking the commit here as well as in `import_shard`.
        assert called == []

    def test_a_tap_with_no_published_shard_says_so(self, tmp_path):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        res = shards.sync(["z/z"], {"z/z": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert res[0]["status"] == "unpublished"

    def test_one_failure_does_not_stop_the_others(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40),
                                                 ("c/d", "2" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        real = shards.download

        def flaky(row, dest, manifest, timeout=300.0):
            if row["tap"] == "a/b":
                raise BoostError("network went away")
            return real(row, dest, manifest, timeout)

        monkeypatch.setattr(shards, "download", flaky)
        res = shards.sync(["a/b", "c/d"], {"a/b": "1" * 40, "c/d": "2" * 40},
                          manifest=manifest, cache_dir=tmp_path / "cache")
        assert [r["status"] for r in res] == ["failed", "imported"]

    def test_an_incompatible_manifest_short_circuits_every_tap(self, tmp_path,
                                                               monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 1024)
        res = shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                          cache_dir=tmp_path / "cache")
        assert [r["status"] for r in res] == ["incompatible"]

    def test_the_downloaded_json_is_deleted_after_import(self, tmp_path,
                                                         monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        cache = tmp_path / "cache"
        shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                    cache_dir=cache)
        # A shard is a transfer format; these run to hundreds of megabytes and
        # are dead weight once their rows are in the store.
        assert list(cache.glob("*.shard.json")) == []

    def test_events_are_emitted_per_tap(self, tmp_path, monkeypatch):
        manifest = self._manifest_for(tmp_path, [("a/b", "1" * 40)])
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (True, "ok"))
        seen = []
        shards.sync(["a/b"], {"a/b": "1" * 40}, manifest=manifest,
                    cache_dir=tmp_path / "cache",
                    on_event=lambda t, s, d: seen.append((t, s)))
        assert ("a/b", "downloading") in seen
        assert ("a/b", "imported") in seen


class _StreamedResponse:
    """A response whose ``read(amt)`` behaves like a socket, not like a file.

    Every other fixture in this file is a ``file:`` URL, where one ``read``
    returns the whole document — which is exactly why the suite could not see
    either failure this class reproduces. ``chunk`` caps how much any single
    read returns (a resumable short read); ``cut`` stops the body early and
    then reports EOF, the way a dropped connection does.
    """

    def __init__(self, body: bytes, chunk: int | None = None,
                 cut: int | None = None, headers: dict | None = None):
        self._body = body
        self._pos = 0
        self._chunk = chunk or len(body)
        self._cut = len(body) if cut is None else cut
        self.headers = ({"Content-Length": str(len(body))}
                        if headers is None else headers)

    def read(self, amt: int | None = None) -> bytes:
        if self._pos >= self._cut:
            return b""
        n = min(amt or len(self._body), self._chunk, self._cut - self._pos)
        out = self._body[self._pos:self._pos + n]
        self._pos += n
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _served(monkeypatch, **kw):
    """Serve a well-formed manifest through a streamed response."""
    body = json.dumps({"version": 1, **SPACE,
                       "shards": [{"tap": "a/b", "commit": "1" * 40,
                                   "url": "https://example.test/a.json",
                                   "sha256": "0" * 64}]}).encode()
    resp = _StreamedResponse(body, **kw)
    monkeypatch.setattr(shards, "_open", lambda url, timeout: resp)
    return body


class TestTruncatedManifest:
    """A body that arrives short must never be parsed as if it were whole.

    ``read(amt)`` returns *up to* amt bytes and performs no length check — that
    belongs to ``read()`` with no argument — so a single read left the JSON
    decoder to report a network artefact as "not valid JSON", pointing the user
    at a corrupt publish that does not exist.
    """

    def test_a_short_reading_stream_still_yields_the_whole_manifest(
            self, monkeypatch):
        """The loop: 32 bytes at a time must still assemble the document."""
        _served(monkeypatch, chunk=32)
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["provider"] == "local"
        assert len(got["shards"]) == 1

    def test_a_cut_stream_says_truncated_rather_than_invalid_json(
            self, monkeypatch):
        """The honest error names the network, not the publisher."""
        body = _served(monkeypatch, chunk=32, cut=40)
        with pytest.raises(BoostError) as err:
            shards.fetch_manifest("https://example.test/m.json")
        assert "truncated" in err.value.message
        # The real numbers, so the message can be acted on.
        assert "40 of %d" % len(body) in err.value.message

    def test_a_compressed_response_is_not_judged_by_content_length(
            self, monkeypatch):
        """Content-Length is the wire size; `raw` is the decoded body.

        Comparing the two behind a gzipping proxy would invent a truncation —
        the same class of bug the check exists to remove.
        """
        _served(monkeypatch, headers={"Content-Length": "999999",
                                      "Content-Encoding": "gzip"})
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["dim"] == 384

    def test_identity_encoding_is_still_checked(self, monkeypatch):
        """`identity` means unencoded, so the length still has to add up."""
        _served(monkeypatch, cut=40, headers={"Content-Length": "999999",
                                              "Content-Encoding": "identity"})
        with pytest.raises(BoostError, match="truncated"):
            shards.fetch_manifest("https://example.test/m.json")

    def test_no_content_length_is_not_a_truncation(self, monkeypatch):
        """An unanswerable question is left alone, not guessed at."""
        _served(monkeypatch, chunk=32, headers={})
        got = shards.fetch_manifest("https://example.test/m.json")
        assert got["version"] == 1

    def test_an_oversized_manifest_is_named_oversized_not_truncated(
            self, monkeypatch):
        """Order matters: too big is also 'shorter than declared'."""
        monkeypatch.setattr(shards, "MAX_MANIFEST_BYTES", 64)
        _served(monkeypatch, chunk=16)
        with pytest.raises(BoostError, match="implausibly large"):
            shards.fetch_manifest("https://example.test/m.json")


class TestStaleVersionStore:
    """A store from an older boost must be replaced, not INSERTed into.

    ``_ensure_schema`` is CREATE TABLE IF NOT EXISTS, so it cannot add a column
    to a table an older boost built. ``build`` has wiped on a version change
    since that bit it once; ``import_shard`` did not, so importing into a v2
    store failed per row with "table chunks has no column named digest" — a
    sqlite message about a column, where the honest answer is that the store
    predates this format. On a real machine that is one confusing failure per
    published shard.
    """

    def _v2_store(self, sandbox):
        """A store stamped with the previous index version."""
        from boost_cli.core import dense
        dense.db_path().parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        # v2's `chunks` has no `digest` column — that is the whole point.
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
                    " snip TEXT)")
        for k, v in (("version", "2"), ("provider", '"local"'),
                     ("model", '"BAAI/bge-small-en-v1.5"'), ("dim", "384")):
            con.execute("INSERT INTO meta (k, v) VALUES (?, ?)", (k, v))
        con.commit()
        con.close()

    def _plain_connect(self, monkeypatch):
        """Open the store without sqlite-vec.

        `_connect` loads the extension and returns None without it, so
        `import_shard` would exit at "no vector backend available" before
        reaching the decision under test. The decision itself is pure sqlite.
        Ubuntu and Windows runners carry the [rag] extra and macOS ones do not,
        so leaving this unpatched passes on two thirds of the matrix.
        """
        from boost_cli.core import dense
        monkeypatch.setattr(
            dense, "_connect",
            lambda: sqlite3.connect(str(dense.db_path())))

    def test_a_stale_version_store_is_replaced_rather_than_appended_to(
            self, sandbox, monkeypatch):
        from boost_cli.core import dense
        self._v2_store(sandbox)
        self._plain_connect(monkeypatch)
        wiped = []
        monkeypatch.setattr(dense, "_wipe", lambda con: wiped.append(1))
        # Stop after the wipe decision; the INSERT path needs sqlite-vec.
        monkeypatch.setattr(dense, "_ensure_schema",
                            lambda con, dim: (_ for _ in ()).throw(
                                _Stop()))
        with contextlib.suppress(_Stop):
            dense.import_shard({"tap": "a/b", "commit": "1" * 40,
                                "provider": "local",
                                "model": "BAAI/bge-small-en-v1.5",
                                "dim": 384, "chunks": []}, commit="1" * 40)
        assert wiped == [1]

    def test_a_matching_version_is_left_alone(self, sandbox, monkeypatch):
        """The wipe is for a format change, not for every import."""
        from boost_cli.core import dense
        self._v2_store(sandbox)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("UPDATE meta SET v = ? WHERE k = 'version'",
                    (str(dense.INDEX_VERSION),))
        con.commit()
        con.close()
        self._plain_connect(monkeypatch)
        wiped = []
        monkeypatch.setattr(dense, "_wipe", lambda con: wiped.append(1))
        monkeypatch.setattr(dense, "_ensure_schema",
                            lambda con, dim: (_ for _ in ()).throw(_Stop()))
        with contextlib.suppress(_Stop):
            dense.import_shard({"tap": "a/b", "commit": "1" * 40,
                                "provider": "local",
                                "model": "BAAI/bge-small-en-v1.5",
                                "dim": 384, "chunks": []}, commit="1" * 40)
        assert wiped == []


class _Stop(Exception):
    """Ends an import once the assertion's decision point has been reached."""


class TestReusableCommits:
    """What `dense.tap_commits` reports decides which taps `ingest` SKIPS.

    That makes a stale-version store's recorded commits actively dangerous:
    the store is about to be discarded — `build` wipes it and so does
    `import_shard` — so its rows are not vectors anyone can reuse. Reported as
    reusable, they let `ingest` skip 417 taps as "already current" and then
    wipe them on the first import, leaving a store silently missing them while
    the run reported success. Observed on a real 466-tap machine.
    """

    def _store(self, version):
        from boost_cli.core import dense
        dense.db_path().parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(dense.db_path()))
        con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT)")
        con.execute("INSERT INTO meta (k, v) VALUES ('version', ?)",
                    (str(version),))
        con.execute("INSERT INTO meta (k, v) VALUES ('commits', ?)",
                    ('{"a__b": "%s"}' % ("1" * 40),))
        con.commit()
        con.close()

    def test_a_current_store_reports_what_it_holds(self, sandbox):
        from boost_cli.core import dense
        self._store(dense.INDEX_VERSION)
        assert dense.tap_commits() == {"a__b": "1" * 40}

    def test_a_stale_version_store_reports_nothing_reusable(self, sandbox):
        """Not the commits it recorded: those vectors are about to be wiped."""
        from boost_cli.core import dense
        self._store(dense.INDEX_VERSION - 1)
        assert dense.tap_commits() == {}
