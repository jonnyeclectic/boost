#!/usr/bin/env python3
"""Render the roadmap dashboards from per-item source files.

The roadmap boards used to be hand-edited HTML: every loop appended
``<article>`` cards and hand-incremented shared counter integers into one big
file, so parallel loops collided constantly. This generator makes the boards
data-driven — one small Markdown-with-frontmatter file per item under
``docs/roadmap/items/`` — and *injects* the rendered cards and counters into the
marker regions of the existing hand-authored pages. Everything outside the
markers (hero, nav, CSS, filters, footer) is preserved byte-for-byte, so the
bespoke design is untouched and only the conflict-prone card grids are generated.

Two loops adding two different items now create two different files → clean
merge. A status flip edits one small file, never a shared line in a 1,400-line
document. Counters are computed, never hand-typed.

Item file (``docs/roadmap/items/<id>.md``):

    ---
    id: store-mutation-hardening
    board: code                 # code -> roadmap.html ; design -> design-roadmap.html
    section: shipped            # which board section the card renders in
    status: shipped             # pill: shipped|inflight|next|planned
    category: "Testing · Bug"
    complexity: M
    impact: High                # High|Med|Low
    wow: 3                      # filled-star count
    note: "25 mutants killed"   # optional trailing meta line (may contain HTML)
    order: 1                    # sort key within the section (migration parity)
    owner:                      # loop/<topic> when claimed (Phase 2)
    pr:                         # PR number/URL once opened
    title: "Mutation hardening — <code>core/store.py</code>"
    ---
    Cut mutmut survivors 54&nbsp;→&nbsp;29 and uncovered a latent
    timestamp-preservation bug the old tests masked ...

Run:    python3 scripts/build_roadmap.py            # regenerate the HTML in place
Verify: python3 scripts/build_roadmap.py --check    # fail if it has drifted
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Reuse the repo's stdlib-only frontmatter parser (no new dependency) instead of
# pulling in PyYAML. Importable without installing the package.
sys.path.insert(0, str(ROOT))
from boost_cli.core import frontmatter  # noqa: E402

ITEMS_DIR = ROOT / "docs" / "roadmap" / "items"
CODE_HTML = ROOT / "docs" / "roadmap.html"
DESIGN_HTML = ROOT / "docs" / "design-roadmap.html"

# Pill class -> visible label (code board).
STATUS_LABEL = {
    "shipped": "Shipped",
    "inflight": "In flight",
    "next": "Next",
    "planned": "Planned",
    # A measured "no". Without it, an item that was investigated and rejected
    # sits on the board as `planned` forever and reads as backlog, so the next
    # loop scanning for work re-opens the same question. The pill is muted
    # rather than coloured because a decline is not a lifecycle stage.
    "declined": "Declined",
}

# rstatus class -> visible label (design board).
DESIGN_STATUS = {
    "done": "Shipped",
    "progress": "In progress",
    "proposed": "Proposed",
}
IMPACT_LABEL = {"high": "High", "med": "Med", "low": "Low"}
DESIGN_TRACKS = ["color", "layout", "motion", "commands", "system"]


class RoadmapError(Exception):
    """Raised on malformed item data so CI fails loudly rather than silently."""


# --------------------------------------------------------------------------- #
# Loading                                                                      #
# --------------------------------------------------------------------------- #
def load_items(board: str) -> list[dict]:
    """Load every item for ``board``, sorted by (section, order, id)."""
    items = []
    for path in sorted(ITEMS_DIR.glob("*.md")):
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        if meta.get("board") != board:
            continue
        meta["body"] = body.strip()
        meta["_file"] = path.name
        if not meta.get("id"):
            raise RoadmapError("%s: missing 'id'" % path.name)
        items.append(meta)
    items.sort(key=lambda m: (str(m.get("section", "")),
                              _as_int(m.get("order"), 9999),
                              str(m.get("id"))))
    return items


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Rendering — code board (roadmap.html)                                        #
# --------------------------------------------------------------------------- #
# Statuses whose body is collapsed. Only `shipped` — 188 of 192 cards, so it is
# effectively the whole win, while anything a reader might act on stays open.
# Collapsing `declined` too was tried and measured: it cut laid-out body text
# by 33%, and moved the Lighthouse performance score by 0.00 (0.83 both ways).
# The page is not layout-bound any more, so the change was reverted rather
# than kept on a rationale the measurement had already falsified.
_SETTLED = ("shipped",)


# Block-level tags that cannot appear inside a paragraph. Every card body is
# emitted inside <p> whatever its status, so any of these implicitly closes it
# and leaves a stray </p> — invalid HTML that only html-validate catches, in a
# different required workflow, minutes after every roadmap script has reported
# clean. Two cards tripped it while being written, so the generator refuses.
_BLOCK_TAGS = ("pre", "table", "div", "ul", "ol", "blockquote", "hr",
               "h1", "h2", "h3", "h4", "h5", "h6", "p")
_BLOCK_RE = re.compile(r"<(%s)[\s/>]" % "|".join(_BLOCK_TAGS), re.IGNORECASE)


def check_body_is_inline(where: str, body: str) -> None:
    """Raise if ``body`` contains a tag that a `<p>` cannot hold."""
    found = _BLOCK_RE.search(body or "")
    if found:
        raise RoadmapError(
            "%s: card bodies render inside <p>, so <%s> is invalid there — it "
            "implicitly closes the paragraph and html-validate fails the build. "
            "Use inline markup (<code>, <b>, <em>, &middot; separators)."
            % (where, found.group(1)))


def _body_html(status: str, body: str) -> str:
    """A card body, collapsed once the work is finished.

    WHY, with the numbers. Closing an item well means recording what was
    measured and what turned out to be wrong, so bodies grow and finished cards
    never stop costing. Measured on the Lighthouse run that first breached the
    `minScore 0.85` floor (perf 0.74): 1.6 s of main-thread work, of which
    `styleLayout` was 705 ms and `paintCompositeRender` 393 ms, against 20 ms of
    script evaluation. The page is not slow because of bytes or JavaScript — it
    is slow because the browser lays out and paints 6,316 elements.

    A *closed* `<details>` is the cheap fix for exactly that shape: the subtree
    still parses and still ships, so every word stays greppable and findable by
    the browser's own find-in-page, but it is never laid out or painted. It does
    not reduce transfer size or DOM node count, and it is not meant to — neither
    is what the measurement blamed.
    """
    check_body_is_inline("", body)
    if status not in _SETTLED:
        return "        <p>%s</p>" % body
    # The <summary> carries real text rather than a bare marker: an unlabelled
    # triangle is a keyboard and screen-reader trap, and the a11y sweep covers
    # this page.
    return ('        <details class="cardbody"><summary>Write-up</summary>\n'
            "        <p>%s</p></details>" % body)


def render_code_card(item: dict) -> str:
    status = str(item.get("status", "planned"))
    if status not in STATUS_LABEL:
        raise RoadmapError("%s: unknown status %r" % (item["_file"], status))
    label = STATUS_LABEL[status]
    impact = str(item.get("impact", "Med"))
    imp_cls = " hi" if impact.lower() == "high" else ""
    stars = "★" * _as_int(item.get("wow"), 0)
    note = item.get("note")
    lines = [
        # The item id doubles as the card's anchor, so one item can link
        # another (`<a href="#other-id">`) and a card can be deep-linked.
        '      <article class="cap rcard" id="%s">' % item.get("id", ""),
        '        <div class="head"><span class="pill %s">%s</span>'
        '<span class="cat">%s</span></div>' % (status, label, item.get("category", "")),
        "        <h3>%s</h3>" % item.get("title", ""),
        _body_html(status, item["body"]),
        '        <div class="meta">',
        '          <span class="m">Complexity <b>%s</b></span>' % item.get("complexity", ""),
        '          <span class="m%s">Impact <b>%s</b></span>' % (imp_cls, impact),
        '          <span class="m">Wow <b class="wow">%s</b></span>' % stars,
    ]
    if note not in (None, ""):
        lines.append('          <span class="m">%s</span>' % note)
    lines += ["        </div>", "      </article>"]
    return "\n".join(lines)


def code_blocks(items: list[dict]) -> dict[str, str]:
    """Marker-key -> rendered HTML for the code board.

    The snapshot's Shipped/Next/Planned tiles count the three *lifecycle*
    sections (not global pill status — the category sections carry many more
    ``planned`` pills that the snapshot deliberately omits). "Loop finds" is the
    total number of items, so it can never drift from what's on the page.
    """
    by_section: dict[str, list[dict]] = {}
    for it in items:
        by_section.setdefault(str(it.get("section", "")), []).append(it)
    blocks = {
        "cards section=%s" % sec: "\n\n".join(render_code_card(i) for i in cards)
        for sec, cards in by_section.items()
    }
    blocks["stats"] = "\n".join([
        '      <div class="stat"><b>%d</b><span>Shipped</span></div>' % len(by_section.get("shipped", [])),
        '      <div class="stat"><b>%d</b><span>Next up</span></div>' % len(by_section.get("next", [])),
        '      <div class="stat"><b>%d</b><span>Planned</span></div>' % len(by_section.get("planned", [])),
        '      <div class="stat"><b>%d</b><span>Loop finds</span></div>' % len(items),
    ])
    return blocks


# --------------------------------------------------------------------------- #
# Rendering — design board (design-roadmap.html)                               #
# --------------------------------------------------------------------------- #
def render_design_card(item: dict) -> str:
    status = str(item.get("status", "proposed"))
    if status not in DESIGN_STATUS:
        raise RoadmapError("%s: unknown status %r" % (item["_file"], status))
    impact = str(item.get("impact", "med")).lower()
    if impact not in IMPACT_LABEL:
        raise RoadmapError("%s: unknown impact %r" % (item["_file"], impact))
    wow = _as_int(item.get("wow"), 0)
    stars = "★" * wow + "☆" * (5 - wow)
    lines = [
        '<article class="ritem" id="%s" data-track="%s" data-impact="%s">'
        % (item.get("id", ""), item.get("track", ""), impact),
        '  <div class="ritem-top"><span class="rid">%s</span>'
        '<span class="rstatus %s">%s</span></div>'
        % (item.get("id", ""), status, DESIGN_STATUS[status]),
        # h3, not h4: the card sits inside a track whose heading is an h2, and a
        # skipped level is a WCAG 1.3.1 failure (scripts/a11y_check.py). The
        # `.ritem h3` selector in design-roadmap.html carries the styling.
        "  <h3>%s</h3>" % item.get("title", ""),
        "  <p>%s</p>" % item["body"],
        '  <div class="rmeta"><span class="m-cat">%s</span>'
        "<span>Complexity %s</span>"
        '<span class="m-imp %s">Impact %s</span>'
        '<span class="m-wow">%s</span></div>'
        % (item.get("category", item.get("track", "")), item.get("complexity", ""),
           impact, IMPACT_LABEL[impact], stars),
    ]
    ref = item.get("ref")
    if ref not in (None, ""):
        lines.append('  <div class="rref"><code>%s</code></div>' % ref)
    lines.append("</article>")
    return "\n".join(lines)


def design_blocks(items: list[dict]) -> dict[str, str]:
    """Marker-key -> rendered HTML/text for the design board."""
    by_track: dict[str, list[dict]] = {}
    for it in items:
        by_track.setdefault(str(it.get("track", "")), []).append(it)
    blocks: dict[str, str] = {}
    for track in DESIGN_TRACKS:
        cards = by_track.get(track, [])
        blocks["cards track=%s" % track] = "\n\n".join(
            render_design_card(i) for i in cards)
        blocks["count track=%s" % track] = "%d items" % len(cards)
    # "N of N opportunities shown" — both start at the total (JS lowers #shown
    # as filters apply, so the committed value is the unfiltered total).
    blocks["count shown"] = str(len(items))
    blocks["count total"] = str(len(items))
    return blocks


# --------------------------------------------------------------------------- #
# Marker injection                                                            #
# --------------------------------------------------------------------------- #
def inject(html: str, key: str, rendered: str) -> str:
    """Replace the content between ``<!-- ROADMAP:key -->`` markers.

    Markers are HTML comments so they are invisible on the rendered page and
    survive round-trips. Missing markers are a hard error — a card block with no
    home means the item would silently vanish.
    """
    begin = "<!-- ROADMAP:%s -->" % key
    end = "<!-- /ROADMAP:%s -->" % key.split(" ")[0]
    pattern = re.compile(
        re.escape(begin) + r"(?P<mid>.*?)" + re.escape(end), re.DOTALL)
    m = pattern.search(html)
    if not m:
        raise RoadmapError("marker %r not found in target HTML" % key)
    mid = m.group("mid")
    if "\n" in mid or "\n" in rendered:
        # Block region: preserve the indentation of the line the end marker sits
        # on so the closing comment stays aligned under its container.
        tail = mid.rsplit("\n", 1)[-1]
        indent = tail if tail.strip() == "" else ""
        body = "\n" + rendered + "\n" + indent
    else:
        # Inline region (e.g. a counter inside <b>…</b>).
        body = rendered
    return html[:m.start()] + begin + body + end + html[m.end():]


def render_board(html: str, blocks: dict[str, str]) -> str:
    for key, rendered in blocks.items():
        html = inject(html, key, rendered)
    return html


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_code() -> tuple[Path, str]:
    items = load_items("code")
    html = render_board(CODE_HTML.read_text(encoding="utf-8"), code_blocks(items))
    return CODE_HTML, html


def build_design() -> tuple[Path, str]:
    items = load_items("design")
    html = render_board(DESIGN_HTML.read_text(encoding="utf-8"), design_blocks(items))
    return DESIGN_HTML, html


_CARD_ID = re.compile(r'<article class="(?:cap rcard|ritem)" id="([^"]+)"')


def diagnose(path, committed: str, fresh: str) -> list[str]:
    """Explain *why* a board drifted, in the terms the reader needs.

    The common cause is not a hand-edit. It is a rebase: another PR's card
    merges in as a clean new ``docs/roadmap/items/*.md``, git merges the
    generated HTML textually and succeeds, and the board is silently missing
    that card. The old message said only "out of date", so a PR that changed no
    Python at all went red across lint and every test leg with nothing in the
    log pointing at the actual cause.
    """
    was = _CARD_ID.findall(committed)
    now = _CARD_ID.findall(fresh)
    missing = [i for i in now if i not in set(was)]
    extra = [i for i in was if i not in set(now)]
    lines = []
    if missing:
        lines.append("  missing %d card(s) present in docs/roadmap/items/: %s"
                     % (len(missing), ", ".join(missing[:8])
                        + (" …" if len(missing) > 8 else "")))
        lines.append("  ↳ almost always a rebase: someone else's card landed on "
                     "main and the generated HTML merged textually.")
    if extra:
        lines.append("  %d card(s) in the HTML have no item file: %s"
                     % (len(extra), ", ".join(extra[:8])
                        + (" …" if len(extra) > 8 else "")))
    if not missing and not extra:
        lines.append("  the same cards, rendered differently — an item file's "
                     "fields or body changed, or the generator did.")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the roadmap boards.")
    parser.add_argument(
        "--check", action="store_true",
        help="verify committed HTML matches a fresh render; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    targets = [build_code(), build_design()]
    drift = []
    for path, fresh in targets:
        if args.check:
            committed = path.read_text(encoding="utf-8")
            if committed != fresh:
                drift.append((path, committed, fresh))
        else:
            path.write_text(fresh, encoding="utf-8")
            print("wrote %s" % path)

    if args.check:
        if drift:
            report = ["ERROR: the roadmap board is stale — regenerate with",
                      "    python3 scripts/build_roadmap.py",
                      "and commit the result (see CONTRIBUTING.md).",
                      ""]
            for path, committed, fresh in drift:
                report.append("%s" % path)
                report.extend(diagnose(path, committed, fresh))
            print("\n".join(report), file=sys.stderr)
            # One annotation so the cause is visible on the checks tab without
            # opening a log: this failure lands on every matrix leg at once and
            # reads as a broken build rather than a stale generated file.
            print("::error::roadmap board is stale — run "
                  "`python3 scripts/build_roadmap.py` and commit "
                  "(usually needed after a rebase)")
            return 1
        print("roadmap boards are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
