# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a corrupt BM25 postings store is noticed and rebuilt.

``printf garbage > rag_postings.sqlite`` used to leave ``ready()`` True (it
checked ``exists()``), so every search read ``{}`` and answered "no matches"
for an exact skill name; doctor said healthy; and a plain ``boost reindex``
reused every tap from ``_all_postings()``'s ``{}`` — docs with no term
frequencies — so only ``--force`` recovered.
"""
from __future__ import annotations

import sys

import pytest

from boost_cli.commands import quality
from boost_cli.core import rag, report


def _entry(name, skill_md):
    return {"name": name, "description": "", "tap": "acme/skills",
            "kind": "skill", "skill_md": skill_md, "rel_dir": name}


@pytest.fixture()
def corpus(tmp_path, monkeypatch, sandbox):
    root = tmp_path / "repo"
    items = {"jest-runner": "Unit testing for React components with jest.",
             "pytest-helper": "Python testing framework with fixtures."}
    entries = []
    for name, body in items.items():
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(
            "---\nname: %s\n---\n\n%s\n" % (name, body), encoding="utf-8")
        entries.append(_entry(name, "%s/SKILL.md" % name))
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    rag.build(entries=entries, force=True)
    rag._CACHE.clear()
    return entries


def _corrupt():
    rag.postings_path().write_bytes(b"garbage\n")


class TestReadiness:
    def test_a_built_index_is_ready_and_readable(self, corpus):
        assert rag.postings_readable() is True
        assert rag.ready() is True
        assert rag.postings_fault() is None

    def test_a_garbage_store_is_not_ready(self, corpus):
        _corrupt()
        assert rag.postings_readable() is False
        assert rag.ready() is False

    def test_a_missing_store_is_not_readable(self, corpus):
        rag.postings_path().unlink()
        assert rag.postings_readable() is False

    def test_a_database_without_the_tables_is_not_readable(self, corpus):
        import sqlite3
        rag.postings_path().unlink()
        con = sqlite3.connect(str(rag.postings_path()))
        con.execute("CREATE TABLE other (x)")
        con.commit()
        con.close()
        assert rag.postings_readable() is False

    def test_all_postings_says_none_not_empty_when_unreadable(self, corpus):
        _corrupt()
        assert rag._all_postings() is None

    def test_all_postings_says_none_when_missing(self, corpus):
        rag.postings_path().unlink()
        assert rag._all_postings() is None

    def test_all_postings_reads_a_good_store(self, corpus):
        assert "jest" in rag._all_postings()


class TestRecovery:
    def test_a_plain_build_rebuilds_instead_of_reusing(self, corpus):
        _corrupt()
        stats = rag.build(entries=corpus)
        assert stats["reused"] == []
        assert stats["reindexed"] == ["acme/skills"]
        assert [h["entry"]["name"] for h in rag.retrieve("jest", entries=corpus)] \
            == ["jest-runner"]

    def test_a_missing_store_also_rebuilds(self, corpus):
        rag.postings_path().unlink()
        stats = rag.build(entries=corpus)
        assert stats["reused"] == []
        assert rag.ready() is True

    def test_ensure_heals_a_corrupt_store(self, corpus, monkeypatch):
        monkeypatch.setattr(rag, "stale", lambda: False)
        monkeypatch.setattr(rag.registry, "list_taps", lambda: ["acme/skills"])
        monkeypatch.setattr(rag.catalog, "all_entries", lambda: corpus)
        _corrupt()
        assert rag.ensure() is True
        assert rag.postings_readable() is True

    def test_a_readable_store_is_still_reused(self, corpus):
        stats = rag.build(entries=corpus)
        assert stats["reused"] == ["acme/skills"]
        assert stats["reindexed"] == []

    def test_kept_docs_refuses_an_unreadable_store(self, corpus):
        raw = rag._load_raw()
        _corrupt()
        assert rag._kept_docs(raw, {"acme__skills"}) is None

    def test_a_corrupt_blob_the_probe_misses_still_rebuilds(self, corpus):
        # The readiness probe reads one row and decodes nothing, so a bad
        # blob gets past it; the reuse path must still not keep empty docs.
        import sqlite3
        con = sqlite3.connect(str(rag.postings_path()))
        con.execute("UPDATE postings SET plist = ?", (b"\x01\x80",))
        con.commit()
        con.close()
        assert rag.postings_readable() is True
        stats = rag.build(entries=corpus)
        assert stats["reused"] == []
        assert stats["reindexed"] == ["acme/skills"]
        assert [h["entry"]["name"] for h in rag.retrieve("jest", entries=corpus)] \
            == ["jest-runner"]


class TestDoctor:
    def _report(self, monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status", lambda count=False: {
            "ready": False, "degraded": False, "reason": "no-extra",
            "store_exists": False, "chunks": None})
        monkeypatch.setattr(dense, "fix_hint", lambda reason, status=None: "x")
        rep = report.Report(as_json=True)
        quality._report_search_engine(rep)
        return rep

    def test_a_corrupt_store_is_an_issue(self, corpus, monkeypatch):
        _corrupt()
        rep = self._report(monkeypatch)
        checks = [c for c in rep.payload()["checks"]
                  if c["name"] == "search-index"]
        assert len(checks) == 1
        assert checks[0]["status"] == "issue"
        assert checks[0]["message"] == (
            "the BM25 postings store is unreadable, so keyword search matches "
            "nothing — `boost reindex --force` rebuilds it")
        assert rep.issues == 1

    def test_a_missing_store_says_missing(self, corpus):
        rag.postings_path().unlink()
        assert rag.postings_fault() == "the BM25 postings store is missing"

    def test_no_index_at_all_is_no_fault(self, sandbox):
        assert rag.postings_fault() is None

    def test_a_healthy_store_adds_no_line(self, corpus, monkeypatch):
        rep = self._report(monkeypatch)
        assert [c for c in rep.payload()["checks"]
                if c["name"] == "search-index"] == []
        assert rep.issues == 0


class TestReadOnlyUri:
    def test_a_home_with_uri_metacharacters_still_reads_the_store(
            self, tmp_path, monkeypatch, sandbox):
        # `?` cannot appear in a Windows filename, so it is POSIX-only; `#`
        # and `%` are the metacharacters every platform can hold.
        odd = sandbox / ("a#b%20d" if sys.platform == "win32" else "a#b?c%20d")
        odd.mkdir()
        monkeypatch.setattr(rag.paths, "cache_dir", lambda: odd)
        root = tmp_path / "repo" / "jest-runner"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(
            "---\nname: jest-runner\n---\n\njest testing\n", encoding="utf-8")
        monkeypatch.setattr(rag, "_tap_paths",
                            lambda: {"acme/skills": root.parent})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        rag.build(entries=[_entry("jest-runner", "jest-runner/SKILL.md")],
                  force=True)
        rag._CACHE.clear()
        assert rag.postings_readable() is True
        assert rag.postings_fault() is None
        assert rag._all_postings() is not None
        # Nothing was opened (and so created) at the truncated path.
        assert not (sandbox / "a").exists()

    def test_the_uri_is_read_only_and_escaped(self, sandbox, monkeypatch):
        monkeypatch.setattr(rag.paths, "cache_dir", lambda: sandbox / "x#y")
        uri = rag._postings_ro_uri()
        assert uri.startswith("file:///")
        assert uri.endswith("/x%23y/rag_postings.sqlite?mode=ro")
