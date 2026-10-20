# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core/browse.py — the logic behind `boost browse`.

The TUI's drawing lives in the command layer, but everything that can be
*wrong* lives here: what a query matches, where the panes sit, which pane the
arrows move to, and what the detail panel says. That split is what makes the
browser mutation-testable — curses cannot be asserted on, and a layout integer
can.

The bug that started this: space was bound to multi-select and the printable
range began at 33, so a space could never reach the query. Two words could not
be searched for at once. Space now types, tokenizes the query, and every token
must match — and Tab took over selection.
"""
from __future__ import annotations

import dataclasses
import typing

import pytest

from boost_cli.core import browse


def _e(name, description="", tap="o/r", kind="skill", version="1.0.0", **kw):
    d = {"name": name, "description": description, "tap": tap, "kind": kind,
         "version": version, "curated": False, "rel_dir": name,
         "skill_md": "%s/SKILL.md" % name, "meta": {}}
    d.update(kw)
    return d


def _dl(*a, **kw):
    """``detail_lines`` flattened to one ``(role, text)`` per line — what a
    line says, for the assertions that only care about the words."""
    return [(browse.line_role(ln), browse.line_text(ln))
            for ln in browse.detail_lines(*a, **kw)]


CORPUS = [
    _e("code-review", "Review a pull request for defects", tap="acme/quality"),
    _e("commit-messages", "Write conventional commit messages", tap="acme/git"),
    _e("tdd-workflow", "Test-driven development loop", tap="beta/testing"),
    _e("rag-engineer", "Retrieval augmented generation", tap="beta/ai",
       kind="rule"),
]


class TestQueryTokenizing:
    """A space is a token separator, which is why it has to reach the query."""

    def test_a_space_separates_two_terms(self):
        assert browse.tokens("code review") == ["code", "review"]

    def test_runs_of_whitespace_collapse(self):
        assert browse.tokens("  code   review  ") == ["code", "review"]

    def test_an_empty_query_has_no_tokens(self):
        assert browse.tokens("") == []
        assert browse.tokens("   ") == []

    def test_tokens_are_lowercased_for_matching(self):
        assert browse.tokens("Code REVIEW") == ["code", "review"]


class TestMatching:
    def test_every_token_must_match(self):
        """`code review` must not behave like `code` alone."""
        got = [e["name"] for e in browse.matches(CORPUS, "code review", "all")]
        assert got == ["code-review"]

    def test_tokens_may_match_out_of_order(self):
        assert [e["name"] for e in browse.matches(CORPUS, "review code", "all")] \
            == ["code-review"]

    def test_an_empty_query_matches_everything(self):
        assert len(browse.matches(CORPUS, "", "all")) == len(CORPUS)

    def test_a_token_matching_nothing_empties_the_result(self):
        assert browse.matches(CORPUS, "code zzzz", "all") == []

    def test_matching_is_still_fuzzy_within_a_token(self):
        assert [e["name"] for e in browse.matches(CORPUS, "cdrv", "name")] \
            == ["code-review"]

    def test_two_words_that_span_name_and_description(self):
        """The whole point of scope `all`: one token from each field."""
        got = [e["name"] for e in browse.matches(CORPUS, "tdd driven", "all")]
        assert got == ["tdd-workflow"]


class TestSubsequence:
    """`subseq` was rewritten from an iterator to `str.find` for speed (4.5x).
    These pin the semantics so the optimisation cannot change the answers."""

    @pytest.mark.parametrize("needle,hay,want", [
        ("", "anything", True),
        ("abc", "abc", True),
        ("abc", "aXbXc", True),
        ("abc", "acb", False),
        ("abc", "ab", False),
        ("aa", "a", False),
        ("aa", "aa", True),
        ("aa", "aXa", True),
        ("z", "abc", False),
        ("abc", "", False),
    ])
    def test_cases(self, needle, hay, want):
        assert browse.subseq(needle, hay) is want

    def test_it_agrees_with_the_reference_implementation(self):
        """Brute-force cross-check against the obvious-but-slow version."""
        import itertools

        def reference(needle, hay):
            it = iter(hay)
            return all(ch in it for ch in needle)

        alphabet = "ab"
        for n in range(4):
            for needle in itertools.product(alphabet, repeat=n):
                for m in range(5):
                    for hay in itertools.product(alphabet, repeat=m):
                        ns, hs = "".join(needle), "".join(hay)
                        assert browse.subseq(ns, hs) == reference(ns, hs), \
                            (ns, hs)


class TestIndexedFiltering:
    def test_indexed_and_direct_filtering_agree(self):
        for scope in browse.SCOPES:
            idx = browse.index_entries(CORPUS, scope)
            for q in ("", "co", "code review", "zzz", "beta"):
                assert browse.matches_indexed(idx, q, scope) == \
                    browse.matches(CORPUS, q, scope), (scope, q)


class TestScopes:
    def test_name_scope_ignores_the_description(self):
        assert browse.matches(CORPUS, "defects", "name") == []
        assert [e["name"] for e in browse.matches(CORPUS, "defects",
                                                  "description")] \
            == ["code-review"]

    def test_tap_scope_searches_the_tap(self):
        got = [e["name"] for e in browse.matches(CORPUS, "beta", "tap")]
        assert got == ["tdd-workflow", "rag-engineer"]

    def test_all_scope_covers_name_description_and_tap(self):
        for q in ("defects", "code-review", "quality"):
            assert browse.matches(CORPUS, q, "all"), q

    def test_every_scope_is_cyclable_and_returns_to_the_start(self):
        seen, scope = [], browse.SCOPES[0]
        for _ in range(len(browse.SCOPES)):
            seen.append(scope)
            scope = browse.next_scope(scope)
        assert seen == list(browse.SCOPES)
        assert scope == browse.SCOPES[0], "cycling must wrap"

    def test_cycling_backwards_wraps_too(self):
        assert browse.next_scope(browse.SCOPES[0], -1) == browse.SCOPES[-1]

    def test_an_unknown_scope_falls_back_rather_than_raising(self):
        """A keystroke must never take down the browser."""
        assert browse.matches(CORPUS, "code", "nonsense-scope")

    @pytest.mark.parametrize("scope", browse.SCOPES)
    def test_every_scope_has_a_label(self, scope):
        assert browse.scope_label(scope)


class TestDedupe:
    """Near-identical rows collapse; homonyms must not.

    A registry that renders one skill into `.claude/`, `.cursor/`, `.gemini/`
    and a plugin root ships it four times, and the browser listed all four.
    Measured on a real 60,047-entry catalogue: 22,379 rows (37%) are exact
    duplicates of another row.

    The dangerous half is the opposite case. `code-reviewer` appears 75 times
    with **42 distinct descriptions**, and `rule` 47 times with 47 distinct —
    those are different skills that share a name, and collapsing them would
    hide real results. So identity is the description, never the name.
    """

    def test_identical_rows_collapse_to_one(self):
        rows = [_e("a", "same text"), _e("a", "same text"), _e("a", "same text")]
        out = browse.dedupe(rows)
        assert len(out) == 1
        assert out[0][1] == 3, "the survivor must carry the copy count"

    def test_the_first_occurrence_is_the_survivor(self):
        rows = [_e("a", "same", tap="first/one"), _e("a", "same", tap="second/two")]
        assert browse.dedupe(rows)[0][0]["tap"] == "first/one"

    def test_a_shared_name_with_different_descriptions_never_collapses(self):
        """`rule` x47 with 47 distinct descriptions — all real, all different."""
        rows = [_e("rule", "format imports"), _e("rule", "no bare except"),
                _e("rule", "prefer pathlib")]
        assert len(browse.dedupe(rows)) == 3

    @pytest.mark.parametrize("suffix,ratio", [(" v2", 0.992), (".", 0.997),
                                              (" (updated)", 0.973)])
    def test_near_identical_descriptions_collapse_at_the_threshold(self, suffix,
                                                                   ratio):
        """Real ratios, computed rather than guessed: a 25-character clause on
        a 177-character description is only 0.934 and must NOT collapse."""
        long = "Security audit, hardening, threat modeling and code review " * 3
        rows = [_e("x", long), _e("x", long + suffix)]
        assert len(browse.dedupe(rows, threshold=0.95)) == 1

    def test_a_visible_edit_stays_two_rows(self):
        long = "Security audit, hardening, threat modeling and code review " * 3
        rows = [_e("x", long), _e("x", long + " plus one trailing clause")]
        assert len(browse.dedupe(rows, threshold=0.95)) == 2, \
            "0.934 is below the threshold — collapsing it would hide an edit"

    def test_a_lower_similarity_survives_as_its_own_row(self):
        rows = [_e("x", "Security audit and hardening"),
                _e("x", "Completely different subject matter entirely here")]
        assert len(browse.dedupe(rows, threshold=0.95)) == 2

    def test_the_threshold_is_honoured(self):
        a, b = "abcdefghij" * 6, "abcdefghij" * 5 + "abcdefghiZ" * 1
        assert len(browse.dedupe([_e("x", a), _e("x", b)], threshold=0.99)) == 2
        assert len(browse.dedupe([_e("x", a), _e("x", b)], threshold=0.90)) == 1

    def test_order_is_preserved(self):
        rows = [_e("b", "one"), _e("a", "two"), _e("c", "three")]
        assert [e["name"] for e, _n in browse.dedupe(rows)] == ["b", "a", "c"]

    def test_singletons_report_a_count_of_one(self):
        assert browse.dedupe([_e("solo", "unique")])[0][1] == 1

    def test_an_empty_catalogue_is_fine(self):
        assert browse.dedupe([]) == []

    def test_entries_with_no_description_do_not_all_merge(self):
        """Empty descriptions are identical strings; the name must still
        separate them, or every undescribed skill becomes one row."""
        rows = [_e("alpha", ""), _e("beta", ""), _e("gamma", "")]
        assert len(browse.dedupe(rows)) == 3

    def test_collapsed_total_is_recoverable(self):
        rows = [_e("a", "x"), _e("a", "x"), _e("b", "y")]
        out = browse.dedupe(rows)
        assert sum(n for _e, n in out) == len(rows), \
            "the counts must account for every input row"


class TestPlainFooter:
    """core/browse.py's ``plain_footer`` — the non-interactive `boost browse`
    fallback's footer line. Cluster ``browse-plain-dump``: the old fallback's
    footer said "10152 skills" over a catalog that was skills+rules+workflows,
    so a reader had no way to tell what was actually in the table above it.
    """

    def test_empty_catalogue(self):
        assert browse.plain_footer([]) == "0 items: none"

    def test_singular_item_and_kind(self):
        assert browse.plain_footer([_e("a", kind="skill")]) == "1 item: 1 skill"

    def test_breaks_down_by_kind_in_fixed_order(self):
        rows = [_e("a", kind="workflow"), _e("b", kind="skill"),
                _e("c", kind="rule"), _e("d", kind="skill")]
        assert browse.plain_footer(rows) == \
            "4 items: 2 skills · 1 rule · 1 workflow"

    def test_a_kind_absent_from_the_input_is_not_listed(self):
        rows = [_e("a", kind="skill"), _e("b", kind="skill")]
        assert browse.plain_footer(rows) == "2 items: 2 skills"

    def test_missing_kind_counts_as_skill(self):
        rows = [_e("a"), _e("b")]
        del rows[0]["kind"]
        assert browse.plain_footer(rows) == "2 items: 2 skills"

    def test_an_unrecognised_kind_still_counts_toward_the_total(self):
        rows = [_e("a", kind="skill"), _e("b", kind="plugin")]
        assert browse.plain_footer(rows) == "2 items: 1 skill · 1 other"

    def test_total_always_equals_the_row_count(self):
        rows = [_e("a", kind="skill"), _e("b", kind="rule"),
                _e("c", kind="workflow"), _e("d", kind="mystery")]
        footer = browse.plain_footer(rows)
        assert footer.startswith("4 items:")


class TestFocusMovement:
    """Arrows cross pane boundaries — item 2 of the request."""

    def test_up_from_the_first_row_lands_on_the_toggle_row(self):
        assert browse.move_focus("list", "up", row=0, n=5, detail=False) == (
            "scopes", 0)

    def test_up_again_reaches_the_search_bar(self):
        assert browse.move_focus("scopes", "up", row=0, n=5, detail=False) == (
            "search", 0)

    def test_up_within_the_list_stays_in_the_list(self):
        assert browse.move_focus("list", "up", row=3, n=5, detail=False) == (
            "list", 2)

    def test_down_from_the_search_bar_enters_the_toggle_row(self):
        assert browse.move_focus("search", "down", row=0, n=5, detail=False) == (
            "scopes", 0)

    def test_down_from_the_toggle_row_enters_the_list(self):
        assert browse.move_focus("scopes", "down", row=0, n=5, detail=False) == (
            "list", 0)

    def test_down_from_the_toggles_with_no_matches_stays_put(self):
        assert browse.move_focus("scopes", "down", row=0, n=0, detail=False) == (
            "scopes", 0)

    def test_the_whole_ring_is_walkable_down_and_back_up(self):
        """Every pane must be reachable by arrow alone — a control you can see
        but cannot walk to reads as decoration."""
        focus, row, seen = "search", 0, []
        for _ in range(4):
            seen.append(focus)
            focus, row = browse.move_focus(focus, "down", row, 5, True)
        assert seen == ["search", "scopes", "list", "list"]
        focus, row = browse.move_focus("list", "right", 0, 5, True)
        assert focus == "detail"
        for _ in range(3):
            focus, row = browse.move_focus(focus, "left" if focus == "detail"
                                           else "up", row, 5, True)
        assert focus == "search"


class TestScopeStepping:
    """Item 2: arrow onto the toggle row, then left/right picks one."""

    def test_left_and_right_move_the_scope_only_while_it_is_focused(self):
        assert browse.scope_step("scopes", "right") == 1
        assert browse.scope_step("scopes", "left") == -1

    def test_elsewhere_the_same_keys_mean_something_else(self):
        for focus in ("search", "list", "detail"):
            assert browse.scope_step(focus, "right") == 0
            assert browse.scope_step(focus, "left") == 0

    def test_vertical_keys_never_step_the_scope(self):
        assert browse.scope_step("scopes", "up") == 0
        assert browse.scope_step("scopes", "down") == 0

    def test_stepping_walks_every_scope_and_wraps(self):
        scope = browse.SCOPES[0]
        for _ in range(len(browse.SCOPES)):
            scope = browse.next_scope(scope, browse.scope_step("scopes", "right"))
        assert scope == browse.SCOPES[0]


class TestInstallStatusLine:
    """Item 1: the detail pane reports the install it just started."""

    def test_busy_is_distinguishable_from_done(self):
        assert browse.status_line(browse.BUSY)[1] != \
            browse.status_line(browse.OK)[1]

    def test_each_state_has_its_own_role_for_theming(self):
        roles = {browse.status_line(s)[0]
                 for s in (browse.BUSY, browse.OK, browse.FAILED)}
        assert len(roles) == 3

    def test_a_failure_shows_the_reason(self):
        role, text = browse.status_line(browse.FAILED, "already installed")
        assert "already installed" in text
        assert role == "failed"

    def test_a_failure_with_no_reason_still_says_something(self):
        assert browse.status_line(browse.FAILED)[1].strip() not in ("", "✗")

    def test_success_can_carry_the_destination(self):
        assert "~/.agents" in browse.status_line(browse.OK, "~/.agents/skills/x")[1]

    def test_with_no_action_it_falls_back_to_installed_state(self):
        assert "not installed" in browse.status_line(None, installed=False)[1]
        assert browse.status_line(None, installed=True)[0] == "ok"

    def test_the_detail_pane_shows_the_live_state_over_the_static_one(self):
        e = _e("x")
        text = " ".join(t for _r, t in _dl(
            e, installed=False, state=browse.BUSY))
        assert "installing" in text
        assert "not installed" not in text

    def test_right_from_the_list_enters_the_detail_pane(self):
        assert browse.move_focus("list", "right", row=2, n=5, detail=True) == (
            "detail", 2)

    def test_right_does_nothing_when_the_detail_pane_is_closed(self):
        assert browse.move_focus("list", "right", row=2, n=5, detail=False) == (
            "list", 2)

    def test_left_from_the_detail_pane_returns_to_the_list(self):
        assert browse.move_focus("detail", "left", row=2, n=5, detail=True) == (
            "list", 2)

    def test_down_at_the_end_of_the_list_does_not_overrun(self):
        assert browse.move_focus("list", "down", row=4, n=5, detail=False) == (
            "list", 4)


class TestLayout:
    """Item 4: a border round the whole thing and between the columns."""

    def test_the_detail_pane_sits_on_the_right(self):
        lay = browse.layout(120, 40, detail=True)
        assert lay.detail_x > lay.list_x
        assert lay.detail_w > 0

    def test_panes_do_not_overlap_or_exceed_the_terminal(self):
        for w in (60, 80, 100, 160, 200):
            lay = browse.layout(w, 40, detail=True)
            assert lay.list_x + lay.list_w <= lay.detail_x
            assert lay.detail_x + lay.detail_w <= w

    def test_a_narrow_terminal_drops_the_detail_pane_rather_than_crushing_it(self):
        lay = browse.layout(50, 24, detail=True)
        assert lay.detail_w == 0, "a 20-column detail pane is unreadable"
        assert lay.list_w > 0, "the list must survive"

    def test_the_list_never_gets_a_negative_width(self):
        for w in range(1, 40):
            assert browse.layout(w, 24, detail=True).list_w >= 0

    def test_a_tiny_terminal_does_not_raise(self):
        for w, h in ((1, 1), (2, 3), (10, 4), (0, 0)):
            browse.layout(w, h, detail=True)

    def test_body_height_leaves_room_for_the_chrome(self):
        lay = browse.layout(100, 30, detail=True)
        assert 0 < lay.body_h < 30


class TestScrollClamping:
    def test_offset_cannot_run_past_the_end(self):
        assert browse.clamp_scroll(99, total=10, visible=4) == 6

    def test_offset_cannot_go_negative(self):
        assert browse.clamp_scroll(-5, total=10, visible=4) == 0

    def test_content_that_fits_never_scrolls(self):
        assert browse.clamp_scroll(3, total=3, visible=10) == 0


class TestDetailLines:
    """Items 6 and 7: the right-hand panel, with real `boost info` facts."""

    def test_it_reports_the_essentials(self):
        e = _e("code-review", "Review a PR", tap="acme/quality", version="2.1.0")
        text = " ".join(t for _role, t in _dl(e))
        for fact in ("code-review", "2.1.0", "acme/quality", "Review a PR"):
            assert fact in text, fact

    def test_frontmatter_keys_are_included(self):
        """"the entire frontmatter users can scroll through" — so an unknown
        key must survive rather than being filtered to a known allowlist."""
        e = _e("x", meta={"license": "MIT", "custom-key": "custom-value"})
        text = " ".join(t for _role, t in _dl(e))
        assert "license" in text and "MIT" in text
        assert "custom-key" in text and "custom-value" in text

    def test_a_list_valued_key_renders_readably(self):
        e = _e("x", meta={"tags": ["a", "b", "c"]})
        text = " ".join(t for _role, t in _dl(e))
        assert "a" in text and "b" in text and "c" in text
        assert "['a'" not in text, "a Python repr is not a rendering"

    def test_every_line_carries_a_role_for_theming(self):
        for role, _text in _dl(_e("x", "d")):
            assert isinstance(role, str) and role

    def test_it_never_raises_on_a_sparse_entry(self):
        assert _dl({"name": "bare"})

    def test_long_values_are_wrapped_to_the_pane_width(self):
        e = _e("x", "word " * 80)
        lines = _dl(e, width=30)
        assert all(len(t) <= 30 for _r, t in lines), "detail text must wrap"

    def test_installed_state_is_surfaced_when_known(self):
        e = _e("code-review")
        text = " ".join(t for _r, t in _dl(e, installed=True))
        assert "installed" in text.lower()


def _render(w=100, h=24, query="", scope="all", focus="list", sel=0,
            detail=True, entries=None, summary=None):
    """Draw one frame into a text grid.

    The draw helpers take `put` as a parameter, so a recording `put` renders
    the real frame with no curses and no terminal — which is the only way the
    box-drawing can be asserted on at all.
    """
    from boost_cli.commands import discovery

    grid = [[" "] * w for _ in range(h)]

    def put(y, x, s, attr=0):
        if 0 <= y < h and 0 <= x < w and s:
            for i, ch in enumerate(str(s)):
                if 0 <= x + i < w:
                    grid[y][x + i] = ch

    class _Theme(dict):
        def __missing__(self, _k):
            return 0

    th, ents = _Theme(), (CORPUS if entries is None else entries)
    found = browse.matches(ents, query, scope)
    lay = browse.layout(w, h, detail=detail)
    discovery._draw_frame(put, th, lay, focus)
    discovery._draw_status(put, th, lay, focus, summary)
    discovery._draw_query(put, th, lay, query, focus, len(found), len(ents), 0)
    discovery._draw_scopes(put, th, lay, scope, focus)
    discovery._draw_rows(put, th, lay, found, sel, set(), query, focus,
                         lambda e: e.get("description", ""), {}, set())
    if lay.has_detail and found:
        discovery._draw_detail(put, th, lay, found[sel], 0, focus, set())
    return ["".join(r) for r in grid]


class TestFrameRendering:
    """Items 4 and 9 — the box actually closes, on every width."""

    def test_all_four_corners_are_drawn(self):
        g = _render()
        assert g[0][0] == "╭" and g[0][-1] == "╮"
        bottom = browse.layout(100, 24, detail=True).bottom
        assert bottom == len(g) - 2, "the status bar owns the last row"
        assert g[bottom][0] == "╰" and g[bottom][-1] == "╯"

    def test_both_side_borders_are_drawn_on_every_body_row(self):
        """The right border sat in the last column, which the old clip bound
        made unwritable — the frame drew with three sides."""
        g = _render()
        lay = browse.layout(100, 24, detail=True)
        sep = lay.body_y - 1
        for y in range(1, lay.bottom):
            if y == sep:                       # the ├───┤ chrome/body rule
                assert g[y][0] == "├" and g[y][-1] == "┤"
                continue
            assert g[y][0] == "│", "row %d has no left border" % y
            assert g[y][-1] == "│", "row %d has no right border" % y

    def test_the_column_divider_is_continuous(self):
        g = _render(w=110, h=24)
        lay = browse.layout(110, 24, detail=True)
        x = lay.detail_x - 1
        assert g[lay.body_y - 1][x] == "┬"
        assert g[lay.bottom][x] == "┴"
        for y in range(lay.body_y, lay.bottom):
            assert g[y][x] == "│", "divider broken at row %d" % y

    @pytest.mark.parametrize("w,h", [(60, 20), (80, 24), (100, 30), (160, 50)])
    def test_every_row_is_exactly_the_terminal_width(self, w, h):
        for row in _render(w=w, h=h):
            assert len(row) == w

    def test_the_title_appears_in_the_top_rule(self):
        assert "boost browse" in _render()[0]

    def test_the_status_bar_never_ends_mid_word(self):
        """A clipped hint ends on `esc`, which reads as a key not a fragment."""
        for focus in browse.PANES:
            for w in (40, 56, 60, 70, 80, 100, 140):
                bar = _render(w=w, h=24, focus=focus)[-1]
                assert "esc quit" in bar, (focus, w)
                assert browse.MODES[focus] in bar, (focus, w)

    def test_the_status_bar_carries_the_session_chip(self):
        bar = _render(w=100, h=24, summary=("ok_line", "✓ 2 installed"))[-1]
        assert bar.rstrip().endswith("✓ 2 installed")
        assert "esc quit" in bar

    def test_a_short_terminal_keeps_the_frame_and_drops_the_bar(self):
        lay = browse.layout(80, 7, detail=False)
        assert not lay.has_status
        assert lay.bottom == 6
        g = _render(w=80, h=7, detail=False)
        assert g[-1][0] == "╰" and g[-1][-1] == "╯"


class TestScopeRadios:
    """Item 8 — the search-scope toggles are visible and show which is on."""

    def test_exactly_one_toggle_is_filled(self):
        row = _render(scope="name")[2]
        assert row.count("●") == 1
        for scope in browse.SCOPES:
            assert browse.scope_label(scope) in row, scope

    def test_the_filled_toggle_tracks_the_active_scope(self):
        """The dot, not just the colour, says which scope is on."""
        for scope in browse.SCOPES:
            row = _render(scope=scope)[2]
            i = row.index("●")
            assert row[i + 2:].startswith(browse.scope_label(scope))


class TestFocusIsVisible:
    """Item 1: you can tell which pane you are driving."""

    def test_the_detail_pane_announces_itself_when_focused(self):
        lay = browse.layout(110, 24, detail=True)
        unfocused = _render(w=110, h=24, focus="list")[lay.body_y - 1]
        focused = _render(w=110, h=24, focus="detail")[lay.body_y - 1]
        assert "details" in unfocused
        assert "scroll" in focused, "a scrollable pane must say it scrolls"
        assert focused != unfocused

    def test_the_toggle_row_announces_itself_when_focused(self):
        assert "pick" in _render(focus="scopes")[2]
        assert "pick" not in _render(focus="list")[2]

    def test_the_focused_border_differs_from_the_unfocused_one(self):
        """Rendered to a grid the glyphs match; the attribute is the signal."""
        from boost_cli.commands import discovery

        seen = {}

        def make_put(bucket):
            def put(y, x, s, attr=0):
                if s == "│":
                    bucket.setdefault(x, set()).add(attr)
            return put

        class _Theme(dict):
            def __missing__(self, k):
                return {"border": 1, "border_focus": 2}.get(k, 0)

        lay = browse.layout(110, 24, detail=True)
        for focus in ("list", "detail"):
            seen[focus] = {}
            discovery._draw_frame(make_put(seen[focus]), _Theme(), lay, focus)
        right = lay.w - 1
        assert seen["list"][right] != seen["detail"][right], \
            "the right-hand border must change when the detail pane is focused"


class TestDedupeIsVisible:
    """Collapsing is fine; collapsing silently is not.

    A browser that drops a third of the catalogue and shows a smaller total is
    indistinguishable from one with a broken filter.
    """

    def test_a_collapsed_row_says_how_many_it_stands_for(self):
        from boost_cli.commands import discovery

        rows, copies = [], {}
        dup = _e("007", "Security audit")
        copies[id(dup)] = 5
        rows.append(dup)

        painted = []

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        def put(y, x, s, attr=0):
            painted.append(str(s))

        lay = browse.layout(100, 24, detail=True)
        discovery._draw_rows(put, _Theme(), lay, rows, 0, set(), "", "list",
                             lambda e: "", {}, set(), copies)
        assert any("×5" in s for s in painted)

    def test_a_unique_row_gets_no_badge(self):
        from boost_cli.commands import discovery

        painted = []

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        lay = browse.layout(100, 24, detail=True)
        discovery._draw_rows(put := (lambda y, x, s, attr=0:
                                     painted.append(str(s))),
                             _Theme(), lay, [_e("solo", "x")], 0, set(), "",
                             "list", lambda e: "", {}, set(), {})
        assert not any("×" in s for s in painted)
        assert put is not None

    def test_the_hidden_total_is_stated_in_the_count(self):
        from boost_cli.commands import discovery

        painted = []

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        lay = browse.layout(100, 24, detail=True)
        discovery._draw_query(lambda y, x, s, attr=0: painted.append(str(s)),
                              _Theme(), lay, "", "list", 10, 10, 0, 22379)
        # Thousands-grouped: at real scale "22379" is a smudge, "22,379" is a
        # number.
        assert any("22,379" in s and "hidden" in s for s in painted)

    def test_no_hidden_rows_means_no_note(self):
        from boost_cli.commands import discovery

        painted = []

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        lay = browse.layout(100, 24, detail=True)
        discovery._draw_query(lambda y, x, s, attr=0: painted.append(str(s)),
                              _Theme(), lay, "", "list", 10, 10, 0, 0)
        assert not any("hidden" in s for s in painted)


class TestInstallStatusInThePane:
    def test_each_state_reaches_the_rendered_pane(self):
        for state, needle in ((browse.BUSY, "installing"),
                              (browse.OK, "installed"),
                              (browse.FAILED, "✗")):
            lines = _dl(CORPUS[0], width=40, installed=False,
                                        state=state, message="boom")
            assert any(needle in t for _r, t in lines), state


class TestRowRendering:
    def test_the_selected_row_is_painted_across_the_whole_list_pane(self):
        """Item 5: the highlight spans the row, not just a marker column."""
        from boost_cli.commands import discovery

        painted = []

        def put(y, x, s, attr=0):
            if attr and isinstance(s, str) and s.strip() == "":
                painted.append((y, x, len(s)))

        class _Theme(dict):
            def __missing__(self, _k):
                return 7          # any truthy attr

        lay = browse.layout(100, 24, detail=True)
        discovery._draw_rows(put, _Theme(), lay, CORPUS, 0, set(), "", "list",
                             lambda e: "", {}, set())
        assert painted, "the selected row was never filled"
        assert max(n for _y, _x, n in painted) == lay.list_w

    def test_a_query_with_no_matches_shows_the_empty_state(self):
        """A silent void is indistinguishable from a hung draw — the pane
        says what happened and which keys widen the net."""
        g = _render(query="zzzzz")
        body = "\n".join(g)
        assert "no matches for 'zzzzz'" in body
        assert "backspace" in body

    def test_a_query_with_matches_shows_no_empty_state(self):
        g = _render(query="code")
        assert "backspace" not in "\n".join(g)


class TestEmptyLines:
    """The zero-match pane's text — pure, so 'what does nothing look like'
    is an assertion instead of a screenshot."""

    def test_never_returns_nothing(self):
        assert browse.empty_lines("", "all")

    def test_names_the_query_and_the_scope(self):
        text = " ".join(t for _r, t in browse.empty_lines("zzq", "name"))
        assert "'zzq'" in text
        assert "name" in text

    def test_uses_the_shared_empty_state_grammar(self):
        lines = browse.empty_lines("x", "all")
        assert lines[0][1].startswith("○ ")
        assert lines[1][1].startswith("→ ")

    def test_every_role_is_muted(self):
        for role, _t in browse.empty_lines("x", "all", hidden=5):
            assert role == "muted"

    def test_the_dupes_hint_appears_only_when_hidden(self):
        joined = " ".join(t for _r, t in browse.empty_lines("x", "all"))
        assert "^D" not in joined
        with_hidden = " ".join(
            t for _r, t in browse.empty_lines("x", "all", hidden=22379))
        assert "^D" in with_hidden
        assert "22,379" in with_hidden

    def test_scope_shows_its_display_label(self):
        text = " ".join(t for _r, t in browse.empty_lines("q", "description"))
        assert browse.scope_label("description") in text

    def test_an_empty_query_says_nothing_here_verbatim(self):
        # The no-entries branch (can only happen mid-refresh) is a fixed
        # phrase, not a template with an empty hole.
        assert browse.empty_lines("", "all")[0][1] == "○ nothing here"
        assert browse.empty_lines("   ", "all")[0][1] == "○ nothing here"

    def test_query_whitespace_collapses_in_the_echo(self):
        assert browse.empty_lines("code  review", "all")[0][1] == \
            "○ no matches for 'code review' in all"

    def test_the_hint_lines_verbatim(self):
        # Exact bytes: a drifted keycap ("^t") or a mangled template would
        # pass any substring check while lying about the keys.
        lines = browse.empty_lines("q", "all", hidden=22379)
        assert lines[1][1] == \
            "→ backspace widens · ^T scope · ^G ^R ^K filters"
        assert lines[2][1] == "→ ^D shows 22,379 hidden duplicates"

    def test_a_single_hidden_duplicate_still_gets_the_hint(self):
        assert len(browse.empty_lines("q", "all", hidden=1)) == 3


class TestRuleSegments:
    """Moved from the command layer so the gradient rule's geometry sits
    under the mutation gate."""

    def test_zero_width_is_empty(self):
        assert browse.rule_segments(0) == []

    def test_segments_partition_the_width_exactly(self):
        segs = browse.rule_segments(10, 3)
        assert [s[1] for s in segs] == [4, 3, 3]
        assert sum(s[1] for s in segs) == 10
        assert [s[0] for s in segs] == [0, 4, 7]

    def test_n_clamps_to_width(self):
        assert len(browse.rule_segments(2, 3)) == 2

    def test_partition_holds_across_widths(self):
        for width in range(1, 40):
            segs = browse.rule_segments(width, 3)
            assert sum(s[1] for s in segs) == width
            x = 0
            for start, length in segs:
                assert start == x
                x += length


class TestScrollbarGeometry:
    """discovery._scrollbar moved into core; list and detail panes share it."""

    def test_none_when_everything_fits(self):
        assert browse.scrollbar(5, 10, 0) is None

    def test_none_when_no_rows(self):
        assert browse.scrollbar(10, 0, 0) is None

    def test_thumb_is_at_least_one_cell(self):
        start, length = browse.scrollbar(100, 10, 0)
        assert start == 0 and 1 <= length <= 10

    def test_bottom_scrolled_thumb_ends_at_the_last_cell(self):
        _start, length = browse.scrollbar(100, 10, 0)
        end_start, _ = browse.scrollbar(100, 10, 90)
        assert end_start == 10 - length

    def test_exact_geometry(self):
        # Exact values, so the arithmetic (integer division, the 1-cell
        # floor, the proportional start) cannot drift: 10²//100 = 1,
        # 10²//30 = 3, and at top=45 of 90 the thumb sits at round(9·0.5).
        assert browse.scrollbar(100, 10, 0) == (0, 1)
        assert browse.scrollbar(100, 10, 45) == (4, 1)
        assert browse.scrollbar(30, 10, 0) == (0, 3)
        assert browse.scrollbar(30, 10, 20) == (7, 3)

    def test_the_thumb_length_is_an_int(self):
        _start, length = browse.scrollbar(30, 10, 5)
        assert isinstance(length, int)

    def test_a_one_row_window_still_gets_a_bar(self):
        assert browse.scrollbar(10, 1, 0) == (0, 1)

    def test_exactly_filled_needs_no_bar(self):
        assert browse.scrollbar(10, 10, 0) is None


class TestBadgePositions:
    RAIL = (("×4", "accent_dim"), ("[skill]", "badge_skill"),
            ("v1.2", "version"), ("[a/b]", "tap"), ("[ui]", "badge_category"))

    def test_the_cluster_right_edge_lands_on_width(self):
        placed = browse.badge_positions(10, self.RAIL, 60)
        x, text, _key = placed[-1]
        assert x + len(text) == 60

    def test_badges_never_overlap_the_name(self):
        for width in range(12, 60):
            placed = browse.badge_positions(10, self.RAIL, width)
            if placed:
                assert placed[0][0] >= 10, width

    def test_one_space_between_badges(self):
        import itertools
        placed = browse.badge_positions(0, self.RAIL, 60)
        for (x1, t1, _k1), (x2, _t2, _k2) in itertools.pairwise(placed):
            assert x2 == x1 + len(t1) + 1

    def test_drops_from_the_least_important_end(self):
        full = browse.badge_positions(0, self.RAIL, 80)
        assert [t for _x, t, _k in full] == [t for t, _k in self.RAIL]
        # 22 columns: the category badge is the one casualty (cluster is 21).
        assert [t for _x, t, _k in browse.badge_positions(0, self.RAIL, 22)] \
            == ["×4", "[skill]", "v1.2", "[a/b]"]
        # 20 columns: the tap follows it.
        assert [t for _x, t, _k in browse.badge_positions(0, self.RAIL, 20)] \
            == ["×4", "[skill]", "v1.2"]

    def test_the_copies_tag_survives_longest(self):
        placed = browse.badge_positions(0, self.RAIL, 3)
        assert [t for _x, t, _k in placed] == ["×4"]

    def test_empty_when_nothing_fits(self):
        assert browse.badge_positions(10, self.RAIL, 11) == []

    def test_a_cluster_may_start_exactly_at_name_end(self):
        # The whole rail is 26 wide; at width 36 with name_end 10 it fits
        # with zero slack, and zero slack is a fit.
        placed = browse.badge_positions(10, self.RAIL, 36)
        assert [t for _x, t, _k in placed] == [t for t, _k in self.RAIL]
        assert placed[0][0] == 10

    def test_theme_keys_ride_along(self):
        placed = browse.badge_positions(0, self.RAIL, 80)
        assert [k for _x, _t, k in placed] == [k for _t, k in self.RAIL]


class TestStateGlyph:
    def test_the_four_states(self):
        assert browse.state_glyph(browse.BUSY, False) == ("◐", "busy")
        assert browse.state_glyph(browse.FAILED, True) == ("✗", "failed")
        assert browse.state_glyph(browse.OK, False) == ("●", "check")
        assert browse.state_glyph(None, False) == (" ", "muted")

    def test_installed_without_a_session_state_is_the_check(self):
        assert browse.state_glyph(None, True) == ("●", "check")

    def test_glyphs_come_from_the_status_table_the_detail_pane_uses(self):
        # One glyph source: mutating _STATUS_GLYPH breaks both surfaces'
        # assertions, so the list and the pane can never disagree.
        assert browse.state_glyph(browse.BUSY, False)[0] == \
            browse._STATUS_GLYPH[browse.BUSY]
        assert browse.state_glyph(browse.OK, False)[0] == \
            browse._STATUS_GLYPH[browse.OK]
        assert browse.state_glyph(browse.FAILED, False)[0] == \
            browse._STATUS_GLYPH[browse.FAILED]
        assert browse.status_line(browse.FAILED, "x")[1].startswith(
            browse.state_glyph(browse.FAILED, False)[0])


class TestInstallTarget:
    TARGETS: typing.ClassVar[dict[str, str]] = {
        "skill": "~/.agents/skills · linked to claude-code",
        "rule": "~/.claude/CLAUDE.md",
        "workflow": "each agent's commands dir (TOML for gemini)"}

    def test_dispatches_on_kind(self):
        assert browse.install_target({"kind": "rule"}, self.TARGETS) == \
            self.TARGETS["rule"]
        assert browse.install_target({"kind": "workflow"}, self.TARGETS) == \
            self.TARGETS["workflow"]

    def test_missing_kind_is_a_skill(self):
        assert browse.install_target({}, self.TARGETS) == self.TARGETS["skill"]

    def test_unknown_kind_stays_honest(self):
        assert browse.install_target({"kind": "mystery"}, self.TARGETS) == "?"

    def test_no_targets_mapping_degrades(self):
        assert browse.install_target({"kind": "skill"}, None) == "?"


class TestCountTail:
    def test_minimal_form(self):
        assert browse.count_tail(5, 9, 0, 0) == "5/9"

    def test_thousands_are_grouped(self):
        assert browse.count_tail(128, 71700, 0, 0) == "128/71,700"

    def test_selection_prefix_only_when_selected(self):
        assert browse.count_tail(1, 2, 2, 0) == "2 selected · 1/2"

    def test_hidden_suffix_only_when_hidden(self):
        assert browse.count_tail(1, 2, 0, 22379) == "1/2  (22,379 dupes hidden)"

    def test_everything_at_once(self):
        assert browse.count_tail(128, 71700, 2, 22379) == \
            "2 selected · 128/71,700  (22,379 dupes hidden)"


class TestSessionSummary:
    def test_empty_map_is_none(self):
        assert browse.session_summary({}) is None

    def test_ok_installs_are_counted(self):
        assert browse.session_summary(
            {"a": (browse.OK, ""), "b": (browse.OK, "x")}) == \
            ("ok_line", "✓ 2 installed")

    def test_busy_outranks_ok(self):
        assert browse.session_summary(
            {"a": (browse.OK, ""), "b": (browse.BUSY, "")}) == \
            ("busy", "◐ 1 installing…")

    def test_failed_outranks_everything(self):
        got = browse.session_summary({"a": (browse.OK, ""),
                                      "b": (browse.BUSY, ""),
                                      "c": (browse.FAILED, "boom")})
        assert got == ("failed", "✗ 1 failed")


class TestGradientRuleInTheFrame:
    """The one gradient moment browse gets: the top border rule."""

    def test_three_distinct_runs_paint_the_top_rule(self):
        from boost_cli.commands import discovery

        attrs = []

        def put(y, x, s, attr=0):
            if y == 0 and set(str(s)) == {"─"}:
                attrs.append((x, len(str(s)), attr))

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        th = _Theme()
        th["rule"] = [11, 22, 33]
        lay = browse.layout(100, 24, detail=True)
        discovery._draw_frame(put, th, lay, "list")
        seen = {a for _x, _n, a in attrs}
        assert {11, 22, 33} <= seen, "all three gradient runs must paint"
        # The runs abut and end just before the corner glyph.
        import itertools
        runs = sorted((x, n) for x, n, a in attrs if a in (11, 22, 33))
        for (x1, n1), (x2, _n2) in itertools.pairwise(runs):
            assert x2 == x1 + n1
        assert runs[-1][0] + runs[-1][1] == lay.w - 1

    def test_the_grid_glyphs_are_unchanged_by_the_gradient(self):
        g = _render()
        assert g[0][0] == "╭" and g[0][-1] == "╮"
        assert "boost browse" in g[0]


class TestSessionChipInTheStatusBar:
    """The install chip moved out of the bottom rule, where it fought the
    divider's tee for the same cells, into the status bar under the frame."""

    def _grid(self, summary, w=100, h=24):
        from boost_cli.commands import discovery

        grid = [[" "] * w for _ in range(h)]

        def put(y, x, s, attr=0):
            if 0 <= y < h and 0 <= x < w and s:
                for i, ch in enumerate(str(s)):
                    if 0 <= x + i < w:
                        grid[y][x + i] = ch

        class _Theme(dict):
            def __missing__(self, _k):
                return 0

        lay = browse.layout(w, h, detail=True)
        discovery._draw_frame(put, _Theme(), lay, "list")
        discovery._draw_status(put, _Theme(), lay, "list", summary)
        return ["".join(r) for r in grid], lay

    def test_the_chip_lands_in_the_status_bar(self):
        g, lay = self._grid(("ok_line", "✓ 2 installed"))
        assert "✓ 2 installed" in g[lay.status_y]
        assert "✓ 2 installed" not in g[lay.bottom]

    def test_the_bottom_rule_is_plain_whatever_the_session_did(self):
        for summary in (None, ("failed", "✗ " + "x" * 200)):
            g, lay = self._grid(summary)
            expected = list("╰" + "─" * (lay.w - 2) + "╯")
            expected[lay.detail_x - 1] = "┴"
            assert g[lay.bottom] == "".join(expected), summary

    def test_a_huge_chip_stays_inside_the_bar(self):
        g, lay = self._grid(("failed", "✗ " + "x" * 200))
        assert len(g[lay.status_y]) == lay.w
        assert g[lay.status_y].startswith(" LIST ")


