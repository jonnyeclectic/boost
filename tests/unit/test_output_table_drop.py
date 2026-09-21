# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a narrow pane drops a table column instead of rendering it as a
bare ellipsis.

`_fit_widths` floored at 1, and `_clip_visible(cell, 1)` is just "…", so at
COLUMNS=80 `boost hooks list` rendered five of its six columns — header
included — as a placeholder that carries nothing, and the row was *still* over
the pane (measured 87 piped / 92 colored against an 80-column target). Dropping
the column and its separator is the only move that recovers the width when the
dead columns are leading ones: `.rstrip()` cannot reach a separator that has
data to its right.

Widths here are measured the way a terminal draws them — ANSI stripped, wide
characters counted as two — via :func:`output.visible_len`.
"""
from __future__ import annotations

import io
import re

import pytest

from boost_cli.core import output

# The shape `boost hooks list` had when this fitter was written: six columns,
# the one the user came to read is the *last* and is the protected one, so
# every dead column is a leading one. Rows are a sandbox ~/.claude/settings.json
# carrying two boost-managed hooks. `hooks list` itself now leads with `name`
# (see tests/functional/test_cli_hooks.py::TestListColumnOrder); this fixture
# keeps the old order because it tests the fitter, not that command.
HOOK_HEADERS = ("host", "scope", "event", "name", "matcher", "command")
HOOK_ROWS = [
    ("claude", "global", "SessionStart", "bmad", "startup|resume|clear",
     "boost bmad orient --quiet --and-then-report-status-to-the-user"),
    ("claude", "global", "PreToolUse", "guard", "Bash",
     'boost check --strict --json | jq -r ".issues[] | .msg" | head -20 | sort'),
]

# The shape from `boost taps` (commands/taps.py:362): NAME is protected, ITEMS
# is numeric, UPDATED is the YYYY-MM-DD `_tap_updated_display` renders, the
# curated column is empty — header included — whenever no tap is curated (the
# 20-repo eval corpus has none), and URL is the chrome.
TAP_HEADERS = ("NAME", "ITEMS", "UPDATED", "", "URL")
TAP_ROWS = [
    ("anthropics/skills", "20", "2026-09-20", "",
     "https://github.com/anthropics/skills"),
    ("composio-community/awesome-codex-skills", "880", "2026-09-18", "",
     "https://github.com/composio-community/awesome-codex-skills"),
    ("minio/skills", "4", "2026-08-31", "",
     "https://github.com/minio/skills"),
]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def widths(printed: str) -> list[int]:
    return [output.visible_len(line) for line in printed.splitlines()]


def updated_cell(printed: str) -> str:
    """The first tap row's UPDATED cell as drawn, or "" when the column went.

    UPDATED is 10 wide (its dates), so the cell's length *is* the column's
    width: a clipped date is exactly as long as the column it was clipped to.
    """
    header, first = _ANSI.sub("", printed).splitlines()[:2]
    if "UPDATED" not in header.split():
        return ""
    return re.search(r"2026-[0-9-]*…?", first).group()


def data_columns(printed: str) -> int:
    """How many of the taps table's non-empty columns survived."""
    header = _ANSI.sub("", printed).splitlines()[0].split()
    return sum(h in header for h in ("NAME", "ITEMS", "UPDATED", "URL"))


