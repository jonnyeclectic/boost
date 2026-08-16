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
        assert any("22379" in s and "hidden" in s for s in painted)

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

    def test_a_query_with_no_matches_renders_an_empty_list(self):
        g = _render(query="zzzzz")
        lay = browse.layout(100, 24, detail=True)
        body = "".join(row[1:lay.list_w] for row in g[lay.body_y:-1])
        assert not body.strip()