class TestListScrollbar:
    def test_the_thumb_appears_when_rows_overflow(self):
        entries = [_e("skill-%02d" % i, "desc") for i in range(40)]
        g = _render(h=14, entries=entries)
        lay = browse.layout(100, 14, detail=True)
        col = [row[lay.list_x + lay.list_w - 1] for row in g[lay.body_y:-1]]
        assert "█" in col, "an overflowing list must show where you are"

    def test_no_bar_when_everything_fits(self):
        g = _render()
        lay = browse.layout(100, 24, detail=True)
        col = [row[lay.list_x + lay.list_w - 1] for row in g[lay.body_y:-1]]
        assert "█" not in col


class TestBadgeRailAlignment:
    def test_badges_right_align_to_the_pane_edge(self):
        g = _render()
        lay = browse.layout(100, 24, detail=True)
        row = g[lay.body_y]
        # CORPUS[0] is code-review from acme/quality: the rail ends with the
        # version badge, whose last digit sits one column short of the divider
        # gap — and the tap shows as its repo name alone.
        assert row[lay.list_x + lay.list_w - 2] == "0"
        assert "quality v1.0.0" in row
        assert "acme/" not in row

    def test_the_kind_badge_text_matches_the_search_vocabulary(self):
        from boost_cli.core import output as out
        g = _render(query="rag")
        assert "[rule]" in "\n".join(g)
        assert out.kind_label("rule") == "[rule]"


