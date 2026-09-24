# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Silence from a build job is not the same answer as "this registry is gone".

`shards.yml` packs ~460 registries into ~60 `fail-fast: false` jobs. A job
reports on its registries in exactly two ways: a fresh `*.shard.json`, or a
line in the `unchanged-N.txt` it uploads beside them. A job that *fails*
uploads neither — the upload step never runs — and the publish job, which
rebuilds `manifest.json` from scratch out of whatever artifacts arrived, then
has no evidence at all about that job's ~10 registries and dropped their rows.

Their assets stay on the release: `gh release upload --clobber` replaces and
never deletes. Measured on the live release generated 2026-09-20 — 453 manifest
rows against 461 `.shard.json` assets, so **8 registries, 245.5 MB, orphaned**,
among them the 199 MB `sickn33/antigravity-awesome-skills` whose rebuild is the
run's 2 h 07 m critical path. Every user of those eight went back to embedding
them locally at ~1.2 s/chunk against a 0.12 s import.

So the publish job has to tell four states apart, and only the third carries:

1. **rebuilt** — a fresh shard is in the dir. Its row wins over everything.
2. **unchanged** — a job named it in `unchanged-*.txt`. Last week's row is
   carried, and only for the exact commit that job saw.
3. **unreported** — no job said anything about it. Last week's row is carried
   verbatim, because the asset it names is still on the release and every
   consumer re-checks commit and sha256 before believing it.
4. **gone** — no job said anything *and* it has left the catalogue. Dropped,
   so the index cannot grow forever on rows nobody can use.

The refusals that were already there still refuse: an unreadable previous
manifest, one in another embedding space, and a row whose commit disagrees with
the job that reported it carry nothing — including down the new path, which is
why the space-mismatch and commit-disagreement cases are tested against a
*catalogued* registry here. A tap that is merely absent from the catalogue
would pass those tests by accident.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from boost_cli.core import config, shards

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_shards  # noqa: E402

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}
A, B = "a" * 40, "b" * 40


def _row(tap, commit, **over):
    row = {"tap": tap, "commit": commit, "chunks": 3, "bytes": 100,
           "sha256": "f" * 64,
           "url": "https://github.com/o/r/releases/download/shards-latest/"
                  + tap.replace("/", "_") + ".shard.json"}
    row.update(over)
    return row


def _manifest(rows, **over):
    data = {"version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
            "shards": rows}
    data.update(over)
    return data


class TestUnreported:
    """The pure decision, in core where the mutation gate can see it."""

    def test_a_registry_no_job_mentioned_keeps_its_published_row(self):
        got = shards.unreported(_manifest([_row("o/a", A)]),
                                reported=set(), known={"o/a"})
        assert list(got) == ["o/a"]
        assert got["o/a"]["sha256"] == "f" * 64

    def test_a_reported_registry_is_not_unreported(self):
        # Reported either way — rebuilt or verified unchanged — is evidence,
        # and evidence beats last week's row.
        assert shards.unreported(_manifest([_row("o/a", A)]),
                                 reported={"o/a"}, known={"o/a"}) == {}

    def test_a_registry_gone_from_the_catalogue_is_dropped(self):
        assert shards.unreported(_manifest([_row("o/a", A)]),
                                 reported=set(), known={"o/b"}) == {}

    def test_an_empty_known_set_carries_nothing(self):
        # The escape hatch, and the old behaviour: with nothing known to still
        # be a registry, silence cannot be told from removal, so nothing moves.
        assert shards.unreported(_manifest([_row("o/a", A)]),
                                 reported=set(), known=set()) == {}

    def test_a_malformed_row_is_never_carried(self):
        # No sha256/url: unusable to a consumer, so carrying it forward only
        # republishes a row that cannot be verified or downloaded.
        bad = {"tap": "o/a", "commit": A}
        assert shards.unreported(_manifest([bad]), reported=set(),
                                 known={"o/a"}) == {}

    def test_several_registries_are_each_decided_on_their_own(self):
        m = _manifest([_row("o/a", A), _row("o/b", B), _row("o/gone", A)])
        got = shards.unreported(m, reported={"o/a"},
                                known={"o/a", "o/b", "o/kept"})
        assert list(got) == ["o/b"]


