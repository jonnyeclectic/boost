"""Committed roadmap HTML stays in lockstep with its item source files.

The roadmap boards are generated from ``docs/roadmap/items/*.md`` by
``scripts/build_roadmap.py`` and injected into the marker regions of the
hand-authored pages. This test — the in-suite twin of the
``build_roadmap.py --check`` CI step — fails if the committed HTML drifts from a
fresh render, so a stale board can't merge.

Skips when the repo-root files aren't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_roadmap.py"
_ITEMS = _ROOT / "docs" / "roadmap" / "items"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_roadmap", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_roadmap_html_is_regenerated():
    builder = _load_builder()
    path, fresh = builder.build_code()
    committed = path.read_text(encoding="utf-8")
    # Reuse the script's own diagnosis rather than restating "out of date".
    # This assertion fires on all nine test legs at once, so what it says is
    # what nine failures say — and the cause is a rebase far more often than a
    # hand-edit.
    assert committed == fresh, "\n".join(
        ["docs/roadmap.html is stale — regenerate with",
         "    python3 scripts/build_roadmap.py",
         "and commit the result (see CONTRIBUTING.md).",
         *builder.diagnose(path, committed, fresh)])


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_design_roadmap_html_is_regenerated():
    builder = _load_builder()
    path, fresh = builder.build_design()
    committed = path.read_text(encoding="utf-8")
    assert committed == fresh, "\n".join(
        ["docs/design-roadmap.html is stale — regenerate with",
         "    python3 scripts/build_roadmap.py",
         "and commit the result (see CONTRIBUTING.md).",
         *builder.diagnose(path, committed, fresh)])


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_check_flag_passes_on_fresh_tree():
    builder = _load_builder()
    assert builder.main(["--check"]) == 0


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_every_code_item_has_required_fields():
    builder = _load_builder()
    for item in builder.load_items("code"):
        for field in ("id", "section", "status", "title"):
            assert item.get(field), "%s: missing %r" % (item["_file"], field)
        assert item["status"] in builder.STATUS_LABEL, (
            "%s: bad status %r" % (item["_file"], item["status"]))


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_a_card_body_may_not_contain_a_block_element():
    """Every body is emitted inside `<p>`, whatever the status.

    So a `<pre>`, `<table>` or `<ul>` in an item file implicitly closes that
    paragraph and leaves a stray `</p>`, which html-validate fails the build on
    — in a *separate* required workflow, several minutes after the roadmap
    scripts have all reported clean. That happened twice while writing these
    cards. Failing at generation time instead names the file.
    """
    builder = _load_builder()
    for board in ("code", "design"):
        for item in builder.load_items(board):
            with pytest.raises(builder.RoadmapError) as ei:
                builder.check_body_is_inline(item["_file"], "x <pre>y</pre>")
            assert item["_file"] in str(ei.value)
            builder.check_body_is_inline(item["_file"], item["body"])
            break


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_every_shipped_card_body_is_inline():
    builder = _load_builder()
    for board in ("code", "design"):
        for item in builder.load_items(board):
            builder.check_body_is_inline(item["_file"], item["body"])


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
def test_every_design_item_has_required_fields():
    builder = _load_builder()
    for item in builder.load_items("design"):
        for field in ("id", "track", "status", "title"):
            assert item.get(field), "%s: missing %r" % (item["_file"], field)
        assert item["status"] in builder.DESIGN_STATUS, (
            "%s: bad status %r" % (item["_file"], item["status"]))
        assert str(item.get("impact", "")).lower() in builder.IMPACT_LABEL, (
            "%s: bad impact %r" % (item["_file"], item.get("impact")))


# ── the diagnosis itself ─────────────────────────────────────────────────────
#
# The failure above lands on lint and on all nine test legs simultaneously, for
# a PR that may have changed no Python at all. Whether it reads as "the build is
# broken" or as "regenerate the board after your rebase" is entirely down to
# what these strings say, so they are tested rather than trusted.

CARD = '<article class="cap rcard" id="%s">body</article>'


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
class TestDiagnose:
    def _lines(self, committed, fresh):
        return _load_builder().diagnose(Path("docs/roadmap.html"),
                                        committed, fresh)

    def test_a_card_missing_from_the_html_names_it_and_blames_the_rebase(self):
        # THE case this exists for: another PR's item file merged in cleanly,
        # the generated HTML merged textually, and the card is simply absent.
        lines = self._lines(CARD % "old-one",
                            (CARD % "old-one") + (CARD % "someone-elses-card"))
        text = "\n".join(lines)
        assert "someone-elses-card" in text
        assert "rebase" in text
        assert "missing 1 card" in text

    def test_several_missing_cards_are_summarised_not_dumped(self):
        fresh = "".join(CARD % ("card-%d" % i) for i in range(20))
        text = "\n".join(self._lines("", fresh))
        assert "missing 20 card(s)" in text
        assert text.count("card-") <= 9, "8 named plus the ellipsis"
        assert "…" in text

    def test_a_card_with_no_item_file_is_called_out_separately(self):
        lines = self._lines(CARD % "deleted-item", "")
        text = "\n".join(lines)
        assert "no item file" in text
        assert "deleted-item" in text
        assert "rebase" not in text, "nothing is missing — different cause"

    def test_same_cards_rendered_differently_says_so(self):
        # A field or body edit, or a generator change — not a rebase.
        lines = self._lines('<article class="cap rcard" id="a">old</article>',
                            '<article class="cap rcard" id="a">new</article>')
        text = "\n".join(lines)
        assert "rendered differently" in text
        assert "missing" not in text

    def test_the_design_board_shape_is_recognised_too(self):
        # design-roadmap.html uses <article class="ritem" …>, not "cap rcard".
        fresh = ('<article class="ritem" id="BOOST-D99" data-track="x" '
                 'data-impact="y">body</article>')
        assert "BOOST-D99" in "\n".join(self._lines("", fresh))

    def test_it_never_returns_nothing(self):
        # An empty diagnosis would leave the assertion message ending on a
        # colon with no explanation — worse than the message it replaced.
        for committed, fresh in (("", ""), ("x", "y"), (CARD % "a", CARD % "a")):
            assert self._lines(committed, fresh)


def test_every_item_file_is_named_for_its_id():
    """The filename must equal the `id`, because the filename is the protocol.

    CLAUDE.md coordinates parallel loops through these files: two loops claiming
    different items edit different files and merge cleanly, two claiming the
    same item conflict on purpose. That only works if the path is derivable from
    the id — otherwise a second loop cannot tell whether an item is already
    claimed without opening all 200-odd files.

    207 of 208 already followed the convention when this was added; the one that
    did not was a temp filename that reached main because nothing checked.
    """
    import re
    bad = []
    for path in sorted(_ITEMS.glob("*.md")):
        m = re.search(r"^id: *(\S+)", path.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) != path.stem:
            bad.append("%s declares id %r" % (path.name, m.group(1)))
    assert not bad, "item filenames must match their id: %s" % "; ".join(bad)


class TestShippedBodiesCollapse:
    """Finished cards ship their text but must not pay to render it.

    Measured from the Lighthouse artefact of the run that first failed the
    ``minScore 0.85`` floor (perf 0.74 on ``docs/roadmap.html``): of 1.6 s of
    main-thread work, ``styleLayout`` was 705 ms and ``paintCompositeRender``
    393 ms, against 20 ms of script evaluation. The cost is laying out and
    painting 6,316 elements, not bytes and not JavaScript — so the fix is to
    stop *rendering* finished cards, which a closed ``<details>`` does while
    leaving every word in the source.
    """

    def _card(self, builder, **over):
        item = {"id": "x", "status": "shipped", "category": "C", "title": "T",
                "body": "BODY-TEXT", "complexity": "S", "impact": "Med",
                "wow": 1, "note": "n", "_file": "x.md"}
        item.update(over)
        return builder.render_code_card(item)

    def test_a_shipped_card_collapses_its_body(self):
        html = self._card(_load_builder())
        assert "<details" in html and "</details>" in html

    def test_the_text_is_still_in_the_source(self):
        # The point is to skip layout, not to hide the writing: closing a card
        # well means recording what was measured, and that has to stay
        # findable with the browser's own find-in-page and by grep.
        assert "BODY-TEXT" in self._card(_load_builder())

    def test_it_is_closed_so_layout_is_actually_skipped(self):
        # An `open` details lays out exactly like a <p> and saves nothing.
        html = self._card(_load_builder())
        assert "<details open" not in html

    def test_unfinished_cards_stay_expanded(self):
        # Planned/next/inflight work is what a reader came for; collapsing it
        # would trade a real page for a score.
        for status in ("planned", "next", "inflight"):
            html = self._card(_load_builder(), status=status)
            assert "<details" not in html, status
            assert "BODY-TEXT" in html

    def test_the_summary_is_labelled(self):
        # A bare <summary> renders as an unlabelled triangle, which is a
        # keyboard/screen-reader trap and would fail the a11y sweep.
        html = self._card(_load_builder())
        start = html.index("<summary")
        text = html[start:html.index("</summary>", start)]
        assert len(text.split(">", 1)[1].strip()) >= 4, text

    def test_the_anchor_survives(self):
        # Cards deep-link each other by id; the drift diagnosis also keys on
        # this exact opening tag.
        assert '<article class="cap rcard" id="x">' in self._card(_load_builder())