def test_a_status_message_keeps_a_backticked_command_whole():
    # textwrap split `chmod u+w ~/.cursor/skills` over two lines of the pane,
    # which leaves a command no one can copy.
    msg = ("not linked: ~/.cursor/skills is not writable — "
           "`chmod u+w ~/.cursor/skills`, then `boost sync` adds the link")
    lines = [t for role, t in _dl(
        {"name": "x", "description": "d"}, width=30, state="ok", message=msg)
        if "chmod" in t or "sync" in t or "linked" in t]
    assert any("`chmod u+w ~/.cursor/skills`" in t for t in lines), lines
    assert all(t.count("`") % 2 == 0 for t in lines), lines


def test_a_status_token_wider_than_the_pane_still_fits_it():
    # output.wrap lets an over-wide token run long; in a curses pane that
    # drew over the frame and cut the tail off.
    msg = "installed ~/.agents/skills/" + "a-very-long-skill-name" * 3
    lines = [t for role, t in _dl(
        {"name": "x"}, width=30, state="ok", message=msg)]
    assert all(len(t) <= 30 for t in lines), lines
    assert "".join(lines).count("a-very-long-skill-name") >= 1


def test_a_command_exactly_as_wide_as_the_pane_is_not_split_by_its_comma():
    # "`chmod u+w ~/.windsurf/skills`," is 31 columns for a 30-column pane:
    # the glued comma sent the span to the textwrap fallback, which split
    # the command it exists to keep whole.
    cmd = "`chmod u+w ~/.windsurf/skills`"
    assert len(cmd) == 30
    msg = "not linked: ~/.windsurf/skills is not writable — %s, then `boost sync`" % cmd
    lines = [t for role, t in _dl(
        {"name": "x"}, width=30, state="ok", message=msg)]
    assert cmd in lines, lines
    assert all(len(t) <= 30 for t in lines), lines