class TestTableDropsUnshowableColumns:
    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    def test_hooks_shape_at_eighty_drops_the_leading_dead_columns(
            self, capsys, monkeypatch):
        # Measured before this behaviour existed: five bare "…" cells per row,
        # header included, and a widest line of 87 against COLUMNS=80. Now the
        # four middle columns go and `host` — which already fits — stays.
        monkeypatch.setenv("COLUMNS", "80")
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",))
        printed = capsys.readouterr().out
        assert "…" not in printed        # no column survives as a placeholder
        for row in HOOK_ROWS:
            assert row[5] in printed     # the command is intact and copyable
        assert printed.splitlines()[0] == "host    command"
        assert max(widths(printed)) == 80

    def test_a_colored_pane_pays_for_its_wider_gutter(
            self, capsys, monkeypatch):
        # Every figure in the finding was a piped one. On a color terminal the
        # separator is " │ " = 3 cells, so the same 80-column pane cannot
        # afford `host` as well and drops it: 72, against 92 before.
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("COLUMNS", "80")
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",))
        printed = capsys.readouterr().out
        assert "…" not in printed
        assert "host" not in printed
        assert max(widths(printed)) == 72

    def test_taps_shape_drops_url_and_updated_at_its_floor(
            self, capsys, monkeypatch):
        # The old floor row was 54 columns wide on every pane narrower than 54,
        # spending 6 of them on two ellipses.
        monkeypatch.setenv("COLUMNS", "53")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        printed = capsys.readouterr().out
        assert "…" not in printed
        assert "https://" not in printed          # the URL column went
        assert "2026-" not in printed             # so did UPDATED
        assert "composio-community/awesome-codex-skills" in printed
        assert "880" in printed                   # the numeric column survived
        assert max(widths(printed)) <= 53

    def test_the_floor_is_seven_cells(self, capsys, monkeypatch):
        """Pinned from both sides on the `taps` shape.

        NAME (39, kept) and ITEMS (5, numeric) are fixed, URL and the empty
        curated column have gone, and UPDATED gets what is left: 56 leaves it
        8 cells, 55 leaves 7 — the floor, "2026-0…" — and 54 leaves 6, so it
        goes rather than print "2026-…".
        """
        monkeypatch.setenv("COLUMNS", "56")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        assert updated_cell(capsys.readouterr().out) == "2026-09…"
        monkeypatch.setenv("COLUMNS", "55")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        assert updated_cell(capsys.readouterr().out) == "2026-0…"
        monkeypatch.setenv("COLUMNS", "54")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        narrow = capsys.readouterr().out
        assert "2026" not in narrow and max(widths(narrow)) == 46

    def test_header_drops_exactly_the_columns_the_body_drops(
            self, capsys, monkeypatch):
        # A header that still announces a column the rows no longer carry (or
        # the reverse) misfiles every cell under the wrong name. 82 columns is
        # the width at which `host` is the one leading column that survives.
        monkeypatch.setenv("COLUMNS", "82")
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",))
        lines = capsys.readouterr().out.splitlines()
        cells = [re.split(r"\s{2,}", line) for line in lines]
        assert cells[0] == ["host", "command"]
        assert [len(c) for c in cells[1:]] == [2] * len(HOOK_ROWS)
        assert max(widths(lines_text := "\n".join(lines))) <= 82
        for gone in ("scope", "event", "matcher"):
            assert gone not in lines[0]
        assert lines_text.count("\n") == len(HOOK_ROWS)

    def test_drop_order_is_right_to_left_not_widest_first(
            self, capsys, monkeypatch):
        # Columns 0 and 1 are 20 wide, column 2 is 5. At 20 columns nothing
        # fits even with every column squeezed to the floor (7+7+5 plus two
        # gutters is 23), so one has to go — and it is the rightmost, not the
        # widest.
        monkeypatch.setenv("COLUMNS", "20")
        output.table([("a" * 20, "b" * 20, "ccccc")])
        printed = capsys.readouterr().out
        assert "ccccc" not in printed
        assert "a" in printed and "b" in printed
        assert max(widths(printed)) <= 20

    def test_keep_columns_are_never_dropped(self, capsys, monkeypatch):
        # `keep=` protects the rightmost column here, so the drop order has to
        # step over it and take its neighbour instead.
        monkeypatch.setenv("COLUMNS", "24")
        output.table([("a" * 20, "b" * 20, "ccccc")], keep=(2,))
        printed = capsys.readouterr().out
        assert "ccccc" in printed
        assert "bbbbbbbbbb" not in printed

    def test_the_last_surviving_column_is_never_dropped(
            self, capsys, monkeypatch):
        # Even a pane too narrow for one column at the floor keeps that column:
        # an empty table is not a better answer than an over-wide one.
        monkeypatch.setenv("COLUMNS", "5")
        output.table([("x" * 40, "y" * 40)])
        line = capsys.readouterr().out.splitlines()[0]
        assert line.startswith("x") and line.endswith("…")
        assert "y" not in line

    def test_all_protected_still_overflows_whole(self, capsys, monkeypatch):
        # Nothing droppable and nothing shrinkable: the row overflows rather
        # than being silently falsified, exactly as before.
        monkeypatch.setenv("COLUMNS", "10")
        output.table([("x" * 40, "y" * 40)], keep=(0, 1))
        line = capsys.readouterr().out.splitlines()[0]
        assert line == "x" * 40 + "  " + "y" * 40

    def test_wide_pane_is_byte_identical(self, capsys, monkeypatch):
        # Pinned from the pre-change implementation: when everything fits,
        # nothing about the layout may move.
        monkeypatch.setenv("COLUMNS", "200")
        output.table(HOOK_ROWS, headers=HOOK_HEADERS, keep=("command",))
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        assert capsys.readouterr().out == (
            "host    scope   event         name   matcher               command\n"
            "claude  global  SessionStart  bmad   startup|resume|clear  "
            "boost bmad orient --quiet --and-then-report-status-to-the-user\n"
            "claude  global  PreToolUse    guard  Bash                  "
            'boost check --strict --json | jq -r ".issues[] | .msg" | head -20 | sort\n'
            "NAME                                     ITEMS  UPDATED       URL\n"
            "anthropics/skills                           20  2026-09-20    "
            "https://github.com/anthropics/skills\n"
            "composio-community/awesome-codex-skills    880  2026-09-18    "
            "https://github.com/composio-community/awesome-codex-skills\n"
            "minio/skills                                 4  2026-08-31    "
            "https://github.com/minio/skills\n")

    def test_a_pipe_has_no_pane_so_nothing_is_dropped(self, monkeypatch):
        # `pane_width` returns None for a pipe; a clipped NAME is not the name
        # and a dropped URL is not the URL either.
        monkeypatch.delenv("COLUMNS", raising=False)
        buf = io.StringIO()
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",),
                     stream=buf)
        printed = buf.getvalue()
        assert "https://github.com/minio/skills" in printed
        assert max(widths(printed)) > 80


