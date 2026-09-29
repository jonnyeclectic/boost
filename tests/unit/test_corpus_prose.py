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

import importlib.util
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TAPS = _ROOT / "tests" / "eval" / "taps.txt"
_BASELINE = _ROOT / "tests" / "eval" / "baseline.json"
_GOLDEN = _ROOT / "tests" / "eval" / "golden.jsonl"

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
    ("CLAUDE.md", "recorded BM25 row ({natural_bm25})"),
    ("CLAUDE.md", "under their measured values ({headroom}), {binding} the tightest"),
    ("CLAUDE.md", "a {spread} spread rather than one number"),
    ("CLAUDE.md", "the tightest of them is worth {slack}"),
    ("Makefile", "under their measured values ({headroom}), {binding} the"),
    ("Makefile", "tightest at {slack}:"),
    ("Makefile", "it is a {spread} spread"),
    ("Makefile", "Over the six ({targets} entries)"),
    ("Makefile", "over twenty it scores {bm25}"),
    ("Makefile", "records ({natural_bm25} at the current pins"),
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

#: The gaps a figure may be separated by: a space, a hyphen, or a
#: non-breaking space, raw or as an HTML entity.
_GAP = r"(?:[ \u00a0-]|&nbsp;|&#160;)"
#: "10,731 entries", "10731 entries", "10,731-entry", "10,731 catalog
#: entries": one word at most between the figure and "entries", so a figure
#: counting some other noun ("10,731 files, 921 entries") is not read as one.
_FIGURE = re.compile(
    r"(?<![\d,.])(\d{1,3}(?:,\d{3})+|\d{4,6})"
    r"(?=%s(?:[A-Za-z]+%s)?entr(?:y|ies)\b)" % (_GAP, _GAP))
#: A pull request number (#410) — the measurement a dated figure belongs to.
#: The lookbehind keeps HTML entities (&#8212;) from reading as one.
_DATED = re.compile(r"(?<![&\w])#\d{3,4}\b")

#: A whole-corpus figure is one within this factor of the current total. The
#: low end is what catches growth — the old total sits BELOW the new one — so
#: it is as low as it can go while staying above eval_corpus.MAX_ROW_SHARE (65%):
#: the size block names the largest repo's entries on an undated line, and the
#: cap keeps that figure out. 0.7 catches the old total after a refresh that
#: grows the corpus by up to 43% (the first one moved it 5.7%); 2.0 catches it
#: after one that halves it. The other subsets quoted today (the six target
#: repos, 9%; the corpus without its largest repo, 38%) and a real install's
#: ~71k are outside it.
_WINDOW = (0.7, 2.0)