class TestBrowseInstallTargetLines:
    """The strings the detail pane shows for "what Enter writes".

    `TestInstallTarget` above pins the *dispatch* against a literal dict, so it
    stays green whatever the real lines say. These pin the lines themselves,
    which is where the defect was: each has to name the agent set the install
    narrows to, or the pane advertises a destination the install refuses.
    """

    @staticmethod
    def _targets(sandbox):
        from boost_cli.commands import discovery
        return discovery._install_targets()

    def test_the_workflow_line_names_only_workflow_agents(self, sandbox):
        # Codex is enabled and takes rules, but has no user-installable
        # slash-command format, so it must not appear here. The old line said
        # "each agent's commands dir", which included it by construction.
        from boost_cli.core import agents
        line = self._targets(sandbox)["workflow"]
        assert "Codex" not in line
        assert agents.display_name("claude-code") in line
        for name in agents.workflow_agents():
            assert agents.display_name(name) in line

    def test_the_workflow_line_survives_having_no_workflow_agents(self, sandbox):
        from boost_cli.core import config
        cfg = config.load()
        for spec in cfg["agents"].values():
            spec["workflows"] = False
        config.save(cfg)
        assert "no agents" in self._targets(sandbox)["workflow"]

    def test_the_skill_line_names_only_linking_agents(self, sandbox):
        # Gemini and Codex discover the canonical store themselves; boost
        # deliberately does not link for them, so naming them would promise a
        # symlink that is never made.
        from boost_cli.core import agents
        line = self._targets(sandbox)["skill"]
        for name in agents.native_store_agents():
            assert agents.display_name(name) not in line
        assert agents.display_name("claude-code") in line

    def test_the_rule_line_names_context_files_beside_the_skills_dir(self, sandbox):
        # `d` is the agent's *skills* dir; the context file sits beside it. The
        # pane used to advertise `~/.claude/skills/CLAUDE.md`, which nothing
        # reads.
        line = self._targets(sandbox)["rule"]
        assert "~/.claude/CLAUDE.md" in line
        assert "skills/CLAUDE.md" not in line