class TestManifestCarriesTheSilent:
    """`publish_shards.py manifest` end to end, with fixture manifests."""

    def _shard(self, dir_, tap, commit):
        body = json.dumps({"tap": tap, "commit": commit, **SPACE,
                           "chunks": [{"name": "x", "embedding": "AAAA"}]})
        (dir_ / (tap.replace("/", "_") + ".shard.json")).write_text(
            body, encoding="utf-8")

    def _run(self, tmp_path, fresh, previous_rows, unchanged_lines,
             known=None, prev_over=None, capsys=None):
        shard_dir = tmp_path / "shards"
        shard_dir.mkdir(exist_ok=True)
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
        argv = ["manifest", "--shard-dir", str(shard_dir), "--repo", "o/r",
                "--out", str(out), "--carry-forward", str(prev),
                "--unchanged", str(unch)]
        if known is not None:
            kf = tmp_path / "known.txt"
            kf.write_text("".join(n + "\n" for n in known), encoding="utf-8")
            argv += ["--known", str(kf)]
        rc = publish_shards.main(argv)
        return rc, (json.loads(out.read_text(encoding="utf-8"))
                    if out.exists() else None)

    def test_a_failed_jobs_registry_keeps_last_weeks_row(self, tmp_path):
        # The bug, in miniature: job 0 published o/a and said o/b was
        # unchanged; job 1 failed, so nothing at all was heard about o/c.
        old = _row("o/c", A, sha256="e" * 64, bytes=777)
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[old, _row("o/b", B)],
                          unchanged_lines=[("o/b", B)],
                          known=["o/a", "o/b", "o/c"])
        assert rc == 0
        by = {r["tap"]: r for r in m["shards"]}
        assert set(by) == {"o/a", "o/b", "o/c"}
        # Carried verbatim: the asset on the release is last week's file, and
        # sha256 is what the consumer verifies the download against.
        assert by["o/c"]["sha256"] == "e" * 64 and by["o/c"]["bytes"] == 777

    def test_a_registry_out_of_the_catalogue_is_still_dropped(self, tmp_path):
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/gone", A)],
                          unchanged_lines=[], known=["o/a"])
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_a_commit_disagreement_is_not_rescued_by_the_silent_path(
            self, tmp_path):
        # The job says o/c is unchanged at B, the previous manifest says A.
        # That row is refused — and must not come straight back in as
        # "unreported", because the job did report on it.
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/c", A)],
                          unchanged_lines=[("o/c", B)],
                          known=["o/a", "o/c"])
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_another_embedding_space_still_carries_nothing(self, tmp_path):
        # The refusal has to cover the silent path too: a 1024-d voyage row
        # cannot be mixed into a 384-d keyless manifest whoever failed to
        # report it.
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/c", A)],
                          unchanged_lines=[], known=["o/a", "o/c"],
                          prev_over={"provider": "voyage",
                                     "model": "voyage-4", "dim": 1024})
        assert rc == 0
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_a_fresh_shard_still_wins_over_the_silent_path(self, tmp_path):
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/a", B, sha256="e" * 64)],
                          unchanged_lines=[], known=["o/a"])
        assert rc == 0
        rows = [r for r in m["shards"] if r["tap"] == "o/a"]
        assert len(rows) == 1 and rows[0]["commit"] == A

    def test_an_unreadable_previous_manifest_carries_nothing(self, tmp_path):
        shard_dir = tmp_path / "shards"
        shard_dir.mkdir()
        self._shard(shard_dir, "o/a", A)
        prev = tmp_path / "previous.json"
        prev.write_text("{not json", encoding="utf-8")
        out = tmp_path / "manifest.json"
        rc = publish_shards.main([
            "manifest", "--shard-dir", str(shard_dir), "--repo", "o/r",
            "--out", str(out), "--carry-forward", str(prev)])
        assert rc == 0
        m = json.loads(out.read_text(encoding="utf-8"))
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_the_counts_say_how_many_rows_nobody_reported(
            self, tmp_path, capsys):
        rc, m = self._run(tmp_path, fresh=[("o/a", A)],
                          previous_rows=[_row("o/b", B), _row("o/c", A),
                                         _row("o/gone", A)],
                          unchanged_lines=[("o/b", B)],
                          known=["o/a", "o/b", "o/c"])
        assert rc == 0
        assert sorted(r["tap"] for r in m["shards"]) == ["o/a", "o/b", "o/c"]
        text = capsys.readouterr()
        both = text.out + text.err
        # A silently shrinking manifest is the failure mode; both directions
        # have to be countable from the job log.
        assert "1 fresh" in both and "1 carried unchanged" in both
        assert "1 carried for registries no job reported" in both
        assert "o/c" in both and "o/gone" in both
        # The dropped count must name only what really left the catalogue:
        # without the `tap not in silent` clause it reads 2 and names o/c,
        # the row this change exists to carry.
        assert "dropped 1 published row(s)" in both, both
        # The dropped line must name only what really left the catalogue:
        # without the `tap not in silent` clause it reads 2 and names o/c,
        # the row this change exists to carry.
        dropped = next(ln for ln in both.splitlines() if "dropped" in ln)
        assert "o/gone" in dropped and "o/c" not in dropped, dropped

    def test_nothing_at_all_is_still_an_error(self, tmp_path):
        rc, _ = self._run(tmp_path, fresh=[], previous_rows=[],
                          unchanged_lines=[], known=["o/a"])
        assert rc == 1


