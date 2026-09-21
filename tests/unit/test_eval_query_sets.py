# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every committed query set is re-baselined, and can be scored.

WHY. `tests/eval/baseline.json` holds one row per query set, keyed
`name@content-digest`, so the keyword set (`golden.jsonl`) and the
natural-language set (`golden-natural.jsonl`) do not overwrite each other. The
monthly corpus refresh then re-baselined with no `--golden`, which is the
keyword set alone. Its first run (cbc0a58b) moved that row and left the natural
row describing the 10,152-entry corpus it replaced. Measured on the 10,731-entry
corpus taps.txt pins now: the natural set exits 1 with "REGRESSION vs baseline:
catalog.search recall@k: 0.080 -> 0.060", a gap between two corpora rather than
a change to the ranker.

`--all-sets` is the fix's shape: the list of sets is derived from the
directory (`query_sets`), so a third set is re-baselined the day it is
committed, with no workflow edit.

The same run found a second defect on the way. `main` read the golden file
BEFORE `--build`, and an exemplar-graded row resolves its exemplar through the
index's content hashes — so on a home with no index yet (a fresh CI runner, a
new `make eval-natural`) every exemplar "resolves to no indexed entry" and the
run dies, and on a home whose index predates a pin move the exemplar is graded
against the old bodies. The natural set is exemplar-graded on every row.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from boost_cli.core import catalog, rag, registry

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_retrieval.py"
_EVAL_DIR = _ROOT / "tests" / "eval"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("eval_retrieval_sets", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text("", encoding="utf-8")


class TestQuerySets:
    def test_only_golden_files_are_query_sets(self, tmp_path):
        # The directory also holds the recommend, explain and tool-call sets,
        # which are not retrieval judgments: a baseline pinned over one of
        # them would be a row nothing can ever compare against.
        _touch(tmp_path, "golden.jsonl", "golden-natural.jsonl",
               "explain.jsonl", "recommend.jsonl", "tool_calls.jsonl",
               "golden.jsonl.bak", "baseline.json", "taps.txt")
        m = _load()
        assert [p.name for p in m.query_sets(tmp_path)] == [
            "golden-natural.jsonl", "golden.jsonl"]

    def test_a_new_set_is_picked_up_without_an_edit(self, tmp_path):
        _touch(tmp_path, "golden.jsonl", "golden-agents.jsonl")
        m = _load()
        assert [p.name for p in m.query_sets(tmp_path)] == [
            "golden-agents.jsonl", "golden.jsonl"]

    def test_an_empty_directory_has_no_sets(self, tmp_path):
        assert _load().query_sets(tmp_path) == []

    def test_the_default_is_the_committed_directory(self):
        m = _load()
        assert m.query_sets() == sorted(_EVAL_DIR.glob("golden*.jsonl"))

    def test_the_shipped_sets_include_both_graded_sets(self):
        m = _load()
        names = [p.name for p in m.query_sets()]
        assert "golden.jsonl" in names and "golden-natural.jsonl" in names
        assert m.DEFAULT_GOLDEN in m.query_sets()


class TestEveryCommittedSetHasACurrentBaseline:
    """A set edited without re-baselining strands its row the same way.

    The key carries the file's digest, so an edit makes the old row
    unreachable: `make eval` finds no baseline and compares nothing, and the
    stale row sits in the file describing questions nobody asks any more.
    """

    def test_each_set_is_keyed_at_its_current_digest(self):
        m = _load()
        sets = json.loads((_EVAL_DIR / "baseline.json").read_text(
            encoding="utf-8"))["sets"]
        missing = [m.golden_key(p) for p in m.query_sets()
                   if m.golden_key(p) not in sets]
        assert missing == [], (
            "no baseline for %s — on the pinned corpus (make eval-natural "
            "taps it), run `python3 scripts/eval_retrieval.py --save-baseline "
            "-k 10 --all-sets`" % missing)

    def test_the_baseline_holds_no_row_for_an_uncommitted_set(self):
        m = _load()
        sets = json.loads((_EVAL_DIR / "baseline.json").read_text(
            encoding="utf-8"))["sets"]
        current = {m.golden_key(p) for p in m.query_sets()}
        assert sorted(set(sets) - current) == []


def _entry(name, skill_md, desc=""):
    return {"name": name, "tap": "acme/skills", "kind": "skill",
            "description": desc, "skill_md": skill_md, "rel_dir": name,
            "curated": False}


_BODIES = {
    "pytest-runner": "fixtures, parametrised cases, markers and plugins",
    "lint-runner": "ruff rules, formatting, import sorting and autofix",
}


@pytest.fixture()
def corpus(tmp_path, monkeypatch, sandbox):
    """A real two-item index with bodies on disk, plus two query sets.

    Returns the module with its eval directory and baseline pointed at the
    temp tree, so nothing a test saves reaches `tests/eval/baseline.json`.
    """
    root = tmp_path / "repo"
    entries = [_entry("pytest-runner", "pytest-runner/SKILL.md", "run the suite"),
               _entry("lint-runner", "lint-runner/SKILL.md", "run ruff")]
    for e in entries:
        p = root / e["skill_md"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("---\nname: %s\n---\n\n%s\n" % (e["name"], _BODIES[e["name"]]),
                     encoding="utf-8")
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(registry, "list_taps",
                        lambda: [registry.Tap(name="acme/skills", url="")])
    monkeypatch.setattr(catalog, "load_tap",
                        lambda tap, rebuild=False: list(entries))
    rag.build(entries, force=True)

    sets = tmp_path / "eval"
    sets.mkdir()
    (sets / "golden.jsonl").write_text(json.dumps(
        {"query": "pytest fixtures and parametrised cases",
         "relevant": ["pytest-runner"], "kind": "skill"}) + "\n", encoding="utf-8")
    # Exemplar-graded, like every row of the shipped natural set.
    (sets / "golden-natural.jsonl").write_text(json.dumps(
        {"query": "ruff import sorting and autofix", "relevant": ["lint-runner"],
         "exemplar": "acme/skills::lint-runner/SKILL.md", "kind": "skill"})
        + "\n", encoding="utf-8")
    (sets / "recommend.jsonl").write_text("{}\n", encoding="utf-8")

    m = _load()
    # raising=False: absent before --all-sets existed, and the exemplar tests
    # below must still run there to show the defect they pin.
    monkeypatch.setattr(m, "EVAL_DIR", sets, raising=False)
    monkeypatch.setattr(m, "BASELINE", sets / "baseline.json")
    return m


def _baseline(m) -> dict:
    return json.loads(m.BASELINE.read_text(encoding="utf-8"))["sets"]


_RUN = ["-k", "1", "--engines", "bm25"]


class TestAllSets:
    def test_save_pins_every_committed_set(self, corpus):
        m = corpus
        assert m.main(["--all-sets", "--save-baseline", *_RUN]) == 0
        assert sorted(_baseline(m)) == sorted(
            m.golden_key(p) for p in m.query_sets())
        assert len(_baseline(m)) == 2

    def test_each_set_is_scored_on_its_own_questions(self, corpus):
        m = corpus
        assert m.main(["--all-sets", "--save-baseline", *_RUN]) == 0
        for key, row in _baseline(m).items():
            assert row["golden"] == key.rsplit("@", 1)[0]
            assert row["k"] == 1
            assert row["engines"]["BM25 full-content"]["recall@k"] == 1.0

    def test_a_superseded_row_is_replaced_and_another_file_kept(self, corpus):
        m = corpus
        m.BASELINE.write_text(json.dumps({"sets": {
            "golden-natural.jsonl@000000000000": {"k": 1, "engines": {}},
            "elsewhere.jsonl@111111111111": {"k": 1, "engines": {}},
        }}), encoding="utf-8")
        assert m.main(["--all-sets", "--save-baseline", *_RUN]) == 0
        keys = set(_baseline(m))
        assert "golden-natural.jsonl@000000000000" not in keys
        assert "elsewhere.jsonl@111111111111" in keys
        assert m.golden_key(m.EVAL_DIR / "golden-natural.jsonl") in keys

    def test_each_set_is_reported_under_its_name(self, corpus, capsys):
        m = corpus
        assert m.main(["--all-sets", *_RUN]) == 0
        out = capsys.readouterr().out
        assert "query set: golden.jsonl" in out
        assert "query set: golden-natural.jsonl" in out
        assert out.index("golden-natural.jsonl") < out.index("query set: golden.jsonl")

    def test_the_index_is_built_once(self, corpus, monkeypatch):
        m = corpus
        calls = []
        real = rag.build
        monkeypatch.setattr(rag, "build",
                            lambda *a, **kw: calls.append(kw) or real(*a, **kw))
        assert m.main(["--all-sets", "--build", *_RUN]) == 0
        assert len(calls) == 1

    def test_a_regression_in_any_set_fails_the_run(self, corpus, capsys):
        m = corpus
        natural = m.EVAL_DIR / "golden-natural.jsonl"
        perfect = {"recall@k": 1.0, "hit@1": 1.0, "MRR": 1.0, "nDCG@k": 1.0}
        m.BASELINE.write_text(json.dumps({"sets": {m.golden_key(natural): {
            "k": 1, "engines": {"BM25 full-content": dict(perfect, MRR=2.0)}},
        }}), encoding="utf-8")
        assert m.main(["--all-sets", *_RUN]) == 1
        out = capsys.readouterr().out
        # The other set is still scored: one bad set does not hide the rest.
        assert "query set: golden.jsonl" in out

    def test_a_refused_corpus_stops_before_anything_is_saved(
            self, corpus, monkeypatch):
        m = corpus
        monkeypatch.setattr(m, "corpus_refusal", lambda _c: "no bodies")
        assert m.main(["--all-sets", "--save-baseline", *_RUN]) == m.EX_NOINPUT
        assert not m.BASELINE.exists()

    @pytest.mark.parametrize("extra", [
        ["--fail-under", "0.5"], ["--floor", "hit@1=0.5"], ["--json"],
        ["--golden", "tests/eval/golden.jsonl"],
    ], ids=["fail-under", "floor", "json", "golden"])
    def test_what_cannot_mean_one_thing_per_set_is_refused(self, corpus, extra):
        # A floor is calibrated on one set; the keyword floors fail the
        # natural set by construction. And --json would print one document
        # per set into a stream a reader parses as one.
        with pytest.raises(SystemExit) as ei:
            corpus.main(["--all-sets", *extra, *_RUN])
        assert ei.value.code == 2


def _record_builds(monkeypatch) -> list:
    calls: list = []
    real = rag.build
    monkeypatch.setattr(rag, "build",
                        lambda *a, **kw: calls.append(kw) or real(*a, **kw))
    return calls


class TestNothingIsBuiltForNothing:
    """A run that cannot score anything says so before the index build.

    The golden file is read AFTER `--build` (see the class below), which made
    a typo in `--golden` cost a whole build before its FileNotFoundError —
    about 11 s on the pinned corpus, minutes on a real ~71k-entry home.
    """

    def test_a_missing_set_fails_before_the_build(self, corpus, monkeypatch):
        m = corpus
        calls = _record_builds(monkeypatch)
        typo = m.EVAL_DIR / "golden-natral.jsonl"
        with pytest.raises(SystemExit) as ei:
            m.main(["--golden", str(typo), "--build", *_RUN])
        assert str(ei.value.code) == "--golden %s: no such file" % typo
        assert calls == []

    def test_a_directory_is_not_a_set(self, corpus, monkeypatch):
        m = corpus
        calls = _record_builds(monkeypatch)
        with pytest.raises(SystemExit) as ei:
            m.main(["--golden", str(m.EVAL_DIR), "--build", *_RUN])
        assert "no such file" in str(ei.value.code)
        assert calls == []

    def test_all_sets_over_no_sets_fails_before_the_build(
            self, corpus, monkeypatch, tmp_path):
        # Exit 0 having scored nothing would read, to the refresh's
        # re-baseline step, as every row moved.
        m = corpus
        empty = tmp_path / "no-sets"
        empty.mkdir()
        _touch(empty, "recommend.jsonl", "explain.jsonl")
        monkeypatch.setattr(m, "EVAL_DIR", empty)
        calls = _record_builds(monkeypatch)
        with pytest.raises(SystemExit) as ei:
            m.main(["--all-sets", "--build", "--save-baseline", *_RUN])
        assert str(ei.value.code) == (
            "--all-sets: no query set matches %s" % (empty / "golden*.jsonl"))
        assert calls == []
        assert not m.BASELINE.exists()

    def test_an_existing_set_still_builds_and_scores(self, corpus, monkeypatch):
        m = corpus
        calls = _record_builds(monkeypatch)
        natural = m.EVAL_DIR / "golden-natural.jsonl"
        assert m.main(["--golden", str(natural), "--build", *_RUN]) == 0
        assert len(calls) == 1


class TestExemplarsResolveAgainstTheFreshIndex:
    """`--build` must come before the golden file is graded, not after."""

    def test_an_exemplar_set_scores_on_a_home_with_no_index(self, corpus):
        m = corpus
        rag.index_path().unlink()
        if rag.postings_path().exists():
            rag.postings_path().unlink()
        natural = m.EVAL_DIR / "golden-natural.jsonl"
        assert m.main(["--golden", str(natural), "--build", *_RUN]) == 0

    def test_the_fresh_index_is_what_grades_it(self, corpus, monkeypatch):
        # A stale index hashes the OLD body. Built before grading, the
        # exemplar's class is the new body's, and it is found at rank 1.
        m = corpus
        natural = m.EVAL_DIR / "golden-natural.jsonl"
        target = rag._tap_paths()["acme/skills"] / "lint-runner" / "SKILL.md"
        target.write_text("---\nname: lint-runner\n---\n\nruff import sorting, "
                          "autofix and a changed body\n", encoding="utf-8")
        assert m.main(["--golden", str(natural), "--build", "--save-baseline",
                       *_RUN]) == 0
        row = _baseline(m)[m.golden_key(natural)]
        assert row["engines"]["BM25 full-content"]["hit@1"] == 1.0
