# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/eval_corpus.py — the corpus the required gate measures.

WHY THIS FILE EXISTS. `tests/eval/taps.txt` pinned repo NAMES, not commits, so
the gate's corpus was whatever those repos happened to contain at clone time.
Measured: the list recorded 743 entries when it was written and resolved to
**3,843** on the same 20 repos later, a 5.2x drift nobody changed a file to
cause. One repo (`affaan-m/ECC`) is 1,616 of those entries, so a single third
party can move the required number on its own.

That matters because the floor is not comfortable: BM25 scores recall@10
**0.912** against a floor of **0.85**, a margin of +0.062. Silent growth spends
that margin, and the first symptom would be a red required gate on an unrelated
PR.

These tests pin the halves of the fix. The file format carries a SHA per repo,
and every repo in the shipped list has one — so a future edit cannot quietly
reintroduce an unpinned entry. It carries an ENTRY COUNT per repo too, because a
SHA fixes the tree and not what the scanner makes of it, and because the
direction of that error is counter-intuitive: measured over the 91-query
required set, dropping the repo that holds 62% of the corpus moves BM25 from
0.852 / 0.473 to 0.885 / 0.593, so a partial corpus clears the floors MORE
easily than the real one and "score whatever is reachable today" is not a safe
fallback. And unreachability now exits 75 rather than 1, so a third party
deleting their repository does not arrive looking like a retrieval regression on
every open pull request at once.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_corpus.py"
_ENSURE = _ROOT / "scripts" / "ensure_eval_corpus.sh"
_TAPS = _ROOT / "tests" / "eval" / "taps.txt"
_REFRESH = _ROOT / ".github/workflows/eval-corpus-refresh.yml"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("eval_corpus", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path, name="origin"):
    """A real two-commit git repo, so the pin logic is exercised, not mocked."""
    path = tmp_path / name
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for cfg in (("user.email", "t@example.test"), ("user.name", "T"),
                ("commit.gpgsign", "false")):
        _git(path, "config", *cfg)
    shas = []
    for n in ("first", "second"):
        (path / "SKILL.md").write_text("# %s\n" % n, encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", n)
        shas.append(_git(path, "rev-parse", "HEAD"))
    return path, shas


class TestParsingTheTapList:
    def test_a_pinned_line_yields_repo_sha_and_count(self):
        m = _load()
        sha = "a" * 40
        assert m.parse_taps("owner/repo %s 12\n" % sha) == [("owner/repo", sha, 12)]

    def test_comments_and_blank_lines_are_skipped(self):
        m = _load()
        text = "# a comment\n\n   \nowner/repo %s 1\n" % ("b" * 40)
        assert [r for r, _s, _n in m.parse_taps(text)] == ["owner/repo"]

    def test_extra_whitespace_is_tolerated(self):
        m = _load()
        sha = "c" * 40
        assert m.parse_taps("  owner/repo \t %s  9 \n" % sha) == [
            ("owner/repo", sha, 9)]

    def test_an_unpinned_line_still_parses(self):
        # Backward compatible on purpose: the format change must not be a flag
        # day for anyone carrying a local list.
        m = _load()
        assert m.parse_taps("owner/repo\n") == [("owner/repo", None, None)]

    def test_a_pinned_line_without_a_count_still_parses(self):
        m = _load()
        sha = "d" * 40
        assert m.parse_taps("owner/repo %s\n" % sha) == [("owner/repo", sha, None)]

    def test_a_malformed_sha_fails_loudly(self):
        # A typo must not fall through to "unpinned" — that is the silent
        # weakening this whole change exists to prevent.
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.parse_taps("owner/repo not-a-sha\n")
        assert "owner/repo" in str(ei.value)

    def test_a_short_sha_is_rejected(self):
        m = _load()
        with pytest.raises(SystemExit):
            m.parse_taps("owner/repo %s\n" % ("d" * 7))

    def test_a_malformed_count_fails_loudly(self):
        # Same reasoning as the SHA: a count that quietly read as "uncounted"
        # would leave the corpus unverified while looking verified.
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.parse_taps("owner/repo %s twelve\n" % ("e" * 40))
        assert "owner/repo" in str(ei.value)

    def test_a_negative_count_is_rejected(self):
        m = _load()
        with pytest.raises(SystemExit):
            m.parse_taps("owner/repo %s -3\n" % ("e" * 40))

    def test_a_count_without_a_pin_is_rejected(self):
        # `repo 123` puts the count where the SHA belongs, so it fails as a bad
        # SHA. That is the right answer: a count beside an unpinned repo would
        # describe a tree free to change underneath it.
        m = _load()
        with pytest.raises(SystemExit):
            m.parse_taps("owner/repo 123\n")

    def test_a_fourth_field_is_rejected(self):
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.parse_taps("owner/repo %s 1 2\n" % ("f" * 40))
        assert "at most 3" in str(ei.value)


class TestTheShippedListIsFullyPinned:
    """The regression guard: this is what stops the drift coming back."""

    def test_every_repo_carries_a_sha(self):
        m = _load()
        unpinned = [r for r, sha, _n in m.parse_taps(_TAPS.read_text(encoding="utf-8"))
                    if not sha]
        assert unpinned == [], "unpinned repos in taps.txt: %s" % unpinned

    def test_every_repo_carries_an_entry_count(self):
        m = _load()
        uncounted = [r for r, _s, n in m.parse_taps(_TAPS.read_text(encoding="utf-8"))
                     if n is None]
        assert uncounted == [], (
            "uncounted repos in taps.txt: %s — run "
            "`python3 scripts/eval_corpus.py --relock`" % uncounted)

    def test_the_list_is_not_empty_and_has_no_duplicates(self):
        m = _load()
        repos = [r for r, _s, _n in m.parse_taps(_TAPS.read_text(encoding="utf-8"))]
        assert len(repos) >= 20
        assert len(repos) == len(set(repos))

    def test_every_sha_is_lowercase_hex(self):
        m = _load()
        for repo, sha, _n in m.parse_taps(_TAPS.read_text(encoding="utf-8")):
            assert re.fullmatch(r"[0-9a-f]{40}", sha or ""), (repo, sha)


class TestConcentration:
    """One publisher owning most of the corpus biases every recall figure.

    It cannot be fixed by trimming — measured, dropping the big repo raises all
    four metrics — so what is enforceable is a ratchet: this may not get worse
    without someone deciding it should.
    """

    def test_shares_are_ordered_largest_first_and_sum_to_one(self):
        m = _load()
        rows = [("a/a", "1" * 40, 60), ("b/b", "2" * 40, 30), ("c/c", "3" * 40, 10)]
        ranked = m.shares(rows)
        assert [r for r, _n, _s in ranked] == ["a/a", "b/b", "c/c"]
        assert sum(s for _r, _n, s in ranked) == pytest.approx(1.0)

    def test_uncounted_rows_are_omitted_rather_than_read_as_zero(self):
        # Counting them as zero would dilute every share and report a
        # concentration lower than the one that exists.
        m = _load()
        rows = [("a/a", "1" * 40, 90), ("b/b", "2" * 40, None)]
        assert m.shares(rows) == [("a/a", 90, 1.0)]

    def test_an_uncounted_list_has_no_shares(self):
        m = _load()
        assert m.shares([("a/a", "1" * 40, None)]) == []

    def test_a_dominant_repo_is_reported(self):
        m = _load()
        rows = [("big/one", "1" * 40, 900), ("small/two", "2" * 40, 100)]
        problem = m.check_concentration(rows)
        assert problem and "big/one" in problem

    def test_a_balanced_list_is_silent(self):
        m = _load()
        rows = [("a/a", "1" * 40, 50), ("b/b", "2" * 40, 50)]
        assert m.check_concentration(rows) is None

    def test_the_boundary_is_inclusive(self):
        # Exactly at the ceiling passes; the ratchet is "no worse than", not
        # "strictly better than", so re-locking identical counts cannot fail.
        m = _load()
        top = int(m.MAX_SHARE * 100)
        rows = [("a/a", "1" * 40, top), ("b/b", "2" * 40, 100 - top)]
        assert m.check_concentration(rows) is None

    def test_the_shipped_list_is_under_the_ceiling(self):
        m = _load()
        rows = m.parse_taps(_TAPS.read_text(encoding="utf-8"))
        assert m.check_concentration(rows) is None, m.check_concentration(rows)

    def test_the_ceiling_is_a_ratchet_on_the_measured_value(self):
        # If this ever passes trivially, the ratchet has stopped ratcheting.
        m = _load()
        top = m.shares(m.parse_taps(_TAPS.read_text(encoding="utf-8")))[0]
        assert 0.5 < top[2] <= m.MAX_SHARE
        assert m.MAX_SHARE - top[2] < 0.10, (
            "MAX_SHARE has drifted far above the measured share — re-tighten it")


class TestExtraTaps:
    """The index is built from every CONFIGURED tap, not from this file."""

    def test_a_tap_outside_the_list_is_reported(self):
        m = _load()
        assert m.extra_taps(["a/a", "b/b"], ["a/a"]) == ["b/b"]

    def test_an_exact_match_reports_nothing(self):
        m = _load()
        assert m.extra_taps(["a/a"], ["a/a"]) == []

    def test_a_pinned_repo_that_is_not_configured_is_not_an_extra(self):
        # That case is a materialisation failure, reported by --ensure with the
        # repo named; it must not also surface here as a spurious "extra".
        m = _load()
        assert m.extra_taps(["a/a"], ["a/a", "b/b"]) == []


class TestRelock:
    def test_counts_are_written_and_read_back(self):
        m = _load()
        sha = "a" * 40
        text = "# header\nowner/repo %s\n" % sha
        out = m.relock_text(text, {"owner/repo": 42})
        assert m.parse_taps(out) == [("owner/repo", sha, 42)]

    def test_comments_and_the_trailing_newline_are_preserved(self):
        m = _load()
        text = "# header\n#\nowner/repo %s 1\n" % ("a" * 40)
        out = m.relock_text(text, {"owner/repo": 2})
        assert out.startswith("# header\n#\n")
        assert out.endswith("\n")

    def test_an_unpinned_row_is_left_alone(self):
        # Writing a count beside an unpinned repo would claim a fixed size for a
        # tree that is free to change.
        m = _load()
        out = m.relock_text("owner/repo\n", {"owner/repo": 5})
        assert out == "owner/repo\n"

    def test_a_row_with_no_new_count_is_left_alone(self):
        m = _load()
        text = "kept/repo %s 7\n" % ("a" * 40)
        assert m.relock_text(text, {"other/repo": 1}) == text

    def test_relocking_the_shipped_list_with_its_own_counts_is_a_no_op(self):
        # The file is the output of --relock, so re-running it must not churn.
        m = _load()
        text = _TAPS.read_text(encoding="utf-8")
        counts = {r: n for r, _s, n in m.parse_taps(text) if n is not None}
        assert m.relock_text(text, counts) == text


class TestRefreshRewritesThePins:
    """`--relock` re-measures the same trees; `--refresh` moves to new ones."""

    def test_a_new_sha_is_written(self):
        m = _load()
        old, new = "a" * 40, "b" * 40
        out = m.relock_text("owner/repo %s 1\n" % old, {"owner/repo": 2},
                            {"owner/repo": new})
        assert m.parse_taps(out) == [("owner/repo", new, 2)]

    def test_a_row_with_no_new_sha_keeps_its_pin(self):
        m = _load()
        old = "a" * 40
        out = m.relock_text("owner/repo %s 1\n" % old, {"owner/repo": 2},
                            {"other/repo": "b" * 40})
        assert m.parse_taps(out) == [("owner/repo", old, 2)]

    def test_a_malformed_new_sha_is_refused_before_it_is_written(self):
        # `git rev-parse` returning "" or an error string must never reach the
        # file: it would parse as a bad pin on the next run, at which point the
        # corpus that produced it is gone.
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.relock_text("owner/repo %s 1\n" % ("a" * 40), {"owner/repo": 1},
                          {"owner/repo": "HEAD"})
        assert "owner/repo" in str(ei.value)


class TestTheRefreshSummary:
    """The diff IS the finding, so the body has to state it, not imply it."""

    def _rows(self):
        return [("a/a", "1" * 40, 100), ("b/b", "2" * 40, 50)]

    def test_an_unchanged_row_says_so(self):
        m = _load()
        rows = self._rows()
        text = m.refresh_summary(rows, {}, {"a/a": 100, "b/b": 50})
        assert "| `a/a` | unchanged | 100 |" in text
        assert "**0 of 2 repositories moved.**" in text

    def test_a_moved_pin_shows_both_shas_abbreviated(self):
        m = _load()
        text = m.refresh_summary(self._rows(), {"a/a": "3" * 40},
                                 {"a/a": 100, "b/b": 50})
        assert "`1111111` → `3333333`" in text
        assert "**1 of 2 repositories moved.**" in text

    def test_an_entry_delta_is_signed(self):
        m = _load()
        text = m.refresh_summary(self._rows(), {"a/a": "3" * 40},
                                 {"a/a": 112, "b/b": 50})
        assert "100 → 112 (+12)" in text

    def test_a_shrinking_repo_is_reported_as_a_loss(self):
        m = _load()
        text = m.refresh_summary(self._rows(), {"a/a": "3" * 40},
                                 {"a/a": 88, "b/b": 50})
        assert "100 → 88 (-12)" in text

    def test_the_corpus_total_is_stated_with_its_delta(self):
        m = _load()
        text = m.refresh_summary(self._rows(), {"a/a": "3" * 40},
                                 {"a/a": 112, "b/b": 50})
        assert "Corpus 150 → 162 entries (+12)." in text


class TestFailuresAreClassified:
    """An unreachable third party and a broken ranker are not the same red."""

    def test_unavailability_exits_tempfail(self, capsys):
        m = _load()
        code = m._report_failures(
            [m.CorpusError(m.UNAVAILABLE, "a/a", "gone")], 20)
        assert code == m.EXIT_UNAVAILABLE == 75
        assert "not a retrieval regression" in capsys.readouterr().out

    def test_drift_exits_one(self, capsys):
        m = _load()
        code = m._report_failures([m.CorpusError(m.DRIFT, "a/a", "12 vs 13")], 20)
        assert code == m.EXIT_DRIFT == 1
        assert "CORPUS DRIFT" in capsys.readouterr().out

    def test_drift_wins_when_both_happen(self, capsys):
        # Drift is the one that says something about this repository, and it is
        # not fixed by waiting; reporting TEMPFAIL would invite a re-run.
        m = _load()
        code = m._report_failures([m.CorpusError(m.UNAVAILABLE, "a/a", "gone"),
                                   m.CorpusError(m.DRIFT, "b/b", "12 vs 13")], 20)
        assert code == m.EXIT_DRIFT
        out = capsys.readouterr().out
        assert "CORPUS UNAVAILABLE" in out and "CORPUS DRIFT" in out

    def test_every_unavailable_repo_is_named_not_just_the_first(self, capsys):
        m = _load()
        m._report_failures([m.CorpusError(m.UNAVAILABLE, "a/a", "gone"),
                            m.CorpusError(m.UNAVAILABLE, "b/b", "gone")], 20)
        out = capsys.readouterr().out
        assert "a/a" in out and "b/b" in out
        assert "2 of 20" in out


class TestTheGateIsDefinedOnce:
    """`make check` claims to BE the required gate. For `eval` it was not.

    CI ran `--fail-under 0.85` and no other floor; the Makefile (and the gate
    table in CLAUDE.md) define four floors with recall at 0.78. So the required
    check was simultaneously tighter than documented on one metric — 0.863
    measured against 0.85 is a buffer of 1.15 queries out of 91 — and absent on
    the other three, which are the ones added to close the "finds it every time,
    never ranks it first" hole. A ranker could regress hit@1 to 0.000 and the
    required gate would pass.
    """

    def _flags(self, text: str):
        # The invocation is line-continued in the Makefile, so match over the
        # whole recipe/step rather than a single line.
        assert "eval_retrieval.py" in text
        floors = dict(re.findall(r"--floor\s+([\w@]+)=([\d.]+)", text))
        under = re.search(r"--fail-under\s+([\d.]+)", text)
        assert under, "no --fail-under in:\n%s" % text
        floors["recall@k"] = under.group(1)
        return floors

    @pytest.mark.skipif(not (_ROOT / "Makefile").exists(),
                        reason="repo-root Makefile not reachable")
    def test_ci_and_make_floor_the_same_metrics_at_the_same_values(self):
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("\neval:", 1)[1].split("\n\n", 1)[0]
        ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        # Anchor on the step, not the prose: the comment block above it names
        # the gate too, and now carries the caching rationale between them.
        step = ci.split("- name: retrieval quality gate", 1)[1].split("\n\n", 1)[0]
        assert self._flags(step) == self._flags(recipe)

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_corpus_refresh_scores_against_the_same_floors(self):
        """Otherwise its PASS/FAIL banner is about a different gate.

        The refresh job runs the eval non-blocking and puts the verdict at the
        top of the PR body, which is the whole point of the job — a reviewer
        decides from that banner whether the new corpus is acceptable. Floors
        that drifted from the required ones would make the banner confidently
        wrong in either direction.
        """
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("\neval:", 1)[1].split("\n\n", 1)[0]
        wf = _REFRESH.read_text(encoding="utf-8")
        step = wf.split("- name: score the refreshed corpus", 1)[1]
        assert self._flags(step) == self._flags(recipe)


class TestPinningAClone:
    def test_a_sha_already_present_is_checked_out_without_fetching(
            self, tmp_path, monkeypatch):
        m = _load()
        path, shas = _repo(tmp_path)
        fetched = []
        monkeypatch.setattr(m, "_fetch", lambda *a: fetched.append(a))
        m.pin_clone(path, shas[0])
        assert _git(path, "rev-parse", "HEAD") == shas[0]
        assert fetched == [], "fetched a commit the clone already had"

    def test_a_missing_sha_is_fetched_from_origin(self, tmp_path):
        # The real case in CI: `boost tap` shallow-clones, so the pinned commit
        # is usually absent until it is fetched by SHA.
        m = _load()
        origin, shas = _repo(tmp_path)
        clone = tmp_path / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        "file://%s" % origin, str(clone)], check=True)
        assert m.has_commit(clone, shas[0]) is False, "fixture is not shallow"
        m.pin_clone(clone, shas[0])
        assert _git(clone, "rev-parse", "HEAD") == shas[0]

    def test_pinning_is_idempotent(self, tmp_path):
        m = _load()
        path, shas = _repo(tmp_path)
        m.pin_clone(path, shas[0])
        m.pin_clone(path, shas[0])
        assert _git(path, "rev-parse", "HEAD") == shas[0]

    def test_an_unreachable_sha_is_unavailability_not_a_generic_failure(
            self, tmp_path):
        # The kind is what CI reads to decide whether the pull request is at
        # fault, so it is the assertion that matters — not just "it raised".
        m = _load()
        path, _shas = _repo(tmp_path)
        with pytest.raises(m.CorpusError) as ei:
            m.pin_clone(path, "e" * 40)
        assert ei.value.kind == m.UNAVAILABLE
        assert path.name in str(ei.value)

    def test_has_commit_is_false_for_a_tree_not_a_commit(self, tmp_path):
        # `cat-file -e <sha>` alone passes for any object; the pin must reject a
        # tree or blob SHA rather than checking out something meaningless.
        m = _load()
        path, _shas = _repo(tmp_path)
        tree = _git(path, "rev-parse", "HEAD^{tree}")
        assert m.has_commit(path, tree) is False


