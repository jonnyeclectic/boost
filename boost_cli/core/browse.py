# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure logic behind `boost browse` — everything the curses layer draws.

The TUI's drawing lives in ``commands/discovery.py``; every decision it makes
lives here. Curses cannot be asserted on, so a browser whose logic sits inside
the draw loop is a browser with no tests and no mutation coverage. Splitting it
this way is what lets the matching rules, the pane geometry, the focus model
and the detail panel each be checked directly.

The rule that shaped the matching: **a space is a token separator, so a space
has to reach the query.** It used to be bound to multi-select, with the
printable range starting at 33 to keep it out — which meant two words could
never be searched for at once. Space now types, the query splits on whitespace,
and every token must match somewhere in the scope. Tab took over selection.
"""
from __future__ import annotations

import difflib
import textwrap
from dataclasses import dataclass

#: Search scopes, in cycle order. `all` first because it is the useful default:
#: one token can come from the name and another from the description.
SCOPES = ("all", "name", "description", "tap", "category")

_SCOPE_LABELS = {
    "all": "all",
    "name": "name",
    "description": "descr",
    "tap": "tap",
    "category": "category",
}

#: Minimum readable width for the detail pane. Below this the pane is dropped
#: rather than rendered as a column of two-character fragments — a narrow
#: terminal is better served by a full-width list.
# Measured against the real row: a name, a [kind] badge, a version and a tap
# badge need ~34 columns before descriptions start truncating to ellipsis, and
# a detail pane under ~32 wraps `Review a pull request for…` into ribbons. At
# 58 columns the old 28/24 pair kept a 27-column list that clipped every
# description — technically two panes, practically neither.
_MIN_DETAIL_W = 32
_MIN_LIST_W = 34
#: Shortest terminal that keeps the status bar: four chrome rows, one result
#: (two rows), the bottom rule and the bar itself.
_MIN_STATUS_H = 8


def scope_label(scope: str) -> str:
    """Short display label for a scope."""
    return _SCOPE_LABELS.get(scope, scope)


def next_scope(scope: str, step: int = 1) -> str:
    """The next scope in cycle order, wrapping in both directions."""
    try:
        i = SCOPES.index(scope)
    except ValueError:
        return SCOPES[0]
    return SCOPES[(i + step) % len(SCOPES)]


def tokens(query: str) -> list[str]:
    """Split a query into lowercased search tokens.

    Whitespace-separated, empties dropped. This is the whole reason space must
    reach the query: without it there is exactly one token and no way to say
    "name mentions code AND description mentions review".
    """
    return [t for t in query.lower().split() if t]


def entry_category(entry: dict, categories=None) -> str:
    """The category an entry is filed under, or ``""``.

    The entry's own stamped ``category`` (``catalog.CACHE_FORMAT`` 2+) wins;
    ``categories`` (tap -> category, from the bundled registry catalogue) is
    the fallback for a cache written before that field existed. One function,
    because the row chip, the detail chips and the ``category`` scope all have
    to agree on what an entry's category *is* — a chip saying ``#testing`` on
    a row the category filter cannot find reads as a broken filter.
    """
    own = entry.get("category")
    if own:
        return str(own)
    return str((categories or {}).get(entry.get("tap", ""), "") or "")


def short_tap(tap: str | None) -> str:
    """A tap as a row shows it: the repo name, without the owner.

    ``trailofbits/skills`` badged in full on every row is the same twenty
    characters 2,000 times over; the owner is in the detail pane, where there
    is room for it.
    """
    return str(tap or "").rsplit("/", 1)[-1]


def haystack(entry: dict, scope: str, categories=None) -> str:
    """The text ``scope`` searches for one entry."""
    name = str(entry.get("name", ""))
    if scope == "name":
        return name.lower()
    if scope == "description":
        return str(entry.get("description", "")).lower()
    if scope == "tap":
        return str(entry.get("tap", "")).lower()
    if scope == "category":
        return entry_category(entry, categories).lower()
    # `all`, and any unrecognised scope: never raise on a keystroke.
    return " ".join((name, str(entry.get("description", "")),
                     str(entry.get("tap", "")),
                     str(entry.get("kind", "")),
                     entry_category(entry, categories))).lower()


def subseq(needle: str, hay: str) -> bool:
    """True when needle is a subsequence of hay (the fuzzy test).

    ``str.find`` rather than the shorter ``all(ch in iter(hay))``: the iterator
    form advances one character at a time in Python, and this runs once per
    entry per token on every keystroke. Over a 71,700-entry catalogue that
    difference is 4.5x — measured 66 ms vs 15 ms for a four-character token —
    which is the gap between a browser that keeps up with typing and one that
    does not.
    """
    i = 0
    for ch in needle:
        i = hay.find(ch, i)
        if i < 0:
            return False
        i += 1
    return True


def index_entries(entries, scope: str,
                  categories=None) -> list[tuple[dict, str]]:
    """Pair each entry with its lowercased haystack for ``scope``.

    Built once per scope and reused for every keystroke. Rebuilding the joined
    string inside the filter cost 125 ms per key on a 71,700-entry catalogue —
    worse than the 80 ms draw poll, so the browser fell behind a typist. The
    index is caller-owned rather than a module cache: the TUI holds the entry
    list for the whole session, and a global keyed on object identity would be
    a use-after-free waiting for the first caller that does not.
    """
    return [(e, haystack(e, scope, categories)) for e in entries]


#: Rank tiers, best first. A match is placed by how its *name* meets the
#: query; anything that matched only through the description, tap or a
#: scattered subsequence sorts last, in catalogue order.
EXACT, PREFIX, SUBSTRING, FUZZY, ELSEWHERE = range(5)


def match_tier(name: str, toks: list[str]) -> int:
    """Which rank tier an entry named ``name`` falls in for ``toks``.

    ``toks`` joined by a space *or* a hyphen both count as the name, because
    the name is ``code-review`` and the user types ``code review``.

    This is what fixes the browser's first impression. Matching is fuzzy, so
    over a 42,000-entry catalogue ``eight-twin`` matched 8,900 rows — and the
    list showed them in alphabetical order, with the one the user typed the
    name of somewhere past the first screen.
    """
    n = name.lower()
    if not toks:
        return ELSEWHERE
    joined = (" ".join(toks), "-".join(toks))
    if n in joined:
        return EXACT
    if n.startswith(joined):
        return PREFIX
    if all(t in n for t in toks):
        return SUBSTRING
    if all(subseq(t, n) for t in toks):
        return FUZZY
    return ELSEWHERE


def rank(found: list[dict], query: str) -> list[dict]:
    """``found`` ordered by :func:`match_tier`, catalogue order within a tier.

    A stable sort on the tier alone, so the incoming order (alphabetical, in
    the browser) breaks every tie. An empty query returns ``found`` untouched:
    there is nothing to rank by, and the first frame should not pay for a sort.
    """
    toks = tokens(query)
    if not toks:
        return found
    return sorted(found, key=lambda e: match_tier(str(e.get("name", "")), toks))


def matches_indexed(indexed, query: str) -> list[dict]:
    """Filter a list built by :func:`index_entries`, best matches first."""
    toks = tokens(query)
    if not toks:
        return [e for e, _hay in indexed]
    return rank([e for e, hay in indexed
                 if all(subseq(t, hay) for t in toks)], query)


def matches(entries, query: str, scope: str = "all",
            categories=None) -> list[dict]:
    """Entries where **every** token matches, ranked by :func:`rank`.

    Every rather than any: typing more must narrow. An `any` rule would make a
    second word widen the result set, which reads as the filter breaking.

    Convenience wrapper that indexes on the spot; a repeated caller should hold
    an :func:`index_entries` result instead.
    """
    return matches_indexed(index_entries(entries, scope, categories), query)


def match_positions(needle: str, hay: str) -> list[int]:
    """Indices of hay consumed by a subsequence match, or [] if it does not."""
    positions, i = [], 0
    for j, ch in enumerate(hay):
        if i < len(needle) and ch == needle[i]:
            positions.append(j)
            i += 1
    return positions if i == len(needle) else []


def highlight_positions(query: str, text: str) -> set[int]:
    """Every index of ``text`` any query token lands on.

    A union across tokens, so `code review` lights up both words rather than
    only whichever one the single-token highlighter happened to see.
    """
    low = text.lower()
    hits: set[int] = set()
    for t in tokens(query):
        hits.update(match_positions(t, low))
    return hits


# --------------------------------------------------------------- dedupe

#: Above this many distinct descriptions under one name, the fuzzy pass is
#: skipped for that name. It is quadratic, and the largest real bucket
#: (`rule`, 47 distinct) is already the pathological case — a bigger one is a
#: registry doing something strange, not a user waiting to be helped.
_FUZZY_BUCKET_CAP = 80
# Bucket name reserved for rows keyed by content digest. A NUL can't occur in a
# slugified skill name, so a digested row can never share a fuzzy bucket with a
# real one — and the fuzzy pass skips this bucket outright, because "95% similar"
# is a question about prose and asking it of two hex digests is meaningless.
_DIGEST_SIG = "\x00digest"


def _sig(entry: dict) -> tuple[str, str]:
    """Identity of a row for dedupe: the scanner's content digest when it has
    one, else name plus description, normalised.

    The digest is the right key and the pair is a fallback, not a peer. Keying
    on name+description alone over-collapses: on a real 60,047-entry catalogue
    it merges **3,383 clusters** the digest keeps apart — items that share a
    name and a description while carrying genuinely different prose, one of
    which then becomes unreachable in the browser. It is still the only key
    available for a row from a cache written before `catalog.CACHE_FORMAT`, so
    it stays.

    Digested and undigested rows can never merge into each other: the two keys
    live in different halves of the tuple, so an unknown is only ever equal to
    another unknown with the same visible metadata.

    Keying on the name alone was never an option — `code-reviewer` is 75 rows
    with **42 distinct descriptions** on a real catalogue.
    """
    content = str(entry.get("content", "")).strip()
    if content:
        return (_DIGEST_SIG, content)
    return (str(entry.get("name", "")).strip().lower(),
            str(entry.get("description", "")).strip().lower())


def dedupe(entries, threshold: float = 0.95) -> list[tuple[dict, int]]:
    """Collapse near-identical rows -> ``[(survivor, copies)]``, order kept.

    Registries render one skill into `.claude/`, `.cursor/`, `.gemini/` and a
    plugin root, so the browser listed the same thing four times. On a real
    60,047-entry catalogue **22,379 rows (37%) are exact duplicates**.

    Two passes, because their value is wildly different and it is worth knowing
    which is carrying the weight:

    * exact signature match — 34 ms, and it does 22,379 of the 22,535 collapses;
    * fuzzy match at ``threshold`` — 301 ms, and it merges the remaining 156.

    The fuzzy pass is nine times the cost for under half a percent more
    collapse. It stays because "95% similar" is the stated contract and this
    runs once when the browser opens rather than per keystroke — but a future
    reader deciding whether to keep it deserves the numbers rather than a guess.
    """
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list] = {}
    for e in entries:
        sig = _sig(e)
        if sig not in groups:
            groups[sig] = [e, 0]
            order.append(sig)
        groups[sig][1] += 1

    # Fuzzy pass, confined to signatures that already share a name: two rows
    # with different names are different skills however similar the prose.
    by_name: dict[str, list] = {}
    for sig in order:
        if sig[0] == _DIGEST_SIG:
            continue        # exact content already decided; see _DIGEST_SIG
        by_name.setdefault(sig[0], []).append(sig)
    absorbed: set[tuple[str, str]] = set()
    for sigs in by_name.values():
        if len(sigs) < 2 or len(sigs) > _FUZZY_BUCKET_CAP:
            continue
        for i, a in enumerate(sigs):
            if a in absorbed:
                continue
            for b in sigs[i + 1:]:
                if b in absorbed:
                    continue
                if _similar(a[1], b[1], threshold):
                    absorbed.add(b)
                    groups[a][1] += groups[b][1]
    return [(groups[s][0], groups[s][1]) for s in order if s not in absorbed]


def _similar(a: str, b: str, threshold: float) -> bool:
    """True when two descriptions are at least ``threshold`` alike.

    The two cheap ratios first: both are upper bounds on the real one, so a
    failure short-circuits before the quadratic matcher runs. Over a real
    catalogue that is most pairs.
    """
    if a == b:
        return True
    if not a or not b:
        return False
    sm = difflib.SequenceMatcher(None, a, b)
    return (sm.real_quick_ratio() >= threshold
            and sm.quick_ratio() >= threshold
            and sm.ratio() >= threshold)


#: Kinds broken out by name in :func:`plain_footer`, in the order they're
#: listed. Anything else (there is no fourth kind today, but a cache entry
#: can carry a stale or missing one) still counts toward the total.
_PLAIN_KINDS = ("skill", "rule", "workflow")


def plain_footer(entries) -> str:
    """Footer text for the non-interactive browse fallback: total row count,
    broken down by kind — e.g. ``"128 items: 100 skills · 20 rules · 8
    workflows"``.

    ``entries`` is what the caller is actually about to show (already
    deduped, already filtered): this describes the rows on screen, not the
    catalog behind them. A kind outside :data:`_PLAIN_KINDS` still counts
    toward the total under "other" rather than silently vanishing from it —
    the same "never let a count go unexplained" rule the TUI's own footer
    (:func:`count_tail`) follows.
    """
    counts: dict[str, int] = {}
    for e in entries:
        kind = str(e.get("kind") or "skill")
        counts[kind] = counts.get(kind, 0) + 1
    parts = ["%d %s%s" % (counts[k], k, "" if counts[k] == 1 else "s")
             for k in _PLAIN_KINDS if counts.get(k)]
    other = sum(n for k, n in counts.items() if k not in _PLAIN_KINDS)
    if other:
        parts.append("%d other%s" % (other, "" if other == 1 else "s"))
    n = len(entries)
    return "%d item%s: %s" % (n, "" if n == 1 else "s",
                              " · ".join(parts) if parts else "none")


# --------------------------------------------------------------- focus

#: Panes the focus ring can hold, top to bottom as the user reads them.
#: `scopes` is in the ring so the match toggles are reachable by arrow rather
#: than only by the ^T shortcut — a control you can see but not walk to reads
#: as decoration.
PANES = ("search", "scopes", "list", "detail")


def move_focus(focus: str, direction: str, row: int, n: int,
               detail: bool) -> tuple[str, int]:
    """Where an arrow key lands: ``(focus, row)``.

    The arrows cross pane boundaries rather than dead-ending, which is what
    makes the query, the toggles and the list feel like one surface. Vertically
    the ring is search → scopes → list; horizontally, right and left cross into
    and out of the detail pane. While the scope row holds focus, left and right
    move between the toggles instead (see :func:`scope_step`).
    """
    if direction == "down":
        if focus == "search":
            return ("scopes", row)
        if focus == "scopes":
            return ("list", row) if n else ("scopes", row)
        if focus == "list":
            return ("list", min(row + 1, max(0, n - 1)))
        return (focus, row)
    if direction == "up":
        if focus == "list":
            # The top row is the boundary: one more `up` is the toggle row.
            return ("scopes", row) if row <= 0 else ("list", row - 1)
        if focus == "scopes":
            return ("search", row)
        return (focus, row)
    if direction == "right":
        if focus == "list" and detail and n:
            return ("detail", row)
        return (focus, row)
    if direction == "left":
        if focus == "detail":
            return ("list", row)
        return (focus, row)
    return (focus, row)


def scope_step(focus: str, direction: str) -> int:
    """How far left/right moves the scope selection, given the focused pane.

    Non-zero only while the toggle row holds focus, so the same arrow keys can
    mean "cross into the detail pane" everywhere else.
    """
    if focus != "scopes":
        return 0
    return {"right": 1, "left": -1}.get(direction, 0)


# --------------------------------------------------------------- layout

@dataclass(frozen=True)
class Layout:
    """Pane geometry for one frame, in absolute terminal cells.

    A frozen record rather than loose ints so the draw loop cannot quietly
    disagree with itself about where a border goes.
    """
    w: int
    h: int
    body_y: int          # first row inside the outer box that holds content
    body_h: int          # rows available to the list / detail panes
    list_x: int
    list_w: int
    detail_x: int
    detail_w: int        # 0 when there is no room for a readable detail pane
    bottom_y: int = -1   # the frame's bottom rule; -1 means ``h - 1``
    status_y: int = -1   # the status bar under the frame; -1 when none fits

    @property
    def bottom(self) -> int:
        """Row of the bottom rule — the first row the panes may not draw on."""
        return self.bottom_y if self.bottom_y >= 0 else self.h - 1

    @property
    def has_status(self) -> bool:
        return self.status_y >= 0

    @property
    def has_detail(self) -> bool:
        return self.detail_w > 0


def layout(w: int, h: int, detail: bool = False) -> Layout:
    """Compute pane geometry for a ``w`` x ``h`` terminal.

    Total column budget, left to right: outer border, list, divider, detail,
    outer border. The detail pane is dropped entirely below
    ``_MIN_DETAIL_W + _MIN_LIST_W`` of usable width — a pane too narrow to hold
    a wrapped sentence costs the list its room and gives nothing back.

    Never raises and never returns a negative span: it is called from inside
    the draw loop on every resize, including the 1x1 frame a terminal reports
    mid-drag.
    """
    w = max(0, w)
    h = max(0, h)
    # Rows 0..3: top rule (with title), query, scope toggles, and the rule
    # that separates chrome from body. Content starts at 4. Below the frame's
    # bottom rule sits the tmux-style status bar — the key hints used to take
    # a chrome row of their own, which on a 24-row terminal is one result in
    # nine. A terminal too short to spare the row keeps the frame and loses
    # the bar, never the other way round.
    body_y = 4
    status_y = h - 1 if h >= _MIN_STATUS_H else -1
    bottom_y = h - 2 if status_y >= 0 else h - 1
    body_h = max(0, bottom_y - body_y)
    inner_w = max(0, w - 2)          # inside the outer left/right border
    list_x = 1

    if not detail or inner_w < _MIN_LIST_W + _MIN_DETAIL_W + 1:
        return Layout(w=w, h=h, body_y=body_y, body_h=body_h,
                      list_x=list_x, list_w=inner_w,
                      detail_x=w, detail_w=0,
                      bottom_y=bottom_y, status_y=status_y)

    # Roughly a 55/45 split, with the divider column paid for out of the list.
    detail_w = max(_MIN_DETAIL_W, (inner_w - 1) * 45 // 100)
    list_w = inner_w - 1 - detail_w
    if list_w < _MIN_LIST_W:                 # give the shortfall back
        list_w = _MIN_LIST_W
        detail_w = inner_w - 1 - list_w
    return Layout(w=w, h=h, body_y=body_y, body_h=body_h,
                  list_x=list_x, list_w=list_w,
                  detail_x=list_x + list_w + 1, detail_w=detail_w,
                  bottom_y=bottom_y, status_y=status_y)


def clamp_scroll(offset: int, total: int, visible: int) -> int:
    """Keep a scroll offset inside its content."""
    if total <= visible or visible <= 0:
        return 0
    return max(0, min(offset, total - visible))


def rule_segments(width: int, n: int = 3) -> list[tuple[int, int]]:
    """Split a ``width``-wide rule into ``n`` near-equal ``(start, length)``
    runs that partition it exactly — [] when there is no width, ``n`` clamped
    to it.

    This is how the frame paints the Aurora cyan → violet → pink gradient
    across the top rule, the browser's one brand moment. It lives here rather
    than in the draw layer so the partition arithmetic sits under the
    mutation gate.
    """
    if width <= 0:
        return []
    n = min(n, width)
    base, extra = divmod(width, n)
    segs, pos = [], 0
    for k in range(n):
        length = base + (1 if k < extra else 0)
        segs.append((pos, length))
        pos += length
    return segs


def scrollbar(total: int, visible: int, top: int) -> tuple[int, int] | None:
    """``(thumb_start, thumb_len)`` for a ``visible``-tall proportional
    scrollbar over ``total`` rows scrolled to ``top`` — None when everything
    fits (or there is no room), so callers can skip drawing entirely.

    One geometry shared by the list and detail panes; two implementations is
    how the two thumbs come to move differently.
    """
    if visible <= 0 or total <= visible:
        return None
    thumb = max(1, visible * visible // total)
    # total > visible here, so max_top >= 1 — no zero-divide guard needed.
    max_top = total - visible
    return (round((visible - thumb) * top / max_top), thumb)


def empty_lines(query: str, scope: str, hidden: int = 0) -> list[tuple[str, str]]:
    """``(role, text)`` lines for a zero-match list pane.

    A silent void is indistinguishable from a hung draw, so the pane says
    what happened and which keys widen the net — in the same ○/→ grammar
    every other boost empty state uses, and every line muted, because an
    absence is the quietest thing on screen. Never returns nothing.
    """
    q = " ".join(query.split())
    head = ("○ no matches for '%s' in %s" % (q, scope_label(scope))
            if q else "○ nothing here")
    lines = [("muted", head), ("muted", "→ backspace widens · ^T scope")]
    if hidden > 0:
        lines.append(("muted",
                      "→ ^D shows %s hidden duplicates" % format(hidden, ",")))
    return lines


def badge_positions(name_end: int, badges, width: int) -> list[tuple[int, str, str]]:
    """Right-align a badge cluster into a ``width``-column row.

    ``badges`` arrives most-important-first as ``(text, theme_key)`` pairs;
    the cluster is placed as ``(x, text, theme_key)`` triples ending exactly
    at ``width``, one space between badges, never crossing ``name_end``.
    When it does not fit, badges drop from the least-important end until it
    does — [] when even the first survivor cannot fit. Right-aligning is what
    stops the rail wandering with every name length; the drop order is what
    keeps the honest badges (the ×N copies count, the kind) alive longest.
    """
    kept = list(badges)
    while kept:
        total = sum(len(t) for t, _k in kept) + (len(kept) - 1)
        start = width - total
        if start >= name_end:
            placed, x = [], start
            for text, key in kept:
                placed.append((x, text, key))
                x += len(text) + 1
            return placed
        kept.pop()
    return []


def count_tail(n_found: int, n_all: int, n_sel: int, hidden: int) -> str:
    """The query row's right-aligned tail, e.g.
    ``2 selected · 128/71,700  (22,379 dupes hidden)``.

    Thousands are grouped — at real catalogue scale ``22379`` is a smudge —
    and each segment appears only when it carries information.
    """
    tail = "%s%s/%s" % ("%d selected · " % n_sel if n_sel else "",
                        format(n_found, ","), format(n_all, ","))
    if hidden:
        tail += "  (%s dupes hidden)" % format(hidden, ",")
    return tail


# --------------------------------------------------------------- palette

#: The selected row's background: a soft slate rather than a solid reversed
#: block of accent, which at 140 columns was the loudest thing on screen and
#: drowned the text it was meant to point at. The ``▌`` bar carries the accent.
SLATE = (0x26, 0x32, 0x45)

#: Colour levels a terminal can offer, best first. ``custom`` can redefine
#: palette slots (true Aurora hues); ``256`` cannot but has the xterm cube
#: (tmux without ``Tc`` lands here); ``base`` is the 8/16-colour set.
CUSTOM, XTERM256, BASE = "custom", "256", "base"

#: Palette slots the browser defines on a ``custom`` terminal: five Aurora
#: tokens plus the slate.
CUSTOM_SLOTS = 6

#: Kind -> palette token, per colour level. The kinds get a hue each because
#: kind is the first thing a reader sorts by. On ``base`` violet and pink both
#: collapse to magenta, so workflow takes yellow there: two kinds in one
#: colour is worse than no colour, because it reads as the same kind.
KIND_HUES = {
    CUSTOM: {"skill": "cyan", "rule": "violet", "workflow": "pink"},
    XTERM256: {"skill": "cyan", "rule": "violet", "workflow": "pink"},
    BASE: {"skill": "cyan", "rule": "violet", "workflow": "yellow"},
}


def palette_level(can_change: bool, colors: int) -> str:
    """Which colour level a terminal reporting ``colors`` supports."""
    if can_change and colors >= 16 + CUSTOM_SLOTS:
        return CUSTOM
    if colors >= 256:
        return XTERM256
    return BASE


def kind_hue(kind: str, level: str) -> str:
    """The palette token a ``kind`` badge is drawn in at ``level``."""
    hues = KIND_HUES.get(level, KIND_HUES[BASE])
    return hues.get(kind, hues["skill"])


_CUBE = (0, 95, 135, 175, 215, 255)


def xterm256(rgb) -> int:
    """The nearest xterm-256 index to ``rgb``, from the 6x6x6 cube or the
    24-step grey ramp.

    For a terminal that has 256 colours but cannot redefine them — the common
    tmux case — this is the difference between the real Aurora hues, near
    enough, and the 8-colour fallback where violet and pink are one magenta.
    """
    r, g, b = (int(c) for c in rgb)

    def dist(a, z):
        return sum((p - q) ** 2 for p, q in zip(a, z, strict=True))

    def near(c):
        return min(range(6), key=lambda i: abs(_CUBE[i] - c))

    ci = (near(r), near(g), near(b))
    cube = tuple(_CUBE[i] for i in ci)
    grey_i = max(0, min(23, round((((r + g + b) / 3) - 8) / 10)))
    grey = 8 + 10 * grey_i
    if dist((grey, grey, grey), (r, g, b)) < dist(cube, (r, g, b)):
        return 232 + grey_i
    return 16 + 36 * ci[0] + 6 * ci[1] + ci[2]


# --------------------------------------------------------------- status bar

#: The mode pill for each focus. Named for what the keys *do* there, the way
#: tmux and vim name theirs, because the same arrow means four different things
#: depending on which pane holds focus.
MODES = {"search": "SEARCH", "scopes": "SCOPE", "list": "LIST",
         "detail": "DETAIL"}

#: ``(key, label)`` hints per focus, most useful first, quitting always last.
HINTS = {
    "search": (("a-z", "filter"), ("↓", "scopes"), ("↵", "install"),
               ("^T", "scope"), ("esc", "quit")),
    "scopes": (("← →", "pick"), ("↓", "list"), ("↑", "search"),
               ("esc", "quit")),
    "list": (("↑↓", "move"), ("⇥", "select"), ("↵", "install"),
             ("→", "detail"), ("^T", "scope"), ("^D", "dupes"),
             ("esc", "quit")),
    "detail": (("↑↓", "scroll"), ("←", "list"), ("↵", "install"),
               ("esc", "quit")),
}

_HINT_GAP = 2


def fit_hints(hints, room: int) -> list[tuple[str, str]]:
    """The hints that fit in ``room`` columns, whole.

    Drops from the middle, never the end: the last hint is how to leave, and a
    bar that shows ``↑↓ move`` but not ``esc quit`` traps a first-time user.
    A hint is never clipped — the old single-line hint, cut mid-phrase, ended
    on ``esc`` and read as a key rather than as a fragment.
    """
    kept = list(hints)

    def width(hs):
        return sum(len(k) + 1 + len(v) for k, v in hs) + _HINT_GAP * max(
            0, len(hs) - 1)

    while kept and width(kept) > room:
        kept.pop(-2 if len(kept) > 1 else -1)
    return kept


def status_spans(focus: str, width: int,
                 summary: tuple[str, str] | None = None
                 ) -> list[tuple[int, str, str]]:
    """``(x, role, text)`` spans for the status bar under the frame.

    Left: the mode pill, then the hints for that mode, keys and labels as
    separate spans so the draw layer can colour the key. Right: the session's
    install chip (:func:`session_summary`), which outranks the hints — it is
    news, and the hints are reference — so hints give way first.
    """
    if width <= 0:
        return []
    pill = " %s " % MODES.get(focus, "LIST")
    spans: list[tuple[int, str, str]] = [(0, "pill", pill[:width])]
    x = len(pill) + 1
    limit = width - 1
    if summary:
        role, text = summary
        room = width - x - 1
        if room > 0:
            text = text[:room]
            sx = width - 1 - len(text)
            spans.append((sx, role, text))
            limit = sx - _HINT_GAP
    for key, label in fit_hints(HINTS.get(focus, HINTS["list"]), limit - x):
        spans.extend(((x, "key", key),
                      (x + len(key) + 1, "hint", label)))
        x += len(key) + 1 + len(label) + _HINT_GAP
    return spans


# --------------------------------------------------------------- detail

#: Install lifecycle as the detail pane shows it. `busy` exists because an
#: install writes files and can take a visible moment; without it the pane sits
#: unchanged and the keypress reads as ignored.
BUSY, OK, FAILED = "busy", "ok", "failed"

_STATUS_GLYPH = {BUSY: "◐", OK: "●", FAILED: "✗"}


def status_line(state: str | None, message: str = "",
                installed: bool | None = None) -> tuple[str, str]:
    """``(role, text)`` for the install line in the detail pane.

    One function so the pane cannot disagree with itself about what a state
    looks like, and so "what does a failed install say" is testable without a
    terminal.
    """
    if state == BUSY:
        return ("busy", "◐ installing…")
    if state == OK:
        return ("ok", "%s installed%s" % (_STATUS_GLYPH[OK],
                                          "  " + message if message else ""))
    if state == FAILED:
        return ("failed", "%s %s" % (_STATUS_GLYPH[FAILED],
                                     message or "install failed"))
    if installed:
        return ("ok", "● installed")
    return ("muted", "○ not installed")


def state_glyph(state: str | None, installed: bool) -> tuple[str, str]:
    """``(glyph, theme_role)`` for a row's status mark in the list pane.

    Drawn from the same ``_STATUS_GLYPH`` table :func:`status_line` uses, so
    the list and the detail pane can never disagree about what a state looks
    like: ``◐`` while installing, ``✗`` on failure, ``●`` once installed
    (this session or before), a reserved blank otherwise.
    """
    if state == BUSY:
        return (_STATUS_GLYPH[BUSY], "busy")
    if state == FAILED:
        return (_STATUS_GLYPH[FAILED], "failed")
    if state == OK or installed:
        return (_STATUS_GLYPH[OK], "check")
    return (" ", "muted")


def session_summary(status) -> tuple[str, str] | None:
    """Fold the ``name -> (state, message)`` install map into one bottom-rule
    chip: ``(role, text)``, or None when nothing happened so the idle frame
    stays byte-identical.

    Precedence failed > busy > ok — the worst news owns the chip. Installs
    otherwise report only inside the detail pane, which may be closed or
    parked on a different entry; callers pass a shallow copy when another
    thread owns the mapping.
    """
    states = [s for s, _m in status.values()]
    n_failed = states.count(FAILED)
    if n_failed:
        return ("failed", "✗ %d failed" % n_failed)
    n_busy = states.count(BUSY)
    if n_busy:
        return ("busy", "◐ %d installing…" % n_busy)
    n_ok = states.count(OK)
    if n_ok:
        return ("ok_line", "✓ %d installed" % n_ok)
    return None


def install_target(entry: dict, targets) -> str:
    """Destination text for the detail pane's ``installs`` line — what Enter
    will actually touch, stated before it is pressed.

    Dispatches on the entry's kind over a caller-supplied ``targets`` mapping
    (kind -> destination text) so this stays pure and import-light: the
    command layer knows the store path, the context files and the per-agent
    command slots; this decides only which of them applies. A missing kind is
    the default kind; an unknown one answers ``?`` rather than guessing.
    """
    kind = str(entry.get("kind") or "skill")
    return str((targets or {}).get(kind, "?"))


def _render_value(value) -> str:
    """A frontmatter value as display text, never as a Python repr.

    `['a', 'b']` is data leaking through the UI; `a, b` is a rendering.
    """
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join("%s=%s" % (k, v) for k, v in value.items())
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


#: One rendered line of the detail pane: ``(role, text)`` spans, left to right.
#: Spans rather than one ``(role, text)`` per line because a field line is two
#: colours — a dim label and a bright value — and the chips line is several.
Span = tuple[str, str]
Line = list[Span]

#: Frontmatter keys the pane already shows above the fold. Listing them again
#: under FRONTMATTER printed every description twice.
_SHOWN_ABOVE = frozenset(("name", "description", "version"))

_LABEL_W = 8


def line_text(line: Line) -> str:
    """A detail line's plain text — what it reads as with the colour off."""
    return "".join(t for _r, t in line)


