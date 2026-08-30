# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost update --shards`: taking delivery of the weekly republish.

The core loop is covered in ``test_shards_ingest``; what this file pins is the
command layer around it — the two modes that cannot both be right at once, the
repair work a moved tap needs beyond its vectors, and `--json` staying parseable
now that the same command also narrates its progress on stdout.
"""
import hashlib
import json

import pytest

from boost_cli.core import embed, gitutil, registry, shards

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}


def _publish(tmp_path, tap, commit):
    """A one-row manifest, served from a `file:` URL like a real one."""
    body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                       "chunks": [{"name": "x", "tap": tap, "path": "p",
                                   "kind": "skill", "cix": 0, "snip": "s",
                                   "embedding": "AAAA"}]})
    shard = tmp_path / "shard.json"
    shard.write_text(body, encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "version": 1, **SPACE,
        "shards": [{"tap": tap, "commit": commit, "chunks": 1,
                    "bytes": len(body.encode()),
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "url": shard.as_uri()}]}), encoding="utf-8")
    return manifest


@pytest.fixture()
def published(boost, tapped, tmp_path, monkeypatch):
    """The fixture tap, plus a manifest describing the commit it is at."""
    monkeypatch.setattr(embed, "provider", lambda: "local")
    monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
    monkeypatch.setattr(embed, "dimension", lambda: 384)
    from boost_cli.core import dense
    monkeypatch.setattr(dense, "import_shard",
                        lambda shard, commit: (True, "1 chunk"))

    def publish(commit=None):
        tap = registry.list_taps()[0]
        at = commit or gitutil.head_commit(tap.path)
        monkeypatch.setenv(shards.MANIFEST_ENV,
                           _publish(tmp_path, tap.name, at).as_uri())
        return tap.name

    return publish


class TestUpdateShards:

    def test_the_two_modes_move_taps_to_different_commits(self, boost):
        """A branch head and a published commit are not the same target."""
        res = boost("update", "--shards", "--taps-only", expect=2)
        assert "different commits" in (res.out + res.err)

    def test_a_tap_at_the_published_commit_imports_without_moving(
            self, boost, published, monkeypatch):
        published()
        moved = []
        monkeypatch.setattr(registry, "retarget",
                            lambda n, c: moved.append((n, c)))
        res = boost("update", "--shards")
        assert "imported 1 shard" in res.out
        assert moved == []

    def test_a_moved_registry_is_pulled_onto_the_published_commit(
            self, boost, published, monkeypatch):
        """The whole point: the manifest is the target, not a coincidence."""
        name = published("9" * 40)
        moved = []
        monkeypatch.setattr(registry, "retarget",
                            lambda n, c: moved.append((n, c)))
        res = boost("update", "--shards")
        assert moved == [(name, "9" * 40)]
        assert "1 moved to a newer commit" in res.out

    def test_json_stays_parseable_beside_the_progress_lines(
            self, boost, published, monkeypatch):
        """Both went to stdout, so `--json` used to emit an unreadable stream."""
        published()
        monkeypatch.setattr(registry, "retarget", lambda n, c: None)
        res = boost("update", "--shards", "--json")
        rows = json.loads(res.out)["shards"]
        assert [r["status"] for r in rows] == ["imported"]
        assert rows[0]["moved"] is False

    def test_a_machine_with_no_taps_is_told_where_to_start(self, boost,
                                                           sandbox):
        res = boost("update", "--shards", expect=1)
        assert "no taps configured" in (res.out + res.err)

    def test_an_incompatible_space_refuses_before_downloading(
            self, boost, published, monkeypatch):
        """Refusing after 129 MB is its own bug; the manifest answers first."""
        published()
        monkeypatch.setattr(embed, "provider", lambda: "voyage")
        fetched = []
        monkeypatch.setattr(shards, "download",
                            lambda *a, **k: fetched.append(1))
        res = boost("update", "--shards", expect=1)
        assert "cannot serve this machine" in (res.out + res.err)
        assert fetched == []


class TestStaleShardHint:
    """What search says about it — one `stat`, and never a network call."""

    def _hint(self, monkeypatch, age, ready):
        from boost_cli.commands import discovery
        from boost_cli.core import dense
        monkeypatch.setattr(shards, "sync_age_days", lambda: age)
        monkeypatch.setattr(dense, "status", lambda **k: {"ready": ready})
        return discovery._hint_stale_shards()

    def test_a_machine_that_never_ingested_says_nothing(self, monkeypatch,
                                                        capsys):
        """Not every install uses shards; a fresh one must not be nagged."""
        assert self._hint(monkeypatch, None, True) is False
        assert capsys.readouterr().out == ""

    def test_fresh_vectors_say_nothing(self, monkeypatch, capsys):
        assert self._hint(monkeypatch, 3.0, True) is False
        assert capsys.readouterr().out == ""

    def test_stale_vectors_name_the_one_next_action(self, monkeypatch, capsys):
        assert self._hint(monkeypatch, 30.0, True) is True
        assert "boost update --shards" in capsys.readouterr().out

    def test_vectors_that_are_not_serving_are_not_the_complaint(
            self, monkeypatch, capsys):
        """`_hint_semantic_search` owns that conversation, and says more."""
        assert self._hint(monkeypatch, 30.0, False) is False
        assert capsys.readouterr().out == ""

    def test_the_shard_hint_silences_the_tap_hint(self, monkeypatch, capsys):
        """Its remedy moves the taps too; two lines is how a hint becomes noise."""
        from boost_cli.commands import discovery
        from boost_cli.core import dense, registry
        monkeypatch.setattr(shards, "sync_age_days", lambda: 30.0)
        monkeypatch.setattr(dense, "status", lambda **k: {"ready": True})
        monkeypatch.setattr(registry, "refresh_age_days", lambda: 99.0)
        discovery._hint_stale_taps()
        out = capsys.readouterr().out
        assert "boost update --shards" in out
        assert "--taps-only" not in out