@pytest.mark.skipif(os.name == "nt" or not _ENSURE.exists(),
                    reason="POSIX shell wrapper")
class TestTheSentinelIsKeyedOnTheTapList:
    """An empty sentinel let an edited taps.txt score the OLD corpus.

    `make eval` skipped re-tapping whenever the sentinel existed at all, so
    moving a pin or adding a repo left the previous corpus in place and scored
    it against the new file's baseline — the same "measuring something other
    than what the file says" bug as an unpinned list, one directory along.
    """

    def _wrapper_run(self, tmp_path, taps_text, calls):
        """Run the wrapper against a stub interpreter, recording --ensure calls."""
        root = tmp_path / "root"
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "eval").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "eval" / "taps.txt").write_text(taps_text,
                                                          encoding="utf-8")
        (root / "scripts" / "ensure_eval_corpus.sh").write_text(
            _ENSURE.read_text(encoding="utf-8"), encoding="utf-8")
        # The wrapper calls the interpreter twice — once with `-c` to digest the
        # tap list, once to run --ensure. The stub delegates the first to real
        # Python and records the second, so no corpus is materialised.
        stub = tmp_path / "stub.py"
        stub.write_text(
            "#!%s\n"
            "import subprocess, sys\n"
            "a = sys.argv[1:]\n"
            "if a and a[0] == '-c':\n"
            "    sys.exit(subprocess.run([sys.executable] + a).returncode)\n"
            "open(%r, 'a').write('ensure\\n')\n" % (sys.executable, str(calls)),
            encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ, BOOST_HOME=str(tmp_path / "home"),
                   PYTHON=str(stub))
        env.pop("FORCE", None)
        res = subprocess.run(
            ["bash", str(root / "scripts" / "ensure_eval_corpus.sh")],
            capture_output=True, text=True, env=env)
        assert res.returncode == 0, res.stderr
        return res.stdout

    def test_a_second_run_over_the_same_list_is_skipped(self, tmp_path):
        calls = tmp_path / "calls"
        text = "owner/repo %s 1\n" % ("a" * 40)
        self._wrapper_run(tmp_path, text, calls)
        out = self._wrapper_run(tmp_path, text, calls)
        assert "skipping" in out
        assert calls.read_text(encoding="utf-8").count("ensure") == 1

    def test_editing_the_list_re_taps(self, tmp_path):
        calls = tmp_path / "calls"
        self._wrapper_run(tmp_path, "owner/repo %s 1\n" % ("a" * 40), calls)
        out = self._wrapper_run(tmp_path, "owner/repo %s 2\n" % ("a" * 40), calls)
        assert "skipping" not in out
        assert calls.read_text(encoding="utf-8").count("ensure") == 2