def _counts(text: str) -> list[int]:
    """The entry count of every pinned row in ``text``."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        # `>= 3`, not `== 3`: a row gained a fourth field (its distinct-content
        # count) and an equality test stopped matching every row at once,
        # taking the total to zero. Nothing failed — a total of zero makes
        # every "is this figure stale" check pass vacuously — which is the
        # failure mode this whole module exists to catch.
        if len(parts) >= 3 and not parts[0].startswith("#"):
            out.append(int(parts[2]))
    return out


def _bm25(query_set: str = "golden.jsonl") -> dict[str, float]:
    """The BM25 row baseline.json records for one query set, by file name."""
    sets = json.loads(_BASELINE.read_text(encoding="utf-8"))["sets"]
    (row,) = [v for k, v in sets.items() if k.startswith(query_set + "@")]
    return row["engines"]["BM25 full-content"]


def _four(row: dict[str, float]) -> str:
    """recall@k / hit@1 / MRR / nDCG@k, as the prose quotes them."""
    return " / ".join("%.3f" % row[k]
                      for k in ("recall@k", "hit@1", "MRR", "nDCG@k"))


def _figures() -> dict[str, str]:
    text = _TAPS.read_text(encoding="utf-8")
    # The rows above the scale divider are the ones holding golden targets.
    head = text.split("\n# --- scale", 1)[0]
    bm25 = _bm25()
    floors = _floors()
    gaps = _headroom(bm25, floors)
    tightest = _METRICS[gaps.index(min(gaps))]
    return {
        "total": f"{sum(_counts(text)):,}",
        "targets": f"{sum(_counts(head)):,}",
        "bm25": _four(bm25),
        # The natural-language set's row: the refresh moves it too, and
        # `make eval-natural`'s floors are calibrated on the figures quoted.
        "natural_bm25": _four(_bm25("golden-natural.jsonl")),
        "recall": "%.3f" % bm25["recall@k"],
        # The margin each floor actually has, rather than the single "~10%"
        # the prose asserted from 170d52c0 (2026-07-31) onward. It was never
        # uniform: at that twenty-tap calibration the gaps were 9.6 / 15.3 /
        # 14.4 / 12.4 (recomputed from 170d52c0's own baseline and Makefile —
        # the roadmap card transposes two of those digits),
        # and the monthly refresh widens the spread because it re-baselines the
        # row and leaves the floors where they are, by design. Quoting the four
        # separately is what makes that visible; holding them here is what
        # makes a refresh restate them.
        "headroom": " / ".join("%.1f%%" % g for g in gaps),
        # Which floor is closest to the row, and so the one a corpus move
        # actually trips. A judgement stated beside held figures has to be held
        # too, or it is the next sentence to go quietly stale.
        "binding": tightest,
        # How wide the spread is. The claim being replaced was that there was
        # no spread, so the number that refutes it has to be held like the
        # rest -- an unheld "2.4x" beside a held "7.2% / 17.3%" is the same
        # defect one sentence along. Two decimals, not one: the verification
        # behind this card rejected "2.4x" for "2.39x", and a figure quoted
        # to the precision it was measured at cannot be argued with.
        "spread": "%.2fx" % (max(gaps) / min(gaps)),
        # The binding floor's margin in queries rather than percent. A
        # percentage does not say whether a margin is one flaky query or ten;
        # over this set, 1 query is 1.1 points of recall@k.
        "slack": "%.1f queries of %d" % (
            (bm25[tightest] - floors[tightest]) * _queries(), _queries()),
    }


def _max_share() -> float:
    """``eval_corpus.MAX_ROW_SHARE``, the cap on one repo's share of the rows.

    A limit the window has to respect, not a figure the prose quotes, so
    reading it from the writer's module costs the check none of its
    independence.
    """
    spec = importlib.util.spec_from_file_location(
        "eval_corpus", _ROOT / "scripts" / "eval_corpus.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return float(mod.MAX_ROW_SHARE)


#: The Makefile recipe whose `--floor` arguments the required gate runs under.
#: Only this one is parsed: `tests/unit/test_eval_corpus.py` already holds the
#: Makefile, ci.yml and eval-corpus-refresh.yml to one argv, so a floor read
#: here is the floor all three use.
_EVAL_RECIPE = "eval"
#: The four metrics, in the order the prose quotes them.
_METRICS = ("recall@k", "hit@1", "MRR", "nDCG@k")


def _argv_reader():
    """`tests/unit/test_eval_corpus.py`, loaded for its argv reader.

    The floors have to be read the way the gate reads them, and the reader
    already exists one file over: `_recipe` slices the Makefile to one
    target, `_invocation` joins line continuations, drops comment lines and
    shlex-splits, and `_meaning` hands the words to
    `eval_retrieval.build_parser()` itself.

    Re-implementing that here with a regex put a hole in this very check
    twice. First an unindented comment block, which sits *above* the next
    target, so slicing to `eval-natural:` swallowed all of its prose. Then —
    after that was fixed by taking tab-indented lines only — a **tab-indented
    comment inside the recipe**, which make ignores and a regex does not:

        eval:
                $(PY) scripts/eval_retrieval.py ... --floor hit@1=0.30 \\
                # relaxed from --floor hit@1=0.40

    make runs the 0.30 gate; a last-match-wins regex reports 0.40, so the
    published margin is held to a floor nothing enforces and nothing is red.
    A third spelling was waiting behind both: argparse accepts
    `--fail-under=0.60`, and a regex keyed on whitespace never sees it.
    Delegating cures all three at once, and any fourth, because the thing
    doing the parsing is the parser.

    Loaded by path rather than imported by name, so this does not depend on
    `tests/unit` being on `sys.path`, and under a private module name so it
    cannot collide with pytest's own import of the same file.
    """
    spec = importlib.util.spec_from_file_location(
        "_corpus_prose_argv", _ROOT / "tests" / "unit" / "test_eval_corpus.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _floors_in(body: str) -> dict[str, float]:
    """The floors one recipe body passes, as the gate's own parser sees them.

    recall@k is `--fail-under` rather than `--floor recall@k=`, which is why
    it is lifted out separately here and why the prose below says "argv"
    rather than naming one flag.
    """
    reader = _argv_reader()
    meaning = reader._meaning(reader._invocation(body))
    floors = {"recall@k": float(meaning["fail_under"])}
    floors.update({k: float(v) for k, v in meaning["floor"].items()})
    return floors


def _floors() -> dict[str, float]:
    """The required gate's four floors, read from the Makefile's own argv."""
    reader = _argv_reader()
    marker = "\n%s:" % _EVAL_RECIPE
    count = (_ROOT / "Makefile").read_text(encoding="utf-8").count(marker)
    assert count == 1, (
        "`%s` is defined %d times; make runs the LAST recipe for a duplicated "
        "target and this reads the first, so the margin below would be held "
        "to floors the gate does not run" % (_EVAL_RECIPE, count))
    return _floors_in(reader._recipe(_EVAL_RECIPE))


def _headroom(row: dict[str, float], floors: dict[str, float]) -> list[float]:
    """How far under the measured row each floor sits, as a percentage."""
    return [(row[m] - floors[m]) / row[m] * 100 for m in _METRICS]


def _queries() -> int:
    """How many cases the gate actually scores.

    `golden.jsonl` is 102 lines and eleven of them are not queries — ten
    comment lines and one blank — so a line count is not the query count.
    `eval_retrieval.load_golden` skips blanks and `#` after stripping, and
    this must skip exactly what it skips. The blank is the case a naive
    `startswith('#')` would miss. The prose quotes
    this figure to turn a percentage into queries, which is the only form in
    which "is that margin big enough" is answerable.
    """
    return sum(1 for line in _GOLDEN.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.strip().startswith("#"))


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


def test_every_pinned_row_is_counted():
    """The row reader sees every row of the shipped list.

    `_counts` derives the total the rest of this module checks prose against,
    by field count. When taps.txt gained a fourth field an `== 3` test matched
    nothing, the total went to zero, and every staleness check passed
    vacuously. A check that fails open is worse than no check, so this pins
    the count of rows READ against the count of rows there.
    """
    text = _TAPS.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.split() and not ln.lstrip().startswith("#")]
    assert len(_counts(text)) == len(rows) >= 20
    assert sum(_counts(text)) > 0


class TestTheCheckItself:
    def test_a_stale_total_is_reported_with_its_line(self):
        assert stale_totals("a\nthe corpus is 10,152 entries\n", 10_731) == [
            "2: the corpus is 10,152 entries"]

    def test_the_current_total_passes(self):
        assert stale_totals("the corpus is 10,731 entries", 10_731) == []

    def test_every_spelling_of_a_size_is_read(self):
        text = "10152 entries\na 10,152-entry corpus\n"
        assert len(stale_totals(text, 10_731)) == 2

    def test_a_word_between_the_figure_and_entries_is_read(self):
        assert stale_totals("the corpus is 10,152 catalog entries", 10_731) \
            == ["1: the corpus is 10,152 catalog entries"]

    def test_a_non_breaking_space_is_read(self):
        text = "10,152\u00a0entries\n10,152&nbsp;entries\n10,152&#160;entries\n"
        assert len(stale_totals(text, 10_731)) == 3

    def test_only_one_word_may_come_between(self):
        # A figure followed by some other noun, then a count of entries, is
        # the other noun's count.
        text = "10,152 files, 921 entries\n10,152 of the entries\n"
        assert stale_totals(text, 10_731) == []

    def test_a_large_growth_still_catches_the_old_total(self):
        # A refresh that grows the corpus 39% leaves the old total at 72% of
        # the new one.
        assert stale_totals("the corpus is 10,731 entries", 14_902) == [
            "1: the corpus is 10,731 entries"]

    def test_a_halving_still_catches_the_old_total(self):
        assert stale_totals("the corpus is 10,731 entries", 5_366) != []

    def test_the_largest_repo_is_never_read_as_a_total(self):
        # The size block names the largest repo's entries on an undated line,
        # and eval_corpus.MAX_ROW_SHARE is the most that figure may be.
        largest = int(10_731 * _max_share())
        text = "# largest: x/y, %s entries" % f"{largest:,}"
        assert stale_totals(text, 10_731) == []

    def test_a_dated_figure_is_a_record_not_a_claim(self):
        assert stale_totals("10,152 entries at the #410 pins", 10_731) == []

    def test_an_html_entity_is_not_a_date(self):
        assert stale_totals("10,152 entries &#8212; now", 10_731) != []

    def test_subsets_and_real_installs_are_not_totals(self):
        text = "921 entries\n3,843 entries\n71,655 entries\n"
        assert stale_totals(text, 10_731) == []

    def test_each_set_is_read_from_its_own_row(self):
        # The keyword and natural rows are different measurements; a figure
        # read from the wrong one would pass while quoting the other set.
        figures = _figures()
        assert figures["bm25"] == _four(_bm25("golden.jsonl"))
        assert figures["natural_bm25"] == _four(_bm25("golden-natural.jsonl"))
        assert figures["bm25"] != figures["natural_bm25"]

    def test_a_set_prefix_is_not_another_sets_name(self):
        # "golden.jsonl@" must not match "golden-natural.jsonl@", or the
        # one-row unpacking above picks whichever it meets.
        sets = json.loads(_BASELINE.read_text(encoding="utf-8"))["sets"]
        assert sum(k.startswith("golden.jsonl@") for k in sets) == 1
        assert sum(k.startswith("golden-natural.jsonl@") for k in sets) == 1

    def test_folding_joins_a_wrapped_comment(self):
        assert _folded("# measures\n# 10,731 entries") == \
            "# measures 10,731 entries"

    def test_the_required_recipe_is_read_and_not_the_advisory_one(self):
        # Two recipes carry `--fail-under` and `--floor hit@1=`: `eval`, which
        # is the required gate, and `eval-natural`, which is advisory and
        # whose floors DO follow the row. A bare search over the file returns
        # whichever comes first, which is the right answer today by ordering
        # alone. Slicing to the named recipe is what makes it the right answer
        # tomorrow, so the slicing is what is pinned -- against the real
        # Makefile, because that is the file the margin is held to.
        reader = _argv_reader()
        assert _floors() == _floors_in(reader._recipe("eval"))
        assert _floors() != _floors_in(reader._recipe("eval-natural"))

    def test_a_target_is_defined_once(self):
        # make runs the LAST recipe for a duplicated target (it warns, then
        # overrides), and every reader here takes the first. `_floors`
        # refuses rather than reading a recipe make would not run; this pins
        # that the real Makefile satisfies it, so the refusal stays a
        # tripwire rather than a permanent failure.
        text = (_ROOT / "Makefile").read_text(encoding="utf-8")
        assert text.count("\n%s:" % _EVAL_RECIPE) == 1

    def test_a_tab_indented_comment_is_not_argv(self):
        # The second hole, found after the first was fixed. A comment line
        # that starts with a TAB is inside the recipe and make ignores it --
        # so a regex over the recipe text reads floors the gate does not run.
        # Last-match-wins made it worse than a miss: the stale number won.
        # Nothing looks broken either way, which is the whole problem.
        body = ("\t$(PY) scripts/eval_retrieval.py --fail-under 0.78 "
                "--floor hit@1=0.40\n"
                "\t# relaxed from --fail-under 0.90 --floor hit@1=0.99\n")
        assert _floors_in(body) == {"recall@k": 0.78, "hit@1": 0.40}

    def test_an_equals_form_flag_is_read(self):
        # The third spelling, and the one a regex keyed on whitespace cannot
        # see at all: argparse accepts `--flag=value`. A regex reported the
        # OLD floor here -- a silent fail-open in the opposite direction from
        # the comment, and the reason this reads argv through the gate's own
        # parser instead of matching text.
        body = ("\t$(PY) scripts/eval_retrieval.py --fail-under=0.60 "
                "--floor=hit@1=0.20\n")
        assert _floors_in(body) == {"recall@k": 0.60, "hit@1": 0.20}

    def test_a_line_continuation_is_joined(self):
        # The real recipe wraps the call over three lines, so a reader that
        # did not join continuations would see one flag and miss the rest --
        # and `_floors` would return fewer than four metrics, which
        # `test_a_floor_that_is_not_read_fails_the_check` catches. Pinned
        # here so the failure names the cause.
        body = ("\t$(PY) scripts/eval_retrieval.py --fail-under 0.78 \\\n"
                "\t  --floor hit@1=0.40 \\\n"
                "\t  --floor MRR=0.52\n")
        assert _floors_in(body) == {
            "recall@k": 0.78, "hit@1": 0.40, "MRR": 0.52}

    def test_a_repeated_flag_is_read_the_way_argparse_reads_it(self):
        # argparse takes the LAST occurrence of a repeated flag. Reading
        # `--fail-under` with re.search took the first, so a duplicate would
        # have held the prose to a number the gate does not use.
        body = ("\t$(PY) scripts/eval_retrieval.py --fail-under 0.78 "
                "--fail-under 0.90 --floor MRR=0.52 --floor MRR=0.61\n")
        assert _floors_in(body) == {"recall@k": 0.90, "MRR": 0.61}

    def test_a_flag_the_gate_does_not_accept_fails_here(self):
        # Reading argv through `eval_retrieval.build_parser()` means a flag
        # the script would reject fails in this test rather than in CI. A
        # regex would have shrugged and returned the floors it did match.
        with pytest.raises(SystemExit):
            _floors_in("\t$(PY) scripts/eval_retrieval.py --no-such-flag 1\n")

    def test_a_floor_that_is_not_read_fails_the_check(self):
        # `_floors` divides by figures it parsed out of argv, so a regex that
        # silently stops matching would not raise -- it would drop a metric
        # and quietly narrow what the prose is held to. Four floors are what
        # the required gate passes; fewer means the parse broke.
        floors = _floors()
        assert sorted(floors) == sorted(_METRICS)
        assert all(0 < v < 1 for v in floors.values())

    def test_the_query_count_skips_the_header_comment(self):
        # golden.jsonl carries ten comment lines and a blank, so a line
        # count is eleven queries too many. `_queries` must skip exactly what
        # `eval_retrieval.load_golden` skips, blank included.
        lines = _GOLDEN.read_text(encoding="utf-8").splitlines()
        assert _queries() == sum(1 for ln in lines if ln.startswith("{"))
        assert _queries() < len(lines)


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
