# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/page_budget.py — bounding how large the docs pages get.

WHY THIS FILE EXISTS. `docs/roadmap.html` scored 0.810, 0.840 and 0.850 across
the three runs of one Lighthouse job against a 0.85 floor, and passed because
`median-run` selected the 0.850. Two of its three runs were under the floor, on
`main`, and nothing noticed — `lighthouse` is not a required check, and no local
gate models render cost at all.

These tests pin the guard and, just as importantly, pin what it does NOT claim.
It is not a Lighthouse predictor: cutting laid-out body text 33% moved that score
by 0.00, and trimming 3,066 characters of prose also moved it by 0.00. It is a
growth budget for a board whose own card observes that it "only grows".
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "page_budget.py"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("page_budget", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMeasuring:
    def test_elements_are_counted_once_each(self):
        m = _load()
        _b, elements, _d = m.measure("<div><p>x</p><p>y</p></div>")
        assert elements == 3

    def test_depth_is_the_deepest_nesting(self):
        m = _load()
        _b, _e, depth = m.measure("<a><b><c></c></b></a><d></d>")
        assert depth == 3

    def test_a_void_element_does_not_nest(self):
        # `<br>` and `<img>` never close, so counting them as open would make
        # depth grow without bound down a long page and turn the alarm into
        # noise — which is how a structural check stops being read.
        m = _load()
        _b, elements, depth = m.measure("<div><br><img src=x><br></div>")
        assert elements == 4
        assert depth == 1

    def test_a_self_closing_tag_counts_but_does_not_nest(self):
        m = _load()
        _b, elements, depth = m.measure("<div><span/></div>")
        assert elements == 2
        assert depth == 1

    def test_an_unbalanced_close_cannot_drive_depth_negative(self):
        # Real pages are generated and balanced, but a stray `</div>` must not
        # make every later element look one level shallower than it is.
        m = _load()
        _b, _e, depth = m.measure("</div><a><b></b></a>")
        assert depth == 2

    def test_bytes_are_utf8_not_characters(self):
        # The board is full of em-dashes and arrows; counting characters would
        # under-report what actually crosses the wire.
        m = _load()
        nbytes, _e, _d = m.measure("<p>—</p>")
        assert nbytes == len("<p>—</p>".encode()) > len("<p>—</p>")


class TestTheCeilings:
    def test_a_page_within_budget_reports_nothing(self):
        m = _load()
        assert m.check_page("tiny.html", "<div><p>hello</p></div>") == []

    def test_too_many_elements_is_reported_with_both_numbers(self):
        m = _load()
        problems = m.check_page("tiny.html", "<p></p>" * 3000)
        assert len(problems) == 1
        assert "3000 elements" in problems[0] and "2000" in problems[0]

    def test_too_many_bytes_is_reported(self):
        m = _load()
        problems = m.check_page("tiny.html", "<p>%s</p>" % ("x" * 200_000))
        assert any("kB of markup" in p for p in problems)

    def test_a_page_with_its_own_row_gets_its_own_ceiling(self):
        m = _load()
        # 3,000 elements is over the default and under roadmap.html's.
        assert m.check_page("tiny.html", "<p></p>" * 3000)
        assert m.check_page("roadmap.html", "<p></p>" * 3000) == []

    def test_an_unknown_page_falls_back_to_the_default(self):
        m = _load()
        assert m.budget_for("brand-new.html") is m.BUDGETS["*"]

    def test_every_message_says_why_the_ceiling_is_what_it_is(self):
        # A budget failure that does not explain itself gets raised reflexively,
        # which is worse than no check at all.
        m = _load()
        for problem in m.check_page("tiny.html", "<p></p>" * 3000):
            assert "(" in problem and ")" in problem


class TestTheShippedPages:
    """The ratchet, and the guard against ceilings that mean nothing."""

    @pytest.mark.skipif(not (_ROOT / "docs").exists(), reason="docs/ absent")
    def test_every_shipped_page_is_within_budget(self):
        m = _load()
        problems = []
        for path in sorted((_ROOT / "docs").glob("*.html")):
            problems.extend(
                m.check_page(path.name, path.read_text(encoding="utf-8")))
        assert problems == [], "\n".join(problems)

    @pytest.mark.skipif(not (_ROOT / "docs" / "roadmap.html").exists(),
                        reason="board absent")
    def test_the_board_is_the_page_this_exists_for(self):
        # If roadmap.html ever stops being the largest page by a wide margin,
        # the reasoning in this script's header is about a page that no longer
        # exists and should be re-derived rather than trusted.
        m = _load()
        sizes = {p.name: m.measure(p.read_text(encoding="utf-8"))[1]
                 for p in (_ROOT / "docs").glob("*.html")}
        board = sizes.pop("roadmap.html")
        assert board > 2 * max(sizes.values())

    @pytest.mark.skipif(not (_ROOT / "docs" / "roadmap.html").exists(),
                        reason="board absent")
    def test_the_board_still_has_headroom_to_grow(self):
        """A ceiling the next shipped card trips is a ceiling nobody respects.

        The board grows one card at a time and this budget is meant to catch a
        step change, so it must sit well clear of today's measurement — if it
        creeps under ~25% headroom, raise it deliberately rather than letting a
        routine card turn the required lint job red.
        """
        m = _load()
        _b, elements, _d = m.measure(
            (_ROOT / "docs" / "roadmap.html").read_text(encoding="utf-8"))
        ceiling = m.BUDGETS["roadmap.html"].elements
        assert elements < ceiling * 0.8, (
            "roadmap.html is at %d of %d elements — raise the ceiling in "
            "BUDGETS deliberately" % (elements, ceiling))

    @pytest.mark.skipif(not (_ROOT / "docs" / "roadmap.html").exists(),
                        reason="board absent")
    def test_the_board_has_byte_headroom_too(self):
        """Bytes had the ceiling but not the warning — the same hole, one over.

        The element ceiling gets an early warning at 80% so the raise is a
        decision; `kbytes` had none, so it would have gone from green straight
        to a red required job with no step in between. When this was written the
        board sat at 565,883 B — 78.6% of the then-720 kB ceiling, 10,117 B
        short of it, which is two to six more cards at the 1.8-5.5 kB the four
        then queued each added.
        """
        m = _load()
        nbytes, _e, _d = m.measure(
            (_ROOT / "docs" / "roadmap.html").read_text(encoding="utf-8"))
        ceiling = m.BUDGETS["roadmap.html"].kbytes * 1000
        assert nbytes < ceiling * 0.8, (
            "roadmap.html is at %d kB of %d kB — raise the ceiling in BUDGETS "
            "deliberately" % (nbytes // 1000, ceiling // 1000))