class TestRefreshingTheScaleCorpusLeavesTheRequiredRowsAlone:
    """The required rows in `taps-scale.txt` belong to `taps.txt`.

    `build_scale_corpus.render` copies them in verbatim — pin and count
    included — because both tiers must start from the same trees: the golden
    floors were calibrated against the required corpus, and a scale tier
    measuring a *different* snapshot of the same repos reports a difference
    that is not scale. The generator's own section header says "verbatim".

    Nothing enforced it. `--refresh` walked every row of whatever file it was
    given, so the monthly scale job moved the required pins too, and the two
    tiers silently decoupled. It also re-columned the whole file (the width is
    the longest name in the file, and the distractor names are longer), so
    every required row changed even where the pin did not.

    The PR it opened could never merge: `build_scale_corpus.py --check` — which
    the same workflow runs one step earlier — calls the result stale, forever.
    """

    def _scale_file(self, tmp_path):
        required = ("anthropics/skills     %s    18\n" % ("a" * 40)
                    + "minio/skills          %s     3\n" % ("b" * 40))
        scale = tmp_path / "taps-scale.txt"
        scale.write_text(
            "# --- the required corpus, verbatim ---\n"
            + required
            + "\n# --- distractors ---\n"
            + "some-very-long-owner/some-very-long-repo-name\n",
            encoding="utf-8")
        (tmp_path / "taps.txt").write_text(required, encoding="utf-8")
        return scale, required

    def test_a_required_row_is_not_re_pinned(self, tmp_path):
        scale, required = self._scale_file(tmp_path)
        frozen = _load().frozen_rows(scale, tmp_path / "taps.txt")
        assert frozen == {"anthropics/skills", "minio/skills"}
        # A refresh that measured new trees for them must still not write them.
        out = _load().relock_text(
            scale.read_text(encoding="utf-8"),
            {"anthropics/skills": 20, "minio/skills": 9},
            {"anthropics/skills": "c" * 40, "minio/skills": "d" * 40},
            frozen=frozen)
        for row in required.splitlines():
            assert row in out, "required row was rewritten: %r" % row

    def test_a_frozen_row_keeps_its_column_width(self, tmp_path):
        """The subtler half: even an unchanged pin was being re-columned.

        `relock_text` pads to the longest name it is rewriting, and the scale
        file's distractors are longer than anything in `taps.txt` — so the
        required block came back at a different width and stopped matching the
        generator byte for byte.
        """
        scale, _required = self._scale_file(tmp_path)
        out = _load().relock_text(
            scale.read_text(encoding="utf-8"),
            {"anthropics/skills": 18,
             "some-very-long-owner/some-very-long-repo-name": 7},
            {"some-very-long-owner/some-very-long-repo-name": "e" * 40},
            frozen={"anthropics/skills"})
        assert "anthropics/skills     %s    18" % ("a" * 40) in out
        assert "some-very-long-owner/some-very-long-repo-name %s" % ("e" * 40) in out

    def test_distractors_are_still_refreshed(self, tmp_path):
        # Freezing must not turn the monthly job into a no-op.
        scale, _required = self._scale_file(tmp_path)
        out = _load().relock_text(
            scale.read_text(encoding="utf-8"),
            {"some-very-long-owner/some-very-long-repo-name": 7},
            {"some-very-long-owner/some-very-long-repo-name": "e" * 40},
            frozen={"anthropics/skills", "minio/skills"})
        assert "some-very-long-owner/some-very-long-repo-name %s     7" % ("e" * 40) in out

    def test_refreshing_the_required_corpus_itself_freezes_nothing(self, tmp_path):
        """`--refresh` on taps.txt is exactly the job that MAY move those pins.

        Freezing on identity rather than on membership would make the required
        corpus permanently unrefreshable — the opposite failure, and a quieter
        one.
        """
        _scale, required = self._scale_file(tmp_path)
        taps = tmp_path / "taps.txt"
        assert _load().frozen_rows(taps, taps) == set()
        out = _load().relock_text(required, {"anthropics/skills": 20},
                             {"anthropics/skills": "c" * 40},
                             frozen=_load().frozen_rows(taps, taps))
        assert "c" * 40 in out

    def test_a_missing_required_file_freezes_nothing(self, tmp_path):
        # A refresh must degrade to the old behaviour, never crash.
        scale, _required = self._scale_file(tmp_path)
        assert _load().frozen_rows(scale, tmp_path / "absent.txt") == set()


