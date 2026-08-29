# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/build_scale_corpus.py — the Tier 1b scale corpus list.

WHY IT EXISTS. The required gate measures 10,152 entries; a real install carries
~71,655, and at that size all four floors fail (0.709 / 0.341 / 0.451 / 0.504
against 0.780 / 0.400 / 0.520 / 0.580). So every retrieval decision validated
against the small corpus is validated at a scale users leave behind.

WHAT THESE TESTS ARE ACTUALLY GUARDING. Two properties, and both are the kind
that fail silently:

  * The scale corpus must be the required corpus PLUS distractors. Every golden
    target lives in the required rows, and a scale list that dropped one would
    collapse recall for a reason that is not scale — measured, dropping a single
    target-bearing repo takes recall@10 from 0.852 to 0.676, which is
    indistinguishable from a retrieval regression.
  * The distractors must not be all one item kind. The curated set is 341 skill
    / 76 workflow / 26 rule registries, so largest-first would bury the rules,
    and the required list's own header records the cost: `boost tap --defaults`
    taps only skill repos and scores 0.000 on every rule and workflow query.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_scale_corpus.py"
_OUT = _ROOT / "tests" / "eval" / "taps-scale.txt"
_REQUIRED = _ROOT / "tests" / "eval" / "taps.txt"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("build_scale_corpus", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _reg(name, kind, est, list_only=False):
    return {"name": name, "type": kind, "est_items": est, "list_only": list_only}


def _rows(text):
    return [ln.split()[0] for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


class TestSelection:
    def test_types_are_drawn_round_robin_not_largest_first(self):
        # Straight largest-first would take all three skills before any rule.
        m = _load()
        pools = m.candidates(
            [_reg("s/1", "skill", 100), _reg("s/2", "skill", 90),
             _reg("s/3", "skill", 80), _reg("r/1", "rule", 10)], [])
        picked = [n for n, _e in m.select(pools, 200)]
        assert "r/1" in picked, "the rule pool was crowded out by the skill tail"

    def test_within_a_type_the_largest_comes_first(self):
        m = _load()
        pools = m.candidates(
            [_reg("s/small", "skill", 5), _reg("s/big", "skill", 500)], [])
        assert next(n for n, _e in m.select(pools, 500)) == "s/big"

    def test_selection_stops_at_the_target(self):
        m = _load()
        pools = m.candidates([_reg("s/%d" % i, "skill", 100) for i in range(50)], [])
        picked = m.select(pools, 250)
        assert sum(e for _n, e in picked) >= 250
        assert len(picked) == 3, "overshot the target by more than one row"

    def test_an_exhausted_pool_terminates_rather_than_spinning(self):
        # A target larger than everything available must not loop forever.
        m = _load()
        pools = m.candidates([_reg("s/1", "skill", 1)], [])
        assert m.select(pools, 10_000) == [("s/1", 1)]

    def test_zero_item_registries_cannot_cause_an_infinite_loop(self):
        # They add nothing to the running total, so a naive loop never advances.
        m = _load()
        pools = m.candidates([_reg("s/%d" % i, "skill", 0) for i in range(5)], [])
        assert len(m.select(pools, 100)) == 5

    def test_list_only_registries_are_dropped(self):
        # An awesome-list index is a page of links, not a tree to scan.
        m = _load()
        pools = m.candidates([_reg("a/list", "skill", 900, list_only=True),
                              _reg("a/real", "skill", 10)], [])
        assert [n for n, _e in m.select(pools, 10)] == ["a/real"]

    def test_repos_already_in_the_required_corpus_are_not_repeated(self):
        m = _load()
        pools = m.candidates([_reg("dup/repo", "skill", 100)], ["dup/repo"])
        assert m.select(pools, 100) == []

    def test_the_output_is_deterministic(self):
        # Two runs over the same committed data must agree, or --check is noise.
        m = _load()
        assert m.build(5_000) == m.build(5_000)


class TestTheShippedList:
    @pytest.mark.skipif(not _OUT.exists(), reason="scale list not generated")
    def test_it_is_regenerated(self):
        m = _load()
        assert _OUT.read_text(encoding="utf-8") == m.build(m.DEFAULT_TARGET), (
            "tests/eval/taps-scale.txt is stale — regenerate with "
            "`python3 scripts/build_scale_corpus.py`")

    @pytest.mark.skipif(not (_OUT.exists() and _REQUIRED.exists()),
                        reason="corpus lists not reachable")
    def test_every_required_repo_is_present(self):
        """The property the whole tier rests on.

        Every golden target lives in the required rows. A scale corpus missing
        one would score a collapse that looks exactly like a retrieval
        regression, and the tier would be measuring the wrong thing while
        reporting confidently.
        """
        required = set(_rows(_REQUIRED.read_text(encoding="utf-8")))
        scale = set(_rows(_OUT.read_text(encoding="utf-8")))
        assert required <= scale, "missing from the scale corpus: %s" % sorted(
            required - scale)

    @pytest.mark.skipif(not (_OUT.exists() and _REQUIRED.exists()),
                        reason="corpus lists not reachable")
    def test_the_required_rows_keep_their_pins_and_counts(self):
        # Copied verbatim, so the two tiers start from the same trees.
        required = [ln.rstrip() for ln in
                    _REQUIRED.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")]
        scale_text = _OUT.read_text(encoding="utf-8")
        for row in required:
            assert row in scale_text, row

    @pytest.mark.skipif(not _OUT.exists(), reason="scale list not generated")
    def test_it_is_meaningfully_larger_than_the_required_corpus(self):
        required = _rows(_REQUIRED.read_text(encoding="utf-8"))
        scale = _rows(_OUT.read_text(encoding="utf-8"))
        assert len(scale) > 5 * len(required)

    @pytest.mark.skipif(not _OUT.exists(), reason="scale list not generated")
    def test_no_repository_appears_twice(self):
        rows = _rows(_OUT.read_text(encoding="utf-8"))
        assert len(rows) == len(set(rows))

    @pytest.mark.skipif(
        not (_OUT.exists() and (_ROOT / "boost_cli/data/registries.json").exists()),
        reason="registries not reachable")
    def test_all_three_item_kinds_are_represented_among_the_distractors(self):
        registries = {r["name"]: r for r in json.loads(
            (_ROOT / "boost_cli/data/registries.json").read_text(
                encoding="utf-8"))["registries"]}
        required = set(_rows(_REQUIRED.read_text(encoding="utf-8")))
        kinds = {registries[r]["type"] for r in _rows(
            _OUT.read_text(encoding="utf-8")) if r not in required
            and r in registries}
        assert kinds == {"skill", "rule", "workflow"}, (
            "distractors cover only %s — a corpus of one kind is not an install"
            % sorted(kinds))

    @pytest.mark.skipif(not _OUT.exists(), reason="scale list not generated")
    def test_any_pin_present_is_well_formed(self):
        """Distractors ship bare and the scheduled `--refresh` pins them.

        So this must NOT assert they are unpinned — that stops being true the
        first time the job runs, and a test that fails on correct behaviour is
        a test someone deletes. What is durable is that a row is either a bare
        name or a fully measured `repo sha count`: a half-written row would
        parse as a bad pin on the next run, when the corpus that produced it is
        already gone.
        """
        for ln in _OUT.read_text(encoding="utf-8").splitlines():
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            parts = ln.split()
            assert len(parts) in (1, 3), "half-written row: %s" % ln
            if len(parts) == 3:
                assert re.fullmatch(r"[0-9a-f]{40}", parts[1]), ln
                assert parts[2].isdigit(), ln


class TestPinsSurviveRegeneration:
    """The generator and `eval_corpus.py --refresh` must not fight each other.

    The scheduled job pins every distractor and writes back the entry count it
    actually scanned. If regenerating threw those away, the next `--check`
    would call the file stale, someone would regenerate, and the measured pins
    would be lost — every month, forever. So `--check` verifies the SELECTION
    and leaves the pins to the job that measured them.
    """

    def test_a_committed_row_is_carried_forward(self):
        m = _load()
        assert m.existing_pins("# c\n\na/b %s 12\n" % ("a" * 40)) == {
            "a/b": "a/b %s 12" % ("a" * 40)}

    def test_comments_and_blanks_are_ignored(self):
        m = _load()
        assert m.existing_pins("# only a comment\n\n   \n") == {}

    def test_render_reuses_the_committed_row(self):
        m = _load()
        pinned = {"s/one": "s/one %s 42" % ("b" * 40)}
        text = m.render([], [("s/one", 10)], 10, pinned)
        assert "s/one %s 42" % ("b" * 40) in text

    def test_render_falls_back_to_a_bare_name(self):
        m = _load()
        assert "\ns/one\n" in m.render([], [("s/one", 10)], 10, {})

    def test_regenerating_after_a_refresh_is_a_no_op(self):
        """The end-to-end property, exercised rather than argued.

        Simulates the scheduled job pinning one distractor, then asserts the
        generator reproduces the file byte for byte — which is what keeps
        `--check` green the month after a refresh.
        """
        m = _load()
        required = ["req/repo %s 5" % ("c" * 40)]
        picked = [("s/one", 10), ("s/two", 20)]
        first = m.render(required, picked, 30, {})
        refreshed = first.replace("\ns/one\n", "\ns/one %s 99\n" % ("d" * 40))
        again = m.render(required, picked, 30, m.existing_pins(refreshed))
        assert again == refreshed


class TestTheScheduledJobCannotOpenAnUnmergeablePR:
    """`--check` must run AFTER the refresh, not only before it.

    Running it first proves the committed file is fresh; it says nothing about
    what the refresh then wrote. For months the job checked, refreshed, and
    opened a PR that the very same check would have rejected — because
    `--refresh` re-pinned and re-columned the required block, which the
    generator copies verbatim from `taps.txt`. The PR was unmergeable by
    construction and the diff read as ordinary pin movement.
    """

    _WORKFLOW = _ROOT / ".github" / "workflows" / "eval-scale.yml"

    @pytest.mark.skipif(not _WORKFLOW.exists(), reason="workflow not reachable")
    def test_the_check_runs_after_the_refresh(self):
        text = self._WORKFLOW.read_text(encoding="utf-8")
        check = "build_scale_corpus.py --check"
        refresh = "eval_corpus.py --refresh"
        assert text.count(check) >= 2, (
            "only one --check: a refresh that breaks the selection would still "
            "open a PR")
        assert text.index(refresh) < text.rindex(check), (
            "the last --check must follow the refresh")

    @pytest.mark.skipif(not _WORKFLOW.exists(), reason="workflow not reachable")
    def test_the_check_is_not_allowed_to_fail_quietly(self):
        # `score it` is continue-on-error by design; the selection check is not.
        text = self._WORKFLOW.read_text(encoding="utf-8")
        tail = text[text.rindex("build_scale_corpus.py --check"):]
        head = text[:text.rindex("build_scale_corpus.py --check")]
        step = head[head.rindex("      - name:"):] + tail.split("      - name:")[0]
        assert "continue-on-error" not in step