# ------------------------------------------------------------------ reskin


class TestRanking:
    """Matches rank by how the *name* meets the query; catalogue order breaks
    ties. Each test isolates one tier boundary, so a `<` / `<=` slip in
    match_tier cannot survive."""

    @pytest.mark.parametrize("name,query,tier", [
        ("code-review", "code-review", browse.EXACT),
        ("code-review", "code review", browse.EXACT),     # space == hyphen
        ("Code-Review", "code review", browse.EXACT),     # case-folded
        ("code-review-pro", "code review", browse.PREFIX),
        ("code-review-pro", "code-review", browse.PREFIX),
        ("my-code-review", "code review", browse.SUBSTRING),
        ("review-the-code", "code review", browse.SUBSTRING),  # any order
        ("cxoxdxe", "code", browse.FUZZY),
        ("unrelated", "code", browse.ELSEWHERE),
        ("code", "code zzz", browse.ELSEWHERE),           # every token counts
    ])
    def test_tiers(self, name, query, tier):
        assert browse.match_tier(name, browse.tokens(query)) == tier

    def test_no_tokens_is_the_lowest_tier(self):
        assert browse.match_tier("anything", []) == browse.ELSEWHERE

    def test_the_tiers_are_ordered_best_first(self):
        assert (browse.EXACT < browse.PREFIX < browse.SUBSTRING
                < browse.FUZZY < browse.ELSEWHERE)

    @pytest.mark.parametrize("better,worse", [
        ("twin", "twin-tool"),                # exact beats prefix
        ("twin-tool", "the-twin"),            # prefix beats substring
        ("the-twin", "t-w-i-n"),              # substring beats fuzzy
        ("t-w-i-n", "other"),                 # fuzzy beats description-only
    ])
    def test_each_boundary_decides_the_order(self, better, worse):
        rows = [_e(worse, "twin"), _e(better, "twin")]
        got = [e["name"] for e in browse.rank(rows, "twin")]
        assert got == [better, worse]

    def test_ties_keep_catalogue_order(self):
        rows = [_e("b-twin", ""), _e("a-twin", ""), _e("c-twin", "")]
        assert [e["name"] for e in browse.rank(rows, "twin")] == \
            ["b-twin", "a-twin", "c-twin"]

    def test_an_empty_query_is_left_untouched(self):
        rows = [_e("b"), _e("a")]
        assert browse.rank(rows, "  ") is rows

    def test_matches_come_back_ranked(self):
        rows = [_e("aaa-eight-twins-helper", ""), _e("eight-twins", ""),
                _e("eagle", "eight twins in prose")]
        got = [e["name"] for e in browse.matches(rows, "eight-twins")]
        assert got[0] == "eight-twins"
        assert got[1] == "aaa-eight-twins-helper"


class TestCategoryScope:
    def test_category_is_a_scope(self):
        assert "category" in browse.SCOPES
        assert browse.scope_label("category") == "category"

    def test_the_entry_category_beats_the_tap_fallback(self):
        e = _e("x", tap="a/b", category="testing")
        assert browse.entry_category(e, {"a/b": "devops"}) == "testing"

    def test_the_tap_fallback_fills_a_missing_category(self):
        assert browse.entry_category(_e("x", tap="a/b"), {"a/b": "devops"}) \
            == "devops"

    def test_no_category_anywhere_is_empty(self):
        assert browse.entry_category(_e("x", tap="a/b"), None) == ""
        assert browse.entry_category(_e("x", tap="a/b"), {"a/b": None}) == ""

    def test_the_category_scope_searches_only_the_category(self):
        rows = [_e("devops-thing", "", tap="a/b"),
                _e("plain", "", tap="c/d", category="devops")]
        got = [e["name"] for e in browse.matches(rows, "devops", "category")]
        assert got == ["plain"]

    def test_the_category_scope_uses_the_tap_fallback(self):
        rows = [_e("plain", "", tap="a/b")]
        assert browse.matches(rows, "devops", "category", {"a/b": "devops"})
        assert not browse.matches(rows, "devops", "category", {})

    def test_all_includes_the_category(self):
        hay = browse.haystack(_e("x", tap="a/b"), "all", {"a/b": "devops"})
        assert "devops" in hay


class TestShortTap:
    @pytest.mark.parametrize("tap,want", [
        ("trailofbits/skills", "skills"),
        ("fixture-tap", "fixture-tap"),
        ("a/b/c", "c"),
        ("", ""),
        (None, ""),
    ])
    def test_short_tap(self, tap, want):
        assert browse.short_tap(tap) == want


class TestStatusBar:
    def test_every_pane_has_a_mode_and_hints_that_end_in_quit(self):
        for pane in browse.PANES:
            assert browse.MODES[pane]
            assert browse.HINTS[pane][-1] == ("esc", "quit")

    def test_fit_hints_keeps_everything_that_fits(self):
        hints = (("a", "one"), ("b", "two"))
        # "a one" (5) + gap (2) + "b two" (5) == 12
        assert browse.fit_hints(hints, 12) == list(hints)
        assert browse.fit_hints(hints, 11) == [("b", "two")]

    def test_fit_hints_drops_from_the_middle_and_keeps_the_last(self):
        hints = (("1", "a"), ("2", "b"), ("3", "c"), ("esc", "quit"))
        kept = browse.fit_hints(hints, 12)   # "1 a" + 2 + "esc quit" == 13
        assert kept == [("esc", "quit")]
        kept = browse.fit_hints(hints, 13)
        assert kept == [("1", "a"), ("esc", "quit")]

    def test_fit_hints_gives_up_whole_rather_than_clipping(self):
        assert browse.fit_hints((("esc", "quit"),), 7) == []
        assert browse.fit_hints((("esc", "quit"),), 8) == [("esc", "quit")]

    def test_spans_start_with_the_pill(self):
        spans = browse.status_spans("detail", 80)
        assert spans[0] == (0, "pill", " DETAIL ")
        assert spans[1] == (9, "key", "↑↓")
        assert spans[2] == (12, "hint", "scroll")

    def test_keys_and_labels_alternate_and_do_not_overlap(self):
        spans = browse.status_spans("list", 200)
        end = 0
        for x, _role, text in spans:
            assert x >= end
            end = x + len(text)
        assert end <= 199

    def test_the_summary_sits_at_the_right_edge(self):
        spans = browse.status_spans("list", 80, ("ok_line", "✓ 3 installed"))
        x, _role, text = next(s for s in spans if s[1] == "ok_line")
        assert x + len(text) == 79
        assert text == "✓ 3 installed"
        hint_end = max(sx + len(t) for sx, r, t in spans
                       if r in ("key", "hint"))
        assert hint_end <= x - 2, "hints give way to the chip"

    def test_a_summary_with_no_room_is_clipped_not_dropped_onto_the_pill(self):
        spans = browse.status_spans("list", 12, ("failed", "✗ 9 failed"))
        x, _r, text = next(s for s in spans if s[1] == "failed")
        assert x >= len(" LIST ")
        assert x + len(text) <= 11

    def test_no_width_no_spans(self):
        assert browse.status_spans("list", 0) == []

    def test_an_unknown_focus_falls_back_to_list(self):
        spans = browse.status_spans("nonsense", 80)
        assert spans[0][2] == " LIST "


class TestPalette:
    @pytest.mark.parametrize("can_change,colors,level", [
        (True, 256, browse.CUSTOM),
        (True, 16 + browse.CUSTOM_SLOTS, browse.CUSTOM),
        (True, 16 + browse.CUSTOM_SLOTS - 1, browse.BASE),
        (False, 256, browse.XTERM256),
        (False, 255, browse.BASE),
        (False, 8, browse.BASE),
    ])
    def test_palette_level(self, can_change, colors, level):
        assert browse.palette_level(can_change, colors) == level

    def test_kind_hues_never_collide_at_any_level(self):
        """Two kinds in one colour read as one kind. On base, violet and pink
        are both magenta — so they may not both be used."""
        base_of = {"cyan": "cyan", "violet": "magenta", "pink": "magenta",
                   "yellow": "yellow"}
        for level in (browse.CUSTOM, browse.XTERM256, browse.BASE):
            hues = [browse.kind_hue(k, level) for k in
                    ("skill", "rule", "workflow")]
            assert len(set(hues)) == 3, level
            if level == browse.BASE:
                assert len({base_of[h] for h in hues}) == 3

    def test_kind_hue_falls_back_to_the_skill_hue(self):
        assert browse.kind_hue("mystery", browse.CUSTOM) == "cyan"
        assert browse.kind_hue("rule", "nonsense") == \
            browse.kind_hue("rule", browse.BASE)

    @pytest.mark.parametrize("rgb,index", [
        ((0, 0, 0), 16),
        ((255, 255, 255), 231),
        ((95, 215, 215), 80),          # exact cube point
        ((0x40, 0xcb, 0xe3), 80),      # Aurora cyan
        ((128, 128, 128), 244),        # grey ramp beats the cube
        ((8, 8, 8), 232),              # bottom of the ramp
        ((238, 238, 238), 255),        # top of the ramp
        ((255, 0, 0), 196),
        ((0, 0, 255), 21),
    ])
    def test_xterm256(self, rgb, index):
        assert browse.xterm256(rgb) == index

    def test_the_slate_is_a_dark_grey_not_a_hue(self):
        assert 232 <= browse.xterm256(browse.SLATE) <= 240


