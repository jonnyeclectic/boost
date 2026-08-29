# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The docsite stays in lockstep with the CLI and with its own design system.

Four drift classes this locks down, each of which had actually shipped:

* ``docs/index.html`` embeds its own copy of the command inventory (a JS array
  the filterable Commands section renders from) plus a hand-typed "N commands"
  headline. Both had fallen five commands behind ``cli.py``'s ``COMMANDS`` —
  ``adapt``, ``run``, ``trust``, ``hooks`` and ``bmad`` were undiscoverable from
  the guide. ``docs/commands.html`` is generated and so can't drift; this page
  is hand-maintained and so can.
* ``style/boost.css`` owns the nav and footer chrome, but a page only gets it by
  using the markup — three pages carried no nav and two carried no footer.
* Footers are user-facing. Stylesheet credits, PR numbers and build chatter had
  accumulated in them.
* The nav has to survive a phone. ``roadmap.html`` hid it outright below 560px.

Skips when the repo-root files aren't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from boost_cli.cli import COMMANDS

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"
_CSS = _ROOT / "style" / "boost.css"
_INDEX = _DOCS / "index.html"

# Every page of the docsite. Each carries the footer, and each is linked from
# all the others — the standing "no new page ships unlinked" rule.
_PAGES = (
    "index.html", "commands.html", "roadmap.html", "design-roadmap.html",
    "mcp-hub.html", "eval.html", "adapters.html", "carousel.html", "demo.html",
    "chat.html", "langchain.html",
)
# commands.html is a sidebar reference, not a top-nav page; it links the rest
# from its footer and its sidebar "back to overview".
_NAV_PAGES = tuple(p for p in _PAGES if p != "commands.html")

_ready = _CSS.exists() and all((_DOCS / p).exists() for p in _PAGES)
pytestmark = pytest.mark.skipif(
    not _ready, reason="repo-root docs/style not reachable (e.g. mutation sandbox)")


def _index() -> str:
    return _INDEX.read_text(encoding="utf-8")


def _embedded_commands(html: str) -> list[tuple[str, str, str]]:
    """The ``const COMMANDS = [...]`` rows the Commands section renders from."""
    start = html.index("const COMMANDS = [")
    end = html.index("];", start)
    return re.findall(r'\["([^"]+)","([^"]+)","([^"]*)"\]', html[start:end])


def test_index_command_inventory_matches_the_cli():
    embedded = _embedded_commands(_index())
    assert embedded == [
        (name, group, summary) for name, group, _mod, summary in COMMANDS
    ], (
        "docs/index.html's embedded command list has drifted from cli.py's "
        "COMMANDS — update the `const COMMANDS = [...]` array in the Commands "
        "section (same order, name/group/summary)."
    )


def test_index_command_count_headline_matches_the_cli():
    claims = re.findall(r"\b(\d+) commands\b", _index())
    assert claims, "docs/index.html no longer states a command count"
    assert set(claims) == {str(len(COMMANDS))}, (
        "docs/index.html advertises %s commands but cli.py's COMMANDS has %d"
        % (sorted(set(claims)), len(COMMANDS))
    )


def test_index_hero_stat_matches_the_command_count():
    stat = re.search(r"<b>(\d+)</b><span>Commands · 8 groups</span>", _index())
    assert stat, "docs/index.html lost its command-count hero stat"
    assert int(stat.group(1)) == len(COMMANDS)


def test_index_command_groups_match_the_cli():
    """The eight group keys the page filters by are the CLI's own groups."""
    declared = set(re.findall(r"^  (\w+):\s+\{ icon:", _index(), re.M))
    assert declared == {group for _n, group, _m, _s in COMMANDS}


def test_carousel_group_counts_match_the_cli():
    """Each slide's "N commands in this group" is hand-typed, so it drifts.

    The page shipped claiming 76 commands with two group counts already wrong;
    every slide is tagged ``data-group`` so this maps to COMMANDS mechanically.
    """
    html = (_DOCS / "carousel.html").read_text(encoding="utf-8")
    slides = re.findall(
        r'data-group="(\w+)".*?<p class="group-note">(\d+) commands in this group',
        html, re.S)
    assert len(slides) == 8, "expected one slide per command group, got %d" % len(slides)
    actual = {}
    for _name, group, _mod, _summary in COMMANDS:
        actual[group] = actual.get(group, 0) + 1
    assert [(g, int(n)) for g, n in slides] == [(g, actual[g]) for g, _n in slides]


