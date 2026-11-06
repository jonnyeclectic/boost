# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a tap may not be named after one of boost's own cache files.

A local tap is named after its directory's basename, and its catalog lives at
``cache/<name>.json``. A directory called ``rag_index`` therefore shared one
file with the BM25 index: each overwrote the other on every command, neither
was ever reused, and ``boost untap rag_index`` deleted the index. ``add`` and
``add_many`` now refuse the name, and a tap configured before they did never
writes, reads or deletes that file.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from boost_cli.core import catalog, config, paths, registry
from boost_cli.errors import BoostError


def _repo(dest):
    (dest / "skills" / "demo").mkdir(parents=True)
    (dest / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\n\nBody.\n", encoding="utf-8")
    for argv in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-qm", "init"]):
        subprocess.run(["git", *argv], cwd=dest, check=True,
                       capture_output=True)
    return dest


class TestReservedCacheName:
    @pytest.mark.parametrize("name", ["rag_index", "discovery",
                                      "rerank_cache", "RAG_INDEX"])
    def test_internal_leaves_are_reserved(self, name):
        assert registry.reserved_cache_name(name) is True

    @pytest.mark.parametrize("name", ["rag", "rag_index2", "owner/rag_index",
                                      "rag_postings", "_names"])
    def test_other_names_are_not(self, name):
        # `owner/rag_index` caches at owner__rag_index.json; `.sqlite` and
        # `.txt` artifacts cannot collide with a `.json` catalog.
        assert registry.reserved_cache_name(name) is False

    def test_owns_cache_file_follows_the_name(self):
        assert registry.Tap(name="rag_index", url="").owns_cache_file is False
        assert registry.Tap(name="tapA", url="").owns_cache_file is True


class TestTapRefusesTheName:
    def test_add_refuses_before_cloning(self, sandbox, tmp_path):
        src = _repo(tmp_path / "rag_index")
        with pytest.raises(BoostError) as exc:
            registry.add(str(src))
        assert exc.value.message == (
            "tap name rag_index is reserved: its catalog would overwrite "
            "boost's own cache/rag_index.json")
        assert exc.value.hint == "rename the directory and tap it again"
        assert registry.list_taps() == []
        assert not (paths.repos_dir() / "rag_index").exists()

    def test_add_many_returns_an_error_row_and_taps_the_rest(
            self, sandbox, tmp_path):
        bad = _repo(tmp_path / "discovery")
        good = _repo(tmp_path / "fine")
        res = registry.add_many([str(bad), str(good)])
        assert res[0] == {
            "spec": str(bad), "name": "discovery", "ok": False,
            "error": "tap name discovery is reserved: its catalog would "
                     "overwrite boost's own cache/discovery.json"}
        assert res[1]["ok"] is True
        assert [t.name for t in registry.list_taps()] == ["fine"]

    def test_cli_exits_1_naming_the_reason(self, boost, sandbox, tmp_path):
        src = _repo(tmp_path / "rag_index")
        res = boost("tap", str(src), expect=1)
        assert "tap name rag_index is reserved" in res.out + res.err


class TestALegacyTapLeavesTheIndexAlone:
    """A config written before the refusal can still name such a tap."""

    @staticmethod
    def _legacy(tmp_path):
        src = _repo(tmp_path / "src")
        tap = registry.Tap(name="rag_index", url=str(src))
        subprocess.run(["git", "clone", "-q", str(src), str(tap.path)],
                       check=True, capture_output=True)

        def put(cfg):
            cfg.setdefault("taps", []).append({"name": "rag_index",
                                               "url": str(src)})
        config.mutate(put)
        index = paths.cache_dir() / "rag_index.json"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text('{"version": 10, "engine": "bm25"}', encoding="utf-8")
        return registry.get("rag_index"), index

    def test_rebuild_scans_but_does_not_overwrite_the_index(
            self, sandbox, tmp_path):
        tap, index = self._legacy(tmp_path)
        entries = catalog.rebuild_tap(tap)
        assert [e["name"] for e in entries] == ["demo"]
        assert json.loads(index.read_text(encoding="utf-8")) == {
            "version": 10, "engine": "bm25"}

    def test_the_index_is_never_read_as_its_catalog(self, sandbox, tmp_path):
        tap, _index = self._legacy(tmp_path)
        assert catalog._cache_record(tap) is None

    def test_untap_keeps_the_index(self, sandbox, tmp_path):
        tap, index = self._legacy(tmp_path)
        registry.remove(tap.name)
        assert index.is_file()
        assert registry.list_taps() == []