class TestRefreshPinsARowThatArrivedBare:
    """`--refresh` resolves a new SHA, so it can pin a row that has none.

    `relock_text` skipped any row with fewer than two fields, on a rule that is
    right for `--relock` and wrong for `--refresh`. The two differ in exactly
    the way that matters: `--relock` re-measures the *same* tree and has no SHA
    to offer, so writing a count beside an unpinned repo would describe a tree
    free to change underneath it. `--refresh` has just resolved upstream HEAD,
    so it has both halves and the row can be closed.

    Measured cost of the old rule: the shipped scale corpus is 165 bare rows
    and 20 pinned ones, and the monthly job rewrote exactly the 20 — the
    required block it must not touch — while pinning none of the 165 it exists
    to pin. The tier that is supposed to measure a pinned 20,000-entry corpus
    was floating on upstream HEAD for 89% of its rows.

    The durable rule is about the SHA, not about the row: never write a count
    without one.
    """

    def test_a_bare_row_gains_a_pin_when_a_sha_was_resolved(self):
        m = _load()
        out = m.relock_text("a/b\n", {"a/b": 7}, {"a/b": "f" * 40})
        assert out == "a/b %s     7\n" % ("f" * 40)

    def test_a_bare_row_is_left_alone_when_no_sha_was_resolved(self):
        """The property the old rule was protecting, kept.

        This is `--relock`: the scanner changed, the trees did not, and there
        is no SHA on offer. A count here would claim a measurement of a tree
        nobody pinned.
        """
        m = _load()
        assert m.relock_text("a/b\n", {"a/b": 7}) == "a/b\n"

    def test_a_bare_row_with_no_count_is_left_alone(self):
        m = _load()
        assert m.relock_text("a/b\n", {}, {"a/b": "f" * 40}) == "a/b\n"

    def test_a_malformed_pin_is_still_refused(self):
        # Not a SHA and nothing resolved for it: writing would launder a typo
        # into a row that reads as measured.
        m = _load()
        assert m.relock_text("a/b nope 3\n", {"a/b": 7}) == "a/b nope 3\n"

    def test_a_malformed_pin_is_replaced_when_a_sha_was_resolved(self):
        m = _load()
        out = m.relock_text("a/b nope 3\n", {"a/b": 7}, {"a/b": "f" * 40})
        assert out == "a/b %s     7\n" % ("f" * 40)

    def test_the_width_covers_rows_that_were_bare(self):
        # A newly-pinned long name must not be excluded from the column maths.
        m = _load()
        out = m.relock_text("short/x\nmuch-longer-owner/repo\n",
                            {"short/x": 1, "much-longer-owner/repo": 2},
                            {"short/x": "a" * 40, "much-longer-owner/repo": "b" * 40})
        assert "short/x                %s     1" % ("a" * 40) in out