class TestEmptyColumnGoesFirst:
    """A column with nothing in it — header included — carries no data and
    still costs a gutter. `boost taps` has one whenever no tap is curated.

    Kept, it made the fitter squeeze the real date to buy the empty column's
    separator: piped at COLUMNS=57 UPDATED read "2026-0…" where 56 gave
    "2026-09…", and a colour pane at 60 printed "2026-0…" and then a dangling
    "│".
    """

    @pytest.fixture(autouse=True)
    def plain(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

    def test_an_empty_column_goes_before_a_data_column(
            self, capsys, monkeypatch):
        # 3 + 2 + 0 + 2 + 3 = 10. At 10 it fits and nothing moves; at 9 the
        # empty column and its gutter go and both data columns stay whole —
        # the alternative was dropping "bbb", the only column carrying data
        # that could go, to keep one that carries none.
        monkeypatch.setenv("COLUMNS", "10")
        output.table([("aaa", "", "bbb")])
        assert capsys.readouterr().out == "aaa    bbb\n"
        monkeypatch.setenv("COLUMNS", "9")
        output.table([("aaa", "", "bbb")])
        assert capsys.readouterr().out == "aaa  bbb\n"

    def test_taps_date_is_not_squeezed_to_keep_the_empty_column(
            self, capsys, monkeypatch):
        # URL cannot fit at the floor at these widths, so the date gets
        # everything NAME and ITEMS leave: one more cell per column of pane,
        # none of them spent on the empty column's gutter.
        for cols, cell in ((56, "2026-09…"), (57, "2026-09-…"),
                           (58, "2026-09-20")):
            monkeypatch.setenv("COLUMNS", str(cols))
            output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
            printed = capsys.readouterr().out
            assert updated_cell(printed) == cell, cols
            assert max(widths(printed)) <= cols

    def test_a_colored_pane_shows_the_date_and_no_dangling_gutter(
            self, capsys, monkeypatch):
        monkeypatch.delenv("NO_COLOR")
        monkeypatch.setenv("BOOST_COLOR", "always")
        monkeypatch.setenv("COLUMNS", "60")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        printed = capsys.readouterr().out
        assert updated_cell(printed) == "2026-09-20"
        lines = _ANSI.sub("", printed).splitlines()
        assert not any(line.rstrip().endswith("│") for line in lines)
        assert max(widths(printed)) <= 60

    @pytest.mark.parametrize("color", [False, True], ids=["piped", "colour"])
    def test_updated_never_narrows_unless_a_data_column_joins(
            self, capsys, monkeypatch, color):
        """As the pane grows, the date column never gets narrower for nothing.

        It does narrow once, and that is not this defect: at 64 piped (67 in
        colour) URL fits again at the floor, and the shrink that makes room
        for it takes UPDATED from 10 back to 7. That is the same
        shrink-before-drop that keeps `hooks list`'s `matcher` piped at
        COLUMNS=66 (see TestFitColumns), so it is allowed here only when a
        column that carries data joined. The empty column rejoining is not
        that.
        """
        if color:
            monkeypatch.delenv("NO_COLOR")
            monkeypatch.setenv("BOOST_COLOR", "always")
        prev_cell, prev_cols = None, None
        for cols in range(40, 91):
            monkeypatch.setenv("COLUMNS", str(cols))
            output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
            printed = capsys.readouterr().out
            assert max(widths(printed)) <= cols, cols
            cell, shown = updated_cell(printed), data_columns(printed)
            if prev_cell is not None and len(cell) < len(prev_cell):
                assert shown > prev_cols, (cols, prev_cell, cell)
            prev_cell, prev_cols = cell, shown


class TestFitColumns:
    """The drop rule on its own, away from the rendering."""

    def test_no_drop_when_everything_fits(self):
        assert output._fit_columns([3, 4], [False, True], avail=80) == \
               ([0, 1], [3, 4])

    def test_shrinks_before_it_drops(self):
        # 20 + 2 + 5 = 27 > 20, but the text column can reach 13 and stay well
        # above the floor, so no column is lost.
        assert output._fit_columns([20, 5], [False, True], avail=20) == \
               ([0, 1], [13, 5])

    def test_drops_the_rightmost_droppable_column(self):
        show, fitted = output._fit_columns([20, 20, 5], [False] * 3, avail=20)
        assert show == [0, 1]
        assert sum(fitted) + 2 * (len(fitted) - 1) <= 20

    def test_a_protected_column_is_stepped_over(self):
        show, _ = output._fit_columns([20, 20, 5], [False] * 3, avail=20,
                                      protected=[2])
        assert show == [0, 2]

    def test_never_returns_an_empty_column_set(self):
        # With nothing left to drop the floor stops applying: one column
        # clipped to the pane beats one column overflowing it.
        show, fitted = output._fit_columns([40, 40], [False, False], avail=5)
        assert show == [0] and fitted == [5]
        # A table with nothing in it at all is not emptied by the empty-column
        # rule either: the ordinary right-to-left drop decides.
        assert output._fit_columns([0, 0, 0], [False] * 3, avail=3) == \
               ([0, 1], [0, 0])

    def test_an_empty_column_goes_first_unless_kept(self):
        assert output._fit_columns([3, 0, 3], [False] * 3, avail=9) == \
               ([0, 2], [3, 3])
        # `keep=` still means never dropped, even for a column with nothing in
        # it; the rightmost droppable column goes instead, as before.
        assert output._fit_columns([3, 0, 3], [False] * 3, avail=9,
                                   protected=[1]) == ([0, 1], [3, 0])

    def test_nothing_droppable_returns_every_column(self):
        # All protected: same answer `_fit_widths` gives on its own.
        assert output._fit_columns([10, 10], [False, False], avail=4,
                                   protected=[0, 1]) == ([0, 1], [10, 10])

    def test_a_surviving_column_never_falls_below_the_floor(self):
        # The defect in one line. Shrinking alone reaches 20 by squeezing
        # the wide columns under the floor — widths at which the cell is
        # mostly ellipsis — so a column goes instead and the survivors stay
        # legible.
        squeezed = output._fit_widths([20, 20, 5], [False] * 3, 20)
        assert min(squeezed) < output._MIN_COL
        _, fitted = output._fit_columns([20, 20, 5], [False] * 3, avail=20)
        assert all(w >= output._MIN_COL for w in fitted)

    def test_a_column_is_not_dropped_when_one_cell_short_of_the_floor(self):
        """Why the floor is 7 and not 8.

        At 8, `boost hooks list` piped at COLUMNS=66 — which fits all six
        columns with `event` at 7 — was given five: `matcher`, 8 wide and
        carrying real data, was spent to buy one cell, and the row then
        measured 61 into a 66-wide pane.
        """
        widths = [6, 6, 12, 5, 8, 24]        # host scope event name matcher command
        show, fitted = output._fit_columns(widths, [False] * 6, avail=66,
                                           protected=[5])
        assert show == [0, 1, 2, 3, 4, 5], "a column was dropped although the row fits"
        assert sum(fitted) + 2 * (len(fitted) - 1) <= 66
        # A column narrower than the floor to begin with is not "squeezed
        # below" it — it is showing everything it has.
        assert all(f >= min(w, output._MIN_COL)
                   for f, w in zip(fitted, widths, strict=True))

    def test_empty_widths_returns_empty(self):
        assert output._fit_columns([], [], avail=80) == ([], [])

    def test_separator_width_is_honoured(self):
        # A color terminal's " │ " is 3 columns, so the same widths need one
        # more cell per gutter and drop one step sooner. 23 is the width where
        # sep=2 still fits three columns at the floor (7+7+5 + 2+2) and sep=3
        # does not (7+7+5 + 3+3 = 25).
        assert output._fit_columns([20, 20, 5], [False] * 3, avail=23,
                                   sep=2)[0] == [0, 1, 2]
        assert output._fit_columns([20, 20, 5], [False] * 3, avail=23,
                                   sep=3)[0] == [0, 1]
