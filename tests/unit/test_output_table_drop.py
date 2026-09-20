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

# The shape from `boost hooks list` (commands/hooks.py:90): six columns, the
# one the user came to read is the *last* and is the protected one, so every
# dead column is a leading one. Rows are a sandbox ~/.claude/settings.json
# carrying two boost-managed hooks.
HOOK_HEADERS = ("host", "scope", "event", "name", "matcher", "command")
HOOK_ROWS = [
    ("claude", "global", "SessionStart", "bmad", "startup|resume|clear",
     "boost bmad orient --quiet --and-then-report-status-to-the-user"),
    ("claude", "global", "PreToolUse", "guard", "Bash",
     'boost check --strict --json | jq -r ".issues[] | .msg" | head -20 | sort'),
]

# The shape from `boost taps` (commands/taps.py:362): NAME is protected, ITEMS
# is numeric, the curated column is empty (no curated tap in the 20-repo eval
# corpus) and still costs a separator, and UPDATED/URL are the chrome.
TAP_HEADERS = ("NAME", "ITEMS", "UPDATED", "", "URL")
TAP_ROWS = [
    ("anthropics/skills", "20", "2 hours ago", "",
     "https://github.com/anthropics/skills"),
    ("composio-community/awesome-codex-skills", "880", "2 hours ago", "",
     "https://github.com/composio-community/awesome-codex-skills"),
    ("minio/skills", "4", "2 hours ago", "",
     "https://github.com/minio/skills"),
]


def widths(printed: str) -> list[int]:
    return [output.visible_len(line) for line in printed.splitlines()]


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
        assert "2 hours ago" not in printed       # so did UPDATED
        assert "composio-community/awesome-codex-skills" in printed
        assert "880" in printed                   # the numeric column survived
        assert max(widths(printed)) <= 53

    def test_the_floor_is_eight_cells_with_one_cell_of_give(
            self, capsys, monkeypatch):
        """Pinned from both sides on the `taps` shape.

        NAME (39, kept) and ITEMS (5, numeric) are fixed and UPDATED gets what
        is left. 56 leaves it its preferred 8 cells; 55 leaves 7, which it is
        allowed to take rather than cost the pane a whole column; 54 leaves 6
        and it goes, because that is a date rendered as "2 ho…".
        """
        monkeypatch.setenv("COLUMNS", "56")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        assert "2 hours…" in capsys.readouterr().out
        monkeypatch.setenv("COLUMNS", "55")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        assert "2 hour…" in capsys.readouterr().out
        monkeypatch.setenv("COLUMNS", "54")
        output.table(TAP_ROWS, headers=TAP_HEADERS, keep=("NAME",))
        narrow = capsys.readouterr().out
        assert "2 hou" not in narrow and max(widths(narrow)) == 46

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
        # Columns 0 and 1 are 20 wide, column 2 is 5. At 24 columns nothing
        # fits even with every column squeezed to the hard floor (7+7+5 plus
        # two gutters is 23, but the 5-wide column cannot give), so one has to
        # go — and it is the rightmost, not the widest.
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
            "NAME                                     ITEMS  UPDATED        URL\n"
            "anthropics/skills                           20  2 hours ago    "
            "https://github.com/anthropics/skills\n"
            "composio-community/awesome-codex-skills    880  2 hours ago    "
            "https://github.com/composio-community/awesome-codex-skills\n"
            "minio/skills                                 4  2 hours ago    "
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

    def test_nothing_droppable_returns_every_column(self):
        # All protected: same answer `_fit_widths` gives on its own.
        assert output._fit_columns([10, 10], [False, False], avail=4,
                                   protected=[0, 1]) == ([0, 1], [10, 10])

    def test_a_surviving_column_never_falls_below_the_hard_floor(self):
        # The defect in one line. Shrinking alone reaches 10 by squeezing
        # the wide columns under the hard floor — widths at which the cell is
        # mostly ellipsis — so a column goes instead and the survivors stay
        # legible.
        squeezed = output._fit_widths([20, 20, 5], [False] * 3, 20)
        assert min(squeezed) < output._HARD_FLOOR
        _, fitted = output._fit_columns([20, 20, 5], [False] * 3, avail=20)
        assert all(w >= output._HARD_FLOOR for w in fitted)

    def test_the_preferred_floor_is_used_when_it_fits(self):
        # Between the two floors the fit is searched, highest first: a row
        # that fits at 8 is never squeezed to 4 to buy room nothing needs.
        _, fitted = output._fit_columns([20, 20, 20], [False] * 3, avail=40)
        assert min(fitted) >= output._MIN_COL

    def test_a_column_is_not_dropped_when_one_cell_short_of_the_floor(self):
        """The regression this pair of floors exists for.

        With a single hard floor of 8, `boost hooks list` at COLUMNS=66 fit on
        six columns at floor 7 and was given five: the rightmost droppable
        column — 8 wide, exactly at the floor, carrying real data — was spent
        to buy one cell, and the row then measured 61 into a 66-wide pane.
        """
        widths = [6, 6, 12, 5, 8, 24]        # host scope event name matcher command
        show, fitted = output._fit_columns(widths, [False] * 6, avail=66,
                                           protected=[5])
        assert show == [0, 1, 2, 3, 4, 5], "a column was dropped although the row fits"
        assert sum(fitted) + 2 * (len(fitted) - 1) <= 66
        # A column narrower than the floor to begin with is not "squeezed
        # below" it — it is showing everything it has.
        assert all(f >= min(w, output._HARD_FLOOR)
                   for f, w in zip(fitted, widths, strict=True))

    def test_empty_widths_returns_empty(self):
        assert output._fit_columns([], [], avail=80) == ([], [])

    def test_separator_width_is_honoured(self):
        # A color terminal's " │ " is 3 columns, so the same widths need one
        # more cell per gutter and drop one step sooner. 23 is the width where
        # sep=2 still fits three columns at the hard floor (7+7+5 + 2+2) and
        # sep=3 does not (7+7+5 + 3+3 = 25).
        assert output._fit_columns([20, 20, 5], [False] * 3, avail=23,
                                   sep=2)[0] == [0, 1, 2]
        assert output._fit_columns([20, 20, 5], [False] * 3, avail=23,
                                   sep=3)[0] == [0, 1]