def line_role(line: Line) -> str:
    """A detail line's leading role — its kind, for anything that asks."""
    return line[0][0] if line else "blank"


def clip_spans(line: Line, width: int) -> Line:
    """``line`` cut to ``width`` columns, spans after the cut dropped."""
    out: Line = []
    room = max(0, width)
    for role, text in line:
        if room <= 0:
            break
        out.append((role, text[:room]))
        room -= len(text[:room])
    return out


def field_lines(label: str, value: str, width: int,
                label_w: int = _LABEL_W) -> list[Line]:
    """A ``label  value`` field, the value wrapped under its own column.

    The label pads to ``label_w`` and is never truncated — a key name is how
    the reader knows *which* field this is, so ``custom-key`` clipped to
    ``custom-k`` throws away the only identifying part. Continuation lines
    indent to the value column rather than folding back under the label, which
    is what made a long description in FRONTMATTER read as a new field.
    """
    lw = max(label_w, len(label))
    vw = max(4, width - lw - 1)
    chunks = textwrap.wrap(value, width=vw) or [""]
    lines: list[Line] = [[("label", label.ljust(lw) + " "), ("field", chunks[0])]]
    lines.extend([("label", " " * (lw + 1)), ("field", c)] for c in chunks[1:])
    return lines


def chips(entry: dict, categories=None) -> Line:
    """The detail pane's one-line summary: kind · version · #category · ★.

    Each fact once, at a glance. ★ curated lives here now rather than as a
    column on every row: on a curated catalogue every row carried it, and a
    mark on every row marks nothing.
    """
    kind = str(entry.get("kind") or "skill")
    parts: Line = [("kind_" + kind, kind)]
    if entry.get("version"):
        parts.append(("version", "v%s" % entry["version"]))
    category = entry_category(entry, categories)
    if category:
        parts.append(("category", "#" + category))
    if entry.get("curated"):
        parts.append(("star", "★ curated"))
    line: Line = []
    for i, part in enumerate(parts):
        if i:
            line.append(("muted", " · "))
        line.append(part)
    return line


