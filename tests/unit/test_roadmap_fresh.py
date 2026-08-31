# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_roadmap.py"
_ITEMS = _ROOT / "docs" / "roadmap" / "items"
_CODE_HTML = _ROOT / "docs" / "roadmap.html"
_DESIGN_HTML = _ROOT / "docs" / "design-roadmap.html"


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


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
@pytest.mark.parametrize("body", [
    "the clip bound was <code>x < w - 1</code>, which fails",
    "compare <code>a < b</code>",
    "prose with a < b comparison",
    "<code>if x<y</code>",
])
def test_a_raw_angle_bracket_is_refused(body):
    """Same trap as the block-tag check, different symptom.

    A `<` that does not open a tag is invalid HTML, and html-validate says so
    in a separate workflow minutes after every roadmap script reports clean —
    which is exactly how `x < w - 1` shipped in a card body. Catching it at
    generation time names the file while the author is still holding it.
    """
    builder = _load_builder()
    with pytest.raises(builder.RoadmapError) as ei:
        builder.check_body_is_inline("some-card.md", body)
    assert "some-card.md" in str(ei.value)
    assert "&lt;" in str(ei.value), "the message must say what to write instead"


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
@pytest.mark.parametrize("text", [
    "boost infer > SKILL.md writes the AI warning as line 1",
    'its "> " prompt leaks into piped stdout',
    "prose with a > b comparison",
    "<code>x -> y</code>",
])
def test_a_raw_greater_than_is_refused(text):
    """The other half of the raw-`<` guard.

    `no-raw-characters` rejects a bare `>` in text content exactly as it
    rejects a bare `<`, and in the same place: a separate required workflow,
    minutes after every roadmap script has reported clean. Two cards shipped
    that way — both in a `note:`, which nothing checked at all.
    """
    builder = _load_builder()
    with pytest.raises(builder.RoadmapError) as ei:
        builder.check_body_is_inline("some-card.md", text)
    assert "some-card.md" in str(ei.value)
    assert "&gt;" in str(ei.value), "the message must say what to write instead"


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
def test_a_card_note_is_guarded_like_a_body():
    """`note:` is interpolated into a <span> as raw HTML, so it needs the guard.

    The body had two angle-bracket guards and the one-line note beside it had
    none, which is how `boost infer > SKILL.md` reached html-validate.
    """
    builder = _load_builder()
    item = {"_file": "some-card.md", "id": "x", "title": "t", "body": "b",
            "status": "planned", "impact": "Med", "wow": 1,
            "complexity": "S", "category": "c",
            "note": "boost infer > SKILL.md"}
    with pytest.raises(builder.RoadmapError) as ei:
        builder.render_code_card(item)
    assert "some-card.md" in str(ei.value)


@pytest.mark.skipif(not (_SCRIPT.exists() and _ITEMS.exists()),
                    reason="repo-root files not reachable")
def test_every_card_note_is_inline():
    """Every shipped `note:` survives the guard the renderer now applies."""
    builder = _load_builder()
    for board in ("code", "design"):
        for item in builder.load_items(board):
            note = item.get("note")
            if note not in (None, ""):
                builder.check_body_is_inline(item["_file"], str(note))


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
@pytest.mark.parametrize("body", [
    "plain prose with no markup at all",
    "<b>bold</b> and <em>italic</em> and <code>code</code>",
    "an escaped <code>a &lt; b</code> comparison",
    "an escaped <code>a &gt; b</code> comparison",
    "an arrow <code>a -&gt; b</code> inside code",
    "an arrow → and a middot &middot; and an entity &amp;",
    "<a href='#x'>a link</a>",
])
def test_legitimate_inline_markup_still_passes(body):
    """The guard must not start rejecting the markup every card already uses."""
    _load_builder().check_body_is_inline("some-card.md", body)


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


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
def test_the_design_board_can_record_a_measured_no():
    """A design idea that was investigated and rejected needs somewhere to land.

    The code board grew a `declined` pill for exactly this: without one, a
    refuted item sits as `proposed` forever, reads as backlog, and the next
    loop scanning for work re-opens the same question. The design board had no
    such status, so `render_design_card` rejected it outright.
    """
    builder = _load_builder()
    assert builder.DESIGN_STATUS["declined"] == "Declined"
    card = builder.render_design_card({
        "_file": "x.md", "id": "BOOST-DX", "track": "motion", "status": "declined",
        "impact": "med", "wow": 3, "title": "t", "body": "b"})
    assert 'class="rstatus declined"' in card
    assert ">Declined<" in card


