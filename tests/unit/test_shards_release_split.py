# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Two rolling releases, because one holds 1,000 assets.

`shards-latest` reached 999 assets — one dense and one keyword shard per
registry, plus orphans — and every `shards.yml` run after 2026-10-11 lost its
upload to ``HTTP 422 ... file_count limited to 1000 assets per release``. Each
failed run's ``--clobber`` also deleted-then-replaced assets the still-live
2026-10-11 manifest described, so by 2026-11-04 that manifest had 162 dense and
149 keyword rows whose asset was missing or a different size.

So keyword shards move to ``shards-keyword-latest``, and these tests pin the
three things that make that safe:

* the CLIENT side needs no change — every boost reading the keyword section
  only requires a shard URL to share the manifest's scheme and host;
* the PUBLISH order never leaves a live manifest naming an asset that does not
  exist, at any point the job can stop — checked by running the workflow's own
  shell against a fake ``gh`` that enforces the 1,000-asset cap;
* the PLAN job refuses, before an hour of embedding, a run that would overfill
  either release.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

from boost_cli.core import rag, shards

ROOT = Path(__file__).resolve().parents[2]
SHARDS_YML = ROOT / ".github" / "workflows" / "shards.yml"
sys.path.insert(0, str(ROOT / "scripts"))

import publish_shards  # noqa: E402

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}
A, B = "a" * 40, "b" * 40
OLD, NEW = publish_shards.DEFAULT_TAG, publish_shards.KEYWORD_TAG


def _url(tag, name, repo="o/r"):
    return publish_shards.release_url(repo, tag, name)


def _row(tap, tag, name=None, commit=A, size=100, **over):
    row = {"tap": tap, "commit": commit, "bytes": size, "sha256": "f" * 64,
           "url": _url(tag, name or publish_shards.dense_asset_name(tap))}
    row.update(over)
    return row


def _kw(tap, tag, commit=A, size=50, **over):
    return _row(tap, tag, publish_shards.keyword_asset_name(tap), commit,
                size, docs=1, **over)


def _manifest(dense_rows, kw_rows=None, **over):
    m = {"version": 1, "generated": "2026-10-11T00:00:00Z", **SPACE,
         "shards": dense_rows}
    if kw_rows is not None:
        m["keyword"] = {"format": rag.SHARD_FORMAT,
                        "index_version": rag.INDEX_VERSION, "shards": kw_rows}
    m.update(over)
    return m


def _release(*assets):
    """A REST release object: `(name, size)` pairs, ids assigned in order."""
    return {"id": 1, "assets": [{"id": 100 + i, "name": n, "size": s}
                                for i, (n, s) in enumerate(assets)]}


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ------------------------------------------------------------ names and URLs

class TestAssetNames:

    @pytest.mark.parametrize("tap", ["o/r", "Some-Org/a.b_c", "x/y-z"])
    def test_dense_name_is_what_the_export_steps_tr_writes(self, tap):
        # The workflow names the file in shell; the projection names it in
        # Python. `tr` maps each `/` to the FIRST char of `__`, so one `_`.
        got = subprocess.run(["tr", "/", "__"], input=tap, text=True,
                             capture_output=True, check=True).stdout
        assert publish_shards.dense_asset_name(tap) == got + ".shard.json"

    def test_the_export_step_still_names_dense_shards_with_that_tr(self):
        text = SHARDS_YML.read_text(encoding="utf-8")
        assert "safe=$(printf '%s' \"$reg\" | tr '/' '__')" in text
        assert '"$safe.shard.json"' in text

    def test_keyword_name_is_what_export_keyword_writes(self):
        assert (publish_shards.keyword_asset_name("o/r")
                == "o__r" + publish_shards.KEYWORD_SUFFIX)

    @pytest.mark.parametrize("url, want", [
        ("https://github.com/o/r/releases/download/shards-latest/x.gz",
         ("shards-latest", "x.gz")),
        ("https://github.com/o/r/releases/download/%s/a__b%s"
         % (NEW, publish_shards.KEYWORD_SUFFIX),
         (NEW, "a__b" + publish_shards.KEYWORD_SUFFIX)),
        ("file:///m/releases/download/t/n.json", ("t", "n.json")),
        ("https://x/o__a", None),
        ("https://github.com/o/r/download/t/n", None),
        ("https://github.com/o/r/releases/download/t/", None),
        ("https://github.com/o/r/releases/download//n", None),
        (None, None), (7, None),
    ])
    def test_asset_location(self, url, want):
        assert publish_shards.asset_location(url) == want


class TestTheSecondTag:
    """Created like `shards-latest`, so the same three readers ignore it."""

    def test_the_tag_keeps_the_prefix_and_carries_no_digit(self):
        assert NEW.startswith("shards-") and NEW != OLD
        # setuptools-scm finds tags with `--match v[0-9]*` and parses them
        # with `tag_regex`; release-drafter and the badge skip prereleases.
        assert not re.search(r"[0-9]", NEW)
        regex = re.search(r'tag_regex = "(.+)"', (ROOT / "pyproject.toml")
                          .read_text(encoding="utf-8")).group(1)
        assert not re.match(regex, NEW)

    def test_both_releases_are_created_prerelease_and_never_latest(self):
        publish = _step("publish", "publish to the rolling releases")["run"]
        assert "--prerelease --latest=false" in publish
        assert re.search(r"ensure_release shards-latest\b", publish)
        assert re.search(r"ensure_release %s\b" % NEW, publish)


# ------------------------------------------------------------ the client side

class TestOldClientsReadTheNewTag:
    """`boost_cli/core` is unchanged; this pins why it can stay so."""

    def test_a_keyword_url_on_the_new_tag_is_on_the_manifests_host(self):
        url = _url(NEW, "o__a.keyword.json.gz", "jonnyeclectic/boost")
        assert shards._same_origin(url, shards.DEFAULT_MANIFEST_URL)

    def test_download_fetches_a_row_on_the_new_tag(self, tmp_path,
                                                    monkeypatch):
        # Through `download` itself — the one gate between a row and a fetch
        # — with only the transport faked.
        import hashlib
        import io
        body = gzip.compress(b"{}")
        seen = []

        def fake_open(url, timeout):
            seen.append(url)
            return io.BytesIO(body)

        monkeypatch.setattr(shards, "_open", fake_open)
        row = {"tap": "o/a", "sha256": hashlib.sha256(body).hexdigest(),
               "url": _url(NEW, "o__a.keyword.json.gz",
                           "jonnyeclectic/boost")}
        dest = tmp_path / "o__a.keyword.json.gz"
        shards.download(row, dest, {"_url": shards.DEFAULT_MANIFEST_URL})
        assert dest.read_bytes() == body and seen == [row["url"]]

    def test_another_host_is_still_refused(self):
        assert not shards._same_origin(
            "https://evil.example/o/r/releases/download/%s/x" % NEW,
            shards.DEFAULT_MANIFEST_URL)


# ------------------------------------------------------------ manifest

def _dense_file(d, tap, commit=A):
    path = d / publish_shards.dense_asset_name(tap)
    path.write_text(json.dumps({"tap": tap, "commit": commit, **SPACE,
                                "chunks": [{}]}), encoding="utf-8")
    return path


