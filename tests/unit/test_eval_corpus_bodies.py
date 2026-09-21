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

* `eval_retrieval.corpus_refusal` / `main` — a run whose numbers bind anything
  (a floor, or a baseline pin) refuses to score, exit 66, before any metric is
  computed. A run that binds nothing prints the same diagnosis as a warning
  and scores anyway.
* `ensure_eval_corpus.sh` — a sentinel with no clone under `repos/` is a cache
  miss, and the sentinel is dropped before every `--ensure`, so only a clean
  one can vouch for the corpus again. That `--ensure` can actually repair the
  state is pinned in test_eval_corpus.py.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import catalog, rag, registry

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_retrieval.py"
_ENSURE = _ROOT / "scripts" / "ensure_eval_corpus.sh"
_REFRESH = _ROOT / ".github" / "workflows" / "eval-corpus-refresh.yml"

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


_GATE = ["--fail-under", "0.78"]


class TestTheGateRefusesABodylessCorpus:
    """The defect: four floors PASS over 95% missing text, and score higher."""

    def test_main_exits_66_when_every_document_lost_its_body(
            self, corpus, capsys):
        m = _load()
        golden = corpus(with_bodies=False)
        rc = m.main(["--golden", str(golden), "-k", "1",
                     "--engines", "bm25", *_GATE])
        # EX_NOINPUT, not 75: in this repository 75 means "a third party is
        # unavailable, re-run later", and waiting repairs nothing here.
        assert rc == 66
        assert m.EX_NOINPUT == 66
        err = capsys.readouterr().err
        assert "CORPUS INCOMPLETE" in err
        assert "2 of 2 indexed documents carry no body" in err

    # Relative too: the line is for pasting, possibly from another directory.
    @pytest.mark.parametrize("relative", [False, True])
    def test_the_remedy_names_the_home_it_repairs(self, corpus, capsys,
                                                  tmp_path, monkeypatch,
                                                  relative):
        """`make eval` sets BOOST_HOME inside its recipe and nowhere else.

        So a bare `FORCE=1 bash scripts/ensure_eval_corpus.sh` pasted from the
        refusal ran against `~/.boost` — the user's real home — tapping twenty
        pinned repos into it and leaving `.eval-home` exactly as broken. The
        command has to carry the home, and the interpreter the gate ran under.
        The home is set apart from `$HOME/.boost` before the index is built,
        or a remedy that named `~/.boost` would print the same string.
        """
        m = _load()
        home = tmp_path / "eval-home"
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BOOST_HOME", "eval-home" if relative else str(home))
        golden = corpus(with_bodies=False)
        assert m.main(["--golden", str(golden), "-k", "1", *_GATE]) == 66
        line = capsys.readouterr().err.splitlines()[-1]
        want = "FORCE=1 BOOST_HOME=%s PYTHON=%s bash %s" % (
            shlex.quote(str(home.resolve())), shlex.quote(sys.executable),
            shlex.quote(str(_ENSURE)))
        assert want in line
        assert str(Path.home() / ".boost") not in line

    def test_nothing_is_scored_before_the_refusal(self, corpus, capsys):
        """A printed GATE table over a body-less corpus is the false green.

        The floors would have PASSED — by a wider margin than over the real
        corpus — so the refusal has to land before the metrics are computed,
        not alongside them.
        """
        m = _load()
        golden = corpus(with_bodies=False)
        assert m.main(["--golden", str(golden), "-k", "1",
                       "--floor", "hit@1=0.40"]) == 66
        out = capsys.readouterr().out
        assert "GATE" not in out
        assert "PASS" not in out

    def test_a_baseline_is_not_pinned_over_a_bodyless_corpus(
            self, corpus, tmp_path, monkeypatch, capsys):
        """A baseline binds every later run the way a floor binds this one.

        eval-corpus-refresh.yml re-baselines with a bare `--save-baseline`, no
        floor on the command line, so scoping the refusal to floors alone would
        let a frontmatter index write the numbers the next month is compared to.
        """
        m = _load()
        monkeypatch.setattr(m, "BASELINE", tmp_path / "baseline.json")
        golden = corpus(with_bodies=False)
        assert m.main(["--golden", str(golden), "-k", "1",
                       "--save-baseline"]) == 66
        assert not (tmp_path / "baseline.json").exists()
        assert "CORPUS INCOMPLETE" in capsys.readouterr().err

    def test_a_run_that_binds_nothing_warns_and_still_scores(
            self, corpus, tmp_path, monkeypatch, capsys):
        """The refusal protects gates, not every reader of the index.

        `make eval-ai`, `--stats` and the natural-language `--golden` runs
        floor nothing and pin nothing, and some of them read a developer's real
        home. Refusing them turned one uncloned tap there into a hard exit that
        pointed at a corpus they were not using.
        """
        m = _load()
        monkeypatch.setattr(m, "BASELINE", tmp_path / "baseline.json")
        golden = corpus(with_bodies=False)
        rc = m.main(["--golden", str(golden), "-k", "1", "--engines", "bm25",
                     "--regression-eps", "1"])
        assert rc == 0
        out, err = capsys.readouterr()
        assert "CORPUS INCOMPLETE" in err
        assert "2 of 2 indexed documents carry no body" in err
        assert "refusing" not in err
        assert "BM25 full-content" in out

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
        assert m.main(["--golden", str(golden), "-k", "1", *_GATE]) == 66
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