@pytest.mark.skipif(not _SCRIPT.exists(), reason="repo-root files not reachable")
def test_the_declined_pill_is_not_struck_through():
    """Strikethrough is this board's "shipped"; a decline is a different answer.

    Styling it like `.done` would say the work happened. Both are muted, and
    only one is crossed out.
    """
    css = (_ROOT / "docs" / "design-roadmap.html").read_text(encoding="utf-8")
    rule = [ln for ln in css.splitlines() if ".rstatus.declined" in ln]
    assert rule, "no .rstatus.declined rule — the pill would render unstyled"
    assert "line-through" not in rule[0]


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


_RULE = re.compile(r"([^{}]+?)\{([^{}]*)\}", re.DOTALL)
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _declares(html: str, selector: str, declaration: str) -> bool:
    """Does the page's stylesheet carry ``declaration`` under ``selector``?

    Crude on purpose — a real CSS parser is a dependency, and the property this
    pins is written on exactly one line. Comments are stripped first because
    everything between two braces is captured as the selector, so a rule
    documented on the line above it would otherwise never match its own name.
    ``@media`` wrappers do not confuse it: the inner rules still match, and the
    outer at-rule is only ever consumed into a selector no assertion looks for.
    """
    style = html.split("<style", 1)[1].split(">", 1)[1].split("</style>", 1)[0]
    return any(sel.strip() == selector and declaration in body
               for sel, body in _RULE.findall(_COMMENT.sub("", style)))


@pytest.mark.skipif(not (_CODE_HTML.exists() and _DESIGN_HTML.exists()),
                    reason="repo-root files not reachable (e.g. mutation sandbox)")
class TestLongCodeTokensCanBreak:
    """Card ``<code>`` must be allowed to break mid-token, on both boards.

    Card text is dense with identifiers; the grid track is
    ``minmax(320px, 1fr)``, a floor that does not shrink; and at a 375px
    viewport the wrap column is 327px and a card's own content box 283px. One
    unbreakable identifier wider than that pushes the track past its floor and
    the whole document scrolls sideways. ``visual_check.mjs`` measures exactly
    that — document ``scrollWidth`` against ``clientWidth``, at 375px, on these
    two pages — and it went red the first time an ``inflight`` card carried a
    46-character test name (68px of overflow on ``docs/roadmap.html``).

    Until then the boards passed by luck: only ``shipped`` bodies collapse into
    a closed ``<details>``, and a closed ``<details>`` subtree is never laid
    out, so the 113-character tokens sitting in shipped cards could not
    overflow. Everything else — ``planned``, ``next``, ``inflight``,
    ``declined`` — renders laid out, and a declined card in particular stays
    expanded forever. This test is what replaces that luck.

    ``overflow-wrap: anywhere`` and not ``break-word``: both break the glyph
    run, but only ``anywhere`` also shrinks the element's *min-content* size,
    which is what lets the grid item reach the width the break makes possible.
    """

    CARDS = (("docs/roadmap.html", _CODE_HTML, ".rcard code"),
             ("docs/design-roadmap.html", _DESIGN_HTML, ".ritem code"))

    def test_each_board_lets_card_code_break(self):
        for name, path, selector in self.CARDS:
            assert _declares(path.read_text(encoding="utf-8"), selector,
                             "overflow-wrap: anywhere"), (
                "%s needs `%s { overflow-wrap: anywhere }` or one long "
                "identifier in an unshipped card scrolls the page sideways"
                % (name, selector))

    def test_the_selector_actually_reaches_a_generated_card(self):
        """The rule is scoped to a class, so pin that the cards still wear it.

        A stylesheet assertion on its own would keep passing if the generator
        renamed the card class — the exact drift that would leave the boards
        unprotected while the test stayed green.
        """
        builder = _load_builder()
        code = builder.render_code_card(
            {"id": "x", "status": "inflight", "category": "C", "title": "T",
             "body": "B", "complexity": "S", "impact": "Med", "wow": 1,
             "note": "n", "_file": "x.md"})
        design = builder.render_design_card(
            # The two boards do not share a status vocabulary, so take the
            # design one from the module rather than pinning a literal here.
            {"id": "y", "status": next(iter(builder.DESIGN_STATUS)),
             "track": "T", "title": "T", "body": "B", "impact": "med",
             "wow": 1, "note": "n", "_file": "y.md"})
        for html, cls in ((code, "rcard"), (design, "ritem")):
            assert re.search(r'class="[^"]*\b%s\b' % cls, html), html[:120]