def _kw_file(d, tap, commit=A):
    shard = {"format": rag.SHARD_FORMAT, "engine": rag.ENGINE,
             "index_version": rag.INDEX_VERSION, "tap": tap,
             "commit": commit, "docs": [{"n": "x", "t": tap, "tf": {"a": 1}}]}
    path = d / publish_shards.keyword_asset_name(tap)
    path.write_bytes(publish_shards.keyword_bytes(shard))
    return path


class TestManifestKeywordTag:

    def _run(self, tmp_path, *extra):
        out = tmp_path / "manifest.json"
        rc = publish_shards.main(["manifest", "--shard-dir",
                                  str(tmp_path / "s"), "--repo", "o/r",
                                  "--out", str(out), *extra])
        assert rc == 0
        return json.loads(out.read_text(encoding="utf-8"))

    def _shards(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a", B)
        return d

    def test_keyword_rows_go_to_the_keyword_tag_and_dense_rows_do_not(
            self, tmp_path):
        self._shards(tmp_path)
        m = self._run(tmp_path, "--keyword-tag", NEW)
        assert publish_shards.asset_location(m["shards"][0]["url"])[0] == OLD
        (kw,) = m["keyword"]["shards"]
        assert kw["url"] == _url(NEW, "o__a.keyword.json.gz")

    def test_without_the_flag_one_release_hosts_both(self, tmp_path):
        # What a fork publishing to one release by the documented recipe gets.
        self._shards(tmp_path)
        m = self._run(tmp_path, "--tag", "mine")
        assert {publish_shards.asset_location(r["url"])[0]
                for r in m["shards"] + m["keyword"]["shards"]} == {"mine"}

    def test_a_reexported_tap_does_not_come_back_through_the_silent_path(
            self, tmp_path):
        # The migration re-exports every reported registry. Its old row on
        # `shards-latest` must be replaced, not kept beside the new one.
        self._shards(tmp_path)
        prev = _write(tmp_path / "prev.json",
                      _manifest([], [_kw("o/a", OLD), _kw("o/s", OLD)]))
        known = tmp_path / "known.txt"
        known.write_text("o/a\no/s\n", encoding="utf-8")
        m = self._run(tmp_path, "--keyword-tag", NEW, "--carry-forward",
                      str(prev), "--known", str(known))
        got = {r["tap"]: (publish_shards.asset_location(r["url"])[0],
                          r["commit"]) for r in m["keyword"]["shards"]}
        # o/s was never reported: kept valid where its asset still is.
        assert got == {"o/a": (NEW, B), "o/s": (OLD, A)}


# ------------------------------------------------------------ unchanged

class TestUnchangedHostedOn:
    """The rule that makes the migration happen in the build jobs."""

    @pytest.mark.parametrize("tag, hosted_on, listed", [
        (OLD, NEW, False),       # still on the old release: re-export it
        (NEW, NEW, True),        # already moved: keep last week's row
        (OLD, None, True),       # no filter: the old behaviour
    ])
    def test_only_rows_on_the_named_tag_count(self, sandbox, fixture_tap_src,
                                              tmp_path, tag, hosted_on,
                                              listed):
        from boost_cli.core import registry
        tap = registry.add(str(fixture_tap_src))
        commit = rag._tap_commits()[tap.safe_name]
        mpath = _write(tmp_path / "manifest.json",
                       _manifest([], [_kw(tap.name, tag, commit)]))
        out = tmp_path / "unchanged.txt"
        argv = ["unchanged", "--kind", "keyword", "--manifest-url",
                mpath.as_uri(), "--out", str(out)]
        if hosted_on:
            argv += ["--hosted-on", hosted_on]
        assert publish_shards.main(argv) == 0
        want = [tap.name, commit] if listed else []
        assert out.read_text(encoding="utf-8").split() == want


# ------------------------------------------------------------ splice

class TestSplice:

    def test_dense_rows_from_one_and_the_keyword_section_from_the_other(self):
        prev = _manifest([_row("o/a", OLD)], [_kw("o/a", OLD)], _url="x")
        new = _manifest([_row("o/b", OLD)], [_kw("o/b", NEW)],
                        generated="2026-11-08T00:00:00Z")
        out = publish_shards.splice(prev, new)
        assert out["shards"] == prev["shards"]
        assert out["keyword"] == new["keyword"]
        assert out["generated"] == "2026-11-08T00:00:00Z"
        assert "_url" not in out           # a fetch-time annotation
        assert out["provider"] == SPACE["provider"]

    def test_no_new_keyword_section_means_none(self):
        prev = _manifest([_row("o/a", OLD)], [_kw("o/a", OLD)])
        assert "keyword" not in publish_shards.splice(prev, _manifest([]))

    def test_cli_refuses_a_previous_manifest_it_cannot_trust(self, tmp_path):
        bad = _write(tmp_path / "prev.json", {"version": 2, "shards": []})
        new = _write(tmp_path / "new.json", _manifest([]))
        out = tmp_path / "interim" / "manifest.json"
        assert publish_shards.main(["splice", "--dense", str(bad),
                                    "--keyword", str(new), "--out",
                                    str(out)]) == 1
        assert not out.exists()

    def test_cli_writes_the_interim(self, tmp_path):
        prev = _write(tmp_path / "prev.json", _manifest([_row("o/a", OLD)]))
        new = _write(tmp_path / "new.json",
                     _manifest([], [_kw("o/a", NEW)]))
        out = tmp_path / "interim" / "manifest.json"
        assert publish_shards.main(["splice", "--dense", str(prev),
                                    "--keyword", str(new), "--out",
                                    str(out)]) == 0
        got = json.loads(out.read_text(encoding="utf-8"))
        assert [r["tap"] for r in got["shards"]] == ["o/a"]
        assert got["keyword"]["shards"][0]["url"].split("/")[-2] == NEW


# ------------------------------------------------------------ verify

class TestVerify:

    RELEASES: ClassVar[dict] = {OLD: {"o_a.shard.json": {"id": 1, "size": 100},
                                "o_b.shard.json": {"id": 2, "size": 999},
                                "o__k.keyword.json.gz": {"id": 3, "size": 50}},
                          NEW: {"o__a.keyword.json.gz": {"id": 4, "size": 50}}}

    @pytest.mark.parametrize("row, fragment", [
        (_row("o/a", OLD), None),
        (_row("o/b", OLD), "999 bytes on shards-latest; the row says 100"),
        (_row("o/c", OLD), "not on shards-latest"),
        (_row("o/a", "elsewhere"), "did not list"),
        (_row("o/a", OLD, url="https://x/o_a.shard.json"), "no release"),
        (_kw("o/a", NEW), None),
        (_kw("o/k", OLD), None),
        (_row("o/a", OLD, bytes=None), None),   # no size: presence alone
        ("junk", "not an object"),
    ])
    def test_row_problem(self, row, fragment):
        why = publish_shards.row_problem(row, self.RELEASES)
        if fragment is None:
            assert why is None
        else:
            assert fragment in why

    def test_bad_rows_are_dropped_and_good_ones_kept(self):
        m = _manifest([_row("o/a", OLD), _row("o/b", OLD)],
                      [_kw("o/a", NEW), _kw("o/k", OLD)])
        out, dropped = publish_shards.verify_manifest(m, self.RELEASES)
        assert [r["tap"] for r in out["shards"]] == ["o/a"]
        assert [r["tap"] for r in out["keyword"]["shards"]] == ["o/a", "o/k"]
        assert [t for t, _w in dropped["dense"]] == ["o/b"]
        assert dropped["keyword"] == []
        assert out["keyword"]["index_version"] == rag.INDEX_VERSION
        assert len(m["shards"]) == 2        # the input is not edited

    def test_only_checks_one_section_and_passes_the_other_through(self):
        m = _manifest([_row("o/b", OLD), _row("o/c", OLD)],
                      [_kw("o/a", NEW), _kw("o/gone", NEW)])
        out, dropped = publish_shards.verify_manifest(m, self.RELEASES,
                                                      only="keyword")
        assert out["shards"] == m["shards"]        # broken, and untouched
        assert [r["tap"] for r in out["keyword"]["shards"]] == ["o/a"]
        assert list(dropped) == ["keyword"]
        out, dropped = publish_shards.verify_manifest(m, self.RELEASES,
                                                      only="dense")
        assert out["shards"] == [] and out["keyword"] == m["keyword"]
        assert list(dropped) == ["dense"]

    def test_cli_only_keyword_ignores_a_dense_section_broken_past_half(
            self, tmp_path):
        # The interim's case: last week's dense rows are what they are, and
        # refusing over them would cost the run its room every week.
        m = _manifest([_row("o/b", OLD), _row("o/c", OLD)], [_kw("o/a", NEW)])
        mpath = _write(tmp_path / "m.json", m)
        argv = ["verify", "--manifest", str(mpath),
                "--release", "%s=%s" % (OLD, _write(tmp_path / "o.json",
                                                    _release())),
                "--release", "%s=%s" % (NEW, _write(
                    tmp_path / "n.json",
                    _release(("o__a.keyword.json.gz", 50))))]
        assert publish_shards.main(argv) == 1
        assert publish_shards.main([*argv, "--only", "keyword"]) == 0
        assert json.loads(mpath.read_text(encoding="utf-8")) == m

    def test_a_keyword_section_left_empty_is_removed(self):
        m = _manifest([_row("o/a", OLD)], [_kw("o/gone", NEW)])
        out, _d = publish_shards.verify_manifest(m, self.RELEASES)
        assert "keyword" not in out

    def _cli(self, tmp_path, manifest, *releases, out=None):
        mpath = _write(tmp_path / "m.json", manifest)
        argv = ["verify", "--manifest", str(mpath)]
        for tag, rel in releases:
            argv += ["--release", "%s=%s" % (tag, _write(
                tmp_path / ("%s.json" % tag), rel))]
        if out:
            argv += ["--out", str(out)]
        return publish_shards.main(argv), mpath

    def test_cli_rewrites_in_place(self, tmp_path):
        rc, mpath = self._cli(
            tmp_path, _manifest([_row("o/a", OLD), _row("o/b", OLD),
                                 _row("o/c", OLD)]),
            (OLD, _release(("o_a.shard.json", 100), ("o_b.shard.json", 100))))
        assert rc == 0
        got = json.loads(mpath.read_text(encoding="utf-8"))
        assert [r["tap"] for r in got["shards"]] == ["o/a", "o/b"]

    def test_cli_writes_elsewhere_when_asked(self, tmp_path):
        out = tmp_path / "out.json"
        m = _manifest([_row("o/a", OLD)])
        rc, mpath = self._cli(tmp_path, m,
                              (OLD, _release(("o_a.shard.json", 100))),
                              out=out)
        assert rc == 0 and out.exists()
        assert json.loads(mpath.read_text(encoding="utf-8")) == m

    def test_exactly_half_dropped_is_allowed(self, tmp_path):
        rc, _p = self._cli(tmp_path, _manifest([_row("o/a", OLD),
                                                _row("o/b", OLD)]),
                           (OLD, _release(("o_a.shard.json", 100))))
        assert rc == 0

    def test_more_than_half_is_a_wrong_listing_and_writes_nothing(
            self, tmp_path):
        m = _manifest([_row("o/a", OLD), _row("o/b", OLD), _row("o/c", OLD)])
        rc, mpath = self._cli(tmp_path, m,
                              (OLD, _release(("o_a.shard.json", 100))))
        assert rc == 1
        assert json.loads(mpath.read_text(encoding="utf-8")) == m

    def test_the_guard_reads_each_section_on_its_own(self, tmp_path):
        m = _manifest([_row("o/a", OLD)], [_kw("o/x", NEW), _kw("o/y", NEW)])
        rc, _p = self._cli(tmp_path, m,
                           (OLD, _release(("o_a.shard.json", 100))),
                           (NEW, _release()))
        assert rc == 1

    def test_a_listing_without_assets_is_an_error_not_an_empty_release(
            self, tmp_path):
        with pytest.raises(SystemExit, match="no `assets` list"):
            self._cli(tmp_path, _manifest([_row("o/a", OLD)]),
                      (OLD, {"message": "Not Found"}))

    def test_no_release_at_all_is_an_error(self, tmp_path):
        with pytest.raises(SystemExit, match="at least one --release"):
            self._cli(tmp_path, _manifest([_row("o/a", OLD)]))

    @pytest.mark.parametrize("value", ["no-equals", "=f", "t="])
    def test_a_malformed_release_argument_is_refused(self, tmp_path, value):
        mpath = _write(tmp_path / "m.json", _manifest([]))
        with pytest.raises(SystemExit, match="TAG=FILE"):
            publish_shards.main(["verify", "--manifest", str(mpath),
                                 "--release", value])


# ------------------------------------------------------------ prune

class TestPrune:

    def _assets(self, *names):
        return {n: {"id": i, "size": 1} for i, n in enumerate(names, 1)}

    def test_only_unnamed_assets_with_the_suffix(self):
        assets = self._assets("o__a.keyword.json.gz", "o__b.keyword.json.gz",
                              "o_c.shard.json", "manifest.json")
        m = _manifest([], [_kw("o/a", OLD)])
        got = publish_shards.prune_candidates(m, OLD, assets, ".keyword.json.gz")
        assert got == [("2", "o__b.keyword.json.gz")]

    def test_a_row_on_the_other_tag_protects_nothing_here(self):
        assets = self._assets("o__a.keyword.json.gz")
        m = _manifest([], [_kw("o/a", NEW)])
        assert publish_shards.prune_candidates(
            m, OLD, assets, ".keyword.json.gz") == [("1", "o__a.keyword.json.gz")]

    def test_a_dense_row_naming_the_file_protects_it_too(self):
        # Whatever a row points at stays, whichever section it is in.
        assets = self._assets("odd.keyword.json.gz")
        m = _manifest([_row("o/a", OLD, "odd.keyword.json.gz")])
        assert publish_shards.prune_candidates(
            m, OLD, assets, ".keyword.json.gz") == []

    def test_a_malformed_row_still_protects_what_it_names(self):
        assets = self._assets("o__a.keyword.json.gz")
        m = _manifest([], [{"url": _url(OLD, "o__a.keyword.json.gz")},
                           "junk"])
        assert publish_shards.prune_candidates(
            m, OLD, assets, ".keyword.json.gz") == []

    def test_room_needed_counts_only_new_names(self):
        cap = publish_shards.RELEASE_ASSET_LIMIT - publish_shards.ROOM_MARGIN
        assets = self._assets(*["x%d.shard.json" % i for i in range(cap - 1)])
        assert publish_shards.room_needed(assets, ["d/x0.shard.json"]) == 0
        assert publish_shards.room_needed(assets, ["n1.shard.json"]) == 0
        assert publish_shards.room_needed(
            assets, ["n1.shard.json", "n2.shard.json"]) == 1
        assert publish_shards.room_needed(
            assets, ["n%d.shard.json" % i for i in range(5)]) == 4

    def _cli(self, tmp_path, manifest, release, *extra):
        out = tmp_path / "out.txt"
        rc = publish_shards.main([
            "prune", "--manifest", str(_write(tmp_path / "m.json", manifest)),
            "--tag", OLD, "--release-json",
            str(_write(tmp_path / "r.json", release)),
            "--suffix", ".keyword.json.gz", "--out", str(out), *extra])
        return rc, (out.read_text(encoding="utf-8") if out.exists() else None)

    def test_cli_lists_id_and_name(self, tmp_path):
        rc, text = self._cli(tmp_path, _manifest([]), _release(
            ("o__a.keyword.json.gz", 1), ("o_a.shard.json", 1)))
        assert rc == 0 and text == "100 o__a.keyword.json.gz\n"

    def test_cli_room_for_lists_only_what_the_upload_needs(self, tmp_path):
        cap = publish_shards.RELEASE_ASSET_LIMIT - publish_shards.ROOM_MARGIN
        names = [("k%04d.keyword.json.gz" % i, 1) for i in range(cap)]
        rc, text = self._cli(tmp_path, _manifest([]), _release(*names),
                             "--room-for", "s/new1.shard.json",
                             "s/new2.shard.json")
        assert rc == 0
        assert text.split() == ["100", "k0000.keyword.json.gz",
                                "101", "k0001.keyword.json.gz"]

    def test_cli_room_for_with_room_to_spare_lists_nothing(self, tmp_path):
        rc, text = self._cli(tmp_path, _manifest([]),
                             _release(("k.keyword.json.gz", 1)),
                             "--room-for", "s/new.shard.json")
        assert rc == 0 and text == ""

    def test_cli_fails_when_no_amount_of_pruning_makes_room(self, tmp_path):
        cap = publish_shards.RELEASE_ASSET_LIMIT - publish_shards.ROOM_MARGIN
        names = [("d%04d.shard.json" % i, 1) for i in range(cap)]
        rc, text = self._cli(tmp_path, _manifest([]), _release(*names),
                             "--room-for", "s/new.shard.json")
        assert rc == 1 and text is None

    def test_cli_refuses_a_listing_without_assets(self, tmp_path):
        with pytest.raises(SystemExit, match="no `assets` list"):
            self._cli(tmp_path, _manifest([]), {})

    # `--bounded`: the guard on the passes that delete hour-long rebuilds.

    def _bounded(self, tmp_path, named, held, *extra):
        rows = [_kw("o/k%03d" % i, OLD) for i in range(named)]
        assets = [(publish_shards.keyword_asset_name("o/k%03d" % i), 1)
                  for i in range(held)]
        return self._cli(tmp_path, _manifest([], rows),
                         _release(*assets, ("o_x.shard.json", 1)), *extra)

    def test_bounded_lists_orphans_up_to_half(self, tmp_path):
        rc, text = self._bounded(tmp_path, 5, 10, "--bounded")
        assert rc == 0 and len(text.splitlines()) == 5

    def test_bounded_refuses_a_manifest_that_leaves_most_unnamed(
            self, tmp_path, capsys):
        # A manifest that lost its carry-forward names only this week's
        # rebuilds; pruning against it would delete the rest of the release.
        rc, text = self._bounded(tmp_path, 4, 10, "--bounded")
        assert rc == 1 and text == ""
        assert "refusing to prune 6 of the 10" in capsys.readouterr().out
        # The fraction is of this suffix's assets alone — the dense one the
        # listing also holds is not in the denominator.
        rc, text = self._bounded(tmp_path, 4, 10)
        assert rc == 0 and len(text.splitlines()) == 6


# ------------------------------------------------------------ capacity

class TestCapacity:

    def test_the_constants(self):
        assert publish_shards.RELEASE_ASSET_LIMIT == 1000
        assert 0 < publish_shards.RELEASE_ASSET_HEADROOM \
            < publish_shards.RELEASE_ASSET_LIMIT
        assert 0 < publish_shards.ROOM_MARGIN \
            < publish_shards.RELEASE_ASSET_HEADROOM

    def test_projection_is_the_union_of_now_and_this_run(self):
        existing = {
            OLD: {"o_a.shard.json": {}, "gone_x.shard.json": {},
                  "o__a.keyword.json.gz": {}, "manifest.json": {}},
            NEW: {"o__a.keyword.json.gz": {}, "gone__y.keyword.json.gz": {}}}
        got = publish_shards.project_assets(["o/a", "o/b"], existing)
        # shards-latest: o_a, gone_x, o_b, manifest — its keyword asset is
        # pruned by the run, so it does not count.
        assert got == {OLD: 4, NEW: 3}

    def test_an_empty_world_still_counts_the_manifest(self):
        assert publish_shards.project_assets(["o/a"], {}) == {OLD: 2, NEW: 1}

    def test_matrix_taps_splits_each_entry(self):
        assert publish_shards.matrix_taps('["o/a o/b", "o/c"]') == [
            "o/a", "o/b", "o/c"]

    @pytest.mark.parametrize("bad", ["{not json", '{"a": 1}'])
    def test_a_bad_matrix_is_refused(self, bad):
        with pytest.raises(SystemExit):
            publish_shards.matrix_taps(bad)

    def test_carried_keyword_rows_keep_their_assets_on_shards_latest(self):
        # o/a is in this run, so its keyword shard is re-exported onto the
        # new release and its old asset pruned; o/b and o/c are not, so their
        # rows are carried and their assets stay. o/d's row names an asset
        # that is not there, which the projection does not invent.
        live = _manifest([_row("o/a", OLD)],
                         [_kw("o/a", OLD), _kw("o/b", OLD), _kw("o/c", OLD),
                          _kw("o/d", OLD), _kw("o/e", NEW)])
        existing = {OLD: {"o_a.shard.json": {}, "manifest.json": {},
                          "o__a.keyword.json.gz": {},
                          "o__b.keyword.json.gz": {},
                          "o__c.keyword.json.gz": {},
                          "stray.keyword.json.gz": {}}}
        assert publish_shards.carried_keyword_assets(live, OLD, ["o/a"]) == {
            "o__b.keyword.json.gz", "o__c.keyword.json.gz",
            "o__d.keyword.json.gz"}
        got = publish_shards.project_assets(["o/a"], existing, live=live)
        # o_a, manifest, o__b and o__c.
        assert got[OLD] == 4
        # Without the live manifest the carried rows were invisible.
        assert publish_shards.project_assets(["o/a"], existing)[OLD] == 2

    def test_live_manifest_follows_the_listing(self, tmp_path):
        good = _write(tmp_path / "live.json", _manifest([]))
        missing = str(tmp_path / "missing.json")
        # No manifest on the release: none is read, whatever the file.
        assert publish_shards.live_manifest(missing, {}) is None
        assert publish_shards.live_manifest(None, {}) is None
        held = {"manifest.json": {}}
        assert publish_shards.live_manifest(str(good), held)["version"] == 1
        # Listed but not delivered is an unknown, not an absence.
        for path in (missing, None,
                     str(_write(tmp_path / "list.json", []))):
            with pytest.raises(SystemExit):
                publish_shards.live_manifest(path, held)

    def _cli(self, tmp_path, taps, existing_dense=0, raw_release=None,
             live=None):
        budget = (publish_shards.RELEASE_ASSET_LIMIT
                  - publish_shards.RELEASE_ASSET_HEADROOM)
        assert budget > 0
        rel = tmp_path / "dense.json"
        if raw_release is not None:
            rel.write_text(raw_release, encoding="utf-8")
        else:
            names = [("e%d.shard.json" % i, 1) for i in range(existing_dense)]
            if live is not None:
                # The manifest, and a dense and a keyword asset for each of
                # its keyword rows' registries.
                rows = live["keyword"]["shards"]
                names += [("manifest.json", 1)]
                names += [(publish_shards.asset_location(r["url"])[1], 1)
                          for r in rows]
                names += [(publish_shards.dense_asset_name(r["tap"]), 1)
                          for r in rows]
            _write(rel, _release(*names))
        extra = []
        if live is not None:
            extra = ["--live-manifest", str(_write(tmp_path / "live.json",
                                                   live))]
        return publish_shards.main([
            "capacity", "--matrix", json.dumps([" ".join(taps)]),
            "--release", "%s=%s" % (OLD, rel),
            "--release", "%s=%s" % (NEW, _write(tmp_path / "none.json",
                                                {"assets": []})), *extra])

    def test_at_the_budget_passes_and_one_over_fails(self, tmp_path):
        budget = (publish_shards.RELEASE_ASSET_LIMIT
                  - publish_shards.RELEASE_ASSET_HEADROOM)
        # existing + 1 planned + the manifest
        assert self._cli(tmp_path, ["o/a"], existing_dense=budget - 2) == 0
        assert self._cli(tmp_path, ["o/a"], existing_dense=budget - 1) == 1

    def test_the_keyword_release_is_checked_too(self, tmp_path):
        budget = (publish_shards.RELEASE_ASSET_LIMIT
                  - publish_shards.RELEASE_ASSET_HEADROOM)
        taps = ["o/r%d" % i for i in range(budget + 1)]
        assert self._cli(tmp_path, taps[:budget - 1]) == 0
        assert self._cli(tmp_path, taps) == 1

    @pytest.mark.parametrize("raw", ["{oops", '{"x": 1}', ""])
    def test_an_unreadable_listing_is_refused_not_read_as_empty(
            self, tmp_path, raw):
        # Read as empty, a failed listing of a full release passes the
        # check — the run then embeds for an hour and 422s at publish.
        with pytest.raises(SystemExit):
            self._cli(tmp_path, ["o/a"], raw_release=raw)

    def test_carried_rows_count_against_the_budget(self, tmp_path):
        budget = (publish_shards.RELEASE_ASSET_LIMIT
                  - publish_shards.RELEASE_ASSET_HEADROOM)
        carried = 30
        live = _manifest([], [_kw("c/%d" % i, OLD) for i in range(carried)])
        # existing + carried dense and keyword + 1 planned + the manifest
        fits = budget - 2 * carried - 2
        assert self._cli(tmp_path, ["o/a"], fits, live=live) == 0
        assert self._cli(tmp_path, ["o/a"], fits + 1, live=live) == 1
        # A run that covers the carried registries re-exports them, so their
        # old assets go and stop counting.
        taps = ["o/a"] + ["c/%d" % i for i in range(carried)]
        assert self._cli(tmp_path, taps, fits + 1, live=live) == 0

    def test_the_cli_reports_both_counts(self, tmp_path, capsys):
        self._cli(tmp_path, ["o/a"], existing_dense=3)
        out = capsys.readouterr().out
        assert "shards-latest: 5 asset(s)" in out
        assert "%s: 1 asset(s)" % NEW in out


# ------------------------------------------------------------ the workflow

PRUNE_STEP = "prune what the published manifest does not name"


def _jobs():
    # Here rather than at module level, so a missing PyYAML skips the tests
    # that read the workflow and not every test in this file.
    yaml = pytest.importorskip("yaml")
    if not SHARDS_YML.exists():
        pytest.skip("workflow not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(SHARDS_YML.read_text(encoding="utf-8"))["jobs"]


def _step(job, name):
    (step,) = [s for s in _jobs()[job]["steps"] if s.get("name") == name]
    return step


class TestWorkflowWiring:

    def test_the_plan_job_checks_capacity_after_packing(self):
        steps = _jobs()["plan"]["steps"]
        names = [s.get("id") or s.get("name") for s in steps]
        check = names.index("check both releases have room for this plan")
        assert check > names.index("pick")
        run = steps[check]["run"]
        assert "publish_shards.py capacity" in run
        assert "--release shards-latest=" in run
        assert "--release %s=" % NEW in run
        assert "--live-manifest live-manifest.json" in run
        # Only a 404 reads as "no release yet".
        assert "grep -q 'HTTP 404'" in run
        # The matrix arrives through env, not `${{ }}` in the script.
        assert "${{" not in run
        assert steps[check]["env"]["MATRIX"] == \
            "${{ steps.pick.outputs.matrix }}"

    def test_the_keyword_check_in_the_build_job_is_tag_aware(self):
        run = _step("build", "tap and embed")["run"]
        kw = run[run.index("unchanged --kind keyword"):]
        kw = kw[:kw.index("--out")]
        assert "--hosted-on %s" % NEW in kw
        # The dense check is not: its rows never moved.
        dense = run[run.index("publish_shards.py unchanged \\\n"):]
        assert "--hosted-on" not in dense[:dense.index("--out")]

    def test_the_manifest_puts_keyword_rows_on_the_keyword_tag(self):
        run = _step("publish", "build the manifest")["run"]
        assert "--tag shards-latest" in run
        assert "--keyword-tag %s" % NEW in run

    def test_the_publish_order(self):
        run = _step("publish", "publish to the rolling releases")["run"]
        order = [
            "gh release upload %s" % NEW,
            "publish_shards.py splice",
            "verify interim/manifest.json --only keyword",
            "--clobber interim/manifest.json",
            "--room-for shards/*.shard.json",
            "--clobber \"${dense[@]}\"",
            "verify shards/manifest.json",
            "--clobber shards/manifest.json",
        ]
        at = [run.index(s) for s in order]
        assert at == sorted(at), list(zip(order, at, strict=True))
        # Keyword shards never land on `shards-latest` again.
        assert "gh release upload shards-latest --repo \"$REPO\" --clobber " \
               "\"${keyword[@]}\"" not in run

    def test_the_bulk_prune_is_last_and_cannot_fail_the_run(self):
        steps = _jobs()["publish"]["steps"]
        names = [s.get("name") for s in steps]
        prune = names.index(PRUNE_STEP)
        assert prune == len(steps) - 1
        assert prune > names.index("publish to the rolling releases")
        assert steps[prune]["continue-on-error"] is True
        assert "--manifest shards/manifest.json" in steps[prune]["run"]
        # No `if:`, so the default `success()` holds: a publish step that
        # failed published no final manifest, and pruning against the
        # unpublished one could delete what the live manifest still names.
        assert "if" not in steps[prune]

    def test_the_bulk_prune_covers_both_releases_and_bounds_the_costly(self):
        run = _step("publish", PRUNE_STEP)["run"]
        calls = re.findall(r"^\s*prune_unnamed (\S+) (\S+)(.*?) \|\|", run,
                           re.MULTILINE)
        assert [(t, x, rest.split()) for t, x, rest in calls] == [
            (OLD, publish_shards.KEYWORD_SUFFIX, []),
            (OLD, publish_shards.DENSE_SUFFIX, ["--bounded"]),
            (NEW, publish_shards.KEYWORD_SUFFIX, ["--bounded"]),
        ]


# ------------------------------------------------- the shell, against a fake gh

FAKE_GH = r'''
import json, os, sys
STATE = os.environ["FAKE_GH_STATE"]
LIMIT = 1000
P = os.path.join(STATE, "releases.json")
s = json.load(open(P))


def save():
    json.dump(s, open(P, "w"))


def note(name, *words):
    with open(os.path.join(STATE, name), "a") as fh:
        fh.write(" ".join(str(w) for w in words) + "\n")


def live_rows():
    path = os.path.join(STATE, "live-manifest.json")
    m = json.load(open(path)) if os.path.exists(path) else {}
    rows = list(m.get("shards") or [])
    rows += list((m.get("keyword") or {}).get("shards") or [])
    return rows


def where(url):
    parts = url.split("/")
    return parts[-2], parts[-1]


def check_live():
    for row in live_rows():
        tag, name = where(row["url"])
        asset = s["releases"].get(tag, {}).get("assets", {}).get(name)
        if asset is None:
            note("violations.txt", "live manifest names missing", tag, name)
        elif row.get("bytes") is not None and asset["size"] != row["bytes"]:
            note("violations.txt", "live manifest size mismatch", tag, name)


def new_id():
    s["next"] += 1
    return s["next"]


a = sys.argv[1:]
if a[:2] == ["release", "view"]:
    sys.exit(0 if a[2] in s["releases"] else 1)
if a[:2] == ["release", "create"]:
    s["releases"][a[2]] = {"flags": a[3:], "assets": {}}
    note("log.txt", "create", a[2])
    save()
    sys.exit(0)
if a[:2] == ["release", "upload"]:
    tag, rest = a[2], a[3:]
    clobber = "--clobber" in rest
    files, skip = [], False
    for x in rest:
        if skip:
            skip = False
        elif x == "--repo":
            skip = True
        elif not x.startswith("--"):
            files.append(x)
    rel = s["releases"][tag]["assets"]
    fail = os.environ.get("FAKE_GH_FAIL_UPLOAD", "")
    for f in files:
        name = os.path.basename(f)
        # `gh release upload --clobber` deletes the old asset, THEN uploads:
        # a failure in between leaves neither, which is modelled faithfully.
        if name in rel:
            assert clobber, "upload without --clobber over " + name
            del rel[name]
        if name == fail:
            save()
            print("HTTP 502: upload failed (" + name + ")", file=sys.stderr)
            sys.exit(1)
        if len(rel) >= LIMIT:
            save()
            print("HTTP 422: Validation Failed\nfile_count limited to 1000 "
                  "assets per release", file=sys.stderr)
            sys.exit(1)
        rel[name] = {"id": new_id(), "size": os.path.getsize(f)}
        s["peak"][tag] = max(s["peak"].get(tag, 0), len(rel))
        note("log.txt", "upload", tag, name)
        if tag == "shards-latest" and name == "manifest.json":
            with open(f) as src, open(os.path.join(
                    STATE, "live-manifest.json"), "w") as dst:
                dst.write(src.read())
            check_live()
    save()
    sys.exit(0)
if a[0] == "api":
    if "-X" in a:
        i = a.index("-X")
        assert a[i + 1] == "DELETE"
        path = [x for x in a[1:] if x not in ("-X", "DELETE")][0]
        aid = int(path.rsplit("/", 1)[1])
        for tag, rel in s["releases"].items():
            for name, asset in list(rel["assets"].items()):
                if asset["id"] == aid:
                    if any(where(r["url"]) == (tag, name)
                           for r in live_rows()):
                        note("violations.txt", "deleted a live asset", tag,
                             name)
                    del rel["assets"][name]
                    note("log.txt", "delete", tag, name)
                    save()
                    sys.exit(0)
        sys.exit(1)
    tag = a[1].rsplit("/", 1)[1]
    # Real `gh api` reports an HTTP error on stderr as `gh: MESSAGE (HTTP N)`.
    if tag in os.environ.get("FAKE_GH_FAIL_API", "").split():
        print("gh: Server Error (HTTP 502)", file=sys.stderr)
        sys.exit(1)
    if tag not in s["releases"]:
        print("gh: Not Found (HTTP 404)", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"id": 1, "tag_name": tag, "assets": [
        {"id": v["id"], "name": k, "size": v["size"]}
        for k, v in s["releases"][tag]["assets"].items()]}))
    sys.exit(0)
print("fake gh: unhandled", a, file=sys.stderr)
sys.exit(2)
'''

#: `curl -fsSL ... -o FILE URL` for the one URL the plan step fetches: the
#: published manifest, served while `shards-latest` holds it.
FAKE_CURL = r'''
import json, os, shutil, sys
STATE = os.environ["FAKE_GH_STATE"]
a = sys.argv[1:]
out, url = a[a.index("-o") + 1], a[-1]
assert url.endswith("/releases/download/shards-latest/manifest.json"), url
s = json.load(open(os.path.join(STATE, "releases.json")))
held = s["releases"].get("shards-latest", {}).get("assets", {})
live = os.path.join(STATE, "live-manifest.json")
if os.environ.get("FAKE_CURL_FAIL") or "manifest.json" not in held \
        or not os.path.exists(live):
    print("curl: (22) The requested URL returned error", file=sys.stderr)
    sys.exit(22)
shutil.copy(live, out)
'''


class FakeRepo:
    """A working directory laid out like the publish job's, plus a fake gh."""

    def __init__(self, tmp_path):
        self.root = tmp_path / "work"
        self.state = tmp_path / "gh"
        self.bin = tmp_path / "bin"
        for d in (self.root / "shards", self.state, self.bin):
            d.mkdir(parents=True)
        (self.root / "scripts").symlink_to(ROOT / "scripts")
        (self.bin / "fake_gh.py").write_text(FAKE_GH, encoding="utf-8")
        (self.bin / "fake_curl.py").write_text(FAKE_CURL, encoding="utf-8")
        for name, body in (
                ("gh", 'exec "%s" -S -E "%s" "$@"\n'
                       % (sys.executable, self.bin / "fake_gh.py")),
                ("curl", 'exec "%s" -S -E "%s" "$@"\n'
                         % (sys.executable, self.bin / "fake_curl.py")),
                ("python3", 'exec "%s" "$@"\n' % sys.executable),
                ("sleep", ":\n")):            # pacing is real time; skip it
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
            path.chmod(0o755)
        self.releases: dict = {"next": 1000, "peak": {}, "releases": {}}

    def seed(self, tag, assets, manifest=None):
        rel = self.releases["releases"].setdefault(
            tag, {"flags": ["--prerelease", "--latest=false"], "assets": {}})
        for name, size in assets.items():
            self.releases["next"] += 1
            rel["assets"][name] = {"id": self.releases["next"], "size": size}
        if manifest is not None:
            text = json.dumps(manifest)
            rel["assets"]["manifest.json"] = {"id": 1, "size": len(text)}
            (self.state / "live-manifest.json").write_text(text,
                                                           encoding="utf-8")
            (self.root / "previous-manifest.json").write_text(
                text, encoding="utf-8")

    def run(self, job, step, **env):
        _write(self.state / "releases.json", self.releases)
        script = self.root / "step.sh"
        script.write_text(_step(job, step)["run"], encoding="utf-8")
        full = {**os.environ, "PATH": "%s:%s" % (self.bin, os.environ["PATH"]),
                "GH_TOKEN": "x", "REPO": "o/r",
                "FAKE_GH_STATE": str(self.state), **env}
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo",
                               "pipefail", str(script)], cwd=self.root,
                              env=full, capture_output=True, text=True,
                              timeout=300)
        self.releases = json.loads((self.state / "releases.json")
                                   .read_text(encoding="utf-8"))
        return proc

    def assets(self, tag):
        return self.releases["releases"].get(tag, {}).get("assets", {})

    def lines(self, name):
        path = self.state / name
        return (path.read_text(encoding="utf-8").splitlines()
                if path.exists() else [])

    def live(self):
        return json.loads((self.state / "live-manifest.json")
                          .read_text(encoding="utf-8"))


