# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/eval_corpus.py — the corpus the required gate measures.

WHY THIS FILE EXISTS. `tests/eval/taps.txt` pinned repo NAMES, not commits, so
the gate's corpus was whatever those repos happened to contain at clone time.
Measured: the list recorded 743 entries when it was written and resolved to
**3,843** on the same 20 repos later, a 5.2x drift nobody changed a file to
cause. One repo (`affaan-m/ECC`) was 1,616 of those entries, so a single third
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

import functools
import importlib.util
import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_corpus.py"
_ENSURE = _ROOT / "scripts" / "ensure_eval_corpus.sh"
_TAPS = _ROOT / "tests" / "eval" / "taps.txt"
_REFRESH = _ROOT / ".github/workflows/eval-corpus-refresh.yml"
_CI = _ROOT / ".github/workflows/ci.yml"
_EVAL = _ROOT / "scripts" / "eval_retrieval.py"

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


class TestTheCorpusSizeBlock:
    """taps.txt states its own size in a block every rewrite of the rows writes.

    It used to be a sentence someone typed. The first monthly refresh moved the
    rows from 10,152 entries to 10,731 and left the sentence at 10,152, fifty
    lines above the rows that contradicted it. Written by the same call that
    writes the rows, the two cannot disagree after `--relock` or `--refresh`.
    """

    _START = "# --- corpus size: written from the rows below by eval_corpus.py ---"
    _END = "# --- end corpus size ---"

    def _text(self, rows, divider_after=None):
        sha = "a" * 40
        lines = ["# header", self._START, "# typed by hand, and stale",
                 self._END, ""]
        for i, (repo, n) in enumerate(rows):
            lines.append("%s %s %d" % (repo, sha, n))
            if divider_after == i:
                lines += ["", "# --- scale: not golden targets ---"]
        return "\n".join(lines) + "\n"

    def _block(self, text):
        return text.split(self._START, 1)[1].split(self._END, 1)[0]

    def test_a_relock_writes_the_total_from_the_new_counts(self):
        m = _load()
        text = self._text([("a/one", 1), ("b/two", 1)])
        block = self._block(m.relock_text(text, {"a/one": 1200, "b/two": 34}))
        assert "1,234 entries in 2 repos" in block
        assert "typed by hand" not in block

    def test_a_refresh_writes_it_too(self):
        # --refresh passes new SHAs; the block must follow the counts all the
        # same, or the monthly job is the one caller that leaves it stale.
        m = _load()
        text = self._text([("a/one", 1)])
        out = m.relock_text(text, {"a/one": 5}, {"a/one": "b" * 40})
        assert "5 entries in 1 repos" in self._block(out)

    def test_the_two_largest_repos_are_named_with_their_share(self):
        m = _load()
        text = self._text([("b/small", 1), ("a/big", 2)])
        block = self._block(m.relock_text(text, {"b/small": 1, "a/big": 2}))
        assert "largest: a/big, 2 entries (66.7%)" in block
        assert "next:    b/small, 1 entries (33.3%)" in block
        assert block.index("largest:") < block.index("next:")

    def test_one_repo_has_no_runner_up(self):
        m = _load()
        block = self._block(m.relock_text(self._text([("a/one", 3)]),
                                          {"a/one": 3}))
        assert "largest: a/one, 3 entries (100.0%)" in block
        assert "next:" not in block

    def test_the_rows_above_the_scale_divider_are_totalled_on_their_own(self):
        # Those rows hold every golden target; CLAUDE.md and the Makefile quote
        # their total beside the scores measured over them alone.
        m = _load()
        text = self._text([("a/one", 30), ("b/two", 10), ("c/three", 60)],
                          divider_after=1)
        counts = {"a/one": 30, "b/two": 10, "c/three": 60}
        block = self._block(m.relock_text(text, counts))
        assert "100 entries in 3 repos" in block
        assert "40 entries in the 2 repos above the scale divider" in block

    def test_without_a_divider_there_is_no_target_line(self):
        m = _load()
        block = self._block(m.relock_text(self._text([("a/one", 7)]),
                                          {"a/one": 7}))
        assert "7 entries in 1 repos" in block
        assert "above the scale divider" not in block

    def test_a_list_without_the_block_does_not_grow_one(self):
        # taps-scale.txt goes through relock_text too, but is generated by
        # build_scale_corpus.py; adding a block there would make its --check
        # fail the month after every refresh.
        m = _load()
        text = "# header\nowner/repo %s 1\n" % ("a" * 40)
        out = m.relock_text(text, {"owner/repo": 9})
        assert out == "# header\nowner/repo %s     9\n" % ("a" * 40)

    def test_the_shipped_list_carries_the_block(self):
        # With it, test_relocking_the_shipped_list_with_its_own_counts_is_a_no_op
        # is also the check that the block matches the rows.
        text = _TAPS.read_text(encoding="utf-8")
        assert text.count(self._START) == 1 and text.count(self._END) == 1


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


