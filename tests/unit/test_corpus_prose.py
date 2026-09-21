# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: prose that quotes the eval corpus agrees with the corpus.

WHY. `.github/workflows/eval-corpus-refresh.yml` moves every pin in
`tests/eval/taps.txt` once a month and rewrites `tests/eval/baseline.json` to
match. Its first run (cbc0a58b) took the corpus from 10,152 entries to 10,731,
and every sentence that quoted the old size kept quoting it: taps.txt's own
header, fifty lines above rows that sum to the new figure; the scale workflow;
and `build_scale_corpus.py`, which wrote the old figure back into
`taps-scale.txt` on every run. Nothing failed, because nothing compared them.

So a figure that tracks the corpus is either WRITTEN from the rows (taps.txt's
corpus-size block, the scale list's header) or quoted on purpose and listed in
QUOTED below, where it is checked against the rows and the baseline. A refresh
that moves the corpus fails here, naming each file, until someone updates them.

The figures are derived here from the raw files rather than through
`eval_corpus.py`, so a bug in the code that writes the size block cannot agree
with itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TAPS = _ROOT / "tests" / "eval" / "taps.txt"
_BASELINE = _ROOT / "tests" / "eval" / "baseline.json"

pytestmark = pytest.mark.skipif(
    not (_TAPS.exists() and _BASELINE.exists()),
    reason="eval corpus files not reachable")

#: Sentences that quote a figure the refresh moves, on purpose. Each template
#: is formatted with the figures below and must appear in its file, so a
#: refresh fails the check until the quote is updated. Line breaks and comment
#: markers are folded to one space first, so re-wrapping a quote is not a
#: failure.
QUOTED = (
    ("tests/eval/taps.txt", "{total} entries in"),
    ("tests/eval/taps-scale.txt", "the required gate measures {total} entries"),
    ("CLAUDE.md", "over the twenty ({total})"),
    ("CLAUDE.md", "over the six alone ({targets} entries"),
    ("CLAUDE.md", "**{bm25}**"),
    ("Makefile", "Over the six ({targets} entries)"),
    ("Makefile", "over twenty it scores {bm25}"),
    ("docs/eval.html", "<b>{recall}</b><span>BM25 recall@10"),
)

#: Files whose whole-corpus sizes are checked: every file in QUOTED, and the
#: ones that used to state a size and now point at taps.txt instead.
LIVE = sorted({path for path, _t in QUOTED} | {
    ".github/workflows/eval-scale.yml",
    "docs/rag-architecture.md",
    "scripts/build_scale_corpus.py",
    "scripts/eval_corpus.py",
    "tests/unit/test_scale_corpus.py",
})

#: "10,731 entries", "10731 entries", "10,731-entry".
_FIGURE = re.compile(
    r"(?<![\d,.])(\d{1,3}(?:,\d{3})+|\d{4,6})(?=[ -]entr(?:y|ies)\b)")
#: A pull request number (#410) — the measurement a dated figure belongs to.
#: The lookbehind keeps HTML entities (&#8212;) from reading as one.
_DATED = re.compile(r"(?<![&\w])#\d{3,4}\b")

#: A whole-corpus figure is one within this factor of the current total. One
#: refresh moved the total 5.7%; the corpus's subsets (the six target repos,
#: the corpus without its largest repo) and a real install's ~71k are far
#: outside it, so they are not mistaken for a stale total.
_WINDOW = (0.8, 1.25)


def _counts(text: str) -> list[int]:
    """The entry count of every pinned row in ``text``."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and not parts[0].startswith("#"):
            out.append(int(parts[2]))
    return out


def _bm25() -> dict[str, float]:
    sets = json.loads(_BASELINE.read_text(encoding="utf-8"))["sets"]
    (golden,) = [v for k, v in sets.items() if k.startswith("golden.jsonl@")]
    return golden["engines"]["BM25 full-content"]


def _figures() -> dict[str, str]:
    text = _TAPS.read_text(encoding="utf-8")
    # The rows above the scale divider are the ones holding golden targets.
    head = text.split("\n# --- scale", 1)[0]
    bm25 = _bm25()
    return {
        "total": f"{sum(_counts(text)):,}",
        "targets": f"{sum(_counts(head)):,}",
        "bm25": " / ".join("%.3f" % bm25[k]
                           for k in ("recall@k", "hit@1", "MRR", "nDCG@k")),
        "recall": "%.3f" % bm25["recall@k"],
    }


def _folded(text: str) -> str:
    return re.sub(r"[ \t]*\n[ \t]*(?:#[ \t]*)?", " ", text)


def stale_totals(text: str, total: int) -> list[str]:
    """Lines of ``text`` stating a whole-corpus size other than ``total``.

    A line naming a pull request is a dated record ("10,152 entries at the
    #410 pins") and is skipped: it describes a corpus that existed, and a
    refresh does not make it untrue.
    """
    low, high = total * _WINDOW[0], total * _WINDOW[1]
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if _DATED.search(line):
            continue
        for m in _FIGURE.finditer(line):
            n = int(m.group(1).replace(",", ""))
            if low <= n <= high and n != total:
                out.append("%d: %s" % (no, line.strip()))
    return out


class TestTheCheckItself:
    def test_a_stale_total_is_reported_with_its_line(self):
        assert stale_totals("a\nthe corpus is 10,152 entries\n", 10_731) == [
            "2: the corpus is 10,152 entries"]

    def test_the_current_total_passes(self):
        assert stale_totals("the corpus is 10,731 entries", 10_731) == []

    def test_every_spelling_of_a_size_is_read(self):
        text = "10152 entries\na 10,152-entry corpus\n"
        assert len(stale_totals(text, 10_731)) == 2

    def test_a_dated_figure_is_a_record_not_a_claim(self):
        assert stale_totals("10,152 entries at the #410 pins", 10_731) == []

    def test_an_html_entity_is_not_a_date(self):
        assert stale_totals("10,152 entries &#8212; now", 10_731) != []

    def test_subsets_and_real_installs_are_not_totals(self):
        text = "921 entries\n3,843 entries\n71,655 entries\n"
        assert stale_totals(text, 10_731) == []

    def test_folding_joins_a_wrapped_comment(self):
        assert _folded("# measures\n# 10,731 entries") == \
            "# measures 10,731 entries"


class TestTheShippedProse:
    @pytest.mark.parametrize("path,template", QUOTED,
                             ids=["%s:%s" % q for q in QUOTED])
    def test_a_quoted_figure_is_the_current_one(self, path, template):
        f = _ROOT / path
        if not f.exists():
            pytest.skip("%s not reachable" % path)
        want = template.format(**_figures())
        assert want in _folded(f.read_text(encoding="utf-8")), (
            "%s no longer says %r, which is what tests/eval/taps.txt's rows "
            "and tests/eval/baseline.json give now. The corpus moved (the "
            "monthly refresh, or a pin edited by hand): update the figures in "
            "%s, and re-measure any score quoted beside them."
            % (path, want, path))

    @pytest.mark.parametrize("path", LIVE)
    def test_no_other_corpus_size_is_stated(self, path):
        f = _ROOT / path
        if not f.exists():
            pytest.skip("%s not reachable" % path)
        total = sum(_counts(_TAPS.read_text(encoding="utf-8")))
        stale = stale_totals(f.read_text(encoding="utf-8"), total)
        assert not stale, (
            "%s states a corpus size that is not the %s entries "
            "tests/eval/taps.txt sums to:\n  %s\nPoint at taps.txt's header "
            "instead of restating the size, or — for a past measurement — name "
            "the pull request it was measured at on the same line."
            % (path, f"{total:,}", "\n  ".join(stale)))