def test_carousel_covers_every_command_group():
    html = (_DOCS / "carousel.html").read_text(encoding="utf-8")
    assert set(re.findall(r'data-group="(\w+)"', html)) == {
        group for _n, group, _m, _s in COMMANDS}


def test_carousel_slides_name_real_commands():
    """The flagship <h3> and the chip list must not outlive a renamed command."""
    html = (_DOCS / "carousel.html").read_text(encoding="utf-8")
    names = {name for name, _g, _m, _s in COMMANDS}
    cited = set(re.findall(r"<h3><code>boost ([\w-]+)</code></h3>", html))
    for block in re.findall(r'<div class="tags">(.*?)</div>', html, re.S):
        cited |= set(re.findall(r"<code>([^<]+)</code>", block))
    assert cited <= names, "carousel names commands the CLI no longer has: %s" % (
        sorted(cited - names))


def test_every_carousel_gif_has_a_tape_and_alt_text():
    """A GIF without its VHS tape can't be regenerated; one without alt text
    makes the page unusable with images off."""
    gifs = {p.stem for p in (_DOCS / "carousel" / "gifs").glob("*.gif")}
    tapes = {p.stem for p in (_DOCS / "carousel" / "tapes").glob("*.tape")}
    assert gifs == tapes, "gif/tape mismatch: %s" % sorted(gifs ^ tapes)
    html = (_DOCS / "carousel.html").read_text(encoding="utf-8")
    for img in re.findall(r"<img[^>]*carousel/gifs/[^>]*>", html):
        alt = re.search(r'alt="([^"]*)"', img)
        assert alt and len(alt.group(1)) > 40, "GIF needs descriptive alt text: %s" % img[:80]


@pytest.mark.parametrize("page", _NAV_PAGES)
def test_every_page_has_the_shared_nav(page):
    """style/boost.css documents two accepted forms: .site-nav or .nav."""
    html = (_DOCS / page).read_text(encoding="utf-8")
    assert 'class="wrap site-nav"' in html or 'class="wrap nav"' in html, (
        "%s does not use the shared nav chrome from style/boost.css" % page)


@pytest.mark.parametrize("page", _PAGES)
def test_every_page_has_exactly_one_footer(page):
    """Match ``<footer`` rather than ``<footer>``: a page carrying a classed
    footer (``<footer class="site-foot">``) reads as having none otherwise, and
    the fix is then to add a second one."""
    html = (_DOCS / page).read_text(encoding="utf-8")
    opens = re.findall(r"<footer[^>]*>", html)
    assert len(opens) == 1, "%s has %d footers (%s)" % (page, len(opens), opens)
    assert opens[0] == "<footer>", (
        "%s styles its footer locally (%s) — the shared sheet owns bare <footer>"
        % (page, opens[0]))


@pytest.mark.parametrize("page", _PAGES)
def test_no_page_is_an_orphan(page):
    """Every page links every other page, so a new page can't ship unreachable."""
    html = (_DOCS / page).read_text(encoding="utf-8")
    for other in _PAGES:
        if other == page:
            continue
        assert 'href="%s"' % other in html, (
            "%s does not link %s — every docs page belongs in the shared nav "
            "and footer" % (page, other))


@pytest.mark.parametrize("page", _PAGES)
def test_footers_carry_no_internal_noise(page):
    """Footers are user-facing: no stylesheet links, PR numbers, or build chatter."""
    html = (_DOCS / page).read_text(encoding="utf-8")
    foot = html[html.index("<footer>"):]
    for noise in ("style/boost.css", "/pull/", "quality loop", "Styled with"):
        assert noise not in foot, (
            "%s's footer still mentions %r — footers stay user-facing"
            % (page, noise))


def _hidden_nav_rules(html: str) -> list[str]:
    """CSS rules that hide the nav element itself (not a descendant of it).

    ``header .nav ul::-webkit-scrollbar { display: none }`` is deliberate — the
    row scrolls without a visible bar. ``.topbar nav { display: none }``, which
    is what roadmap.html shipped below 560px, is not.
    """
    return [
        "%s{%s}" % (one.strip(), body.strip())
        for style in re.findall(r"<style>(.*?)</style>", html, re.S)
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style)
        if re.search(r"display:\s*none", body)
        for one in sel.split(",")
        if re.search(r"(^|[\s>+~])(nav|\.[\w-]*nav)$", one.strip())
    ]