class TestDetailSpans:
    def test_line_text_and_role(self):
        line = [("label", "kind     "), ("field", "skill")]
        assert browse.line_text(line) == "kind     skill"
        assert browse.line_role(line) == "label"
        assert browse.line_role([]) == "blank"

    def test_clip_spans(self):
        line = [("a", "abc"), ("b", "defg"), ("c", "h")]
        assert browse.clip_spans(line, 5) == [("a", "abc"), ("b", "de")]
        assert browse.clip_spans(line, 3) == [("a", "abc")]
        assert browse.clip_spans(line, 8) == line
        assert browse.clip_spans(line, 0) == []

    def test_a_field_is_a_dim_label_and_a_bright_value(self):
        (line,) = browse.field_lines("tap", "acme/quality", 40)
        assert line == [("label", "tap      "), ("field", "acme/quality")]

    def test_a_wrapped_value_stays_in_its_column(self):
        lines = browse.field_lines("tap", "word " * 20, 30)
        assert len(lines) > 1
        col = len(lines[0][0][1])
        assert col == 9
        for ln in lines:
            assert len(browse.line_text(ln)) <= 30
        for ln in lines[1:]:
            assert ln[0] == ("label", " " * col)
            assert not ln[1][1].startswith(" ")

    def test_a_long_key_is_never_truncated(self):
        (line, *_rest) = browse.field_lines("custom-long-key", "v", 40)
        assert line[0] == ("label", "custom-long-key ")

    def test_an_empty_value_still_renders_its_label(self):
        assert browse.field_lines("k", "", 40) == [
            [("label", "k        "), ("field", "")]]

    def test_chips_carry_kind_version_category_and_curated(self):
        e = _e("x", kind="rule", version="2.0", tap="a/b", curated=True)
        chips = browse.chips(e, {"a/b": "qa"})
        assert browse.line_text(chips) == "rule · v2.0 · #qa · ★ curated"
        assert chips[0] == ("kind_rule", "rule")
        assert ("star", "★ curated") in chips
        assert ("category", "#qa") in chips

    def test_chips_leave_out_what_is_unknown(self):
        e = {"name": "x"}
        assert browse.line_text(browse.chips(e)) == "skill"

    def test_the_title_no_longer_carries_the_version(self):
        lines = browse.detail_lines(_e("code-review", version="2.1.0"))
        assert browse.line_text(lines[0]) == "code-review"
        assert "v2.1.0" in browse.line_text(lines[1])
        assert browse.line_role(lines[2]) == "rule"

    def test_frontmatter_does_not_repeat_what_is_shown_above(self):
        e = _e("x", "the description", meta={
            "name": "x", "description": "the description", "version": "1",
            "model": "inherit"})
        text = [t for _r, t in _dl(e)]
        assert sum("the description" in t for t in text) == 1
        assert any(t.startswith("model") for t in text)
        assert not any(t.startswith("name ") for t in text)

    def test_frontmatter_with_only_shown_keys_has_no_section(self):
        e = _e("x", "d", meta={"name": "x", "description": "d"})
        assert not any(t == "FRONTMATTER" for _r, t in _dl(e))

    def test_curated_moved_to_the_chips(self):
        e = _e("x", curated=True)
        text = [t for _r, t in _dl(e)]
        assert any("★ curated" in t for t in text)
        assert not any(t.startswith("curated") for t in text)

    def test_the_chips_line_is_clipped_to_the_pane(self):
        e = _e("x", kind="workflow", version="10.20.30", category="c" * 40,
               curated=True)
        lines = browse.detail_lines(e, width=20)
        assert len(browse.line_text(lines[1])) <= 20

    def test_every_span_carries_a_role(self):
        for line in browse.detail_lines(_e("x", "d", meta={"k": "v"}),
                                        install_to="~/.agents/skills"):
            assert line
            for role, _text in line:
                assert isinstance(role, str) and role


class TestLayoutStatusRow:
    def test_a_default_layout_puts_the_bar_under_the_frame(self):
        lay = browse.layout(100, 24, detail=True)
        assert (lay.body_y, lay.bottom, lay.status_y) == (4, 22, 23)
        assert lay.body_h == 18
        assert lay.has_status

    def test_the_bar_needs_eight_rows(self):
        assert browse.layout(80, 8).has_status
        assert not browse.layout(80, 7).has_status
        assert browse.layout(80, 7).bottom == 6
        assert browse.layout(80, 7).body_h == 2

    def test_a_hand_built_layout_defaults_to_the_last_row(self):
        lay = browse.Layout(w=10, h=10, body_y=4, body_h=5, list_x=1,
                            list_w=8, detail_x=10, detail_w=0)
        assert lay.bottom == 9
        assert not lay.has_status

    def test_a_degenerate_terminal_never_goes_negative(self):
        lay = browse.layout(0, 0)
        assert lay.body_h == 0 and lay.bottom >= -1


# ------------------------------------------------------------------ scoring


def _names(rows):
    return [e["name"] for e in rows]


class TestFold:
    def test_every_separator_becomes_a_space(self):
        assert browse.fold("A-b_c/d.e:f(g h") == "a b c d e f g h"

    def test_positions_survive(self):
        for text in ("code-review", "owner/repo", "x(y)", ""):
            assert len(browse.fold(text)) == len(text)

    def test_the_haystack_is_folded(self):
        assert browse.haystack(_e("Code-Review"), "name") == "code review"
        assert browse.haystack(_e("x", tap="a/b"), "tap") == "a b"


class TestWordStarts:
    def test_a_word_starts_at_the_beginning_or_after_a_space(self):
        assert browse._word_start("ab cd", 0)
        assert browse._word_start("ab cd", 3)
        assert not browse._word_start("ab cd", 1)
        assert not browse._word_start("ab cd", 4)

    @pytest.mark.parametrize("hay,s,i,want", [
        ("code review", "rev", 0, 5),
        ("code review", "cod", 0, 0),
        ("code review", "cod", 1, -1),       # only word starts at or after i
        ("xcode code", "code", 0, 6),        # mid-word occurrences are skipped
        ("ab ab", "ab", 1, 3),
        ("ab ab", "ab", 3, 3),               # a start exactly at i counts
        ("ab ab", "ab", 4, -1),
        ("", "a", 0, -1),
    ])
    def test_next_word_start(self, hay, s, i, want):
        assert browse._next_word_start(hay, s, i) == want


class TestAlignment:
    def test_a_long_name_aligns_to_its_words_not_one_letter_per_word(self):
        # The reported failure: `arch` used to be fished out one letter at a
        # time after taking the `a` of `agent`.
        hay = "bmad agent architect"
        assert browse._align_words("bmadarch", hay) == [0, 1, 2, 3, 11, 12, 13, 14]
        assert browse.match_positions("bmadarch", "bmad-agent-architect") == \
            [0, 1, 2, 3, 11, 12, 13, 14]

    def test_a_run_is_continued_before_any_jump(self):
        assert browse._align_words("cod", "code cod") == [0, 1, 2]

    def test_a_letter_found_nowhere_at_a_word_start_falls_back_to_anywhere(self):
        assert browse._align_words("bs", "brainstorm") == [0, 5]

    def test_no_fit_is_none(self):
        assert browse._align_words("zz", "abc") is None
        assert browse._align_plain("zz", "abc") is None
        assert browse._align_substring("zz", "abc") is None

    def test_plain_alignment_takes_first_occurrences(self):
        assert browse._align_plain("om", "brainstorm") == [7, 9]

    def test_a_substring_prefers_its_word_start_occurrence(self):
        assert browse._align_substring("rev", "prev rev") == [5, 6, 7]
        assert browse._align_substring("rev", "prev") == [1, 2, 3]

    def test_align_takes_the_better_of_its_candidates(self):
        # Word-aware wins here...
        _sc, pos = browse.align("ar", "a b ar")
        assert pos == [4, 5]
        # ...and a substring short-circuits.
        assert browse.align("view", "review")[1] == [2, 3, 4, 5]
        assert browse.align("", "x") is None
        assert browse.align("q", "x") is None

    def test_runs(self):
        assert browse.runs([]) == []
        assert browse.runs([0, 1, 2, 5, 7, 8]) == [(0, 3), (5, 1), (7, 2)]


class TestScoreWeights:
    """Each pair flips if one weight moves the wrong way, so a mutated
    constant cannot survive by leaving every ordering intact."""

    def test_empty_scores_zero(self):
        assert browse.score_positions([], "abc") == 0

    def test_the_exact_arithmetic(self):
        # c(0): word + first; o(1): run; r(5): word, gap 3; v(7): gap 1
        assert browse.score_positions([0, 1, 5, 7], "code review") == \
            (browse._BONUS_WORD + browse._BONUS_FIRST) + browse._BONUS_RUN \
            + (browse._BONUS_WORD - 3) - 1

    def test_the_gap_penalty_is_capped(self):
        near = browse.score_positions([0, 5], "a" * 10)
        far = browse.score_positions([0, 9], "a" * 10)
        assert near == far == browse._BONUS_WORD + browse._BONUS_FIRST \
            - browse._GAP_CAP

    def test_a_shorter_gap_beats_a_longer_one_under_the_cap(self):
        assert browse.score_positions([0, 2], "a" * 5) > \
            browse.score_positions([0, 3], "a" * 5)

    def test_a_word_start_beats_mid_word(self):
        assert browse.score_positions([2], "a bc") > \
            browse.score_positions([3], "a bc")

    def test_the_first_word_beats_a_later_one(self):
        assert browse.score_positions([0], "ab ab") > \
            browse.score_positions([3], "ab ab")

    def test_a_run_beats_a_jump_to_a_word(self):
        # `co` as one run in `code` versus `c` + the `o` of a later word.
        assert browse.score_positions([0, 1], "code o") > \
            browse.score_positions([0, 5], "code o")

    @pytest.mark.parametrize("name", [
        "code-review", "a-code-review", "xcode", "pr review", "code review pro",
        "ccode-c", "c", "review-code", "co-de", "x",
    ])
    @pytest.mark.parametrize("tok", [
        "c", "co", "code", "code review", "e r", "review", "ode", "o", "xc",
        "crv", "zz",
    ])
    def test_the_fast_score_agrees_with_the_alignment(self, name, tok):
        fn, ft = browse.fold(name), browse.fold(tok)
        hit = browse.align(ft, fn)
        assert browse._score(fn, [ft]) == (hit[0] if hit else 0)

    def test_scores_sum_across_tokens(self):
        fn = "code review"
        assert browse._score(fn, ["code", "review"]) == \
            browse._score(fn, ["code"]) + browse._score(fn, ["review"])


def _pieces_reference(needle, hay, min_piece=3):
    """Every split of needle into >= min_piece runs, each starting a word of
    hay after the last — tried by brute force."""
    starts = [i for i in range(len(hay)) if i == 0 or hay[i - 1] == " "]

    def go(j, i):
        if j == len(needle):
            return True
        for cut in range(j + min_piece, len(needle) + 1):
            piece = needle[j:cut]
            for k in starts:
                if k >= i and hay.startswith(piece, k) and go(cut, k + len(piece)):
                    return True
        return False

    return go(0, 0)


