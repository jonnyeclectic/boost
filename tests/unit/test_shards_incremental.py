# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A weekly shard run must not re-embed what it already published.

Every run used to embed every registry from scratch — ~9 job-hours for the
catalogue — on ephemeral runners with no memory of last week. Registries move
slowly, so most of that was buying the same vectors again. The manifest
already pins the commit each shard was built from, so "has this registry
moved?" is one comparison, and a registry that has not moved keeps last
week's row rather than a fresh (and byte-identical) shard.

The rule that makes this safe is the same one that makes shards importable at
all: a row is reused only for the EXACT commit it describes. Unknown is not
equal — a tap whose commit could not be read is embedded, not skipped — and a
manifest in a different embedding space reuses nothing, because none of its
rows would be importable by the consumer this run is publishing for.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import shards

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_shards  # noqa: E402

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}
A, B = "a" * 40, "b" * 40


def _row(tap, commit, **over):
    row = {"tap": tap, "commit": commit, "chunks": 3, "bytes": 100,
           "sha256": "f" * 64,
           "url": "https://github.com/o/r/releases/download/shards-latest/"
                  + tap.replace("/", "__") + ".shard.json"}
    row.update(over)
    return row


def _manifest(rows, **over):
    data = {"version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
            "shards": rows}
    data.update(over)
    return data


class TestUnchanged:
    """The pure decision: which taps keep last week's row."""

    def test_same_commit_is_unchanged(self):
        got = shards.unchanged(_manifest([_row("o/a", A)]), {"o/a": A})
        assert list(got) == ["o/a"]
        assert got["o/a"]["commit"] == A

    def test_a_moved_registry_is_not(self):
        assert shards.unchanged(_manifest([_row("o/a", A)]), {"o/a": B}) == {}

    def test_a_registry_with_no_published_row_is_not(self):
        assert shards.unchanged(_manifest([_row("o/a", A)]), {"o/b": A}) == {}

    def test_an_unknown_local_commit_never_counts_as_unchanged(self):
        # "" is what a tap whose clone failed reports. Treating that as a match
        # would carry a row forward for a registry nobody verified this week.
        assert shards.unchanged(_manifest([_row("o/a", A)]), {"o/a": ""}) == {}

    def test_a_malformed_row_is_skipped_not_matched(self):
        bad = {"tap": "o/a", "commit": A}          # no sha256/url: unusable
        assert shards.unchanged(_manifest([bad]), {"o/a": A}) == {}

    def test_only_the_taps_asked_about_are_answered(self):
        got = shards.unchanged(_manifest([_row("o/a", A), _row("o/b", B)]),
                               {"o/a": A})
        assert list(got) == ["o/a"]


