# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Ingesting the weekly republish: the manifest as target state, not as luck.

``sync`` asks "does a published shard happen to match the commit this machine
has?" — the right question on setup day and the wrong one a week later, because
the weekly run republishes against whatever the registries have moved to.
``ingest`` asks it the other way round: the manifest names the commit the
vectors describe, so a tap sitting elsewhere is moved onto it.

Two properties carry the design, and both are asserted here rather than
inferred. **Order**: the bytes are downloaded and verified before the tap moves,
because a move followed by a failed download leaves vectors that are stale but
still present — the failure that looks like nothing at all. **Idempotence**: a
tap already at the published commit *with vectors built there* is skipped
without a download, which is what makes a weekly cron line cost one manifest
fetch and nothing else.
"""
import hashlib
import json

import pytest

from boost_cli.core import shards
from boost_cli.errors import BoostError

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}
A, B = "1" * 40, "2" * 40


def _boom(*_a, **_k):
    """A download that fails, without the generator-throw contortion."""
    raise BoostError("network went away")


def _shard_file(tmp_path, tap, commit):
    """A shard on disk, and the manifest row that describes it."""
    body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                       "chunks": [{"name": "x", "tap": tap, "path": "p",
                                   "kind": "skill", "cix": 0, "snip": "s",
                                   "embedding": "AAAA"}]})
    path = tmp_path / (tap.replace("/", "__") + ".shard.json")
    path.write_text(body, encoding="utf-8")
    return {"tap": tap, "commit": commit, "chunks": 1,
            "bytes": len(body.encode()),
            "sha256": hashlib.sha256(body.encode()).hexdigest(),
            "url": path.as_uri()}


def _manifest(tmp_path, taps):
    rows = [_shard_file(tmp_path, tap, commit) for tap, commit in taps]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, **SPACE, "shards": rows}),
                    encoding="utf-8")
    return shards.fetch_manifest(path.as_uri())


class _Retarget:
    """Records what would have been moved, so ordering is observable."""

    def __init__(self):
        self.calls = []

    def __call__(self, name, commit):
        self.calls.append((name, commit))


@pytest.fixture()
def keyless(monkeypatch):
    """This machine embeds in the same space the fixture manifests publish."""
    monkeypatch.setattr(shards.embed, "provider", lambda: "local")
    monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
    monkeypatch.setattr(shards.embed, "dimension", lambda: 384)


@pytest.fixture()
def imports_cleanly(monkeypatch):
    """The store accepts what it is handed; these tests are about what it is."""
    from boost_cli.core import dense
    monkeypatch.setattr(dense, "import_shard",
                        lambda shard, commit: (True, "1 chunk"))


@pytest.mark.usefixtures("sandbox", "keyless", "imports_cleanly")
class TestIngest:
    """`sandbox` is not optional here: a successful ingest stamps the sync
    marker, and without a fake ``$HOME`` these tests would write into the
    developer's real ``~/.boost/state``."""

    def test_a_tap_already_current_costs_nothing(self, tmp_path, monkeypatch):
        """The weekly no-op: same commit, and vectors already built at it."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        moved, fetched = _Retarget(), []
        monkeypatch.setattr(shards, "download",
                            lambda *a, **k: fetched.append(1))
        res = shards.ingest(["a/b"], {"a/b": A}, built={"a/b": A},
                            manifest=manifest, cache_dir=tmp_path / "c",
                            retarget=moved)
        assert res[0]["status"] == "current"
        assert res[0]["moved"] is False
        assert fetched == [] and moved.calls == []

    def test_the_same_commit_without_vectors_is_still_imported(self, tmp_path):
        """Pinned right, embedded never — the shard is exactly what is missing."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        moved = _Retarget()
        res = shards.ingest(["a/b"], {"a/b": A}, built={}, manifest=manifest,
                            cache_dir=tmp_path / "c", retarget=moved)
        assert res[0]["status"] == "imported"
        # Nothing to move: the tap is already where the vectors say it is.
        assert res[0]["moved"] is False and moved.calls == []

    def test_a_moved_registry_pulls_the_tap_onto_the_published_commit(
            self, tmp_path):
        """The case ``sync`` can only refuse, and the reason this exists."""
        manifest = _manifest(tmp_path, [("a/b", B)])
        moved = _Retarget()
        res = shards.ingest(["a/b"], {"a/b": A}, built={"a/b": A},
                            manifest=manifest, cache_dir=tmp_path / "c",
                            retarget=moved)
        assert res[0]["status"] == "imported"
        assert res[0]["moved"] is True
        assert moved.calls == [("a/b", B)]

    def test_the_tap_is_not_moved_until_the_bytes_verify(self, tmp_path,
                                                         monkeypatch):
        """Move-then-fail leaves stale-but-present vectors. Never do it."""
        manifest = _manifest(tmp_path, [("a/b", B)])
        moved = _Retarget()
        monkeypatch.setattr(shards, "download", _boom)
        res = shards.ingest(["a/b"], {"a/b": A}, built={"a/b": A},
                            manifest=manifest, cache_dir=tmp_path / "c",
                            retarget=moved)
        assert res[0]["status"] == "failed"
        assert res[0]["moved"] is False
        assert moved.calls == []

    def test_a_tap_that_left_the_manifest_is_left_where_it_sits(self, tmp_path):
        """Never fall back to HEAD: no published vectors describe that tree."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        moved = _Retarget()
        res = shards.ingest(["z/z"], {"z/z": A}, built={}, manifest=manifest,
                            cache_dir=tmp_path / "c", retarget=moved)
        assert res[0]["status"] == "unpublished"
        assert moved.calls == []

    def test_a_refusing_import_after_a_move_is_reported_failed(self, tmp_path,
                                                               monkeypatch):
        """``ok=False`` is not a quiet success — the vectors did not land."""
        from boost_cli.core import dense
        manifest = _manifest(tmp_path, [("a/b", B)])
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit: (False, "dim mismatch"))
        res = shards.ingest(["a/b"], {"a/b": A}, built={}, manifest=manifest,
                            cache_dir=tmp_path / "c", retarget=_Retarget())
        assert res[0]["status"] == "failed"
        assert res[0]["detail"] == "dim mismatch"

    def test_an_incompatible_space_moves_nothing(self, tmp_path, monkeypatch):
        """Refused before the download, and therefore before the checkout."""
        manifest = _manifest(tmp_path, [("a/b", B)])
        monkeypatch.setattr(shards.embed, "provider", lambda: "voyage")
        moved = _Retarget()
        res = shards.ingest(["a/b"], {"a/b": A}, manifest=manifest,
                            cache_dir=tmp_path / "c", retarget=moved)
        assert res[0]["status"] == "incompatible"
        assert moved.calls == []

    def test_one_failure_never_costs_another_tap_its_vectors(self, tmp_path,
                                                             monkeypatch):
        manifest = _manifest(tmp_path, [("a/b", A), ("c/d", B)])
        real = shards.download

        def flaky(row, dest, manifest, timeout=300.0):
            if row["tap"] == "a/b":
                raise BoostError("network went away")
            return real(row, dest, manifest, timeout)

        monkeypatch.setattr(shards, "download", flaky)
        res = shards.ingest(["a/b", "c/d"], {"a/b": A, "c/d": A}, built={},
                            manifest=manifest, cache_dir=tmp_path / "c",
                            retarget=_Retarget())
        assert [r["status"] for r in res] == ["failed", "imported"]

    def test_the_shard_json_does_not_survive_the_import(self, tmp_path):
        """Hundreds of megabytes of transfer format, deleted once merged."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        cache = tmp_path / "c"
        shards.ingest(["a/b"], {"a/b": A}, built={}, manifest=manifest,
                      cache_dir=cache, retarget=_Retarget())
        assert list(cache.glob("*.shard.json")) == []

    def test_the_event_stream_names_the_move(self, tmp_path):
        """The command layer renders these; a silent move is an unexplained wait."""
        manifest = _manifest(tmp_path, [("a/b", B)])
        seen = []
        shards.ingest(["a/b"], {"a/b": A}, built={}, manifest=manifest,
                      cache_dir=tmp_path / "c", retarget=_Retarget(),
                      on_event=lambda t, s, d: seen.append(s))
        assert seen == ["downloading", "moving", "imported"]