class TestTight:
    @pytest.mark.parametrize("needle,hay,want", [
        ("view", "a review tool", True),          # a substring, mid-word too
        ("codrev", "code review", True),          # two word-starting pieces
        ("crv", "create react vite", False),      # one letter a word is thin
        ("coderev", "my code and reviews", True),
        ("codrev", "xcode review", False),        # `cod` must start a word
        ("abcdef", "abx abcd ef", False),         # `ef` is too short a piece
        ("abcdefg", "abx abcd efg", True),        # needs the shorter `abcd`
        ("ab", "a b", False),                     # too short to be pieces
        ("", "anything", True),
    ])
    def test_cases(self, needle, hay, want):
        assert browse.tight(needle, hay) is want

    def test_the_minimum_piece(self):
        assert browse._MIN_PIECE == 3
        assert browse.tight("abcdef", "abc def")
        assert not browse.tight("abcde", "abc de")

    def test_it_agrees_with_a_brute_force_reference(self):
        hays = ["code review tool", "abx abcd efg", "re rev review",
                "aaa aaa aaa", "test driven development", "x"]
        needles = ["codrev", "abcdefg", "rerev", "aaaaaa", "testdev",
                   "tesdridev", "revrev", "aaaaaaaaa", "xyz", "coder"]
        for h in hays:
            for n in needles:
                if n in h:
                    continue
                assert browse._pieces(n, h) == _pieces_reference(n, h), (n, h)

    def test_repeated_words_do_not_blow_up(self):
        # Memoised: without it this is exponential in the word count.
        hay = " ".join(["abc"] * 60) + " zzz"
        assert not browse.tight("abcabcabcabcabcabcq", hay)


class TestTokenMatching:
    def test_loose_text_per_scope(self):
        assert browse.loose_text("name", "hay", "nm") == "hay"
        assert browse.loose_text("tap", "hay", "nm") == "hay"
        assert browse.loose_text("category", "hay", "nm") == "hay"
        assert browse.loose_text("all", "hay", "nm") == "nm"
        assert browse.loose_text("description", "hay", "nm") is None

    def test_a_substring_always_matches(self):
        assert browse.token_matches("view", "a review", None)

    def test_not_a_subsequence_never_matches(self):
        assert not browse.token_matches("zq", "a review", "a review")

    def test_a_scattered_subsequence_needs_the_loose_text(self):
        hay = "create react vite"
        assert browse.token_matches("crv", hay, hay)
        assert not browse.token_matches("crv", hay, None)
        assert not browse.token_matches("crv", hay, "other")

    def test_word_pieces_match_without_the_loose_text(self):
        assert browse.token_matches("codrev", "code review", None)


class TestThinSpread:
    """The user-visible behaviour: letters spread one per word stop matching
    prose, and stop outranking the name the user was typing."""

    def test_a_scattered_description_match_is_dropped_in_all(self):
        rows = [_e("alpha", "create a react based vite starter")]
        assert not browse.matches(rows, "crv", "all")

    def test_a_scattered_name_match_survives_in_all(self):
        rows = [_e("create-react-vite", "")]
        assert _names(browse.matches(rows, "crv", "all")) == \
            ["create-react-vite"]

    def test_the_description_scope_is_strict(self):
        rows = [_e("x", "create react vite"), _e("y", "code review notes")]
        assert _names(browse.matches(rows, "crv", "description")) == []
        assert _names(browse.matches(rows, "codrev", "description")) == ["y"]

    def test_tap_and_category_keep_acronyms(self):
        rows = [_e("x", tap="anthropics/skills", category="data-science")]
        assert browse.matches(rows, "as", "tap")
        assert browse.matches(rows, "dsci", "category")

    def test_scope_is_required(self):
        with pytest.raises(TypeError):
            browse.matches_indexed(browse.index_entries(CORPUS, "all"), "x")  # type: ignore[call-arg]

    def test_the_index_carries_the_folded_name(self):
        (_entry, hay, fname), = browse.index_entries([_e("Code-Review", "d")], "all")
        assert fname == "code review"
        assert hay.startswith("code review d")

    def test_an_empty_query_returns_every_row(self):
        idx = browse.index_entries(CORPUS, "all")
        assert browse.matches_indexed(idx, " ", "all") == CORPUS


class TestScoredRanking:
    def test_the_word_aligned_name_outranks_the_scattered_one(self):
        rows = [_e("bagisto-datagrid-development", ""), _e("tdd-developer", "")]
        assert _names(browse.matches(rows, "tdddev", "all"))[0] == \
            "tdd-developer"

    def test_a_mid_word_substring_does_not_jump_the_tier(self):
        rows = [_e("accrual-schedule", ""), _e("cc-review", "")]
        assert browse.match_tier("accrual-schedule", ["ccr"]) == browse.FUZZY
        assert browse.match_tier("cc-review", ["cc"]) == browse.PREFIX
        assert _names(browse.matches(rows, "ccr", "all")) == \
            ["cc-review", "accrual-schedule"]

    def test_a_word_start_substring_is_the_substring_tier(self):
        assert browse.match_tier("my-code-review", ["review"]) == \
            browse.SUBSTRING
        assert browse.match_tier("prereview", ["review"]) == browse.FUZZY

    def test_within_a_tier_the_better_alignment_leads(self):
        rows = [_e("gxixtx-wxf", ""), _e("git-workflow", "")]
        assert _names(browse.rank(rows, "gitwf")) == ["git-workflow",
                                                      "gxixtx-wxf"]

    def test_a_shorter_name_breaks_a_score_tie(self):
        rows = [_e("code-review-for-monorepos", ""), _e("code-review-pro", "")]
        assert _names(browse.rank(rows, "code review")) == \
            ["code-review-pro", "code-review-for-monorepos"]

    def test_rows_the_name_did_not_score_keep_catalogue_order(self):
        rows = [_e("zz-long-name", "code review"), _e("aa", "code review")]
        assert _names(browse.rank(rows, "code review")) == ["zz-long-name", "aa"]
        assert browse.rank_key("aa", ["code"]) == (browse.ELSEWHERE, 0, 0)

    def test_a_partial_name_match_outranks_a_description_only_one(self):
        rows = [_e("other", "code review"), _e("code-helper", "a review")]
        assert _names(browse.matches(rows, "code review", "all")) == \
            ["code-helper", "other"]

    def test_the_rank_key_shape(self):
        tier, neg, length = browse.rank_key("code-review", ["code"])
        assert tier == browse.PREFIX and neg < 0 and length == 11

    def test_highlighting_follows_the_ranking_alignment(self):
        assert browse.highlight_positions("arch", "bmad-agent-architect") == \
            {11, 12, 13, 14}
        assert browse.highlight_positions("code rev", "Code-Review") == \
            {0, 1, 2, 3, 5, 6, 7}


# ------------------------------------------------------------------ categories


class TestCategories:
    ROWS: typing.ClassVar[list[dict]] = [
        _e("a", category="testing"), _e("b", category="Testing"),
        _e("c", tap="x/y"), _e("d", tap="p/q"), _e("e", category="ai")]
    CATS: typing.ClassVar[dict[str, str]] = {"x/y": "devops"}

    def test_category_of_lowercases_and_names_the_empty_one(self):
        assert browse.category_of(self.ROWS[1]) == "testing"
        assert browse.category_of(self.ROWS[2], self.CATS) == "devops"
        assert browse.category_of(self.ROWS[3], self.CATS) == \
            browse.UNCATEGORIZED

    def test_counts_largest_first_then_by_name(self):
        assert browse.category_counts(self.ROWS, self.CATS) == [
            ("testing", 2), ("ai", 1), ("devops", 1),
            (browse.UNCATEGORIZED, 1)]

    def test_counts_add_up_to_the_total(self):
        assert sum(n for _c, n in browse.category_counts(self.ROWS)) == \
            len(self.ROWS)

    def test_in_category(self):
        assert browse.in_category(self.ROWS[0], "TESTING ")
        assert browse.in_category(self.ROWS[2], "devops", self.CATS)
        assert not browse.in_category(self.ROWS[2], "devops")
        assert browse.in_category(self.ROWS[3], browse.UNCATEGORIZED)
        assert not browse.in_category(self.ROWS[4], "testing")

    def test_no_category_is_no_filter(self):
        assert all(browse.in_category(e, "") for e in self.ROWS)


class TestPicker:
    def test_rows_lead_with_everything_then_sort_a_to_z(self):
        rows = browse.picker_rows(TestCategories.ROWS, TestCategories.CATS)
        assert rows == [("", 5), ("ai", 1), ("devops", 1), ("testing", 2),
                        (browse.UNCATEGORIZED, 1)]

    def test_rows_by_count_still_pin_uncategorized_last(self):
        rows = browse.picker_rows(TestCategories.ROWS, TestCategories.CATS,
                                  order="count")
        assert rows == [("", 5), ("testing", 2), ("ai", 1), ("devops", 1),
                        (browse.UNCATEGORIZED, 1)]

    def test_it_opens_on_the_active_category(self):
        rows = [("", 9), ("testing", 5), ("ai", 4)]
        assert browse.picker_index(rows, "AI") == 2
        assert browse.picker_index(rows, "") == 0
        assert browse.picker_index(rows, "gone") == 0

    @pytest.mark.parametrize("sel,n,visible,want", [
        (0, 5, 10, 0),        # everything fits
        (0, 30, 10, 0),
        (5, 30, 10, 0),       # centred, clamped at the top
        (15, 30, 10, 10),     # centred
        (29, 30, 10, 20),     # clamped at the bottom
        (3, 30, 0, 0),        # no room
        (10, 10, 10, 0),      # exactly fits
    ])
    def test_top(self, sel, n, visible, want):
        assert browse.picker_top(sel, n, visible) == want

    def test_line_layout(self):
        line = browse.picker_line("testing", 1234, 20, True)
        assert line == "● testing      1,234"
        assert len(line) == 20
        assert browse.picker_line("", 5, 10, False) == "  all    5"

    def test_a_long_label_is_cut_before_the_count(self):
        line = browse.picker_line("a" * 40, 12, 16, False)
        assert line.endswith(" 12") and len(line) == 16

    def test_a_zero_width_line_is_empty(self):
        assert browse.picker_line("x", 1, 0, False) == ""

    def test_query_chip(self):
        assert browse.query_chip("testing") == "#testing"
        assert browse.query_chip("") == ""

    def test_the_picker_has_a_mode_and_cancels_rather_than_quits(self):
        assert browse.MODES["picker"] == "FILTER"
        assert browse.FACET_MODES == {"category": "CATEGORY", "tap": "TAP",
                                      "kind": "KIND"}
        assert browse.HINTS["picker"] == (
            ("a-z", "filter"), ("↑↓", "move"), ("↵", "apply"),
            ("⇥", "facet"), ("^T", "sort"), ("esc", "cancel"))
        assert "picker" not in browse.PANES

    def test_the_search_and_list_bars_advertise_every_facet_key(self):
        for pane in ("search", "list"):
            for facet, key in browse.FACET_KEYS.items():
                assert (key, facet) in browse.HINTS[pane]
        assert browse.FACET_KEYS == {"category": "^G", "tap": "^R",
                                     "kind": "^K"}

    def test_the_mode_override_names_the_facet_in_the_pill(self):
        spans = browse.status_spans("picker", 80, mode="TAP")
        assert spans[0] == (0, "pill", " TAP ")
        assert browse.status_spans("picker", 80)[0] == (0, "pill", " FILTER ")


class TestEmptyLinesCategory:
    def test_the_category_is_named_with_the_query(self):
        head = browse.empty_lines("zz", "name", category="testing")[0][1]
        assert head == "○ no matches for 'zz' in name · #testing"

    def test_an_empty_category_says_so(self):
        assert browse.empty_lines("", "all", category="testing")[0][1] == \
            "○ nothing in #testing"


# ------------------------------------------------------------------ facets


_F = [_e("a", tap="Acme/Quality", category="testing"),
      _e("b", tap="acme/quality", kind="rule", category="Testing"),
      _e("c", tap="beta/ai", kind="workflow", category="ai"),
      _e("d", tap="", kind="", category="")]