class TestUnchangedSubcommand:
    """`publish_shards.py unchanged`: the decision applied to a real HOME."""

    def _publish(self, tmp_path, rows, **over):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(_manifest(rows, **over)), encoding="utf-8")
        return path.as_uri()

    def test_lists_tap_and_commit_for_each_unchanged_registry(
            self, sandbox, fixture_tap_src, tmp_path, monkeypatch):
        from boost_cli.core import gitutil, registry
        tap = registry.add(str(fixture_tap_src))
        head = gitutil.head_commit(tap.path)
        url = self._publish(tmp_path, [_row(tap.name, head)])
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        out = tmp_path / "unchanged.txt"
        rc = publish_shards.main(["unchanged", "--manifest-url", url,
                                  "--out", str(out)])
        assert rc == 0
        assert out.read_text(encoding="utf-8").split() == [tap.name, head]

    def test_a_moved_registry_is_left_to_be_embedded(
            self, sandbox, fixture_tap_src, tmp_path, monkeypatch):
        from boost_cli.core import registry
        tap = registry.add(str(fixture_tap_src))
        url = self._publish(tmp_path, [_row(tap.name, B)])
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        out = tmp_path / "unchanged.txt"
        assert publish_shards.main(["unchanged", "--manifest-url", url,
                                    "--out", str(out)]) == 0
        assert out.read_text(encoding="utf-8") == ""

    def test_no_manifest_means_embed_everything(self, sandbox, fixture_tap_src,
                                                tmp_path):
        # First run, or offline: an empty list is the honest answer and the
        # exit code stays 0 so the workflow embeds rather than aborts.
        from boost_cli.core import registry
        registry.add(str(fixture_tap_src))
        out = tmp_path / "unchanged.txt"
        rc = publish_shards.main(["unchanged", "--manifest-url",
                                  (tmp_path / "missing.json").as_uri(),
                                  "--out", str(out)])
        assert rc == 0
        assert out.read_text(encoding="utf-8") == ""

    def test_a_different_embedding_space_reuses_nothing(
            self, sandbox, fixture_tap_src, tmp_path, monkeypatch):
        # Rows from a 1024-d manifest are worthless to the 384-d consumer this
        # run is publishing for, however fresh their commits are.
        from boost_cli.core import gitutil, registry
        tap = registry.add(str(fixture_tap_src))
        head = gitutil.head_commit(tap.path)
        url = self._publish(tmp_path, [_row(tap.name, head)],
                            provider="voyage", model="voyage-4", dim=1024)
        monkeypatch.setattr(shards.embed, "provider", lambda: "local")
        monkeypatch.setattr(shards.embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(shards.embed, "dimension", lambda: 384)
        out = tmp_path / "unchanged.txt"
        assert publish_shards.main(["unchanged", "--manifest-url", url,
                                    "--out", str(out)]) == 0
        assert out.read_text(encoding="utf-8") == ""


class TestManifestCarryForward:
    """`publish_shards.py manifest --carry-forward`: last week's rows survive."""

    def _shard(self, dir_, tap, commit):
        body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                           "chunks": [{"name": "x", "embedding": "AAAA"}]})
        (dir_ / (tap.replace("/", "__") + ".shard.json")).write_text(
            body, encoding="utf-8")

    def _run(self, tmp_path, fresh, previous_rows, unchanged_lines,
             prev_over=None):
        shard_dir = tmp_path / "shards"
        shard_dir.mkdir()
        for tap, commit in fresh:
            self._shard(shard_dir, tap, commit)
        prev = tmp_path / "previous.json"
        prev.write_text(json.dumps(_manifest(previous_rows,
                                             **(prev_over or {}))),
                        encoding="utf-8")
        unch = tmp_path / "unchanged-0.txt"
        unch.write_text("".join("%s %s\n" % l for l in unchanged_lines),
                        encoding="utf-8")
        out = tmp_path / "manifest.json"
        rc = publish_shards.main([
            "manifest", "--shard-dir", str(shard_dir), "--repo", "o/r",
            "--out", str(out), "--carry-forward", str(prev),
            "--unchanged", str(unch)])
        return rc, (json.loads(out.read_text(encoding="utf-8"))
                    if out.exists() else None)

    def test_an_unchanged_row_is_carried_verbatim(self, tmp_path):
        old = _row("o/b", B, sha256="e" * 64, bytes=777)
        rc, m = self._run(tmp_path, fresh=[("o/a", A)], previous_rows=[old],
                          unchanged_lines=[("o/b", B)])
        assert rc == 0
        by = {r["tap"]: r for r in m["shards"]}
        assert set(by) == {"o/a", "o/b"}
        # The old sha256 and size are the whole point: the asset on the
        # release is the old file, and the consumer verifies against these.
        assert by["o/b"]["sha256"] == "e" * 64 and by["o/b"]["bytes"] == 777

    def test_a_fresh_shard_wins_over_a_carried_row(self, tmp_path):
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/a", B, sha256="e" * 64)],
                          unchanged_lines=[("o/a", B)])
        assert rc == 0
        rows = [r for r in m["shards"] if r["tap"] == "o/a"]
        assert len(rows) == 1 and rows[0]["commit"] == A

    def test_a_row_is_carried_only_for_the_commit_it_describes(self, tmp_path):
        # The job says "unchanged at B"; the previous manifest has A. Someone
        # is wrong, and a row carried under those conditions could describe a
        # tree the registry is no longer at.
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/b", A)],
                          unchanged_lines=[("o/b", B)])
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_a_registry_neither_fresh_nor_unchanged_is_dropped(self, tmp_path):
        # Removed from the catalogue, or failed to tap this week: the row goes,
        # rather than a stale index growing forever. The asset stays on the
        # release, harmless, and comes back the week the registry does.
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/gone", A)],
                          unchanged_lines=[])
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_a_previous_manifest_in_another_space_carries_nothing(
            self, tmp_path):
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/b", B)],
                          unchanged_lines=[("o/b", B)],
                          prev_over={"provider": "voyage", "model": "voyage-4",
                                     "dim": 1024})
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_a_run_with_no_fresh_shards_still_publishes_the_carried_rows(
            self, tmp_path):
        # The steady state of a quiet week: every registry unchanged. The
        # manifest must still be written, from the previous space.
        rc, m = self._run(tmp_path, fresh=[], previous_rows=[_row("o/b", B)],
                          unchanged_lines=[("o/b", B)])
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/b"]
        assert m["provider"] == SPACE["provider"] and m["dim"] == SPACE["dim"]

    def test_nothing_at_all_is_still_an_error(self, tmp_path):
        rc, _ = self._run(tmp_path, fresh=[], previous_rows=[],
                          unchanged_lines=[])
        assert rc == 1


class TestWorkflowUsesIt:
    """The mechanism is only worth anything if the workflow calls it."""

    SHARDS = ROOT / ".github" / "workflows" / "shards.yml"

    @pytest.fixture(autouse=True)
    def _present(self):
        if not self.SHARDS.exists():
            pytest.skip("workflow not reachable (e.g. mutation sandbox)")

    def test_the_build_step_asks_before_embedding(self):
        text = self.SHARDS.read_text(encoding="utf-8")
        assert "publish_shards.py unchanged" in text

    def test_the_publish_step_carries_forward(self):
        text = self.SHARDS.read_text(encoding="utf-8")
        assert "--carry-forward" in text
        # The previous manifest comes from the release, never from a guess.
        assert "releases/download/shards-latest/manifest.json" in text

    def test_the_cli_is_reachable_the_way_the_workflow_calls_it(self):
        proc = subprocess.run([sys.executable,
                               str(ROOT / "scripts" / "publish_shards.py"),
                               "unchanged", "--help"],
                              capture_output=True, text=True)
        assert proc.returncode == 0
        assert "--manifest-url" in proc.stdout
