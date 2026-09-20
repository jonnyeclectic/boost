# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the required `eval` gate refuses a corpus without its bodies.

A catalog cache outlives the clone it was built from — `catalog.load_tap`
serves a stale cache when the clone is gone, deliberately — and `rag.read_body`
then degrades that entry to its name and description, also deliberately. Each
is right on its own. Stacked under a gate that read neither, `make eval`
indexed the identical entry count across the identical tap count under the
identical "BM25 full-content" label and floored four metrics on a frontmatter
index.

Measured on the pinned 20-tap corpus with `$BOOST_HOME/repos` moved aside and
the cache and sentinel intact: 10,731 of 10,731 documents carry no body, mean
document length falls 862.2 -> 41.4 tokens (95.2% of the scored text absent),
and all four floors PASS at 0.852 / 0.582 / 0.684 / 0.717 against the intact
corpus's 0.841 / 0.484 / 0.607 / 0.655 — the body-less run scores HIGHER, so
the loss reads as an improvement rather than a defect.

These tests pin both halves of the fix, which live in the harness rather than
the engine (`rag` already counts what it could not read and exposes it through
`index_completeness`; nothing asked):

* `eval_retrieval.corpus_refusal` / `main` — refuse to score, exit 75, before
  any metric is computed.
* `ensure_eval_corpus.sh` — a sentinel with no `repos/` under it is a cache
  miss, so the state repairs itself into a re-tap instead of a false green.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import catalog, rag, registry

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_retrieval.py"
_ENSURE = _ROOT / "scripts" / "ensure_eval_corpus.sh"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("eval_retrieval", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(name, skill_md, desc=""):
    return {"name": name, "tap": "acme/skills", "kind": "skill",
            "description": desc, "skill_md": skill_md, "rel_dir": name,
            "curated": False}


@pytest.fixture()
def corpus(tmp_path, monkeypatch, sandbox):
    """Build a real index over two items; the clone is the caller's to remove.

    Returns a callable taking ``with_bodies`` so the same two entries are
    indexed either way — which is the whole point: the *catalog* is identical
    and only the files behind it differ, exactly the state a reclaimed
    `repos/` tree leaves behind.
    """
    root = tmp_path / "repo"
    golden = tmp_path / "golden.jsonl"
    golden.write_text(
        json.dumps({"query": "pytest fixtures and parametrised cases",
                    "relevant": ["pytest-runner"], "kind": "skill"}) + "\n",
        encoding="utf-8")

    bodies = {
        "pytest-runner": "fixtures, parametrised cases, markers and plugins",
        "lint-runner": "ruff rules, formatting, import sorting and autofix",
    }

    def build(with_bodies: bool):
        entries = [_entry("pytest-runner", "pytest-runner/SKILL.md",
                          "run the suite"),
                   _entry("lint-runner", "lint-runner/SKILL.md", "run ruff")]
        if with_bodies:
            for e in entries:
                p = root / e["skill_md"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("---\nname: %s\n---\n\n%s\n"
                             % (e["name"], bodies[e["name"]]), encoding="utf-8")
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": root})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        # The tap stays configured and its catalog stays readable in BOTH
        # arms — that is the defect's shape: the entries survive their files.
        monkeypatch.setattr(registry, "list_taps",
                            lambda: [registry.Tap(name="acme/skills", url="")])
        monkeypatch.setattr(catalog, "load_tap",
                            lambda tap, rebuild=False: list(entries))
        rag.build(entries, force=True)
        return golden
    return build


class TestTheGateRefusesABodylessCorpus:
    """The defect: four floors PASS over 95% missing text, and score higher."""

    def test_main_exits_75_when_every_document_lost_its_body(
            self, corpus, capsys):
        m = _load()
        golden = corpus(with_bodies=False)
        rc = m.main(["--golden", str(golden), "-k", "1",
                     "--engines", "bm25", "--fail-under", "0.78"])
        assert rc == m.EX_TEMPFAIL == 75
        err = capsys.readouterr().err
        assert "CORPUS INCOMPLETE" in err
        assert "2 of 2 indexed documents carry no body" in err
        # The remedy, not just the diagnosis.
        assert "ensure_eval_corpus.sh" in err

    def test_nothing_is_scored_before_the_refusal(self, corpus, capsys):
        """A printed GATE table over a body-less corpus is the false green.

        The floors would have PASSED — by a wider margin than over the real
        corpus — so the refusal has to land before the metrics are computed,
        not alongside them.
        """
        m = _load()
        golden = corpus(with_bodies=False)
        assert m.main(["--golden", str(golden), "-k", "1",
                       "--floor", "hit@1=0.40"]) == 75
        out = capsys.readouterr().out
        assert "GATE" not in out
        assert "PASS" not in out

    def test_a_complete_corpus_is_scored_as_before(self, corpus, capsys):
        """The control: the check must not fire on a corpus that is all there."""
        m = _load()
        golden = corpus(with_bodies=True)
        rc = m.main(["--golden", str(golden), "-k", "1", "--engines", "bm25",
                     "--fail-under", "0.5", "--regression-eps", "1"])
        assert rc == 0
        out, err = capsys.readouterr()
        assert "CORPUS INCOMPLETE" not in err
        assert "GATE" in out

    def test_one_missing_body_out_of_two_still_refuses(
            self, corpus, tmp_path, capsys):
        """Half-materialised, not only fully missing.

        The roadmap card measured the fully-absent case and said so; the
        partial case is covered by construction rather than by calibration,
        because the check counts documents that could not be read rather than
        estimating how far the numbers moved.
        """
        m = _load()
        golden = corpus(with_bodies=True)
        (tmp_path / "repo" / "lint-runner" / "SKILL.md").unlink()
        rag.build([_entry("pytest-runner", "pytest-runner/SKILL.md", "run it"),
                   _entry("lint-runner", "lint-runner/SKILL.md", "run ruff")],
                  force=True)
        assert m.main(["--golden", str(golden), "-k", "1"]) == 75
        assert "1 of 2 indexed documents" in capsys.readouterr().err


class TestCorpusRefusalIsGatedOnDocumentsNotTokenShare:
    """`body_share` is a share of the tokens this index HAS.

    It reads 0.0 for an empty index as well as for a body-less one (see
    `rag.index_completeness`), so a share-based check would refuse an empty
    sandbox for the wrong reason and would understate a half-cloned machine —
    a body runs about an order of magnitude longer than the metadata standing
    in for it. The document count has one honest answer.
    """

    def test_no_index_is_not_a_refusal(self):
        m = _load()
        assert m.corpus_refusal(None) is None

    def test_an_empty_index_is_not_a_refusal(self):
        m = _load()
        assert m.corpus_refusal(
            {"docs": 0, "metadata_only": 0, "tokens": 0,
             "metadata_only_tokens": 0, "body_share": 0.0}) is None

    def test_a_complete_index_is_not_a_refusal(self):
        m = _load()
        assert m.corpus_refusal(
            {"docs": 9, "metadata_only": 0, "tokens": 900,
             "metadata_only_tokens": 0, "body_share": 1.0}) is None

    def test_a_high_body_share_still_refuses_when_documents_are_missing(self):
        """The case a token-share threshold would wave through.

        Half the documents lost their bodies and `body_share` is still 0.83,
        because the tokens that survived are the long ones. Any threshold
        expressed as a share of tokens passes this corpus.
        """
        m = _load()
        msg = m.corpus_refusal(
            {"docs": 10, "metadata_only": 5, "tokens": 6000,
             "metadata_only_tokens": 1000, "body_share": 0.8333})
        assert msg is not None
        assert "5 of 10 indexed documents" in msg


@pytest.mark.skipif(os.name == "nt" or not _ENSURE.exists(),
                    reason="POSIX shell wrapper")
class TestTheSentinelDoesNotOutliveTheClones:
    """The state that produced the false green, and its repair.

    The sentinel records that a corpus was built for this tap list. It cannot
    record that the corpus is still on disk, so reclaiming the 265 MB `repos/`
    tree by hand left the sentinel and every per-tap catalog cache behind and
    `make eval` skipped straight to scoring frontmatter.
    """

    def _run(self, tmp_path, calls, make_repos=True):
        root = tmp_path / "root"
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "eval").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "eval" / "taps.txt").write_text(
            "owner/repo %s 1\n" % ("a" * 40), encoding="utf-8")
        (root / "scripts" / "ensure_eval_corpus.sh").write_text(
            _ENSURE.read_text(encoding="utf-8"), encoding="utf-8")
        home = tmp_path / "home"
        stub = tmp_path / "stub.py"
        # A real --ensure materialises clones, so the stub does too: that is
        # what makes the *second* run a legitimate skip rather than an
        # accident of the fixture never creating the tree at all.
        stub.write_text(
            "#!%s\n"
            "import os, subprocess, sys\n"
            "a = sys.argv[1:]\n"
            "if a and a[0] == '-c':\n"
            "    sys.exit(subprocess.run([sys.executable] + a).returncode)\n"
            "open(%r, 'a').write('ensure\\n')\n"
            "%s\n"
            % (sys.executable, str(calls),
               ("os.makedirs(%r, exist_ok=True)"
                % str(home / "repos" / "owner__repo")) if make_repos else "pass"),
            encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ, BOOST_HOME=str(home), PYTHON=str(stub))
        env.pop("FORCE", None)
        res = subprocess.run(
            ["bash", str(root / "scripts" / "ensure_eval_corpus.sh")],
            capture_output=True, text=True, env=env)
        assert res.returncode == 0, res.stderr
        return res, home

    def test_a_sentinel_with_no_clones_under_it_re_taps(self, tmp_path):
        calls = tmp_path / "calls"
        _res, home = self._run(tmp_path, calls)
        assert calls.read_text(encoding="utf-8").count("ensure") == 1
        # Exactly the reproduced state: clones reclaimed, sentinel and caches
        # left behind.
        for child in (home / "repos").iterdir():
            child.rmdir()
        assert (home / ".eval-corpus-ready").exists()
        res, _home = self._run(tmp_path, calls)
        assert "skipping" not in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 2

    def test_an_intact_corpus_is_still_skipped(self, tmp_path):
        """The sentinel's whole purpose: a second `make check` stays offline."""
        calls = tmp_path / "calls"
        self._run(tmp_path, calls)
        res, _home = self._run(tmp_path, calls)
        assert "skipping" in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 1