class TestFacetValues:
    def test_each_facet_files_an_entry_lowercased(self):
        assert [browse.facet_value(e, "category") for e in _F] == [
            "testing", "testing", "ai", browse.UNCATEGORIZED]
        assert [browse.facet_value(e, "tap") for e in _F] == [
            "acme/quality", "acme/quality", "beta/ai", browse.UNTAPPED]
        assert [browse.facet_value(e, "kind") for e in _F] == [
            "skill", "rule", "workflow", "skill"]

    def test_an_unknown_facet_files_nothing(self):
        assert browse.facet_value(_F[0], "colour") == ""

    def test_a_blank_kind_is_a_skill(self):
        assert browse.facet_value(_e("w", kind="  "), "kind") == "skill"
        assert browse.facet_value(_e("w", tap="  "), "tap") == browse.UNTAPPED

    def test_category_uses_the_tap_fallback(self):
        e = _e("z", tap="p/q", category="")
        assert browse.facet_value(e, "category", {"p/q": "DevOps"}) == "devops"

    def test_counts(self):
        assert browse.facet_counts(_F, "tap") == {
            "acme/quality": 2, "beta/ai": 1, browse.UNTAPPED: 1}

    def test_next_facet_wraps_both_ways(self):
        assert browse.next_facet("category") == "tap"
        assert browse.next_facet("kind") == "category"
        assert browse.next_facet("category", -1) == "kind"
        assert browse.next_facet("bogus") == "category"


class TestNarrow:
    def test_filters_and_together(self):
        got = browse.narrow(_F, {"category": "testing", "kind": "rule"})
        assert [e["name"] for e in got] == ["b"]

    def test_values_are_normalised_once(self):
        got = browse.narrow(_F, {"tap": " ACME/Quality ", "kind": ""})
        assert [e["name"] for e in got] == ["a", "b"]

    def test_no_filter_keeps_everything_as_a_new_list(self):
        got = browse.narrow(_F, dict.fromkeys(browse.FACETS, ""))
        assert got == _F and got is not _F
        assert browse.narrow(_F, None) == _F

    def test_an_unknown_facet_filter_keeps_nothing(self):
        assert browse.narrow(_F, {"colour": "red"}) == []

    def test_the_has_none_values_are_filters_too(self):
        assert [e["name"] for e in
                browse.narrow(_F, {"tap": browse.UNTAPPED})] == ["d"]


class TestSortFacetRows:
    ROWS: typing.ClassVar[list[tuple[str, int]]] = [
        ("web", 1), (browse.UNCATEGORIZED, 50), ("AI", 3), ("ai", 3),
        ("data", 9), ("Design", 9)]

    def test_a_to_z_is_case_insensitive_with_the_none_value_last(self):
        assert browse.sort_facet_rows(self.ROWS, "category") == [
            ("AI", 3), ("ai", 3), ("data", 9), ("Design", 9), ("web", 1),
            (browse.UNCATEGORIZED, 50)]

    def test_by_count_breaks_ties_by_name(self):
        assert browse.sort_facet_rows(self.ROWS, "category", "count") == [
            ("data", 9), ("Design", 9), ("AI", 3), ("ai", 3), ("web", 1),
            (browse.UNCATEGORIZED, 50)]

    def test_only_a_facets_own_none_value_is_pinned(self):
        rows = [(browse.UNCATEGORIZED, 1), ("a", 1), (browse.UNTAPPED, 1)]
        assert browse.sort_facet_rows(rows, "tap") == [
            ("a", 1), (browse.UNCATEGORIZED, 1), (browse.UNTAPPED, 1)]
        assert browse.sort_facet_rows(rows, "kind") == [
            ("a", 1), (browse.UNCATEGORIZED, 1), (browse.UNTAPPED, 1)]
        assert browse.sort_facet_rows(rows, "category") == [
            ("a", 1), (browse.UNTAPPED, 1), (browse.UNCATEGORIZED, 1)]

    def test_order_label(self):
        assert browse.order_label("az") == "A–Z"
        assert browse.order_label("count") == "by count"
        assert browse.order_label("x") == "x"


def _pk(active="", order="az", **kw):
    counts = [("testing", 4), ("ai", 2), ("data-science", 3),
              ("devops", 1), (browse.UNCATEGORIZED, 5)]
    p = browse.open_picker("category", counts, 15, active, order)
    return dataclasses.replace(p, **kw) if kw else p


def _step(p, *keys):
    act = None
    for k in keys:
        p, act = browse.picker_step(p, k, page=2)
    return p, act


class TestPickerState:
    def test_opens_sorted_on_the_value_in_force(self):
        p = _pk(" DevOps ")
        assert browse.picker_visible(p) == [
            ("", 15), ("ai", 2), ("data-science", 3), ("devops", 1),
            ("testing", 4), (browse.UNCATEGORIZED, 5)]
        assert p.active == "devops"
        assert p.sel == 3 and browse.picker_value(p) == "devops"
        assert _pk().sel == 0 and browse.picker_value(_pk()) == ""

    def test_typing_filters_with_the_label_matcher_and_hides_all(self):
        p, act = _step(_pk(), "d", "s")
        assert act is None and p.query == "ds"
        # A subsequence is enough in a label, as in the name scope: `ds` is
        # data-science's initials and also fits d-evop-s. `all` is gone while
        # a query is typed.
        assert browse.picker_visible(p) == [("data-science", 3), ("devops", 1)]
        assert p.sel == 0

    def test_the_all_row_leaves_while_a_query_is_typed(self):
        p, _ = _step(_pk(), "a")
        assert ("", 15) not in browse.picker_visible(p)
        assert browse.picker_value(p) == "ai"

    def test_tokens_and_together(self):
        p, _ = _step(_pk(), *"dat sci")
        assert browse.picker_visible(p) == [("data-science", 3)]

    def test_no_match_leaves_nothing_and_enter_does_nothing(self):
        p, _ = _step(_pk(), "z", "z")
        assert browse.picker_visible(p) == []
        assert browse.picker_value(p) is None
        assert browse.picker_step(p, "enter") == (p, None)

    def test_backspace_edits_and_an_empty_query_returns_to_the_active_row(
            self):
        p, _ = _step(_pk("testing"), "a", "i")
        assert p.query == "ai" and p.sel == 0
        p, _ = _step(p, "backspace")
        assert p.query == "a"
        p, _ = _step(p, "backspace")
        assert p.query == "" and browse.picker_value(p) == "testing"
        p, act = _step(p, "backspace")          # nothing left to delete
        assert p.query == "" and act is None

    def test_esc_clears_a_query_first_then_cancels(self):
        p, act = _step(_pk("ai"), "t", "e", "esc")
        assert act is None and p.query == ""
        assert browse.picker_value(p) == "ai"
        assert browse.picker_step(p, "esc") == (p, "cancel")

    def test_moves_clamp_to_the_visible_rows(self):
        p = _pk()
        assert _step(p, "up")[0].sel == 0
        assert _step(p, "down", "down", "down")[0].sel == 3
        assert _step(p, "pgdn")[0].sel == 2
        assert _step(p, "pgdn", "pgdn", "pgdn", "pgdn")[0].sel == 5
        assert _step(p, "pgdn", "pgdn", "pgup")[0].sel == 2
        # `d` keeps data-science, devops and uncategorized (a label takes
        # any subsequence), so three downs clamp on the third.
        q, _ = _step(p, "d")
        assert len(browse.picker_visible(q)) == 3
        assert _step(q, "down", "down", "down")[0].sel == 2
        z, _ = _step(p, "z", "z")
        assert _step(z, "down")[0].sel == 0

    def test_enter_applies_the_selected_value(self):
        p, act = _step(_pk(), "d", "e", "v", "enter")
        assert act == "apply" and browse.picker_value(p) == "devops"
        p, act = _step(_pk("ai"), "up", "enter")
        assert act == "apply" and browse.picker_value(p) == ""

    def test_sort_toggles_and_the_selection_follows_its_value(self):
        p, act = _step(_pk("ai"), "sort")
        assert act is None and p.order == "count"
        assert browse.picker_visible(p) == [
            ("", 15), ("testing", 4), ("data-science", 3), ("ai", 2),
            ("devops", 1), (browse.UNCATEGORIZED, 5)]
        assert browse.picker_value(p) == "ai" and p.sel == 3
        p, _ = _step(p, "sort")
        assert p.order == "az" and browse.picker_value(p) == "ai"
        assert _step(_pk(order="bogus"), "sort")[0].order == "az"

    def test_sort_under_a_query_keeps_the_query(self):
        p, _ = _step(_pk(), "d", "down", "sort")
        assert p.query == "d" and p.order == "count"
        assert browse.picker_value(p) == "devops"

    def test_facet_keys_switch_or_close(self):
        assert _step(_pk(), "facet:category")[1] == "cancel"
        assert _step(_pk(), "facet:tap")[1] == "facet:tap"
        assert _step(_pk(), "next")[1] == "next"
        assert _step(_pk(), "prev")[1] == "prev"

    def test_an_unknown_key_changes_nothing(self):
        p = _pk()
        assert browse.picker_step(p, "f12") == (p, None)
        assert browse.picker_step(p, "\x01") == (p, None)

    def test_space_types_into_the_query(self):
        assert _step(_pk(), "d", " ", "s")[0].query == "d s"


class TestPickerDrawingHelpers:
    def test_marks_offset_past_the_dot_lead(self):
        # "  devops ... 1": label starts at column 2.
        assert browse.picker_marks("dev", "devops", 1, 20) == [2, 3, 4]
        assert browse.picker_marks("", "devops", 1, 20) == []

    def test_marks_light_the_all_label(self):
        assert browse.picker_marks("al", "", 5, 20) == [2, 3]

    def test_marks_stop_at_the_cut(self):
        # width 10, count "12": room = 10 - 3 - 2 = 5 label columns.
        assert browse.picker_marks("abcdefg", "abcdefg", 12, 10) == [
            2, 3, 4, 5, 6]
        assert browse.picker_line("abcdefg", 12, 10, False) == "  abcde 12"

    def test_tail_counts_values_not_the_all_row(self):
        assert browse.picker_tail(_pk()) == "5/5"
        assert browse.picker_tail(_step(_pk(), "d", "e", "v")[0]) == "1/5"
        assert browse.picker_tail(_step(_pk(), "z", "z")[0]) == "0/5"

    def test_empty_lines(self):
        assert browse.picker_empty(" zz  q ") == [
            ("muted", "○ no match for 'zz q'"),
            ("muted", "→ backspace edits · esc clears")]

    def test_chips_read_with_the_colour_off(self):
        f = {"category": "testing", "tap": "acme/quality", "kind": "rule"}
        assert browse.query_chips(f) == ["#testing", "@acme/quality",
                                         "kind:rule"]
        assert browse.query_chips({"kind": "rule", "tap": ""}) == ["kind:rule"]
        assert browse.query_chips(None) == []
        assert browse.facet_chip("tap", "") == ""
        assert browse.facet_chip("colour", "red") == "colour:red"

    def test_empty_lines_name_every_filter(self):
        f = {"category": "testing", "tap": "", "kind": "rule"}
        assert browse.empty_lines("zz", "all", filters=f)[0][1] == \
            "○ no matches for 'zz' in all · #testing kind:rule"
        assert browse.empty_lines("", "all", filters=f)[0][1] == \
            "○ nothing in #testing kind:rule"
        assert browse.empty_lines("", "all", filters={})[0][1] == \
            "○ nothing here"