@pytest.mark.usefixtures("keyless")
class TestSyncMarker:
    """The offline half: search reads an mtime, and never the network."""

    def test_a_machine_that_never_ingested_reports_none_not_zero(self, sandbox):
        """None and 0.0 mean opposite things to the hint that reads this."""
        assert shards.sync_age_days() is None

    def test_marking_makes_the_age_readable(self, sandbox):
        shards.mark_synced()
        age = shards.sync_age_days()
        assert age is not None and age < 1

    @pytest.mark.usefixtures("imports_cleanly")
    def test_an_all_current_run_still_stamps_the_marker(self, sandbox,
                                                       tmp_path):
        """The successful weekly case changes nothing and must not read stale."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        shards.ingest(["a/b"], {"a/b": A}, built={"a/b": A}, manifest=manifest,
                      cache_dir=tmp_path / "c", retarget=_Retarget())
        assert shards.sync_age_days() is not None

    def test_a_run_where_nothing_landed_leaves_the_marker_cold(
            self, sandbox, tmp_path, monkeypatch):
        """Otherwise a week of failures reads as a week of fresh vectors."""
        manifest = _manifest(tmp_path, [("a/b", A)])
        monkeypatch.setattr(shards, "download", _boom)
        shards.ingest(["a/b"], {"a/b": A}, built={}, manifest=manifest,
                      cache_dir=tmp_path / "c", retarget=_Retarget())
        assert shards.sync_age_days() is None

    @pytest.mark.usefixtures("imports_cleanly")
    def test_sync_stamps_it_too_because_quickstart_goes_through_sync(
            self, sandbox, tmp_path):
        """Otherwise the hint never fires for the users it was written for.

        A new machine gets its vectors from `boost quickstart`, which imports
        through `sync`, not `ingest`. Stamping only in `ingest` would leave the
        marker unset for life on the onboarding path — and the marker is the
        only thing that ever tells that user `boost update --shards` exists.
        """
        manifest = _manifest(tmp_path, [("a/b", A)])
        shards.sync(["a/b"], {"a/b": A}, manifest=manifest,
                    cache_dir=tmp_path / "c")
        assert shards.sync_age_days() is not None

    def test_stale_is_two_missed_weekly_runs(self):
        """A hint firing the morning after every publish is one users ignore."""
        assert shards.STALE_SHARDS_DAYS == 14


class TestRetarget:
    """Moving an existing clone: the operation ``add`` and ``update`` refuse."""

    def test_checkout_comes_before_the_pin(self, sandbox, fixture_tap_src,
                                           monkeypatch):
        """A pin for a tree never checked out is a lie ``update`` then honours."""
        from boost_cli.core import gitutil, registry
        registry.add(str(fixture_tap_src))
        name = registry.list_taps()[0].name
        order = []
        monkeypatch.setattr(gitutil, "checkout_commit",
                            lambda repo, sha: order.append(("checkout", sha)))
        real_pin = registry.pin
        monkeypatch.setattr(registry, "pin",
                            lambda n, c: (order.append(("pin", c)),
                                          real_pin(n, c))[1])
        tap = registry.retarget(name, A)
        assert order == [("checkout", A), ("pin", A)]
        assert tap.pin == A
        # Durable, not just returned: `update` reads it back out of config.
        assert registry.get(name).pin == A

    def test_a_failed_checkout_records_no_pin(self, sandbox, fixture_tap_src,
                                              monkeypatch):
        """Half a move is worse than none: the pin would freeze the old tree."""
        from boost_cli.core import gitutil, registry
        registry.add(str(fixture_tap_src))
        name = registry.list_taps()[0].name

        def refuse(repo, sha):
            raise BoostError("no such commit")

        monkeypatch.setattr(gitutil, "checkout_commit", refuse)
        with pytest.raises(BoostError):
            registry.retarget(name, A)
        assert registry.get(name).pin == ""