def _one_of_many():
    """The pinned corpus's measured size (10,731 documents, 9,252,773 tokens)
    with ONE document's body missing; its 41 stand-in tokens are illustrative."""
    return {"docs": 10731, "metadata_only": 1, "tokens": 9252773,
            "metadata_only_tokens": 41, "body_share": 0.99999557}


class TestTheRefusalIsStrict:
    """No tolerance: the pinned corpus measures exactly zero missing bodies."""

    def test_one_document_in_ten_thousand_refuses(self):
        """Kills "tolerate under half" and "tolerate under 1%" alike."""
        m = _load()
        msg = m.corpus_refusal(_one_of_many())
        assert msg is not None
        assert "1 of 10731 indexed documents carry no body" in msg

    def test_the_metadata_is_stated_as_a_count_not_a_rounded_share(self):
        """`%.1f` printed "100.0% of the indexed tokens are body text" here.

        A share that rounds to 100 over a corpus the same message calls
        incomplete contradicts itself, so the stand-in text is a count.
        """
        m = _load()
        msg = m.corpus_refusal(_one_of_many())
        assert "41 of the index's 9252773 tokens" in msg
        assert "100.0%" not in msg

    def test_higher_is_claimed_only_where_it_was_measured(self):
        """Every body missing was measured to score HIGHER; a partial loss was
        not measured at all, so the message may not claim a direction for it."""
        m = _load()
        partial = m.corpus_refusal(_one_of_many())
        assert "HIGHER" not in partial
        assert "not been measured" in partial
        total = m.corpus_refusal(
            {"docs": 10731, "metadata_only": 10731, "tokens": 444003,
             "metadata_only_tokens": 444003, "body_share": 0.0})
        assert "HIGHER" in total
        assert "not been measured" not in total


@pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
class TestTheRefreshJobKeepsARefusalApartFromAVerdict:
    """eval-corpus-refresh.yml scores with floors, so the gate can refuse there.

    Its pull-request banner branched on `steps.gate.outcome`, which is binary:
    a refusal would have reached the reviewer as "The refreshed corpus does
    NOT clear the floors" — a verdict on a corpus nothing had scored, sent to
    the one person deciding whether to re-floor.
    """

    def _steps(self):
        """The `corpus` job's steps, read as text rather than through PyYAML.

        PyYAML is in the lint and mutation toolchains but not in the one the
        required unit job installs, so `importorskip("yaml")` skipped these
        exactly where they had to run. Each step is a `      - ` item; the
        scalar keys it needs sit at eight spaces, and `run: |` is everything
        indented deeper under it.
        """
        text = _REFRESH.read_text(encoding="utf-8")
        body = text.split("\n  corpus:\n", 1)[1].split("\n    steps:\n", 1)[1]
        steps = []
        for chunk in re.split(r"^      - ", body, flags=re.M)[1:]:
            lines = ("        " + chunk).splitlines()
            step, run = {}, None
            for ln in lines:
                if run is not None:
                    if ln.startswith("          ") or not ln.strip():
                        run.append(ln[10:])
                        continue
                    step["run"], run = "\n".join(run), None
                m = re.match(r"^        ([\w-]+): ?(.*)$", ln)
                if m and m.group(2) == "|" and m.group(1) == "run":
                    run = []
                elif m:
                    step[m.group(1)] = m.group(2).strip()
            if run is not None:
                step["run"] = "\n".join(run)
            steps.append(step)
        assert steps, "no steps parsed from %s" % _REFRESH
        return steps

    def test_the_gate_step_records_its_exit_code(self):
        gate = next(s for s in self._steps() if s.get("id") == "gate")
        assert 'echo "rc=$rc" >> "$GITHUB_OUTPUT"' in gate["run"]
        assert 'exit "$rc"' in gate["run"]

    def test_a_refusal_fails_the_job_before_the_banner_is_written(self):
        m = _load()
        steps = self._steps()
        names = [s.get("name", "") for s in steps]
        refused = [i for i, s in enumerate(steps)
                   if s.get("if") == "steps.gate.outputs.rc == '%d'"
                   % m.EX_NOINPUT]
        assert refused, "no step tells a refusal apart from a floor verdict"
        step = steps[refused[0]]
        assert step.get("continue-on-error", "false") != "true"
        assert "exit %d" % m.EX_NOINPUT in step["run"]
        assert refused[0] < names.index("assemble the pull request body")