@pytest.mark.parametrize("page", _NAV_PAGES)
def test_nav_links_stay_reachable_on_small_screens(page):
    """No page may hide its nav outright at a breakpoint (roadmap.html once did)."""
    hidden = _hidden_nav_rules((_DOCS / page).read_text(encoding="utf-8"))
    assert not hidden, (
        "%s hides its nav (%s) — the shared .site-nav scrolls instead, so links "
        "stay reachable on a phone" % (page, "; ".join(hidden)))


def test_the_hidden_nav_detector_actually_detects():
    """Guard the guard — the regression this test exists for must still trip it."""
    assert _hidden_nav_rules(
        "<style>@media (max-width: 560px) { .topbar nav { display: none; } }</style>")
    assert not _hidden_nav_rules(
        "<style>header .nav ul::-webkit-scrollbar { display: none; }</style>")


def test_shared_sheet_gives_nav_links_a_touch_target():
    """The small-screen rules are what make a 14-link bar usable on a phone."""
    css = _CSS.read_text(encoding="utf-8")
    mobile = css[css.index("@media (max-width: 720px)"):]
    assert "min-height: 40px" in mobile, (
        "style/boost.css no longer gives small-screen nav links a 40px tap target")


def test_shared_sheet_uses_modern_color_notation():
    """stylelint-config-standard's notation rules, checked in the always-run suite.

    theme-lint.yml only fires on ``style/**`` changes and needs npm, so a
    legacy ``rgba(r, g, b, .08)`` slipped into an otherwise uniformly modern
    sheet reaches CI before anything else notices.
    """
    legacy = re.findall(r"\b(?:rgba|hsla)\([^)]*\)", _CSS.read_text(encoding="utf-8"))
    assert not legacy, (
        "style/boost.css uses legacy color notation (%s) — the sheet is "
        "uniformly `rgb(r g b / n%%)`, and stylelint's color-function-notation "
        "and alpha-value-notation rules require it" % ", ".join(legacy))


def test_only_the_nav_header_is_sticky_chrome():
    """A page's hero must not be a second bare <header>.

    style/boost.css styles the bare element (`header { position: sticky }`), so
    a hero wrapped in <header> silently picks up the nav's sticky bar —
    roadmap.html did exactly that.
    """
    for page in _NAV_PAGES:
        html = (_DOCS / page).read_text(encoding="utf-8")
        opens = re.findall(r"<header[^>]*>", html)
        assert len(opens) == 1, (
            "%s has %d <header> elements (%s) — only the nav may be one, or it "
            "inherits the shared sticky chrome" % (page, len(opens), opens))


@pytest.mark.parametrize("page", _PAGES)
def test_generic_elements_with_aria_label_declare_a_role(page):
    """html-validate's aria-label-misuse, checked in-suite so it fails first.

    ``aria-label`` is only meaningful on an element whose role supports a
    name — a bare ``<div aria-label="...">`` is invalid, and a screen reader
    ignores the label. ``<div class="pills" role="tablist">`` is the correct
    shape; the carousel shipped two divs without one.
    """
    html = (_DOCS / page).read_text(encoding="utf-8")
    bad = [
        tag for tag in re.findall(r"<(?:div|span)\b[^>]*>", html)
        if "aria-label=" in tag and not re.search(r'\brole="[^"]+"', tag)
    ]
    assert not bad, (
        "%s labels a generic element with no role: %s — add the role whose "
        "name the label provides" % (page, [t[:90] for t in bad]))


@pytest.mark.parametrize("page", _PAGES)
def test_no_duplicate_element_ids(page):
    """html-validate's no-dup-id, checked in-suite so it fails before CI does.

    Adding an anchor to a page that already carries one is easy to miss: the
    footer's own `#top` self-link keeps working either way, and only the
    validate job notices.
    """
    html = (_DOCS / page).read_text(encoding="utf-8")
    ids = re.findall(r'\sid="([^"]+)"', html)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, "%s repeats id(s): %s" % (page, ", ".join(dupes))