#: The migration's shape at a size a unit test can afford: `shards-latest`
#: one asset short of full, every asset named by the live manifest (so no
#: orphan can make room), and a run that adds five registries — which a
#: single-manifest order cannot upload without first deleting something the
#: live manifest still names.
N_DENSE, N_KW, N_NEW = 950, 48, 5


def _migration(tmp_path, moved=3, broken=0, dead=0):
    """Seed the fake and build this run's manifest, as the build jobs would.

    `moved` registries were re-embedded this run; the first `broken` of them
    were also clobbered by a failed run, so the live manifest's row for them
    no longer matches the asset's size — the 2026-10-11 manifest's state.
    The `dead` registries after them were in a build job that died, so no
    job reports on them and both their rows are carried as they are.
    """
    repo = FakeRepo(tmp_path)
    old = [f"t/{i:04d}" for i in range(N_DENSE)]
    new = [f"n/{i}" for i in range(N_NEW)]
    dense_rows = [_row(t, OLD, size=100 + i) for i, t in enumerate(old)]
    kw_rows = [_kw(t, OLD, size=50 + i) for i, t in enumerate(old[:N_KW])]
    live = _manifest(dense_rows, kw_rows)
    sizes = {publish_shards.asset_location(r["url"])[1]: r["bytes"]
             for r in dense_rows + kw_rows}
    for t in old[:broken]:
        sizes[publish_shards.dense_asset_name(t)] += 1
    repo.seed(OLD, sizes, live)
    assert len(repo.assets(OLD)) == publish_shards.RELEASE_ASSET_LIMIT - 1
    # What the build jobs hand over: the moved registries and the five new
    # ones re-embedded, every keyword shard re-exported (none was on the new
    # tag), the rest of the dense rows reported unchanged.
    d = repo.root / "shards"
    rebuilt = old[:moved] + new
    for t in rebuilt:
        _dense_file(d, t, B)
    assert not dead or moved + dead <= N_KW   # dead ones have keyword rows
    silent = set(old[moved:moved + dead])
    for t in old[:N_KW] + new:
        if t not in silent:
            _kw_file(d, t, B)
    (d / "unchanged-0.txt").write_text(
        "".join("%s %s\n" % (t, A) for t in old[moved:] if t not in silent),
        encoding="utf-8")
    (d / "keyword-unchanged-0.txt").write_text("", encoding="utf-8")
    known = repo.root / "known.txt"
    known.write_text("\n".join(old + new) + "\n", encoding="utf-8")
    assert publish_shards.main([
        "manifest", "--shard-dir", str(d), "--repo", "o/r",
        "--tag", OLD, "--keyword-tag", NEW,
        "--out", str(d / "manifest.json"),
        "--carry-forward", str(repo.root / "previous-manifest.json"),
        "--unchanged", str(d / "unchanged-0.txt"),
        "--keyword-unchanged", str(d / "keyword-unchanged-0.txt"),
        "--known", str(known)]) == 0
    return repo


