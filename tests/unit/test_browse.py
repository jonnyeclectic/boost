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

import typing

import pytest

from boost_cli.core import browse


def _e(name, description="", tap="o/r", kind="skill", version="1.0.0", **kw):
    d = {"name": name, "description": description, "tap": tap, "kind": kind,
         "version": version, "curated": False, "rel_dir": name,
         "skill_md": "%s/SKILL.md" % name, "meta": {}}
    d.update(kw)
    return d


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
                assert browse.matches_indexed(idx, q) == \
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
        text = " ".join(t for _r, t in browse.detail_lines(
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
        text = " ".join(t for _role, t in browse.detail_lines(e))
        for fact in ("code-review", "2.1.0", "acme/quality", "Review a PR"):
            assert fact in text, fact

    def test_frontmatter_keys_are_included(self):
        """"the entire frontmatter users can scroll through" — so an unknown
        key must survive rather than being filtered to a known allowlist."""
        e = _e("x", meta={"license": "MIT", "custom-key": "custom-value"})
        text = " ".join(t for _role, t in browse.detail_lines(e))
        assert "license" in text and "MIT" in text
        assert "custom-key" in text and "custom-value" in text

    def test_a_list_valued_key_renders_readably(self):
        e = _e("x", meta={"tags": ["a", "b", "c"]})
        text = " ".join(t for _role, t in browse.detail_lines(e))
        assert "a" in text and "b" in text and "c" in text
        assert "['a'" not in text, "a Python repr is not a rendering"

    def test_every_line_carries_a_role_for_theming(self):
        for role, _text in browse.detail_lines(_e("x", "d")):
            assert isinstance(role, str) and role

    def test_it_never_raises_on_a_sparse_entry(self):
        assert browse.detail_lines({"name": "bare"})

    def test_long_values_are_wrapped_to_the_pane_width(self):
        e = _e("x", "word " * 80)
        lines = browse.detail_lines(e, width=30)
        assert all(len(t) <= 30 for _r, t in lines), "detail text must wrap"

    def test_installed_state_is_surfaced_when_known(self):
        e = _e("code-review")
        text = " ".join(t for _r, t in browse.detail_lines(e, installed=True))
        assert "installed" in text.lower()


def _render(w=100, h=24, query="", scope="all", focus="list", sel=0,
            detail=True, entries=None):
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
        assert g[-1][0] == "╰" and g[-1][-1] == "╯"

    def test_both_side_borders_are_drawn_on_every_body_row(self):
        """The right border sat in the last column, which the old clip bound
        made unwritable — the frame drew with three sides."""
        g = _render()
        sep = browse.layout(100, 24, detail=True).body_y - 1
        for y in range(1, len(g) - 1):
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
        assert g[-1][x] == "┴"
        for y in range(lay.body_y, len(g) - 1):
            assert g[y][x] == "│", "divider broken at row %d" % y

    @pytest.mark.parametrize("w,h", [(60, 20), (80, 24), (100, 30), (160, 50)])
    def test_every_row_is_exactly_the_terminal_width(self, w, h):
        for row in _render(w=w, h=h):
            assert len(row) == w

    def test_the_title_appears_in_the_top_rule(self):
        assert "boost browse" in _render()[0]

    def test_the_help_row_never_ends_mid_word(self):
        """A clipped hint ends on `esc`, which reads as a key not a fragment."""
        for w in (56, 60, 70, 80, 100, 140):
            lay = browse.layout(w, 24, detail=True)
            help_row = _render(w=w, h=24)[lay.body_y - 2]
            assert "esc" not in help_row or "esc quit" in help_row, w


class TestScopeRadios:
    """Item 8 — the search-scope toggles are visible and show which is on."""

    def test_exactly_one_radio_is_filled(self):
        row = _render(scope="name")[2]
        assert row.count("(●)") == 1
        assert row.count("( )") == len(browse.SCOPES) - 1

    def test_the_filled_radio_tracks_the_active_scope(self):
        for scope in browse.SCOPES:
            row = _render(scope=scope)[2]
            i = row.index("(●)")
            assert row[i + 4:].startswith(browse.scope_label(scope))


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
            lines = browse.detail_lines(CORPUS[0], width=40, installed=False,
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
        assert lines[1][1] == "→ backspace widens · ^T scope"
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


class TestSessionChipInTheFrame:
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
        discovery._draw_frame(put, _Theme(), lay, "list", summary=summary)
        return ["".join(r) for r in grid], lay

    def test_the_chip_lands_in_the_bottom_rule(self):
        g, _lay = self._grid(("ok_line", "✓ 2 installed"))
        assert "✓ 2 installed" in g[-1]
        assert g[-1][0] == "╰" and g[-1][-1] == "╯"

    def test_no_summary_keeps_the_idle_rule_byte_identical(self):
        g, lay = self._grid(None)
        expected = list("╰" + "─" * (lay.w - 2) + "╯")
        expected[lay.detail_x - 1] = "┴"
        assert g[-1] == "".join(expected)

    def test_the_chip_never_overwrites_the_divider_tee(self):
        g, lay = self._grid(("failed", "✗ " + "x" * 200))
        assert g[-1][lay.detail_x - 1] == "┴"
        assert g[-1][-1] == "╯"


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
        # tap badge, whose closing bracket sits one column short of the
        # divider gap.
        assert row[lay.list_x + lay.list_w - 2] == "]"
        assert "[acme/quality]" in row

    def test_the_kind_badge_text_matches_the_search_vocabulary(self):
        from boost_cli.core import output as out
        g = _render(query="rag")
        assert "[rule]" in "\n".join(g)
        assert out.kind_label("rule") == "[rule]"