def detail_lines(entry: dict, width: int = 60,
                 installed: bool | None = None,
                 state: str | None = None,
                 message: str = "",
                 install_to: str | None = None,
                 categories=None) -> list[Line]:
    """The detail pane, as :data:`Line` s wrapped to ``width``.

    Roles let the curses layer theme without re-deriving meaning from the text.
    The whole frontmatter is included, not a known-keys allowlist: the request
    was to scroll through *the entire frontmatter*, and an allowlist silently
    hides exactly the custom key a registry author cared about. Only the keys
    already shown above it (name, description, version) are left out.
    """
    width = max(8, width)
    lines: list[Line] = []

    def add(role: str, text: str) -> None:
        lines.extend([(role, chunk)] for chunk in
                     textwrap.wrap(text, width=width) or [""])

    def blank() -> None:
        lines.append([("blank", "")])

    add("title", str(entry.get("name", "?")))
    lines.extend((clip_spans(chips(entry, categories), width),
                  [("rule", "")]))

    if entry.get("description"):
        add("desc", str(entry["description"]))
        blank()

    if installed is not None or state:
        role, text = status_line(state, message, installed)
        # output.wrap, not textwrap: the message can carry a backticked
        # command (`chmod u+w ~/.cursor/skills`), and a command split across
        # two lines is not one a user can copy.
        # A token wider than the pane is the one thing output.wrap lets run
        # long, which a terminal soft-wraps and a curses pane draws over its
        # own frame; only that chunk is broken, so a command that fits stays
        # whole and nothing leaves the pane.
        from . import output  # stdlib-only too; lazy to keep this module light
        for chunk in output.wrap(text, width) or [""]:
            parts = [chunk]
            if output.visible_len(chunk) > width:
                # output.wrap glues trailing punctuation to a code span, so a
                # command exactly as wide as the pane arrives one column over.
                # Drop the comma, not the command.
                bare = chunk.rstrip(",.;:")
                parts = ([bare] if output.visible_len(bare) <= width
                         else textwrap.wrap(chunk, width))
            lines.extend([(role, part)] for part in parts)
        blank()

    add("head", "SOURCE")
    for label, key in (("kind", "kind"), ("tap", "tap"), ("path", "rel_dir"),
                       ("file", "skill_md")):
        if entry.get(key):
            lines.extend(field_lines(label, _render_value(entry[key]), width))
    if install_to:
        # The cost of Enter, stated before it is pressed — for a rule this is
        # the highest-stakes fact on the screen, because it edits a file the
        # user reads every session.
        lines.extend(field_lines("installs", install_to, width))

    meta = entry.get("meta") or {}
    shown = {k: v for k, v in meta.items()
             if k not in _SHOWN_ABOVE and _render_value(v)} \
        if isinstance(meta, dict) else {}
    if shown:
        blank()
        add("head", "FRONTMATTER")
        for key in sorted(shown):
            lines.extend(field_lines(str(key), _render_value(shown[key]), width))
    return lines
