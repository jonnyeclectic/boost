# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a `whole` column is shown whole or not at all.

Just before `out.table` drops a column it shrinks the widest one that can
still shrink, down to `_MIN_COL`. For prose that is the right trade. For an
identifier it is not: `bmad-r…` reads like a hook name and is not one
`boost hooks remove -n` accepts, and `brainstorm…` is not a skill any command
takes. `keep=` cannot say "may drop, never shrink" — it means never drop
either, and two such columns together outgrow the pane with nothing left to
give. `whole=` is the third class: never shrunk, dropped right to left like
any other column.
"""
from __future__ import annotations

import pytest

from boost_cli.core import output

NAMES = ("bmad", "bmad-route", "lint-on-edit")
HOOK_HEADERS = ("name", "host", "scope", "event", "matcher", "command")
HOOK_ROWS = [
    ("bmad", "claude", "global", "SessionStart", "startup|resume|clear|compact",
     "boost bmad orient --scope global || true"),
    ("bmad-route", "claude", "global", "UserPromptSubmit", "-",
     "boost bmad route --scope global || true"),
    ("lint-on-edit", "claude", "global", "PreToolUse", "Edit|Write",
     "ruff check ."),
]


def _render(monkeypatch, capsys, cols, **kw) -> list[str]:
    monkeypatch.setenv("COLUMNS", str(cols))
    output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",), **kw)
    return capsys.readouterr().out.splitlines()


class TestFitColumnsWhole:
    """The class on its own, away from the rendering."""

    def test_a_whole_column_is_not_shrunk_a_neighbour_goes_instead(self):
        # Without `whole` the 20-wide column absorbs the deficit at 13.
        assert output._fit_columns([20, 10], [False, False], avail=25) == \
               ([0, 1], [13, 10])
        # Marked whole it cannot, and its neighbour cannot reach the pane at
        # the floor (20 + 2 + 7 = 29), so the neighbour is dropped.
        assert output._fit_columns([20, 10], [False, False], avail=25,
                                   whole=[0]) == ([0], [20])

    def test_the_shrink_lands_on_the_other_text_columns(self):
        # Room to shrink elsewhere: the whole column keeps every cell and the
        # other text column pays the whole deficit.
        assert output._fit_columns([12, 20], [False, False], avail=30,
                                   whole=[0]) == ([0, 1], [12, 16])

    def test_a_whole_column_drops_where_keep_would_overflow(self):
        # The card's shape: an identifier beside a kept command. Unmarked,
        # the identifier is squeezed to 8 to stay (the `bmad-r…` defect)...
        assert output._fit_columns([12, 30], [False, False], avail=40,
                                   protected=[1]) == ([0, 1], [8, 30])
        # ...marked whole it goes, and the kept column stands alone. Were it
        # `keep` too, both would stay at full width and overflow the pane.
        assert output._fit_columns([12, 30], [False, False], avail=40,
                                   protected=[1], whole=[0]) == ([1], [30])

    def test_drop_order_is_right_to_left_whole_or_not(self):
        # Three 10-wide columns into 25: one must go. The rightmost does,
        # even though it is the whole one.
        assert output._fit_columns([10, 10, 10], [False] * 3, avail=25,
                                   whole=[2]) == ([0, 1], [10, 10])

    def test_the_last_whole_column_overflows_rather_than_clips(self):
        # Unmarked, the floor stops applying and the survivor clips to 5.
        assert output._fit_columns([40, 40], [False, False], avail=5) == \
               ([0], [5])
        # Whole means whole: it overflows unshrunk, as a kept column does.
        assert output._fit_columns([40, 40], [False, False], avail=5,
                                   whole=[0]) == ([0], [40])

    def test_an_empty_whole_column_still_goes_first(self):
        # Empty carries nothing to clip; it goes before any data column, which
        # `keep` would have prevented.
        assert output._fit_columns([3, 0, 3], [False] * 3, avail=9,
                                   whole=[1]) == ([0, 2], [3, 3])

    def test_a_row_that_fits_is_untouched(self):
        assert output._fit_columns([12, 30], [False, False], avail=44,
                                   protected=[1], whole=[0]) == \
               ([0, 1], [12, 30])


class TestTableWhole:
    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    @pytest.mark.parametrize("cols", range(40, 101))
    def test_a_shown_name_is_never_clipped(self, monkeypatch, capsys, cols):
        lines = _render(monkeypatch, capsys, cols, whole=("name",))
        header = lines[0].split()
        if "name" not in header:
            return
        assert header[0] == "name"
        assert [ln.split()[0] for ln in lines[1:]] == list(NAMES), \
            (cols, lines)

    def test_unmarked_the_same_pane_clips_the_name(self, monkeypatch, capsys):
        # The defect, measured: at 65 the name column was squeezed to 7.
        lines = _render(monkeypatch, capsys, 65)
        assert [ln.split()[0] for ln in lines[1:]] == \
               ["bmad", "bmad-r…", "lint-o…"]

    def test_marked_the_same_pane_shows_it_whole(self, monkeypatch, capsys):
        lines = _render(monkeypatch, capsys, 65, whole=("name",))
        assert lines[0].split() == ["name", "host", "command"]
        assert [ln.split()[0] for ln in lines[1:]] == list(NAMES)
        assert max(len(ln) for ln in lines) <= 65

    def test_a_column_index_resolves_like_a_header(self, monkeypatch, capsys):
        by_name = _render(monkeypatch, capsys, 65, whole=("name",))
        by_index = _render(monkeypatch, capsys, 65, whole=(0,))
        assert by_index == by_name

    @pytest.mark.parametrize("cols", [None, 110, 250])
    def test_a_pane_that_fits_is_byte_identical(self, monkeypatch, capsys,
                                                cols):
        if cols is None:
            monkeypatch.delenv("COLUMNS", raising=False)
        else:
            monkeypatch.setenv("COLUMNS", str(cols))
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",))
        before = capsys.readouterr().out
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",),
                     whole=("name",))
        assert capsys.readouterr().out == before
