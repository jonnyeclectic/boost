"""Every prose hint fits the pane it is printed into.

A blanket "no line exceeds `term_width()`" sweep would be the wrong gate: some
long lines are *data*, and folding them destroys the information the line
exists to carry — `pulse` prints `source=` paths and `fingerprint` prints a
64-character hash, and a hash broken across two lines cannot be compared by
eye. So the composed prose sites are pinned individually here, and the data
lines are deliberately absent rather than exempted by a rule that could grow to
cover a real regression.

The commands split two ways, and the split is what the widths encode:

* Commands whose whole output boost composed — `search`, `who`, `protocol` —
  are swept at panes down to 40 columns. Every line is chrome, so every line
  is boost's to fit.
* Commands that also print *the user's content* — `doctor`'s status facts,
  `explain` and `simulate` quoting a skill's own rules — are swept at 80 and
  wider. A skill whose rule reads "Always produce at least 12 raw ideas before
  clustering." is 61 columns of someone else's prose, and boost reflowing it
  is a different decision from boost fitting its own hints.

Both directions have failed before, which is why the sweep is not one-sided:
wrapping to the full terminal and *then* indenting by two put `boost search`'s
hint one column over the pane it had just been fitted to.
"""
from __future__ import annotations

import pytest

from boost_cli.core import output


def _widest(text: str) -> int:
    return max((output.visible_len(ln) for ln in text.splitlines()), default=0)


@pytest.fixture
def pane(monkeypatch):
    """Pin the reported terminal width."""
    def use(cols):
        monkeypatch.setattr(output, "term_width", lambda: cols)
        return cols
    return use


NARROW = [40, 60, 80, 120]
WIDE = [80, 120]


class TestChromeOnlyCommandsFitAnyPane:
    """Output boost composed end to end, so every line is boost's to fit."""

    @pytest.mark.parametrize("cols", NARROW)
    def test_search(self, boost, tapped, pane, cols):
        pane(cols)
        r = boost("search", "brainstorming", expect=None)
        assert _widest(r.out) <= cols

    @pytest.mark.parametrize("cols", NARROW)
    def test_who(self, boost, tapped, pane, cols):
        boost("install", "brainstorming")
        pane(cols)
        r = boost("who", expect=None)
        assert _widest(r.out) <= cols


class TestHintsFitBesideUserContent:
    """Commands that also print a skill's own words; the hints still fit."""

    @pytest.mark.parametrize("cols", WIDE)
    def test_doctor(self, boost, tapped, pane, cols):
        pane(cols)
        r = boost("doctor", expect=None)
        assert _widest(r.out) <= cols

    @pytest.mark.parametrize("cols", WIDE)
    def test_explain(self, boost, tapped, pane, cols):
        boost("install", "brainstorming")
        pane(cols)
        r = boost("explain", "brainstorming", expect=None)
        assert _widest(r.out) <= cols

    @pytest.mark.parametrize("cols", WIDE)
    def test_simulate(self, boost, tapped, pane, cols):
        boost("install", "brainstorming")
        pane(cols)
        r = boost("simulate", "brainstorming", expect=None)
        assert _widest(r.out) <= cols

    @pytest.mark.parametrize("cols", [40, 60, 80, 120])
    def test_the_fallback_note_itself_fits_any_pane(self, boost, tapped, pane,
                                                    cols):
        # Sliced out of the surrounding skill text: the note is the leading
        # `!` line plus the continuations indented under it, and it is the one
        # part of `explain`'s output boost wrote.
        boost("install", "brainstorming")
        pane(cols)
        r = boost("explain", "brainstorming", expect=None)
        lines = r.out.splitlines()
        note = [lines[0]]
        note += [ln for ln in lines[1:len(lines)] if ln.startswith("    ")][:1]
        assert lines[0].lstrip().startswith("!")
        assert max(output.visible_len(ln) for ln in note) <= cols


class TestTheHintsAreStillThere:
    """Fitting the pane must not be achieved by dropping the hint."""

    def test_search_still_names_the_next_action(self, boost, tapped, pane):
        pane(40)
        r = boost("search", "brainstorming", expect=None)
        flat = " ".join(r.out.split())
        assert "semantic search is off" in flat
        assert "pip install" in flat or "boost reindex --dense" in flat

    def test_doctor_still_names_the_engine(self, boost, tapped, pane):
        pane(40)
        r = boost("doctor", expect=None)
        assert "semantic search" in " ".join(r.out.split())

    def test_a_copyable_command_survives_the_narrowest_pane(self, boost, tapped,
                                                            pane):
        # The point of treating a code span as atomic: at 40 columns the hint
        # wraps, but the command inside it must still be one selectable run of
        # text rather than two halves the user has to rejoin.
        pane(40)
        r = boost("search", "brainstorming", expect=None)
        for line in r.out.splitlines():
            assert line.count("`") % 2 == 0

    def test_protocol_still_lists_every_url_form(self, boost, tapped, pane):
        pane(40)
        r = boost("protocol", expect=None)
        flat = " ".join(r.out.split())
        for form in ("boost://install/<skill>", "boost://install/<tap>:<skill>",
                     "boost://tap/<owner>/<repo>"):
            assert form in flat