@pytest.mark.skipif(os.name == "nt" or not _ENSURE.exists(),
                    reason="POSIX shell wrapper")
class TestTheSentinelDoesNotOutliveTheClones:
    """The state that produced the false green, and its repair.

    The sentinel records that a corpus was built for this tap list. It cannot
    record that the corpus is still on disk, so reclaiming the ~300 MB `repos/`
    tree by hand left the sentinel and every per-tap catalog cache behind and
    `make eval` skipped straight to scoring frontmatter.
    """

    def _run(self, tmp_path, calls, ensure_rc=0, force=False):
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
        # accident of the fixture never creating the tree at all. It exits
        # `ensure_rc`, which is how a DRIFT or UNAVAILABLE --ensure is staged.
        stub.write_text(
            "#!%s\n"
            "import os, subprocess, sys\n"
            "a = sys.argv[1:]\n"
            "if a and a[0] == '-c':\n"
            "    sys.exit(subprocess.run([sys.executable] + a).returncode)\n"
            "open(%r, 'a').write('ensure\\n')\n"
            "os.makedirs(%r, exist_ok=True)\n"
            "sys.exit(%d)\n"
            % (sys.executable, str(calls),
               str(home / "repos" / "owner__repo"), ensure_rc),
            encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ, BOOST_HOME=str(home), PYTHON=str(stub))
        env.pop("FORCE", None)
        if force:
            env["FORCE"] = "1"
        res = subprocess.run(
            ["bash", str(root / "scripts" / "ensure_eval_corpus.sh")],
            capture_output=True, text=True, env=env)
        return res, home

    def test_a_sentinel_with_no_clones_under_it_re_taps(self, tmp_path):
        calls = tmp_path / "calls"
        res, home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        assert calls.read_text(encoding="utf-8").count("ensure") == 1
        # Exactly the reproduced state: clones reclaimed, sentinel and caches
        # left behind.
        for child in (home / "repos").iterdir():
            child.rmdir()
        assert (home / ".eval-corpus-ready").exists()
        res, _home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        assert "skipping" not in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 2

    def test_a_stray_file_is_not_a_clone(self, tmp_path):
        """Finder drops `.DS_Store` into any directory it shows.

        `ls -A` counted it as a populated `repos/`, so browsing to the emptied
        tree once was enough to bring the false green back. A clone is a
        directory; nothing else under `repos/` says there is a corpus.
        """
        calls = tmp_path / "calls"
        res, home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        (home / "repos" / "owner__repo").rmdir()
        (home / "repos" / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
        res, _home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        assert "skipping" not in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 2

    def test_a_failed_ensure_leaves_no_sentinel_behind(self, tmp_path):
        """Only a clean --ensure may vouch for the corpus again.

        The sentinel used to be written after a clean run and never removed,
        so a FORCE=1 run that ended in DRIFT (exit 1) kept the OLD sentinel —
        and the next `make eval` skipped straight past the corpus it had just
        failed to repair. Measured: a deleted SKILL.md, the gate refused, the
        remedy exited 1 having rebuilt that tap's cache without the entry, and
        the next run scored 10,730 entries green with nothing to refuse.
        """
        calls = tmp_path / "calls"
        res, home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        sentinel = home / ".eval-corpus-ready"
        assert sentinel.exists()
        res, _home = self._run(tmp_path, calls, ensure_rc=1, force=True)
        assert res.returncode == 1
        assert not sentinel.exists()
        # And so the next run re-taps rather than trusting the tree.
        res, _home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        assert "skipping" not in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 3

    def test_an_intact_corpus_is_still_skipped(self, tmp_path):
        """The sentinel's whole purpose: a second `make check` stays offline."""
        calls = tmp_path / "calls"
        res, _home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        res, _home = self._run(tmp_path, calls)
        assert res.returncode == 0, res.stderr
        assert "skipping" in res.stdout
        assert calls.read_text(encoding="utf-8").count("ensure") == 1
