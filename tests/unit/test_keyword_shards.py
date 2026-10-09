# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The BM25 keyword index is published and imported the way vectors are.

Every machine used to rebuild the same index from the same registries at the
same pinned commits, and one kind of machine could not rebuild it properly at
all: `boost catalog --import` restores catalogues with no clone behind them,
so every entry indexed from its metadata alone — 6.0% of the searchable text,
measured. These tests drive the whole path a published keyword shard takes:

* ``rag.export_shard`` builds one from a clone, and refuses a tap without one;
* ``scripts/publish_shards.py`` gzips it, lists unchanged registries, and
  writes the manifest's ``keyword`` section with the dense carry-forward rules;
* ``shards.sync_keyword`` downloads against a local ``file:`` manifest,
  verifies, and merges through ``rag.import_shards``, which refuses on a
  commit mismatch — two absences included — before writing anything;
* ``boost reindex --fetch-index`` turns a metadata-only index into a body
  index, end to end.

The CI half cannot run here; ``TestWorkflowWiring`` pins it statically, the
way the dense side's tests do.
"""
from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import rag, registry, shards
from boost_cli.errors import BoostError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_shards  # noqa: E402

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}
A, B = "a" * 40, "b" * 40

#: A word that appears in the fixture's `cowboy-coding` BODY and nowhere in
#: its name, description or any other item — reachable only through a body.
BODY_ONLY = "prototypes"


def _doc(tap, name="x", body=("alpha", "beta"), **over):
    tf: dict[str, int] = {}
    for w in body:
        tf[w] = tf.get(w, 0) + 1
    d = {"n": name, "t": tap, "f": "skills/%s/SKILL.md" % name, "k": "skill",
         "h": "h" + name, "l": sum(tf.values()), "snip": " ".join(body),
         "tf": tf}
    d.update(over)
    return d


def _shard(tap="o/a", commit=A, docs=None, **over):
    s = {"format": rag.SHARD_FORMAT, "engine": rag.ENGINE,
         "index_version": rag.INDEX_VERSION, "tap": tap, "commit": commit,
         "docs": docs if docs is not None else [_doc(tap)]}
    s.update(over)
    return s


def _tap_cloned(fixture_tap_src):
    tap = registry.add(str(fixture_tap_src))
    return tap, rag._tap_commits()[tap.safe_name]


def _publish(tmp_path, shard_list, version=None, extra_rows=()):
    """Write each shard as a `.keyword.json.gz` plus a file: manifest."""
    pub = tmp_path / "pub"
    pub.mkdir(exist_ok=True)
    rows = []
    for s in shard_list:
        data = publish_shards.keyword_bytes(s)
        path = pub / (s["tap"].replace("/", "__") + ".keyword.json.gz")
        path.write_bytes(data)
        row, _v = publish_shards._keyword_row(path, "o/r", "shards-latest")
        row["url"] = path.as_uri()
        rows.append(row)
    rows.extend(extra_rows)
    manifest = {"version": 1, **SPACE, "shards": [],
                "keyword": {"format": rag.SHARD_FORMAT,
                            "index_version": (rag.INDEX_VERSION
                                              if version is None else version),
                            "shards": rows}}
    mpath = pub / "manifest.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")
    return mpath


def _hits(query):
    """Names BM25 scores above zero for `query`, read off the index on disk.

    Straight through `_bm25` rather than `retrieve`, which would first ask
    `ensure()` to rebuild an index whose taps are not configured here.
    """
    raw = rag._load_raw()
    if raw is None:
        return []
    terms = rag.tokenize(query)
    scores = rag._bm25(terms, raw, rag.read_postings(terms))
    return sorted(raw["docs"][i]["n"] for i, v in scores.items() if v > 0)


# --------------------------------------------------------------- shard_problem

class TestShardProblem:
    """Every refusal, and the one acceptance, before anything is written."""

    def test_a_whole_shard_at_the_taps_commit_is_accepted(self):
        assert rag.shard_problem(_shard(), A) is None

    def test_the_optional_digest_and_metadata_flag_are_accepted(self):
        bare = {k: v for k, v in _doc("o/a").items() if k != "h"}
        assert rag.shard_problem(_shard(docs=[bare]), A) is None
        assert rag.shard_problem(_shard(docs=[_doc("o/a", m=1)]), A) is None

    @pytest.mark.parametrize("shard, commit, fragment", [
        ([], A, "not an object"),
        (_shard(engine="dense"), A, "engine"),
        (_shard(format=2), A, "format"),
        (_shard(index_version=rag.INDEX_VERSION - 1), A, "index version"),
        (_shard(tap=""), A, "names no tap"),
        (_shard(commit=""), A, "commit unknown"),
        # Two absences are not a match.
        (_shard(commit=""), "", "commit unknown"),
        (_shard(), "", "commit unknown"),
        (_shard(commit=B), A, "commit mismatch"),
        (_shard(docs=[]), A, "no documents"),
        (_shard(docs=["x"]), A, "not an object"),
        (_shard(docs=[_doc("o/a", l=True)]), A, "valid 'l'"),
        (_shard(docs=[{k: v for k, v in _doc("o/a").items() if k != "snip"}]),
         A, "valid 'snip'"),
        (_shard(docs=[_doc("o/other")]), A, "belongs to"),
        (_shard(docs=[_doc("o/a", tf={}, l=0)]), A, "malformed term table"),
        (_shard(docs=[_doc("o/a", tf={"x": 0}, l=0)]), A, "malformed"),
        (_shard(docs=[_doc("o/a", tf={"x": True}, l=1)]), A, "malformed"),
        (_shard(docs=[_doc("o/a", tf={"": 1}, l=1)]), A, "malformed"),
        (_shard(docs=[_doc("o/a", l=3)]), A, "disagrees"),
        (_shard(docs=[_doc("o/a", n="")]), A, "empty name or path"),
        (_shard(docs=[_doc("o/a", f="")]), A, "empty name or path"),
        (_shard(docs=[_doc("o/a", h=["x"])]), A, "valid 'h'"),
        (_shard(docs=[_doc("o/a", m=2)]), A, "valid 'm'"),
        (_shard(docs=[_doc("o/a", m=0)]), A, "valid 'm'"),
        (_shard(docs=[_doc("o/a", m=True)]), A, "valid 'm'"),
    ])
    def test_refusals(self, shard, commit, fragment):
        why = rag.shard_problem(shard, commit)
        assert why is not None and fragment in why


# --------------------------------------------------------------- import_shards

class TestImport:

    def test_an_import_into_no_index_makes_one_that_searches(self, sandbox):
        rag.import_shards([(_shard(docs=[_doc("o/a", "one", ("zebra",))]), A)])
        assert rag.ready()
        assert _hits("zebra") == ["one"]

    def test_other_taps_survive_and_the_imported_tap_is_replaced(self, sandbox):
        rag.import_shards([
            (_shard("o/a", A, [_doc("o/a", "old", ("walrus",))]), A),
            (_shard("o/b", B, [_doc("o/b", "keep", ("otter",))]), B)])
        res = rag.import_shards(
            [(_shard("o/a", A, [_doc("o/a", "new", ("narwhal",))]), A)])
        assert res == [("o/a", True, "1 documents")]
        raw = rag._load_raw()
        assert sorted(d["n"] for d in raw["docs"]) == ["keep", "new"]
        assert raw["commits"] == {"o__a": A, "o__b": B}
        assert _hits("walrus") == []          # replaced, never doubled
        assert _hits("otter") == ["keep"]     # its postings came through
        assert _hits("narwhal") == ["new"]

    def test_a_refused_shard_writes_nothing(self, sandbox):
        rag.import_shards([(_shard(docs=[_doc("o/a", "one", ("zebra",))]), A)])
        before = rag.index_path().read_bytes()
        res = rag.import_shards(
            [(_shard(commit=B, docs=[_doc("o/a", "two", ("yak",))]), A)])
        assert res[0][1] is False and "mismatch" in res[0][2]
        assert rag.index_path().read_bytes() == before

    def test_nothing_accepted_means_no_index_is_created(self, sandbox):
        rag.import_shards([(_shard(commit=""), "")])
        assert not rag.index_path().exists()

    def test_a_second_shard_for_one_tap_in_a_batch_is_refused(self, sandbox):
        res = rag.import_shards([(_shard(), A), (_shard(), A)])
        assert [r[1] for r in res] == [True, False]
        assert "second shard" in res[1][2]
        assert len(rag._load_raw()["docs"]) == 1

    def test_import_shard_is_the_one_shard_form(self, sandbox):
        assert rag.import_shard(_shard(), A) == (True, "1 documents")
        ok, why = rag.import_shard(_shard(), B)
        assert not ok and "mismatch" in why

    def test_avg_len_is_recomputed_over_the_merged_corpus(self, sandbox):
        rag.import_shards([
            (_shard("o/a", A, [_doc("o/a", "x", ("a",) * 2)]), A),
            (_shard("o/b", B, [_doc("o/b", "y", ("b",) * 6)]), B)])
        assert rag._load_raw()["stats"]["avg_len"] == 4.0


class TestCompleteTapCommits:

    def test_no_index_is_empty(self, sandbox):
        assert rag.complete_tap_commits() == {}

    def test_a_tap_with_a_metadata_only_document_is_not_complete(self, sandbox):
        rag.import_shards([
            (_shard("o/a", A, [_doc("o/a", "x"), _doc("o/a", "y", m=1)]), A),
            (_shard("o/b", B, [_doc("o/b", "z")]), B)])
        assert rag.complete_tap_commits() == {"o/b": B}


    def test_an_unknown_commit_or_a_tap_with_no_documents_is_not_complete(
            self, sandbox):
        rag._save([{**_doc("o/a", "x"), "c": 0}, {**_doc("o/b", "y"), "c": 0}],
                  {"o__a": A, "o__b": "", "o__c": B})
        assert rag.complete_tap_commits() == {"o/a": A}


# ------------------------------------------------------- export, real fixture

class TestExport:

    def test_exports_every_entry_with_bodies_at_the_tap_commit(
            self, sandbox, fixture_tap_src):
        tap, commit = _tap_cloned(fixture_tap_src)
        shard = rag.export_shard(tap.name)
        assert shard["commit"] == commit and len(commit) == 40
        assert shard["tap"] == tap.name
        assert shard["index_version"] == rag.INDEX_VERSION
        assert rag.shard_problem(shard, commit) is None
        assert not any(d.get("m") for d in shard["docs"])
        assert all("c" not in d for d in shard["docs"])
        assert [d["f"] for d in shard["docs"]] == sorted(
            d["f"] for d in shard["docs"])
        assert any(BODY_ONLY in d["tf"] for d in shard["docs"])
        # Deterministic bytes, so an unchanged registry republishes nothing.
        assert (publish_shards.keyword_bytes(shard)
                == publish_shards.keyword_bytes(rag.export_shard(tap.name)))

    def test_a_tap_without_a_clone_is_refused(self, sandbox, fixture_tap_src):
        tap, _c = _tap_cloned(fixture_tap_src)
        shutil.rmtree(tap.path)
        with pytest.raises(BoostError, match="no clone"):
            rag.export_shard(tap.name)

    def test_an_untapped_registry_is_refused(self, sandbox):
        with pytest.raises(BoostError, match="not tapped"):
            rag.export_shard("o/nope")

    def test_an_unknown_commit_is_refused(self, sandbox, fixture_tap_src,
                                          monkeypatch):
        tap, _c = _tap_cloned(fixture_tap_src)
        monkeypatch.setattr(rag, "_tap_commits", lambda: {tap.safe_name: ""})
        with pytest.raises(BoostError, match="which commit"):
            rag.export_shard(tap.name)


# --------------------------------------------------- the manifest's section

class TestKeywordSection:

    def test_no_section_is_incompatible_and_has_no_rows(self):
        m = {"shards": []}
        assert shards.keyword_section(m) == {}
        assert shards.keyword_rows(m) == {}
        assert "no keyword index" in shards.keyword_incompatible(m)
        assert shards.keyword_section({"keyword": []}) == {}

    def test_version_and_format_must_be_this_builds(self):
        good = {"keyword": {"format": rag.SHARD_FORMAT,
                            "index_version": rag.INDEX_VERSION, "shards": []}}
        assert shards.keyword_incompatible(good) is None
        old = {"keyword": {**good["keyword"],
                           "index_version": rag.INDEX_VERSION - 1}}
        assert "version" in shards.keyword_incompatible(old)
        fmt = {"keyword": {**good["keyword"], "format": 99}}
        assert "format" in shards.keyword_incompatible(fmt)

    def test_rows_skip_malformed_entries(self):
        m = {"keyword": {"shards": [
            {"tap": "o/a", "commit": A, "url": "u", "sha256": "s"},
            {"tap": "o/b", "commit": A, "url": "u"},           # no digest
            "junk"]}}
        assert list(shards.keyword_rows(m)) == ["o/a"]


class TestInflate:

    def test_not_gzip(self, tmp_path):
        p = tmp_path / "x.gz"
        p.write_bytes(b"plain")
        with pytest.raises(BoostError, match="gzip"):
            shards._inflate(p)

    def test_not_json(self, tmp_path):
        p = tmp_path / "x.gz"
        p.write_bytes(gzip.compress(b"{nope"))
        with pytest.raises(BoostError, match="JSON"):
            shards._inflate(p)

    def test_not_an_object(self, tmp_path):
        p = tmp_path / "x.gz"
        p.write_bytes(gzip.compress(b"[1]"))
        with pytest.raises(BoostError, match="object"):
            shards._inflate(p)

    def test_inflation_is_capped(self, tmp_path, monkeypatch):
        p = tmp_path / "x.gz"
        p.write_bytes(gzip.compress(b'{"a": "' + b"x" * 100 + b'"}'))
        monkeypatch.setattr(shards, "MAX_KEYWORD_INFLATED", 108)
        with pytest.raises(BoostError, match="inflates"):
            shards._inflate(p)
        monkeypatch.setattr(shards, "MAX_KEYWORD_INFLATED", 109)
        assert shards._inflate(p) == {"a": "x" * 100}


# --------------------------------------------- sync, against a file: manifest

class TestSyncKeyword:

    def _load(self, mpath):
        return shards.fetch_manifest(mpath.as_uri())

    def test_imports_a_verified_shard(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard(docs=[_doc("o/a", "one",
                                                      ("zebra",))])])
        res = shards.sync_keyword(["o/a"], {"o/a": A},
                                  manifest=self._load(mpath),
                                  cache_dir=tmp_path / "c")
        assert res == [{"tap": "o/a", "status": "imported",
                        "detail": "1 documents", "docs": 1}]
        assert _hits("zebra") == ["one"]
        assert list((tmp_path / "c").iterdir()) == []    # no leftover file

    def test_a_tap_already_complete_at_the_commit_downloads_nothing(
            self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        (tmp_path / "pub" / "o__a.keyword.json.gz").unlink()  # would fail
        res = shards.sync_keyword(["o/a"], {"o/a": A},
                                  manifest=self._load(mpath),
                                  built={"o/a": A})
        assert [r["status"] for r in res] == ["current"]

    def test_a_tampered_asset_is_refused_and_writes_nothing(
            self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        asset = tmp_path / "pub" / "o__a.keyword.json.gz"
        asset.write_bytes(publish_shards.keyword_bytes(
            _shard(docs=[_doc("o/a", "evil", ("evil",))])))
        res = shards.sync_keyword(["o/a"], {"o/a": A},
                                  manifest=self._load(mpath))
        assert res[0]["status"] == "failed"
        assert "verification" in res[0]["detail"]
        assert not rag.index_path().exists()

    def test_a_url_off_the_manifests_host_is_refused(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        m = self._load(mpath)
        m["keyword"]["shards"][0]["url"] = "https://evil.example/x.gz"
        res = shards.sync_keyword(["o/a"], {"o/a": A}, manifest=m)
        assert res[0]["status"] == "failed"
        assert "manifest's own host" in res[0]["detail"]

    def test_a_moved_tap_is_refused_before_downloading(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        res = shards.sync_keyword(["o/a"], {"o/a": B},
                                  manifest=self._load(mpath))
        assert res[0]["status"] == "refused"
        assert not rag.index_path().exists()

    def test_a_shard_whose_own_commit_disagrees_with_its_row_is_refused(
            self, sandbox, tmp_path):
        # The row says A and so does the tap, but the bytes say B: the
        # import-time check is the one that catches it.
        mpath = _publish(tmp_path, [_shard(commit=B)])
        m = self._load(mpath)
        m["keyword"]["shards"][0]["commit"] = A
        res = shards.sync_keyword(["o/a"], {"o/a": A}, manifest=m)
        assert res[0]["status"] == "refused"
        assert "mismatch" in res[0]["detail"]

    def test_an_unknown_local_commit_is_never_a_match(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        res = shards.sync_keyword(["o/a"], {"o/a": ""},
                                  manifest=self._load(mpath))
        assert res[0]["status"] == "refused"
        assert "commit unknown" in res[0]["detail"]

    def test_unpublished_and_incompatible(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        res = shards.sync_keyword(["o/zz"], {"o/zz": A},
                                  manifest=self._load(mpath))
        assert res == [{"tap": "o/zz", "status": "unpublished"}]
        old = _publish(tmp_path, [_shard()], version=rag.INDEX_VERSION - 1)
        res = shards.sync_keyword(["o/a", "o/b"], {"o/a": A},
                                  manifest=self._load(old))
        assert [r["status"] for r in res] == ["incompatible"] * 2

    @pytest.mark.parametrize("section", [
        {"format": rag.SHARD_FORMAT, "index_version": rag.INDEX_VERSION},
        {"format": rag.SHARD_FORMAT, "index_version": rag.INDEX_VERSION,
         "shards": None},
    ])
    def test_a_compatible_section_with_no_rows_is_unpublished(
            self, sandbox, section):
        # keyword_incompatible accepts a section with no `shards` key; the
        # sync must degrade to "unpublished", not raise KeyError.
        m = {"version": shards.MANIFEST_VERSION, "shards": [],
             "keyword": section}
        res = shards.sync_keyword(["o/a"], {"o/a": A}, manifest=m)
        assert res == [{"tap": "o/a", "status": "unpublished"}]
        assert not rag.index_path().exists()

    def test_one_failure_does_not_cost_the_others(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [
            _shard("o/a", A, [_doc("o/a", "one", ("zebra",))]),
            _shard("o/b", B, [_doc("o/b", "two", ("yak",))])])
        (tmp_path / "pub" / "o__a.keyword.json.gz").unlink()
        events = []
        res = shards.sync_keyword(
            ["o/a", "o/b"], {"o/a": A, "o/b": B}, manifest=self._load(mpath),
            on_event=lambda t, s, d: events.append((t, s)))
        assert [r["status"] for r in res] == ["failed", "imported"]
        assert ("o/b", "imported") in events
        assert _hits("yak") == ["two"]

    def test_an_unwritable_cache_dir_fails_that_tap(self, sandbox, tmp_path):
        mpath = _publish(tmp_path, [_shard()])
        blocker = tmp_path / "file"
        blocker.write_text("", encoding="utf-8")
        res = shards.sync_keyword(["o/a"], {"o/a": A},
                                  manifest=self._load(mpath),
                                  cache_dir=blocker / "sub")
        assert res[0]["status"] == "failed"
        assert not rag.index_path().exists()

    def test_an_import_error_is_reported_per_tap(self, sandbox, tmp_path,
                                                 monkeypatch):
        mpath = _publish(tmp_path, [_shard()])

        def boom(_batch):
            raise BoostError("disk full")
        monkeypatch.setattr(rag, "import_shards", boom)
        res = shards.sync_keyword(["o/a"], {"o/a": A},
                                  manifest=self._load(mpath))
        assert res[0]["status"] == "refused" and res[0]["detail"] == "disk full"


# ----------------------------------- the bundle-import machine, end to end

class TestFetchIndexEndToEnd:
    """The case the card exists for: catalogues, no clones, a 6% index."""

    def _bundle_machine(self, fixture_tap_src, tmp_path):
        tap, commit = _tap_cloned(fixture_tap_src)
        mpath = _publish(tmp_path, [rag.export_shard(tap.name)])
        shutil.rmtree(tap.path)               # what `catalog --import` leaves
        rag.build(force=True)
        assert rag.index_completeness()["body_share"] == 0.0
        assert BODY_ONLY not in " ".join(_hits(BODY_ONLY))
        assert _hits(BODY_ONLY) == []
        return tap, commit, mpath

    def test_fetch_index_turns_a_metadata_index_into_a_body_index(
            self, boost, fixture_tap_src, tmp_path, monkeypatch):
        tap, _commit, mpath = self._bundle_machine(fixture_tap_src, tmp_path)
        monkeypatch.setenv(shards.MANIFEST_ENV, mpath.as_uri())
        res = boost("reindex", "--fetch-index")
        assert "imported the keyword index for 1 tap" in res.out
        assert rag.index_completeness()["body_share"] == 1.0
        assert _hits(BODY_ONLY) == ["cowboy-coding"]
        # A rebuild on the same machine reuses the import rather than
        # regressing to metadata, because the commits agree.
        stats = rag.build()
        assert stats["reused"] == [tap.name]
        assert rag.index_completeness()["body_share"] == 1.0
        # And a second fetch knows it is current, in both renderings.
        res = boost("reindex", "--fetch-index", "--json")
        assert [r["status"] for r in json.loads(res.out)["keyword"]] == [
            "current"]
        res = boost("reindex", "--fetch-index")
        assert "1 tap(s) already indexed" in res.out
        assert "no published keyword index matched" not in res.out

    def test_a_metadata_index_at_the_published_commit_is_not_current(
            self, sandbox, fixture_tap_src, tmp_path):
        tap, commit, _m = self._bundle_machine(fixture_tap_src, tmp_path)
        assert rag._load_raw()["commits"][tap.safe_name] == commit
        assert rag.complete_tap_commits() == {}

    def test_the_metadata_warning_names_the_cheap_remedy(
            self, boost, fixture_tap_src, tmp_path):
        self._bundle_machine(fixture_tap_src, tmp_path)
        res = boost("reindex", "--force")
        assert "--fetch-index" in " ".join(res.out.split())

    def test_an_unusable_manifest_is_an_error(self, boost, fixture_tap_src,
                                              tmp_path, monkeypatch):
        _tap_cloned(fixture_tap_src)
        mpath = _publish(tmp_path, [_shard()], version=rag.INDEX_VERSION - 1)
        monkeypatch.setenv(shards.MANIFEST_ENV, mpath.as_uri())
        res = boost("reindex", "--fetch-index", expect=None)
        assert res.rc != 0
        assert "is version %d" % (rag.INDEX_VERSION - 1) in " ".join(
            (res.out + res.err).split())

    def test_no_taps_is_an_error(self, boost):
        res = boost("reindex", "--fetch-index", expect=None)
        assert res.rc != 0

    def test_nothing_matching_says_so(self, boost, fixture_tap_src, tmp_path,
                                      monkeypatch):
        _tap_cloned(fixture_tap_src)
        mpath = _publish(tmp_path, [_shard()])
        monkeypatch.setenv(shards.MANIFEST_ENV, mpath.as_uri())
        res = boost("reindex", "--fetch-index")
        out = " ".join(res.out.split())
        assert "no published keyword index matched" in out
        assert "boost reindex" in out


# ------------------------------------------------------ publish_shards.py

class TestPublishScript:

    def test_export_keyword_writes_a_verified_gzip_and_honours_skip(
            self, sandbox, fixture_tap_src, tmp_path, capsys):
        tap, commit = _tap_cloned(fixture_tap_src)
        out = tmp_path / "out"
        assert publish_shards.main(["export-keyword", "--out", str(out)]) == 0
        asset = out / (tap.safe_name + publish_shards.KEYWORD_SUFFIX)
        shard = json.loads(gzip.decompress(asset.read_bytes()))
        assert rag.shard_problem(shard, commit) is None
        asset.unlink()
        skip = tmp_path / "skip.txt"
        skip.write_text("%s %s\n" % (tap.name, commit), encoding="utf-8")
        assert publish_shards.main(["export-keyword", "--out", str(out),
                                    "--skip", str(skip)]) == 0
        assert not asset.exists()

    def test_export_keyword_skips_a_tap_it_cannot_export(
            self, sandbox, fixture_tap_src, tmp_path, capsys):
        tap, _c = _tap_cloned(fixture_tap_src)
        shutil.rmtree(tap.path)
        out = tmp_path / "out"
        assert publish_shards.main(["export-keyword", "--out", str(out)]) == 0
        assert list(out.iterdir()) == []
        assert "no clone" in capsys.readouterr().err

    def test_export_keyword_skips_a_tap_with_no_documents(
            self, sandbox, fixture_tap_src, tmp_path, capsys, monkeypatch):
        _tap, commit = _tap_cloned(fixture_tap_src)
        monkeypatch.setattr(rag, "export_shard",
                            lambda t: _shard(t, commit, docs=[]))
        out = tmp_path / "out"
        assert publish_shards.main(["export-keyword", "--out", str(out)]) == 0
        assert list(out.iterdir()) == []
        assert "no documents" in capsys.readouterr().err

    @pytest.mark.parametrize("version, listed", [
        (None, True), (rag.INDEX_VERSION - 1, False)])
    def test_unchanged_kind_keyword(self, sandbox, fixture_tap_src, tmp_path,
                                    version, listed):
        tap, commit = _tap_cloned(fixture_tap_src)
        mpath = _publish(tmp_path, [rag.export_shard(tap.name)],
                         version=version)
        out = tmp_path / "unchanged.txt"
        assert publish_shards.main(["unchanged", "--kind", "keyword",
                                    "--manifest-url", mpath.as_uri(),
                                    "--out", str(out)]) == 0
        want = [tap.name, commit] if listed else []
        assert out.read_text(encoding="utf-8").split() == want

    def test_unchanged_kind_keyword_ignores_a_moved_registry(
            self, sandbox, fixture_tap_src, tmp_path):
        tap, _c = _tap_cloned(fixture_tap_src)
        mpath = _publish(tmp_path, [_shard(tap.name, B,
                                           [_doc(tap.name)])])
        out = tmp_path / "unchanged.txt"
        publish_shards.main(["unchanged", "--kind", "keyword",
                             "--manifest-url", mpath.as_uri(),
                             "--out", str(out)])
        assert out.read_text(encoding="utf-8") == ""


def _dense_file(d, tap, commit=A):
    (d / (tap.replace("/", "__") + ".shard.json")).write_text(json.dumps(
        {"tap": tap, "commit": commit, **SPACE, "chunks": [{}]}),
        encoding="utf-8")


def _kw_file(d, tap, commit=A, version=None):
    s = _shard(tap, commit, [_doc(tap)])
    if version is not None:
        s["index_version"] = version
    (d / (tap.replace("/", "__") + publish_shards.KEYWORD_SUFFIX)).write_bytes(
        publish_shards.keyword_bytes(s))


def _kw_row(tap, commit):
    return {"tap": tap, "commit": commit, "docs": 1, "bytes": 9,
            "sha256": "e" * 64, "url": "https://x/" + tap}


class TestManifestKeywordSection:

    def _run(self, tmp_path, *extra):
        out = tmp_path / "manifest.json"
        rc = publish_shards.main(["manifest", "--shard-dir",
                                  str(tmp_path / "s"), "--repo", "o/r",
                                  "--out", str(out), *extra])
        return rc, (json.loads(out.read_text(encoding="utf-8"))
                    if out.exists() else None)

    def _prev(self, tmp_path, kw_rows, version=None):
        p = tmp_path / "prev.json"
        p.write_text(json.dumps({
            "version": 1, **SPACE, "shards": [],
            "keyword": {"format": 1, "index_version": (
                rag.INDEX_VERSION if version is None else version),
                "shards": kw_rows}}), encoding="utf-8")
        return p

    def test_fresh_keyword_shards_become_the_section(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a")
        rc, m = self._run(tmp_path)
        assert rc == 0
        sec = m["keyword"]
        assert sec["index_version"] == rag.INDEX_VERSION
        assert sec["format"] == rag.SHARD_FORMAT
        (row,) = sec["shards"]
        raw = (d / "o__a.keyword.json.gz").read_bytes()
        import hashlib
        assert row["sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["bytes"] == len(raw) and row["docs"] == 1
        assert row["url"].endswith("/shards-latest/o__a.keyword.json.gz")
        # The dense rows are untouched by the section.
        assert [r["tap"] for r in m["shards"]] == ["o/a"]

    def test_no_keyword_shards_means_no_section(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _rc, m = self._run(tmp_path)
        assert "keyword" not in m

    def test_mixed_index_versions_are_refused(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a")
        _kw_file(d, "o/b", version=rag.INDEX_VERSION - 1)
        with pytest.raises(SystemExit, match="index versions"):
            self._run(tmp_path)

    def test_a_keyword_shard_missing_provenance_is_refused(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a", commit="")
        with pytest.raises(SystemExit, match="missing commit"):
            self._run(tmp_path)

    def test_carry_forward_four_states(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/fresh")
        _kw_file(d, "o/fresh", B)
        prev = self._prev(tmp_path, [
            _kw_row("o/fresh", A),       # rebuilt: the fresh row wins
            _kw_row("o/same", A),        # unchanged at A
            _kw_row("o/moved", A),       # job says B: dropped
            _kw_row("o/silent", A),      # nobody reported, still known
            _kw_row("o/gone", A)])       # nobody reported, left catalogue
        unchanged = tmp_path / "kw-unchanged.txt"
        unchanged.write_text("o/same %s\no/moved %s\n" % (A, B),
                             encoding="utf-8")
        known = tmp_path / "known.txt"
        known.write_text("o/fresh\no/same\no/moved\no/silent\n",
                         encoding="utf-8")
        rc, m = self._run(tmp_path, "--carry-forward", str(prev),
                          "--keyword-unchanged", str(unchanged),
                          "--known", str(known))
        assert rc == 0
        got = {r["tap"]: r["commit"] for r in m["keyword"]["shards"]}
        assert got == {"o/fresh": B, "o/same": A, "o/silent": A}

    def test_a_quiet_week_still_publishes_the_carried_section(self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        prev = self._prev(tmp_path, [_kw_row("o/same", A)])
        unchanged = tmp_path / "kw.txt"
        unchanged.write_text("o/same %s\n" % A, encoding="utf-8")
        _rc, m = self._run(tmp_path, "--carry-forward", str(prev),
                           "--keyword-unchanged", str(unchanged),
                           "--known")
        assert m["keyword"]["index_version"] == rag.INDEX_VERSION
        assert [r["tap"] for r in m["keyword"]["shards"]] == ["o/same"]

    def test_a_previous_section_at_another_version_carries_nothing(
            self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a")
        prev = self._prev(tmp_path, [_kw_row("o/same", A)],
                          version=rag.INDEX_VERSION - 1)
        unchanged = tmp_path / "kw.txt"
        unchanged.write_text("o/same %s\n" % A, encoding="utf-8")
        _rc, m = self._run(tmp_path, "--carry-forward", str(prev),
                           "--keyword-unchanged", str(unchanged))
        assert [r["tap"] for r in m["keyword"]["shards"]] == ["o/a"]

    def test_an_unreadable_previous_manifest_carries_no_keyword_rows(
            self, tmp_path):
        d = tmp_path / "s"
        d.mkdir()
        _dense_file(d, "o/a")
        _kw_file(d, "o/a")
        bad = tmp_path / "prev.json"
        bad.write_text("{nope", encoding="utf-8")
        _rc, m = self._run(tmp_path, "--carry-forward", str(bad))
        assert [r["tap"] for r in m["keyword"]["shards"]] == ["o/a"]


# ------------------------------------------------------------ the workflow

class TestWorkflowWiring:
    """CI cannot run here, so the wiring is pinned statically."""

    SHARDS = ROOT / ".github" / "workflows" / "shards.yml"

    @pytest.fixture(autouse=True)
    def _text(self):
        if not self.SHARDS.exists():
            pytest.skip("workflow not reachable (e.g. mutation sandbox)")
        self.text = self.SHARDS.read_text(encoding="utf-8")

    def test_keyword_shards_are_exported_before_anything_is_untapped(self):
        export = self.text.index("publish_shards.py export-keyword")
        ask = self.text.index("publish_shards.py unchanged --kind keyword")
        untap = self.text.index("boost_cli untap")
        assert ask < export < untap

    def test_a_failed_keyword_export_cannot_cost_the_dense_work(self):
        # The step runs under `set -e`: an unexpected crash in export-keyword
        # must warn and carry on to the embed, not end the chunk.
        line = self.text[self.text.index("publish_shards.py export-keyword"):]
        line = line[:line.index("\n          #")]
        assert "|| echo \"::warning::" in line

    def test_the_export_skips_what_the_keyword_check_listed(self):
        assert '--out "keyword-unchanged-$JOB.txt"' in self.text
        assert '--skip "keyword-unchanged-$JOB.txt"' in self.text

    def test_the_artifact_carries_keyword_shards_and_their_evidence(self):
        upload = self.text[self.text.index("name: upload"):]
        upload = upload[:upload.index("publish:")]
        assert "*.keyword.json.gz" in upload
        assert "keyword-unchanged-*.txt" in upload

    def test_the_publish_job_carries_and_uploads_them(self):
        publish = self.text[self.text.index("  publish:"):]
        assert ("--keyword-unchanged shards/keyword-unchanged-*.txt"
                in publish)
        assert "shards/*.keyword.json.gz" in publish

    def test_the_dense_glob_cannot_swallow_the_keyword_evidence(self):
        # `shards/unchanged-*.txt` must not match `keyword-unchanged-0.txt`,
        # or a keyword line would carry a DENSE row forward.
        import fnmatch
        assert not fnmatch.fnmatch("keyword-unchanged-0.txt", "unchanged-*.txt")
        assert not fnmatch.fnmatch("o__a.keyword.json.gz", "*.shard.json")

    @pytest.mark.parametrize("argv, flag", [
        (["unchanged", "--help"], "--kind"),
        (["export-keyword", "--help"], "--skip"),
        (["manifest", "--help"], "--keyword-unchanged"),
    ])
    def test_the_cli_takes_the_flags_the_workflow_passes(self, argv, flag):
        proc = subprocess.run([sys.executable,
                               str(ROOT / "scripts" / "publish_shards.py"),
                               *argv], capture_output=True, text=True)
        assert proc.returncode == 0
        assert flag in proc.stdout