@functools.lru_cache(maxsize=1)
def _eval_retrieval():
    spec = importlib.util.spec_from_file_location("eval_retrieval", _EVAL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A shell word that ends the command rather than passing it an argument: a
# pipe, a list operator or a redirection. The refresh workflow scores through
# `2>&1 | tee ... || rc=$?`, and none of that is the gate's business.
_SHELL_CHROME = re.compile(r"^(\||&|;|\d*[<>])")


def _recipe(target: str) -> str:
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    return makefile.split("\n%s:" % target, 1)[1].split("\n\n", 1)[0]


def _step(workflow: str, name: str) -> str:
    """One workflow step, from its `- name:` up to the step after it."""
    body = workflow.split("- name: " + name, 1)[1]
    return re.split(r"\n\s*- (?:name|uses):", body, maxsplit=1)[0]


def _invocation(text: str) -> list[str]:
    """The argv `scripts/eval_retrieval.py` receives from one shell block.

    Continuations are joined first, because both the Makefile and the
    workflows wrap the call over three lines. Comment lines are skipped
    before anything is anchored: the refresh workflow names
    `scripts/eval_retrieval.py` in the comment above its `run:`. And exactly
    one call is required, so a block that grew a second one is an error
    rather than a coin toss over which of them is compared.
    """
    calls = _invocations(text)
    assert len(calls) == 1, (
        "expected one eval_retrieval.py call, found %d in:\n%s"
        % (len(calls), text))
    return calls[0]


def _invocations(text: str) -> list[list[str]]:
    """Every argv `scripts/eval_retrieval.py` receives from `text`, in order."""
    joined = re.sub(r"\\\r?\n", " ", text)
    calls = [line for line in joined.splitlines()
             if "eval_retrieval.py" in line
             and not line.lstrip().startswith("#")]
    out: list[list[str]] = []
    for call in calls:
        words = shlex.split(call)
        first = next(i for i, word in enumerate(words)
                     if word.endswith("eval_retrieval.py")) + 1
        argv: list[str] = []
        for word in words[first:]:
            if _SHELL_CHROME.match(word):
                break
            argv.append(word)
        out.append(argv)
    return out


def _meaning(argv: list[str]) -> dict:
    """What a run of the gate with `argv` measures and enforces.

    Parsed by the script's own parser, so every flag it accepts is compared
    — including one added after this test was written — and a flag it does
    not accept fails here instead of in CI. Floors become a mapping, since
    their order means nothing; `--golden` is resolved from the repo root,
    where every one of these invocations runs.
    """
    ev = _eval_retrieval()
    meaning = vars(ev.build_parser().parse_args(argv))
    meaning["floor"] = ev.parse_floors(meaning["floor"])
    meaning["golden"] = (_ROOT / meaning["golden"]).resolve()
    return meaning


class TestTheGateIsDefinedOnce:
    """`make check` claims to BE the required gate. For `eval` it was not.

    CI ran `--fail-under 0.85` and no other floor; the Makefile (and the gate
    table in CLAUDE.md) define four floors with recall at 0.78. So the required
    check was simultaneously tighter than documented on one metric — 0.863
    measured against 0.85 is a buffer of 1.15 queries out of 91 — and absent on
    the other three, which are the ones added to close the "finds it every time,
    never ranks it first" hole. A ranker could regress hit@1 to 0.000 and the
    required gate would pass.

    The first version of this guard compared the floor VALUES and nothing
    else, so it could not see the flags that decide what a floor is measured
    on. Measured: `-k 5` in ci.yml alone kept it at "2 passed" while the
    required gate went from exit 0 to exit 1 (recall@k 0.841 -> 0.742 against
    a 0.780 floor) and `make eval` stayed green; dropping `--build`, adding
    `--golden` or changing `--regression-eps` slipped past it the same way. It
    now compares the whole invocation, parsed.
    """

    def _gate(self) -> dict:
        return _meaning(_invocation(_recipe("eval")))

    @pytest.mark.skipif(not (_ROOT / "Makefile").exists(),
                        reason="repo-root Makefile not reachable")
    def test_ci_runs_the_make_eval_invocation_flag_for_flag(self):
        ci = _CI.read_text(encoding="utf-8")
        step = _step(ci, "retrieval quality gate")
        assert _meaning(_invocation(step)) == self._gate()

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_corpus_refresh_scores_with_the_same_invocation(self):
        """Otherwise its PASS/FAIL banner is about a different gate.

        The refresh job runs the eval non-blocking and puts the verdict at the
        top of the PR body, which is the whole point of the job — a reviewer
        decides from that banner whether the new corpus is acceptable. The
        step differs from `make eval` only around the call — `set -o
        pipefail`, `tee`, the exit code kept for the next step — so its argv
        must match exactly.
        """
        wf = _REFRESH.read_text(encoding="utf-8")
        step = _step(wf, "score the refreshed corpus")
        assert _meaning(_invocation(step)) == self._gate()

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_refresh_rebaselines_what_the_gate_measures(self):
        """The re-baseline call differs on purpose, but not in what it measures.

        It saves rather than judges, so it takes no floors, does not rebuild
        the index the scoring step just built, and never runs the regression
        check its `--regression-eps` would tune. But the baseline it writes is
        what every later `make eval` compares to, and it records the `k` and
        the query set it was taken at: written at another cutoff, or over
        another golden set or engine list, it describes a different
        measurement from the one it is compared against.
        """
        wf = _REFRESH.read_text(encoding="utf-8")
        rebase = _meaning(_invocation(
            _step(wf, "re-baseline against the refreshed corpus")))
        gate = self._gate()
        assert rebase["save_baseline"] and not gate["save_baseline"]
        for flag in ("k", "engines"):
            assert rebase[flag] == gate[flag], flag
        # Which query sets it covers is TestTheRefreshRebaselinesEverySet's.
        assert gate["golden"] in _rebaselined()

    @pytest.mark.parametrize("old, new", [
        ("--build -k 10", "--build -k 5"),
        ("--build -k 10", "-k 10"),
        ("--regression-eps 1\n", "--regression-eps 0.02\n"),
        ("--build -k 10", "--build -k 10 --golden tests/eval/golden-natural.jsonl"),
        ("--build -k 10", "--build -k 10 --engines bm25"),
        ("--fail-under 0.78", "--fail-under 0.70"),
        ("--floor hit@1=0.40", "--floor hit@1=0.10"),
        (" --floor nDCG@k=0.58", ""),
    ], ids=["k", "build", "regression-eps", "golden", "engines", "fail-under",
            "floor-value", "floor-dropped"])
    def test_an_edit_to_the_ci_invocation_alone_breaks_parity(self, old, new):
        """The -k case is the card's: the old guard stayed green on it."""
        step = _step(_CI.read_text(encoding="utf-8"), "retrieval quality gate")
        assert old in step
        edited = step.replace(old, new)
        assert _meaning(_invocation(edited)) != self._gate()

    @pytest.mark.parametrize("old, new", [
        ("-k 10", "-k10"),
        ("--floor hit@1=0.40 --floor MRR=0.52",
         "--floor MRR=0.52 --floor hit@1=0.40"),
        ("--floor hit@1=0.40", "--floor hit@1=0.4"),
        ("--build -k 10", "--build -k 10 --golden tests/eval/golden.jsonl"),
        (" \\\n            --", " --"),
        ("--regression-eps 1\n", "--regression-eps 1 2>&1 | tee g.txt || rc=$?\n"),
    ], ids=["glued-k", "floor-order", "float-spelling", "explicit-default-golden",
            "one-line", "piped"])
    def test_a_respelling_of_the_same_gate_still_matches(self, old, new):
        """Parity is about what the gate checks, not how the line is typed."""
        step = _step(_CI.read_text(encoding="utf-8"), "retrieval quality gate")
        assert old in step
        edited = step.replace(old, new)
        assert _meaning(_invocation(edited)) == self._gate()


_EVAL_DIR = _ROOT / "tests" / "eval"
_NATURAL = (_EVAL_DIR / "golden-natural.jsonl").resolve()
_NATURAL_CI_STEP = "natural-language retrieval set (advisory)"
_NATURAL_REFRESH_STEP = "score the natural-language set on the refreshed corpus"
_REBASELINE_STEP = "re-baseline against the refreshed corpus"


def _committed_sets() -> set[Path]:
    """The query sets in the tree, derived here rather than by the script.

    Globbed independently, so a bug in `eval_retrieval.query_sets` cannot
    agree with itself; `test_the_script_derives_the_same_list` then pins the
    two together.
    """
    return {p.resolve() for p in _EVAL_DIR.glob("golden*.jsonl")}


def _rebaselined() -> set[Path]:
    """The query sets the refresh's re-baseline step writes a row for."""
    wf = _REFRESH.read_text(encoding="utf-8")
    meaning = _meaning(_invocation(_step(wf, _REBASELINE_STEP)))
    if meaning.get("all_sets"):
        return {p.resolve() for p in _eval_retrieval().query_sets()}
    return {meaning["golden"]}


def _scored(text: str) -> set[Path]:
    """The query sets every eval_retrieval.py call in `text` scores."""
    return {_meaning(argv)["golden"] for argv in _invocations(text)}


@pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
class TestTheRefreshRebaselinesEverySet:
    """card: refresh-strands-the-natural-set-baseline.

    The re-baseline step passed no `--golden`, and the default is the keyword
    set, so the monthly refresh moved one row of two. Its first run left the
    natural row describing the corpus it replaced, and on the new corpus the
    natural set reported "REGRESSION vs baseline: catalog.search recall@k:
    0.080 -> 0.060" for a ranker nobody had touched.
    """

    def test_every_committed_query_set_is_rebaselined(self):
        missed = sorted(p.name for p in _committed_sets() - _rebaselined())
        assert missed == [], "the refresh leaves these rows stale: %s" % missed

    def test_every_set_the_baseline_records_is_rebaselined(self):
        sets = json.loads((_EVAL_DIR / "baseline.json").read_text(
            encoding="utf-8"))["sets"]
        names = {key.rsplit("@", 1)[0] for key in sets}
        covered = {p.name for p in _rebaselined()}
        assert sorted(names - covered) == []

    def test_every_set_a_gate_scores_is_rebaselined(self):
        scored = set()
        for path in (_ROOT / "Makefile", _CI, _REFRESH):
            scored |= _scored(path.read_text(encoding="utf-8"))
        assert sorted(p.name for p in scored - _rebaselined()) == []

    def test_the_list_is_derived_not_named(self):
        # Naming the two sets in the step would strand the third the day it
        # is committed; `--all-sets` asks the directory instead.
        step = _step(_REFRESH.read_text(encoding="utf-8"), _REBASELINE_STEP)
        assert ".jsonl" not in step.split("run:", 1)[1]

    def test_the_script_derives_the_same_list(self):
        assert {p.resolve() for p in _eval_retrieval().query_sets()} == \
            _committed_sets()


#: How the natural-language floors are set: ~10% under the recorded BM25
#: row, rounded DOWN to two places (hit@1 0.160 -> 0.14, not 0.144).
_UNDER, _ROUNDING = 0.10, 0.01


def _natural_queries() -> int:
    """How many questions the natural set asks, counted as `load_golden` does."""
    lines = (line.strip() for line in
             _NATURAL.read_text(encoding="utf-8").splitlines())
    return sum(1 for line in lines if line and not line.startswith("#"))


def floors_out_of_band(floors: dict[str, float], row: dict[str, float],
                       n: int) -> list[str]:
    """Each floor a row more than one query from its calibration no longer fits.

    Every metric is a mean over `n` questions of a per-question score in
    [0, 1], so one question moves it by at most 1/n — at 50 questions, 0.02,
    more than the ~10% margin on hit@1 (0.016 at 0.160). The band therefore
    allows one query of movement either way and no more:

    - UP: the floor may be one query plus ~10% (and the rounding) under the
      row. It used to be ~20% with no query allowance, and a one-query
      improvement on hit@1 (8 -> 9 of 50, 0.160 -> 0.180) put the unchanged
      0.14 floor 22% under, failing a required test for a better ranker. Two
      queries of improvement is past the band for a floor set by the rule.
    - DOWN: the floor may equal the row. The gate breaches on `got < minimum`
      (`check_floors`), so a floor the row meets exactly still passes, and a
      one-query drop on hit@1 (8 -> 7 of 50) lands exactly there.
    """
    step, eps = 1 / n, 1e-9
    out = []
    for metric, minimum in sorted(floors.items()):
        got = row[metric]
        if minimum > got + eps:
            out.append("%s: floor %.2f is above the row's %.3f, so the gate "
                       "fails on the corpus it was set on" % (metric, minimum, got))
        elif minimum < (1 - _UNDER) * got - _ROUNDING - step - eps:
            out.append("%s: floor %.2f is more than one query plus ~10%% under "
                       "the row's %.3f, so it no longer measures anything"
                       % (metric, minimum, got))
    return out


def _folded_echo(block: str) -> str:
    """The text a run of `echo "..."` lines prints, as one line."""
    return " ".join(re.findall(r'^\s*echo "(.*)"\s*$', block, re.M))


class TestTheFloorBand:
    """The band itself, on synthetic rows: 50 questions, hit@1 floored 0.14."""

    FLOOR: ClassVar[dict[str, float]] = {"hit@1": 0.14}

    @pytest.mark.parametrize("hits", [7, 8, 9], ids=["down-one", "at", "up-one"])
    def test_one_query_either_way_is_inside(self, hits):
        # 9 of 50 is the reviewer's case: a one-query improvement that failed
        # the old 0.8x lower bound (0.14 < 0.144).
        assert floors_out_of_band(self.FLOOR, {"hit@1": hits / 50}, 50) == []

    @pytest.mark.parametrize("hits", [6, 10], ids=["down-two", "up-two"])
    def test_two_queries_either_way_are_outside(self, hits):
        out = floors_out_of_band(self.FLOOR, {"hit@1": hits / 50}, 50)
        assert len(out) == 1 and out[0].startswith("hit@1: floor 0.14 is ")

    def test_the_direction_is_named(self):
        (above,) = floors_out_of_band(self.FLOOR, {"hit@1": 6 / 50}, 50)
        (under,) = floors_out_of_band(self.FLOOR, {"hit@1": 10 / 50}, 50)
        assert "above the row" in above and "no longer measures" in under

    def test_a_floor_the_row_meets_exactly_passes_the_gate(self):
        # Why DOWN allows equality: the gate's own comparison.
        ev = _eval_retrieval()
        result = {"agg": {"overall": {"hit@1": 7 / 50}}}
        assert ev.check_floors(result, dict(self.FLOOR)) == []
        assert ev.check_floors(result, {"hit@1": 0.15}) != []

    def test_the_query_count_scales_the_allowance(self):
        # At 500 questions one query is 0.002, so 0.180 is nine queries up.
        assert floors_out_of_band(self.FLOOR, {"hit@1": 0.18}, 500) != []

    def test_every_floor_is_checked(self):
        floors = {"hit@1": 0.14, "MRR": 0.21}
        out = floors_out_of_band(floors, {"hit@1": 0.20, "MRR": 0.20}, 50)
        assert [line.split(":")[0] for line in out] == ["MRR", "hit@1"]

    @pytest.mark.parametrize("hits", range(5, 50))
    def test_a_floor_set_by_the_rule_allows_exactly_one_query_up(self, hits):
        # The band and the calibration rule agree for any row, not only the
        # one committed today: set a floor ~10% under, rounded down to two
        # places, and the row may rise one query but not two.
        n, row = 50, hits / 50
        floor = {"MRR": math.floor(round((1 - _UNDER) * row * 100, 6)) / 100}
        assert floors_out_of_band(floor, {"MRR": row}, n) == []
        assert floors_out_of_band(floor, {"MRR": row + 1 / n}, n) == []
        assert floors_out_of_band(floor, {"MRR": row + 2 / n}, n) != []

    def test_the_shipped_set_is_counted_by_its_rows(self):
        # Comments and blank lines are not questions; 137 lines hold 50.
        rows = [line for line in
                _NATURAL.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("{")]
        assert _natural_queries() == len(rows) > 0


class TestTheNaturalSetIsMeasured:
    """card: exemplar-graded-golden-set-runs-in-no-gate.

    golden-natural.jsonl is the one set graded by exemplar on every row, and
    no Makefile target or workflow passed `--golden` — so the only way its
    numbers were ever produced was a person typing the command.

    It runs ADVISORY (continue-on-error in CI, outside `make check`), and the
    reason is a count of queries. The keyword gate's recall floor sits five
    queries of 91 under its measurement; a natural-set hit@1 floor ~10% under
    its row is one query under it (7 of 50 against 8, at the pins the floors
    were set on) — one query of slack. The refresh's
    own header says corpus growth moves these numbers down, so a required
    gate that thin would redden every open pull request the month after a
    refresh. Advisory, it still prints every number and the regression line
    in every CI run.
    """

    def _gate(self) -> dict:
        return _meaning(_invocation(_recipe("eval-natural")))

    def test_ci_scores_the_natural_set(self):
        assert _NATURAL in _scored(_CI.read_text(encoding="utf-8"))

    def test_a_make_target_scores_the_natural_set(self):
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        assert _NATURAL in _scored(makefile)

    def test_the_target_scores_the_natural_set(self):
        assert self._gate()["golden"] == _NATURAL

    def test_ci_runs_the_make_invocation_flag_for_flag(self):
        step = _step(_CI.read_text(encoding="utf-8"), _NATURAL_CI_STEP)
        assert _meaning(_invocation(step)) == self._gate()

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_refresh_scores_it_with_the_same_invocation(self):
        wf = _REFRESH.read_text(encoding="utf-8")
        step = _step(wf, _NATURAL_REFRESH_STEP)
        assert _meaning(_invocation(step)) == self._gate()

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_refresh_scores_it_before_rebaselining(self):
        # After, it would compare the new corpus with itself and could never
        # report the movement the refresh pull request exists to show.
        wf = _REFRESH.read_text(encoding="utf-8")
        assert wf.index("- name: " + _NATURAL_REFRESH_STEP) < \
            wf.index("- name: " + _REBASELINE_STEP)

    def test_it_floors_all_four_metrics(self):
        gate = self._gate()
        floors = dict(gate["floor"])
        if gate["fail_under"] is not None:
            floors.setdefault("recall@k", gate["fail_under"])
        assert set(floors) == {"recall@k", "hit@1", "MRR", "nDCG@k"}

    def _floors(self) -> dict[str, float]:
        gate = self._gate()
        return dict(gate["floor"], **{"recall@k": gate["fail_under"]})

    def _row(self) -> dict[str, float]:
        row = _eval_retrieval().baseline_for(_NATURAL)
        assert row is not None
        return row["engines"]["BM25 full-content"]

    def test_the_floors_sit_under_the_recorded_baseline(self):
        # The row it is compared to is the one the refresh keeps current, so
        # a refresh that moves it more than one query from where the floors
        # were set fails here, in either direction, naming each floor.
        out = floors_out_of_band(self._floors(), self._row(),
                                 _natural_queries())
        assert out == [], (
            "the natural-language floors no longer fit the recorded BM25 row "
            "in tests/eval/baseline.json:\n  %s\nMove each one named to ~10%% "
            "under the new row, rounded down to two places, in the Makefile's "
            "eval-natural, ci.yml and eval-corpus-refresh.yml together."
            % "\n  ".join(out))

    @pytest.mark.skipif(not _REFRESH.exists(), reason="refresh workflow absent")
    def test_the_refresh_pull_request_names_the_floor_check(self):
        # The refresh is where the row moves, so its pull request is where a
        # person learns the floors move with it — and in both directions,
        # since a one-way note sends them looking only for a drop.
        body = _step(_REFRESH.read_text(encoding="utf-8"),
                     "assemble the pull request body")
        name = "test_the_floors_sit_under_the_recorded_baseline"
        assert name in body and callable(getattr(self, name, None))
        assert "in both directions" in _folded_echo(body)

    def test_it_is_advisory_in_ci_and_the_keyword_gate_is_not(self):
        ci = _CI.read_text(encoding="utf-8")
        assert "continue-on-error: true" in _step(ci, _NATURAL_CI_STEP)
        assert "continue-on-error" not in _step(ci, "retrieval quality gate")

    def test_it_is_not_part_of_make_check(self):
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        check = re.search(r"^check:(.*)$", makefile, re.M)
        assert check and "eval-natural" not in check.group(1).split()

    @pytest.mark.parametrize("old, new", [
        ("--build -k 10", "--build -k 5"),
        ("--build -k 10", "-k 10"),
        ("tests/eval/golden-natural.jsonl", "tests/eval/golden.jsonl"),
        ("--fail-under 0.32", "--fail-under 0.20"),
        ("--floor hit@1=0.14", "--floor hit@1=0.02"),
        (" --floor nDCG@k=0.23", ""),
    ], ids=["k", "build", "golden", "fail-under", "floor-value", "floor-dropped"])
    def test_an_edit_to_the_ci_invocation_alone_breaks_parity(self, old, new):
        step = _step(_CI.read_text(encoding="utf-8"), _NATURAL_CI_STEP)
        assert old in step
        assert _meaning(_invocation(step.replace(old, new))) != self._gate()


class TestReadingAnInvocation:
    @pytest.mark.parametrize("text", [
        "python scripts/eval_retrieval.py -k 3 --build",
        "python scripts/eval_retrieval.py -k 3 \\\n    --build",
        "# scripts/eval_retrieval.py\npython scripts/eval_retrieval.py -k 3 --build",
        "python scripts/eval_retrieval.py -k 3 --build 2>&1 | tee x",
        "python scripts/eval_retrieval.py -k 3 --build || rc=$?",
        "python scripts/eval_retrieval.py -k 3 --build && echo ok",
        "python scripts/eval_retrieval.py -k 3 --build ; echo ok",
        "python scripts/eval_retrieval.py -k 3 --build > out.txt",
        "python scripts/eval_retrieval.py -k 3 --build &",
    ], ids=["plain", "continued", "commented", "redirected-and-piped", "or",
            "and", "semicolon", "redirected", "background"])
    def test_the_argv_is_what_follows_the_script_up_to_the_shell(self, text):
        assert _invocation(text) == ["-k", "3", "--build"]

    def test_the_words_before_the_script_are_not_its_arguments(self):
        text = "BOOST_HOME=$(EVAL_HOME) $(PY) scripts/eval_retrieval.py --json"
        assert _invocation(text) == ["--json"]

    @pytest.mark.parametrize("text", [
        "echo nothing to see",
        "# python scripts/eval_retrieval.py -k 3",
        "python scripts/eval_retrieval.py -k 3\npython scripts/eval_retrieval.py",
    ], ids=["none", "only-a-comment", "two"])
    def test_anything_but_one_call_is_refused(self, text):
        with pytest.raises(AssertionError, match="expected one"):
            _invocation(text)

    def test_a_step_ends_where_the_next_one_begins(self):
        wf = ("      - name: first\n        run: a\n"
              "      - uses: some/action@v1\n"
              "      - name: second\n        run: b\n")
        assert _step(wf, "first") == "\n        run: a"
        assert _step(wf, "second") == "\n        run: b\n"

    def test_an_unknown_flag_fails_rather_than_being_ignored(self):
        with pytest.raises(SystemExit):
            _meaning(["--no-such-flag"])

    def test_floors_are_read_as_a_mapping(self):
        meaning = _meaning(["--floor", "MRR=0.5", "--floor", "hit@1=0.25"])
        assert meaning["floor"] == {"MRR": 0.5, "hit@1": 0.25}
        assert meaning["golden"].is_absolute()


class TestPinningAClone:
    def test_a_directory_that_is_not_a_clone_is_refused(self, tmp_path):
        # Without its own .git, `git -C` walks UP to the nearest enclosing
        # repository. Under `make eval` that is the boost checkout itself
        # (.eval-home sits inside it), and the forced checkout would act on
        # the developer's working tree.
        m = _load()
        outer, shas = _repo(tmp_path)
        inner = outer / "repos" / "owner__repo"
        inner.mkdir(parents=True)
        with pytest.raises(m.CorpusError) as exc:
            m.pin_clone(inner, shas[0])
        assert exc.value.kind == m.UNAVAILABLE
        assert "not a git clone" in exc.value.detail
        assert _git(outer, "rev-parse", "HEAD") == shas[-1], \
            "pin_clone moved the enclosing repository"

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

    def test_re_pinning_restores_a_deleted_tracked_file(self, tmp_path):
        """The pin names a tree, not just a commit HEAD happens to sit on.

        A plain `checkout --detach` onto the commit HEAD already names is a
        no-op for the working tree, so a SKILL.md deleted by hand stayed
        deleted: the next --ensure rescanned one entry short and exited DRIFT,
        which is the one remedy the eval gate's refusal points at.
        """
        m = _load()
        path, shas = _repo(tmp_path)
        m.pin_clone(path, shas[1])
        (path / "SKILL.md").unlink()
        m.pin_clone(path, shas[1])
        assert (path / "SKILL.md").is_file()
        assert (path / "SKILL.md").read_text(encoding="utf-8") == "# second\n"

    def test_has_commit_is_false_for_a_tree_not_a_commit(self, tmp_path):
        # `cat-file -e <sha>` alone passes for any object; the pin must reject a
        # tree or blob SHA rather than checking out something meaningless.
        m = _load()
        path, _shas = _repo(tmp_path)
        tree = _git(path, "rev-parse", "HEAD^{tree}")
        assert m.has_commit(path, tree) is False


def _skills_repo(tmp_path, name, skills=("alpha", "beta")):
    """A real git repo holding ``skills/<n>/SKILL.md`` — what `scan_dir` finds."""
    path = tmp_path / name
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for cfg in (("user.email", "t@example.test"), ("user.name", "T"),
                ("commit.gpgsign", "false")):
        _git(path, "config", *cfg)
    for skill in skills:
        md = path / "skills" / skill / "SKILL.md"
        md.parent.mkdir(parents=True)
        md.write_text("---\nname: %s\ndescription: %s from %s\n---\n\n"
                      "The %s body.\n" % (skill, skill, name, skill),
                      encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "skills")
    return path, _git(path, "rev-parse", "HEAD")


@pytest.fixture()
def pinned_corpus(tmp_path, sandbox):
    """Two local taps, configured and materialised by a real --ensure.

    Local paths rather than owner/repo so nothing reaches the network, but the
    clone, the config row, the pin and the rescan are all the real ones.
    Returns ``(module, taps_file, {tap name: (origin, sha)})``.
    """
    from boost_cli.core import registry
    m = _load()
    origins = {}
    lines = []
    for name in ("one-skills", "two-skills"):
        origin, sha = _skills_repo(tmp_path, name)
        tap = registry.add(str(origin))
        origins[tap.name] = (origin, sha)
        lines.append("%s %s 2" % (tap.name, sha))
    taps = tmp_path / "taps.txt"
    taps.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert m.main(["--ensure", "--taps", str(taps)]) == 0
    return m, taps, origins


class TestEnsureRepairsWhatTheGateRefuses:
    """The eval gate's refusal names `--ensure` as the fix, so it has to be one.

    The card's own state — `repos/` reclaimed, `config.json`, the catalog
    caches and the sentinel intact — reached `_materialise`, which found every
    tap still configured, skipped `registry.add`, and ran `git -C` in a
    directory that no longer existed. Every row then read "the pin in
    tests/eval/taps.txt is stale" and the run exited 75 as CORPUS UNAVAILABLE,
    blaming twenty third parties for a directory deleted by hand. The false
    green became a false red, and the remedy repaired nothing.
    """

    def test_a_configured_tap_whose_clone_is_gone_is_re_cloned(
            self, pinned_corpus, capsys):
        from boost_cli.core import registry, util
        m, taps, origins = pinned_corpus
        name = sorted(origins)[0]
        tap = registry.get(name)
        util.rmtree(tap.path)
        assert registry.get(name).name == name, "config.json must survive"
        assert m.main(["--ensure", "--taps", str(taps)]) == 0, \
            capsys.readouterr().out
        assert _git(tap.path, "rev-parse", "HEAD") == origins[name][1]
        assert (tap.path / "skills" / "alpha" / "SKILL.md").is_file()

    def test_a_whole_reclaimed_repos_tree_is_re_cloned(
            self, pinned_corpus, capsys):
        from boost_cli.core import paths, util
        m, taps, origins = pinned_corpus
        for child in paths.repos_dir().iterdir():
            util.rmtree(child)
        assert m.main(["--ensure", "--taps", str(taps)]) == 0, \
            capsys.readouterr().out
        assert sorted(c.name for c in paths.repos_dir().iterdir()) \
            == sorted(origins)

    def test_an_empty_directory_where_the_clone_was_is_re_cloned(
            self, pinned_corpus, capsys):
        # `is_cloned` is `is_dir()`, so an emptied clone directory read as a
        # clone: the update was skipped and git ran in a directory with no
        # repository of its own.
        from boost_cli.core import registry, util
        m, taps, origins = pinned_corpus
        name = sorted(origins)[0]
        tap = registry.get(name)
        util.rmtree(tap.path)
        tap.path.mkdir()
        assert m.main(["--ensure", "--taps", str(taps)]) == 0, \
            capsys.readouterr().out
        assert _git(tap.path, "rev-parse", "HEAD") == origins[name][1]

    def test_a_non_clone_directory_with_files_is_not_deleted(
            self, pinned_corpus, capsys):
        # Someone else's files are not a clone to be replaced: say so and
        # leave them, rather than delete them to make room.
        from boost_cli.core import registry, util
        m, taps, origins = pinned_corpus
        name = sorted(origins)[0]
        tap = registry.get(name)
        util.rmtree(tap.path)
        tap.path.mkdir()
        (tap.path / "notes.txt").write_text("mine\n", encoding="utf-8")
        assert m.main(["--ensure", "--taps", str(taps)]) != 0
        assert "not a git clone" in capsys.readouterr().out
        assert (tap.path / "notes.txt").read_text(encoding="utf-8") == "mine\n"

    def test_a_deleted_skill_md_is_restored_rather_than_drifted(
            self, pinned_corpus, capsys):
        from boost_cli.core import registry
        m, taps, origins = pinned_corpus
        md = registry.get(sorted(origins)[1]).path / "skills" / "beta" / "SKILL.md"
        md.unlink()
        assert m.main(["--ensure", "--taps", str(taps)]) == 0, \
            capsys.readouterr().out
        assert md.is_file()

    def test_a_clone_that_cannot_be_re_made_is_still_unavailability(
            self, pinned_corpus, capsys):
        """Exit 75 keeps its meaning: the tree is not obtainable here and now."""
        import shutil

        from boost_cli.core import registry, util
        m, taps, origins = pinned_corpus
        name = sorted(origins)[0]
        util.rmtree(registry.get(name).path)
        shutil.rmtree(origins[name][0])
        assert m.main(["--ensure", "--taps", str(taps)]) == m.EXIT_UNAVAILABLE
        out = capsys.readouterr().out
        assert "CORPUS UNAVAILABLE" in out and name in out


@pytest.mark.skipif(os.name == "nt" or not _ENSURE.exists(),
                    reason="POSIX shell wrapper")
class TestTheCardScenarioRepairsItself:
    """The reproduction from the review, through the real wrapper and --ensure.

    No stub interpreter: the stub the sentinel tests use creates
    `repos/owner__repo` itself, which is exactly how the broken re-tap passed.
    """

    def test_an_emptied_repos_tree_under_a_live_sentinel_is_re_cloned(
            self, pinned_corpus, tmp_path):
        from boost_cli.core import paths, util
        _m, taps, origins = pinned_corpus
        root = tmp_path / "root"
        (root / "scripts").mkdir(parents=True)
        (root / "tests" / "eval").mkdir(parents=True)
        for script in ("ensure_eval_corpus.sh", "eval_corpus.py"):
            (root / "scripts" / script).write_text(
                (_ROOT / "scripts" / script).read_text(encoding="utf-8"),
                encoding="utf-8")
        (root / "tests" / "eval" / "taps.txt").write_text(
            taps.read_text(encoding="utf-8"), encoding="utf-8")
        # The wrapper puts its own root on PYTHONPATH; point that at this tree.
        (root / "boost_cli").symlink_to(_ROOT / "boost_cli")
        env = dict(os.environ, PYTHON=sys.executable)
        env.pop("FORCE", None)
        wrapper = ["bash", str(root / "scripts" / "ensure_eval_corpus.sh")]
        first = subprocess.run(wrapper, capture_output=True, text=True, env=env)
        assert first.returncode == 0, first.stdout + first.stderr
        assert (paths.boost_home() / ".eval-corpus-ready").is_file()
        for child in paths.repos_dir().iterdir():
            util.rmtree(child)
        again = subprocess.run(wrapper, capture_output=True, text=True, env=env)
        assert again.returncode == 0, again.stdout + again.stderr
        assert "re-tapping" in again.stderr
        assert "stale" not in again.stdout
        assert sorted(c.name for c in paths.repos_dir().iterdir()) \
            == sorted(origins)


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
        # Python and records the second, so no corpus is materialised. It does
        # create the clone directory a real --ensure would, because the sentinel
        # is honoured only over a non-empty `repos/` — see
        # test_eval_corpus_bodies.TestTheSentinelDoesNotOutliveTheClones.
        home = tmp_path / "home"
        stub = tmp_path / "stub.py"
        stub.write_text(
            "#!%s\n"
            "import os, subprocess, sys\n"
            "a = sys.argv[1:]\n"
            "if a and a[0] == '-c':\n"
            "    sys.exit(subprocess.run([sys.executable] + a).returncode)\n"
            "open(%r, 'a').write('ensure\\n')\n"
            "os.makedirs(%r, exist_ok=True)\n"
            % (sys.executable, str(calls), str(home / "repos" / "owner__repo")),
            encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ, BOOST_HOME=str(home), PYTHON=str(stub))
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