class TestTheCatalogueIsTheDefault:
    """With no `--known`, the bundled catalogue answers "still a registry?".

    This is the test that is red on the base tree with the *same* command line
    the workflow already runs: no new flag, a real catalogued registry, and no
    job reporting on it.
    """

    def test_a_catalogued_registry_survives_a_run_that_never_mentioned_it(
            self, tmp_path):
        catalogued = sorted(str(e.get("name") or "")
                            for e in config.load_registry_catalog()
                            if e.get("name"))
        assert catalogued, "the bundled registry catalogue is empty"
        name = catalogued[0]
        shard_dir = tmp_path / "shards"
        shard_dir.mkdir()
        (shard_dir / "o_a.shard.json").write_text(
            json.dumps({"tap": "o/a", "commit": A, **SPACE,
                        "chunks": [{"name": "x", "embedding": "AAAA"}]}),
            encoding="utf-8")
        prev = tmp_path / "previous.json"
        prev.write_text(json.dumps(_manifest([_row(name, B)])),
                        encoding="utf-8")
        out = tmp_path / "manifest.json"
        rc = publish_shards.main([
            "manifest", "--shard-dir", str(shard_dir), "--repo", "o/r",
            "--out", str(out), "--carry-forward", str(prev)])
        assert rc == 0
        m = json.loads(out.read_text(encoding="utf-8"))
        assert sorted(r["tap"] for r in m["shards"]) == sorted(["o/a", name])

    def test_an_uncatalogued_registry_does_not(self, tmp_path):
        shard_dir = tmp_path / "shards"
        shard_dir.mkdir()
        (shard_dir / "o_a.shard.json").write_text(
            json.dumps({"tap": "o/a", "commit": A, **SPACE,
                        "chunks": [{"name": "x", "embedding": "AAAA"}]}),
            encoding="utf-8")
        prev = tmp_path / "previous.json"
        prev.write_text(
            json.dumps(_manifest([_row("nobody/left-the-catalogue", B)])),
            encoding="utf-8")
        out = tmp_path / "manifest.json"
        rc = publish_shards.main([
            "manifest", "--shard-dir", str(shard_dir), "--repo", "o/r",
            "--out", str(out), "--carry-forward", str(prev)])
        assert rc == 0
        m = json.loads(out.read_text(encoding="utf-8"))
        assert [r["tap"] for r in m["shards"]] == ["o/a"]


class TestKnownListParsing:
    """`--known` takes the files the workflow already has lying around."""

    def test_a_tap_commit_file_is_read_as_a_name_list(self, tmp_path):
        # `unchanged-N.txt` is `tap commit`; a plain list is one name per line.
        # Both have to work, so the publish job can hand over either.
        f = tmp_path / "known.txt"
        f.write_text("o/a %s\n# a comment\n\no/b\n" % A, encoding="utf-8")
        assert publish_shards.known_registries([str(f)]) == {"o/a", "o/b"}

    def test_an_unreadable_file_is_reported_not_fatal(self, tmp_path, capsys):
        got = publish_shards.known_registries([str(tmp_path / "nope.txt")])
        assert got == set()
        assert "nope.txt" in capsys.readouterr().err

    def test_no_files_means_the_bundled_catalogue(self):
        got = publish_shards.known_registries(None)
        names = {str(e.get("name") or "")
                 for e in config.load_registry_catalog() if e.get("name")}
        assert got == names and len(got) > 100

    def test_an_explicit_empty_list_is_not_the_catalogue(self):
        # `--known` with no files is "carry nothing for silence", which is
        # a different answer from not passing the flag at all.
        assert publish_shards.known_registries([]) == set()