@pytest.mark.skipif(sys.platform == "win32", reason="runs the bash step")
class TestPublishShell:
    """The workflow's own `run:` blocks, executed against a fake `gh`."""

    def test_the_migration_run_never_names_a_missing_asset(self, tmp_path):
        repo = _migration(tmp_path)
        proc = repo.run("publish", "publish to the rolling releases")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert repo.lines("violations.txt") == []
        log = repo.lines("log.txt")
        # The keyword release was made the way `shards-latest` was.
        assert log[0] == "create " + NEW
        flags = repo.releases["releases"][NEW]["flags"]
        assert "--prerelease" in flags and "--latest=false" in flags
        # The interim manifest went up before the first dense shard, and
        # room was made only after it.
        manifests = [i for i, ln in enumerate(log)
                     if ln == "upload shards-latest manifest.json"]
        first_dense = next(i for i, ln in enumerate(log)
                           if ln.startswith("upload shards-latest")
                           and ln.endswith(".shard.json"))
        first_delete = next(i for i, ln in enumerate(log)
                            if ln.startswith("delete"))
        assert len(manifests) == 2
        assert manifests[0] < first_delete < first_dense < manifests[1]
        assert max(repo.releases["peak"].values()) <= \
            publish_shards.RELEASE_ASSET_LIMIT
        live = repo.live()
        assert {publish_shards.asset_location(r["url"])[0]
                for r in live["keyword"]["shards"]} == {NEW}
        assert len(live["keyword"]["shards"]) == N_KW + N_NEW
        assert len(live["shards"]) == N_DENSE + N_NEW
        # Every row is still downloadable by a boost that predates the split.
        assert all(shards._same_origin(r["url"], "https://github.com/o/r/"
                                       "releases/download/shards-latest/"
                                       "manifest.json")
                   for r in live["shards"] + live["keyword"]["shards"])

        proc = repo.run("publish", PRUNE_STEP)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert repo.lines("violations.txt") == []
        assert not [n for n in repo.assets(OLD)
                    if n.endswith(publish_shards.KEYWORD_SUFFIX)]
        assert len(repo.assets(OLD)) == N_DENSE + N_NEW + 1
        assert len(repo.assets(NEW)) == N_KW + N_NEW

        # The week after: nothing moved. Nothing is deleted, nothing named
        # goes missing, and the counts hold.
        for p in (repo.root / "shards").iterdir():
            if p.name != "manifest.json":
                p.unlink()
        (repo.root / "previous-manifest.json").write_text(
            json.dumps(live), encoding="utf-8")
        proc = repo.run("publish", "publish to the rolling releases")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        proc = repo.run("publish", PRUNE_STEP)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert repo.lines("violations.txt") == []
        assert len(repo.assets(OLD)) == N_DENSE + N_NEW + 1

    def test_a_run_cut_off_mid_upload_leaves_a_valid_live_manifest(
            self, tmp_path):
        repo = _migration(tmp_path)
        # The first dense shard in glob order is a new name, so nothing has
        # been clobbered when the upload dies — `--clobber`'s own
        # delete-then-upload window is the one gap this order cannot close.
        proc = repo.run("publish", "publish to the rolling releases",
                        FAKE_GH_FAIL_UPLOAD="n_0.shard.json")
        assert proc.returncode != 0
        assert repo.lines("violations.txt") == []
        # What is live is the interim: keyword rows already on their own
        # release, every one of them there at its recorded size.
        live = repo.live()
        assert {publish_shards.asset_location(r["url"])[0]
                for r in live["keyword"]["shards"]} == {NEW}

    def test_a_live_manifest_broken_past_half_still_publishes(self, tmp_path):
        # More failed weeks of `--clobber` push the live dense rows past
        # MAX_DROP_FRACTION. The interim must still go up, or no room is
        # made and the run 422s — and so does every run after it.
        broken = int(N_DENSE * publish_shards.MAX_DROP_FRACTION) + 50
        repo = _migration(tmp_path, moved=broken, broken=broken)
        proc = repo.run("publish", "publish to the rolling releases")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # The only complaints are the interim re-publishing the rows that
        # were already broken while live; the final manifest has none.
        stale = {publish_shards.dense_asset_name(f"t/{i:04d}")
                 for i in range(broken)}
        for line in repo.lines("violations.txt"):
            assert line.startswith("live manifest size mismatch shards-latest")
            assert line.split()[-1] in stale
        live = repo.live()
        for row in live["shards"] + live["keyword"]["shards"]:
            tag, name = publish_shards.asset_location(row["url"])
            assert repo.assets(tag)[name]["size"] == row["bytes"], name

    def test_the_plan_step_fails_a_run_that_would_overfill(self, tmp_path):
        repo = FakeRepo(tmp_path)
        budget = (publish_shards.RELEASE_ASSET_LIMIT
                  - publish_shards.RELEASE_ASSET_HEADROOM)
        repo.seed(OLD, {"e%d.shard.json" % i: 1 for i in range(budget)})
        proc = repo.run("plan", "check both releases have room for this plan",
                        MATRIX=json.dumps(["o/a"]))
        assert proc.returncode == 1
        assert "::error::shards-latest would hold %d" % (budget + 2) \
            in proc.stdout

    def test_the_plan_step_reads_a_missing_release_as_empty(self, tmp_path):
        repo = FakeRepo(tmp_path)
        repo.seed(OLD, {"e.shard.json": 1})
        proc = repo.run("plan", "check both releases have room for this plan",
                        MATRIX=json.dumps(["o/a o/b"]))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "no %s release to count yet" % NEW in proc.stdout
        assert "%s: 2 asset(s)" % NEW in proc.stdout

    def _plan(self, repo, taps, **env):
        return repo.run("plan", "check both releases have room for this plan",
                        MATRIX=json.dumps([" ".join(taps)]), **env)

    @pytest.mark.parametrize("failing", [OLD, NEW])
    def test_the_plan_step_fails_closed_on_any_other_listing_error(
            self, tmp_path, failing):
        # A 502 or a rate limit is not "no release yet". Read as one, a
        # release a few assets from full passes, and the run 422s an hour
        # later at publish — the late failure this step exists to prevent.
        repo = FakeRepo(tmp_path)
        repo.seed(OLD, {"e%d.shard.json" % i: 1 for i in range(950)})
        repo.seed(NEW, {"e%d.keyword.json.gz" % i: 1 for i in range(950)})
        proc = self._plan(repo, ["o/a"], FAKE_GH_FAIL_API=failing)
        assert proc.returncode != 0, proc.stdout
        assert "could not list %s" % failing in proc.stdout
        assert "HTTP 502" in proc.stderr

    def test_the_plan_step_refuses_a_listed_manifest_it_did_not_fetch(
            self, tmp_path):
        repo = FakeRepo(tmp_path)
        repo.seed(OLD, {}, _manifest([], [_kw("c/0", OLD)]))
        assert self._plan(repo, ["o/a"]).returncode == 0
        # A fresh checkout, as on a runner: no file left by the run above.
        (repo.root / "live-manifest.json").unlink()
        proc = self._plan(repo, ["o/a"], FAKE_CURL_FAIL="1")
        assert proc.returncode != 0
        assert "live-manifest.json" in proc.stderr

    def test_the_plan_step_counts_rows_carried_for_unreported_registries(
            self, tmp_path):
        # Five registries' build job died during the migration run, so their
        # keyword rows are carried, still naming `shards-latest`, and the
        # assets stay there with them.
        dead = 5
        repo = _migration(tmp_path, dead=dead)
        for step in ("publish to the rolling releases", PRUNE_STEP):
            proc = repo.run("publish", step)
            assert proc.returncode == 0, proc.stdout + proc.stderr
        assert repo.lines("violations.txt") == []
        held = repo.assets(OLD)
        assert sum(n.endswith(publish_shards.KEYWORD_SUFFIX)
                   for n in held) == dead
        old = [f"t/{i:04d}" for i in range(N_DENSE)]
        # A scoped run that leaves them out carries them again, so the
        # projection is exactly what the release holds. (Both counts are
        # over the 900 budget at this fixture's size; the numbers are the
        # point here, not the verdict.)
        proc = self._plan(repo, ["n/0"])
        assert "%s: %d asset(s)" % (OLD, len(held)) in proc.stdout
        # A run that covers them re-exports them onto the keyword release.
        proc = self._plan(repo, old)
        assert "%s: %d asset(s)" % (OLD, len(held) - dead) in proc.stdout

    def test_the_final_prune_clears_orphans_on_both_releases(self, tmp_path):
        repo = _migration(tmp_path)
        proc = repo.run("publish", "publish to the rolling releases")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # A registry that left the catalogue: its rows are gone from the
        # manifest, its assets are not.
        repo.seed(OLD, {"gone_x.shard.json": 7})
        repo.seed(NEW, {"gone__x.keyword.json.gz": 7})
        proc = repo.run("publish", PRUNE_STEP)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert repo.lines("violations.txt") == []
        assert "gone_x.shard.json" not in repo.assets(OLD)
        assert "gone__x.keyword.json.gz" not in repo.assets(NEW)
        assert len(repo.assets(OLD)) == N_DENSE + N_NEW + 1
        assert len(repo.assets(NEW)) == N_KW + N_NEW

    def test_the_final_prune_will_not_follow_a_manifest_that_lost_its_rows(
            self, tmp_path):
        # "build the manifest" reads a failed fetch of last week's manifest
        # as a first run: the result names only this week's rebuilds. It is
        # published, and the dense prune must not take the rest with it.
        repo = _migration(tmp_path)
        proc = repo.run("publish", "publish to the rolling releases")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        path = repo.root / "shards" / "manifest.json"
        shrunk = json.loads(path.read_text(encoding="utf-8"))
        shrunk["shards"] = [r for r in shrunk["shards"]
                            if r["commit"] == B]
        assert 0 < len(shrunk["shards"]) < N_DENSE // 2
        for dest in (path, repo.state / "live-manifest.json"):
            dest.write_text(json.dumps(shrunk), encoding="utf-8")
        repo.seed(NEW, {"gone__x.keyword.json.gz": 7})
        dense_before = {n for n in repo.assets(OLD)
                        if n.endswith(publish_shards.DENSE_SUFFIX)}
        proc = repo.run("publish", PRUNE_STEP)
        assert proc.returncode != 0
        assert "refusing to prune" in proc.stdout
        assert {n for n in repo.assets(OLD)
                if n.endswith(publish_shards.DENSE_SUFFIX)} == dense_before
        # The refusal stopped only its own pass: the keyword release's
        # orphan, one pass later, is gone.
        assert "gone__x.keyword.json.gz" not in repo.assets(NEW)
