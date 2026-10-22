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
from dataclasses import dataclass, field, replace

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


#: What the picker and the query chip call an entry with no category at all —
#: a tap the bundled registry catalogue does not list, on a cache too old to
#: carry a stamped one. Listed rather than dropped, so the picker's counts add
#: up to the total above them.
UNCATEGORIZED = "uncategorized"


def category_of(entry: dict, categories=None) -> str:
    """:func:`entry_category` as the picker files it: lowercased, and
    :data:`UNCATEGORIZED` rather than empty."""
    return entry_category(entry, categories).strip().lower() or UNCATEGORIZED


def in_category(entry: dict, category: str, categories=None) -> bool:
    """True when ``entry`` is filed under ``category`` (case-insensitive).

    An empty ``category`` is no filter and matches everything, so callers can
    apply it unconditionally. Goes through :func:`entry_category`, tap
    fallback included, for the reason that function exists: the chip on a row
    and the filter that finds it must agree.
    """
    if not category:
        return True
    return category_of(entry, categories) == category.strip().lower()


def category_counts(entries, categories=None) -> list[tuple[str, int]]:
    """``(category, rows)`` for every category in ``entries``, largest first,
    then by name — the order the picker lists them in."""
    counts: dict[str, int] = {}
    for e in entries:
        c = category_of(e, categories)
        counts[c] = counts.get(c, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def short_tap(tap: str | None) -> str:
    """A tap as a row shows it: the repo name, without the owner.

    ``trailofbits/skills`` badged in full on every row is the same twenty
    characters 2,000 times over; the owner is in the detail pane, where there
    is room for it.
    """
    return str(tap or "").rsplit("/", 1)[-1]


#: Characters after which a new word starts: kebab and snake names, owner/repo
#: taps, dotted file names, and prose.
_SEPS = " -_/.:("

_FOLD = str.maketrans(dict.fromkeys(_SEPS, " "))


def fold(text: str) -> str:
    """``text`` lowercased with every word separator turned into a space.

    One separator instead of seven is what makes "the next word starting with
    ``arch``" a single ``find(" arch")``; seven finds per lookup were 85% of a
    keystroke over the real catalogue. Positions survive — every character
    maps to exactly one — so an alignment found in the folded text highlights
    the original.
    """
    return text.lower().translate(_FOLD)


def haystack(entry: dict, scope: str, categories=None) -> str:
    """The text ``scope`` searches for one entry, :func:`fold` ed."""
    name = str(entry.get("name", ""))
    if scope == "name":
        return fold(name)
    if scope == "description":
        return fold(str(entry.get("description", "")))
    if scope == "tap":
        return fold(str(entry.get("tap", "")))
    if scope == "category":
        return fold(entry_category(entry, categories))
    # `all`, and any unrecognised scope: never raise on a keystroke.
    return fold(" ".join((name, str(entry.get("description", "")),
                          str(entry.get("tap", "")),
                          str(entry.get("kind", "")),
                          entry_category(entry, categories))))


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
                  categories=None) -> list[tuple[dict, str, str]]:
    """``(entry, haystack, folded name)`` for each entry, for ``scope``.

    Built once per scope and reused for every keystroke. Rebuilding the joined
    string inside the filter cost 125 ms per key on a 71,700-entry catalogue —
    worse than the 80 ms draw poll, so the browser fell behind a typist. The
    index is caller-owned rather than a module cache: the TUI holds the entry
    list for the whole session, and a global keyed on object identity would be
    a use-after-free waiting for the first caller that does not.

    The folded name rides along because ranking reads it for every surviving
    row on every keystroke, whatever the scope.
    """
    return [(e, haystack(e, scope, categories), fold(str(e.get("name", ""))))
            for e in entries]


#: Rank tiers, best first. A match is placed by how its *name* meets the
#: query; anything that matched only through the description, tap or a
#: scattered subsequence sorts last, in catalogue order.
EXACT, PREFIX, SUBSTRING, FUZZY, ELSEWHERE = range(5)

# --------------------------------------------------------------- scoring
#
# A subsequence test answers "could these letters be found in this order",
# which over a long name is nearly always yes and says nothing about *how*.
# `bmadarch` is a subsequence of `bmad-agent-architect` two ways: one takes
# the `a` of `agent` and then fishes `r`, `c`, `h` out of `architect`; the
# other takes `bmad` and `arch`, two runs, each starting a word. A reader
# means the second. The first is the thin spread — one letter per word — and
# the browser used to highlight it and rank every such row the same.
#
# So a match is aligned, not just found: the aligner prefers to continue a run
# and, when a run breaks, to restart at the next word that begins with as much
# of the rest of the token as possible. The alignment is then scored, and the
# score orders rows inside a tier. Every step is a `str.find`, never a
# per-character Python loop over the text, because this runs on every row that
# survives the filter on every keystroke.

#: How far ahead the aligner looks for a word that starts with the rest of the
#: token. Four is enough to tell `arch` in `architect` from the `a` of `agent`;
#: longer only costs finds.
_LOOKAHEAD = 4

_BONUS_WORD = 10     # a match that starts a word
_BONUS_FIRST = 6     # ...the first word of the text, on top
_BONUS_RUN = 8       # a match directly after the previous one
_GAP_CAP = 4         # a gap costs one per skipped character, at most this


# Everything below takes :func:`fold` ed text, where a space is the only
# separator left.

def _word_start(hay: str, j: int) -> bool:
    """True when ``hay[j]`` begins a word."""
    return j == 0 or hay[j - 1] == " "


def _next_word_start(hay: str, s: str, i: int) -> int:
    """The first index ``>= i`` where a word starts with ``s``, else -1."""
    if i == 0 and hay.startswith(s):
        return 0
    k = hay.find(" " + s, max(0, i - 1))
    return k + 1 if k >= 0 else -1


def _align_words(needle: str, hay: str) -> list[int] | None:
    """Positions of ``needle`` in ``hay``, aligned to runs and word starts.

    Greedy, left to right: continue the current run when the next character
    allows it; otherwise jump to the nearest word that starts with the longest
    prefix (up to :data:`_LOOKAHEAD`) of what is left; otherwise take the next
    occurrence anywhere. None when the needle does not fit.

    Greedy can miss an alignment a full search would find — that is what
    :func:`align` pairs it with a plain scan and a substring hit for.
    """
    pos: list[int] = []
    j, i, m = 0, 0, len(needle)
    while j < m:
        if pos and hay.startswith(needle[j], pos[-1] + 1):
            k = pos[-1] + 1
        else:
            k = -1
            for size in range(min(m - j, _LOOKAHEAD), 0, -1):
                k = _next_word_start(hay, needle[j:j + size], i)
                if k >= 0:
                    break
            if k < 0:
                k = hay.find(needle[j], i)
                if k < 0:
                    return None
        pos.append(k)
        i = k + 1
        j += 1
    return pos


def _align_plain(needle: str, hay: str) -> list[int] | None:
    """Positions of the first-occurrence subsequence match, or None."""
    pos, i = [], 0
    for ch in needle:
        k = hay.find(ch, i)
        if k < 0:
            return None
        pos.append(k)
        i = k + 1
    return pos


def _align_substring(needle: str, hay: str) -> list[int] | None:
    """Positions of ``needle`` as one run — at a word start when it occurs at
    one — or None when it is not a substring at all."""
    k = _next_word_start(hay, needle, 0)
    if k < 0:
        k = hay.find(needle)
    if k < 0:
        return None
    return list(range(k, k + len(needle)))


def score_positions(pos: list[int], hay: str) -> int:
    """How well an alignment reads: runs and word starts up, gaps down.

    Higher is better. The numbers only have to order alignments of one token
    against each other, so their scale means nothing on its own.
    """
    if not pos:
        return 0
    s = _BONUS_FIRST if pos[0] == 0 else 0
    prev = -1
    for k in pos:
        if _word_start(hay, k):
            s += _BONUS_WORD
        if prev >= 0:
            s += _BONUS_RUN if k == prev + 1 else -min(_GAP_CAP, k - prev - 1)
        prev = k
    return s


def align(needle: str, hay: str) -> tuple[int, list[int]] | None:
    """``(score, positions)`` of the best alignment of ``needle`` in ``hay``,
    or None when it is not a subsequence.

    A substring is one run and nothing beats it, so it short-circuits; that is
    also the common case, which keeps a one-letter query over the whole
    catalogue cheap. Otherwise the word-aware and the plain alignment are both
    scored and the better one wins.
    """
    if not needle:
        return None
    pos = _align_substring(needle, hay)
    if pos is not None:
        return score_positions(pos, hay), pos
    best = None
    for found in (_align_words(needle, hay), _align_plain(needle, hay)):
        if found is not None:
            sc = score_positions(found, hay)
            if best is None or sc > best[0]:
                best = (sc, found)
    return best


def runs(pos: list[int]) -> list[tuple[int, int]]:
    """An alignment as ``(start, length)`` runs of consecutive positions."""
    out: list[tuple[int, int]] = []
    for k in pos:
        if out and k == out[-1][0] + out[-1][1]:
            out[-1] = (out[-1][0], out[-1][1] + 1)
        else:
            out.append((k, 1))
    return out


#: Shortest run that counts as a piece of a word outside the name. A single
#: letter at the start of a word is an acronym, which is a fine way to type a
#: name and no way to find a sentence: over a 200-character description,
#: `c`, `r`, `v` each start some word, in that order, almost every time.
_MIN_PIECE = 3


def tight(needle: str, hay: str) -> bool:
    """True when ``needle`` meets ``hay`` as a substring or as pieces of words.

    The filter outside the name. A token found only by picking single letters
    out of many words is not a match a reader recognises — it is what made a
    three-letter query in the ``all`` scope keep most of the catalogue — so
    every run must start a word and be at least :data:`_MIN_PIECE` long:
    ``codrev`` meets ``code review``; ``crv`` does not.
    """
    return needle in hay or _pieces(needle, hay)


def _pieces(needle: str, hay: str) -> bool:
    """The non-substring half of :func:`tight`."""
    head = needle[:_MIN_PIECE]
    if len(needle) < _MIN_PIECE or (
            not hay.startswith(head) and " " + head not in hay):
        return False        # no word starts the first piece: most rows, in C
    failed: set[tuple[int, int]] = set()

    def pieces(j: int, i: int) -> bool:
        # needle[j:] as word-starting runs of hay at or after i. Exhaustive,
        # not greedy: `abc` over `abx bc` needs `a`+`bc`... which is a
        # one-letter run, so it fails here by rule — but `abcd` over
        # `abx bcd` needs the *shorter* first run, and greedy longest-first
        # without backtracking would miss it. `failed` memoises dead ends,
        # so a description of repeated words cannot make it exponential.
        if j == len(needle):
            return True
        if len(needle) - j < _MIN_PIECE or (j, i) in failed:
            return False
        head = needle[j:j + _MIN_PIECE]
        k = _next_word_start(hay, head, i)
        while k >= 0:
            n = _MIN_PIECE
            while (j + n < len(needle) and k + n < len(hay)
                   and hay[k + n] == needle[j + n]):
                n += 1
            for cut in range(n, _MIN_PIECE - 1, -1):
                if pieces(j + cut, k + cut):
                    return True
            k = _next_word_start(hay, head, k + 1)
        failed.add((j, i))
        return False

    return pieces(0, 0)


def match_tier(name: str, toks: list[str]) -> int:
    """Which rank tier an entry named ``name`` falls in for ``toks``.

    ``toks`` joined by a space *or* a hyphen both count as the name, because
    the name is ``code-review`` and the user types ``code review``.

    This is what fixes the browser's first impression. Matching is fuzzy, so
    over a 42,000-entry catalogue ``eight-twin`` matched 8,900 rows — and the
    list showed them in alphabetical order, with the one the user typed the
    name of somewhere past the first screen.

    A substring only counts when it starts a word. ``ccr`` inside
    ``accrual-schedule`` is three letters that happen to sit together, and
    ranking it above ``cc-review`` — which the user was typing — is the same
    thin match the scorer exists to demote; mid-word it competes on score.
    """
    return _tier(fold(name), [fold(t) for t in toks])


def _tier(fname: str, ftoks: list[str]) -> int:
    if not ftoks:
        return ELSEWHERE
    joined = " ".join(ftoks)
    if fname == joined:
        return EXACT
    if fname.startswith(joined):
        return PREFIX
    if all(_next_word_start(fname, t, 0) >= 0 for t in ftoks):
        return SUBSTRING
    if all(subseq(t, fname) for t in ftoks):
        return FUZZY
    return ELSEWHERE


def _substring_score(t: str, k: int) -> int:
    """:func:`score_positions` of ``t`` as one run starting at ``k`` — the
    same number, by arithmetic. Ranking runs on every surviving row, and a
    substring hit is the common case; building its position list only to walk
    it back was most of a one-letter query's cost."""
    return ((_BONUS_FIRST if k == 0 else 0)
            + _BONUS_RUN * (len(t) - 1)
            + _BONUS_WORD * t[:-1].count(" "))


def _score(fname: str, ftoks: list[str]) -> int:
    """Summed :func:`align` score of every token that meets ``fname``.

    A token that does not meet the name adds nothing rather than disqualifying
    the row, so a row whose name carries ``code`` and whose description carries
    ``review`` still outranks one that matched only in its description.
    """
    total = 0
    for t in ftoks:
        k = _next_word_start(fname, t, 0)
        if k >= 0:
            total += _substring_score(t, k) + _BONUS_WORD
            continue
        k = fname.find(t)
        if k >= 0:
            total += _substring_score(t, k)
            continue
        hit = align(t, fname)
        if hit is not None:
            total += hit[0]
    return total


def _key(fname: str, ftoks: list[str]) -> tuple[int, int, int]:
    sc = _score(fname, ftoks)
    return (_tier(fname, ftoks), -sc, len(fname) if sc else 0)


def rank_key(name: str, toks: list[str]) -> tuple[int, int, int]:
    """Sort key: tier, then alignment score, then the shorter name.

    The shorter name breaks a tie because the query covers more of it —
    ``code-review`` before ``code-review-for-monorepos`` for ``code review``.
    A row the name gave no score at all keeps catalogue order instead: its
    name length says nothing about how it matched.
    """
    return _key(fold(name), [fold(t) for t in toks])


def rank(found: list[dict], query: str) -> list[dict]:
    """``found`` ordered by :func:`rank_key`, catalogue order breaking ties.

    A stable sort, so the incoming order (alphabetical, in the browser) breaks
    every remaining tie. An empty query returns ``found`` untouched: there is
    nothing to rank by, and the first frame should not pay for a sort.
    """
    toks = tokens(query)
    if not toks:
        return found
    return sorted(found, key=lambda e: rank_key(str(e.get("name", "")), toks))


#: Scopes whose whole haystack is a short label — a name, ``owner/repo``, a
#: category. Any subsequence of a label still matches: an acronym is a fine
#: way to type one (``as`` for ``anthropics/skills``), and the score ranks a
#: scattered one last. The thin spread is a property of *prose*, so only text
#: that carries prose has to be :func:`tight`.
_LABEL_SCOPES = frozenset(("name", "tap", "category"))


def loose_text(scope: str, hay: str, fname: str) -> str | None:
    """The part of a row any subsequence may match in, for ``scope``.

    The whole haystack for a label scope, the name alone for ``all`` (whose
    haystack also carries the description), and nothing for ``description``.
    """
    if scope in _LABEL_SCOPES:
        return hay
    if scope == "description":
        return None
    return fname


def token_matches(tok: str, hay: str, name: str | None = None) -> bool:
    """Whether one :func:`fold` ed token keeps a row whose haystack is
    ``hay``: anywhere in ``name`` (the :func:`loose_text`, or None), or
    :func:`tight` ly in the haystack."""
    # Cheapest test first: a substring is the common hit and is one C-level
    # scan, and it settles both arms at once.
    if tok in hay:
        return True
    if not subseq(tok, hay):
        return False
    if name is not None and subseq(tok, name):
        return True
    return _pieces(tok, hay)


def matches_indexed(indexed, query: str, scope: str) -> list[dict]:
    """Filter a list built by :func:`index_entries`, best matches first.

    ``scope`` is required and must be the one the index was built for: it
    decides where a loose subsequence is enough (:func:`loose_text`). A default
    would let a caller that forgot it filter the description scope as loosely
    as a name — the leak :func:`tight` exists to close — and never notice.
    """
    toks = tokens(query)
    if not toks:
        return [e for e, _hay, _n in indexed]
    ftoks = [fold(t) for t in toks]
    kept = [(e, n) for e, hay, n in indexed
            if all(token_matches(t, hay, loose_text(scope, hay, n))
                   for t in ftoks)]
    kept.sort(key=lambda r: _key(r[1], ftoks))
    return [e for e, _n in kept]


def matches(entries, query: str, scope: str = "all",
            categories=None) -> list[dict]:
    """Entries where **every** token matches, ranked by :func:`rank`.

    Every rather than any: typing more must narrow. An `any` rule would make a
    second word widen the result set, which reads as the filter breaking.

    Convenience wrapper that indexes on the spot; a repeated caller should hold
    an :func:`index_entries` result instead.
    """
    return matches_indexed(index_entries(entries, scope, categories), query,
                           scope)


def match_positions(needle: str, hay: str) -> list[int]:
    """Indices of ``hay`` the best alignment of ``needle`` lands on, or [].

    The best alignment, not the first: highlighting the first occurrence of
    each letter is what lit up one letter per word on a long name, so the row
    showed a reason for the match that was not the one it ranked by.
    """
    hit = align(fold(needle), fold(hay))
    return hit[1] if hit else []


def highlight_positions(query: str, text: str) -> set[int]:
    """Every index of ``text`` any query token lands on.

    A union across tokens, so `code review` lights up both words rather than
    only whichever one the single-token highlighter happened to see.
    """
    low = fold(text)
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


def empty_lines(query: str, scope: str, hidden: int = 0,
                category: str = "", filters=None) -> list[tuple[str, str]]:
    """``(role, text)`` lines for a zero-match list pane.

    A silent void is indistinguishable from a hung draw, so the pane says
    what happened and which keys widen the net — in the same ○/→ grammar
    every other boost empty state uses, and every line muted, because an
    absence is the quietest thing on screen. Never returns nothing.

    Every active facet filter (``filters``, or the older lone ``category``)
    is named in the head: each narrows as much as the query does, and a "no
    matches for 'x'" that leaves them out sends the user deleting a query
    that was never the problem.
    """
    q = " ".join(query.split())
    chip = " ".join(query_chips(filters if filters is not None
                                else {"category": category}))
    where = scope_label(scope) + (" · " + chip if chip else "")
    head = ("○ no matches for '%s' in %s" % (q, where) if q
            else "○ nothing in %s" % chip if chip
            else "○ nothing here")
    lines = [("muted", head),
             ("muted", "→ backspace widens · ^T scope · ^G ^R ^K filters")]
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


# --------------------------------------------------------------- facets
#
# A facet is a list-style filter: every entry is filed under exactly one of
# its values, and the picker lists those values with a count each. Category
# was the first; tap and kind are the same shape, so they share one picker
# rather than growing three — three pickers is three sets of keys that drift
# apart, and the user learns one.

#: Facets in the order Tab walks them inside the picker.
FACETS = ("category", "tap", "kind")

#: What a tap facet files an entry with no tap under. Every scanned entry has
#: one; a synthesised row may not, and it still has to be counted somewhere so
#: the picker's rows add up to the total above them.
UNTAPPED = "untapped"

#: The "has none" value of a facet, pinned below the sorted rows. It is not a
#: name the user is looking for, so it should not sit between ``design`` and
#: ``web`` where A–Z would put it.
_PINNED_LAST = {"category": UNCATEGORIZED, "tap": UNTAPPED}

#: The key that opens each facet's picker, as the status bar spells it.
#: ^G was category before there were others. ^R (repo) and ^K (kind) were
#: picked from what a terminal in cbreak mode still delivers: ^C ^Z ^\ raise
#: signals, ^S ^Q are flow control, and on macOS ^O (discard), ^V (literal
#: next) and ^Y (delayed suspend) can be eaten by the tty before curses sees
#: them. ^I ^J ^M ^H are Tab, Enter and Backspace already.
FACET_KEYS = {"category": "^G", "tap": "^R", "kind": "^K"}

#: The status bar's mode pill while each facet's picker is open.
FACET_MODES = {"category": "CATEGORY", "tap": "TAP", "kind": "KIND"}

#: Chip prefix per facet. Distinct prefixes are what let the chips read with
#: the colour off: ``#testing @acme/quality kind:rule`` says which filter is
#: which without a legend.
_CHIP_PREFIX = {"category": "#", "tap": "@", "kind": "kind:"}

#: Picker sort orders, in toggle order. A–Z first: a list you scan for a name
#: is a list sorted by name; largest-first put ``uncategorized`` and the two
#: biggest registries on top and every name anywhere else.
ORDERS = ("az", "count")

_ORDER_LABELS = {"az": "A–Z", "count": "by count"}


def order_label(order: str) -> str:
    """How the picker header names a sort order."""
    return _ORDER_LABELS.get(order, order)


def next_facet(facet: str, step: int = 1) -> str:
    """The next facet in Tab order, wrapping in both directions."""
    try:
        i = FACETS.index(facet)
    except ValueError:
        return FACETS[0]
    return FACETS[(i + step) % len(FACETS)]


def facet_value(entry: dict, facet: str, categories=None) -> str:
    """The value ``entry`` is filed under for ``facet``: lowercased, never
    empty for a known facet (the "has none" value instead), ``""`` for an
    unknown one."""
    if facet == "category":
        return category_of(entry, categories)
    if facet == "tap":
        return str(entry.get("tap") or "").strip().lower() or UNTAPPED
    if facet == "kind":
        # "skill" for a missing kind: the default everywhere else boost
        # reads one (plain_footer, chips, install_target).
        return str(entry.get("kind") or "skill").strip().lower() or "skill"
    return ""


def narrow(entries, filters, categories=None) -> list[dict]:
    """``entries`` kept by every active facet filter (AND).

    ``filters`` maps facet -> value; an empty value is no filter, so a caller
    can pass every facet unconditionally. Values are normalised once here
    rather than per entry, because this walks the whole catalogue.
    """
    want = [(f, str(v).strip().lower()) for f, v in (filters or {}).items()
            if str(v or "").strip()]
    if not want:
        return list(entries)
    return [e for e in entries
            if all(facet_value(e, f, categories) == v for f, v in want)]


def facet_counts(entries, facet: str, categories=None) -> dict[str, int]:
    """``value -> rows`` for ``facet`` over ``entries``."""
    counts: dict[str, int] = {}
    for e in entries:
        v = facet_value(e, facet, categories)
        counts[v] = counts.get(v, 0) + 1
    return counts


def sort_facet_rows(rows, facet: str, order: str = "az"
                    ) -> list[tuple[str, int]]:
    """``(value, count)`` rows in picker order: A–Z (case-insensitive) or
    largest first, with the facet's "has none" value pinned last either way.
    """
    pin = _PINNED_LAST.get(facet)
    body = [r for r in rows if r[0] != pin]
    if order == "count":
        body.sort(key=lambda r: (-r[1], r[0].casefold(), r[0]))
    else:
        body.sort(key=lambda r: (r[0].casefold(), r[0]))
    return body + [r for r in rows if r[0] == pin]


def picker_rows(entries, categories=None, facet: str = "category",
                order: str = "az") -> list[tuple[str, int]]:
    """A facet picker's full row list: ``("", total)`` — no filter — first,
    then every value with its count in ``order``."""
    return [("", len(entries)),
            *sort_facet_rows(list(facet_counts(entries, facet,
                                               categories).items()),
                             facet, order)]


def picker_index(rows, value: str) -> int:
    """The row whose value is ``value`` (case-insensitive), else the top."""
    want = value.strip().lower()
    for i, (c, _n) in enumerate(rows):
        if c == want:
            return i
    return 0


def picker_top(sel: int, n: int, visible: int) -> int:
    """First visible picker row: the selection kept on screen, centred where
    the list allows, never scrolled past either end."""
    if visible <= 0 or n <= visible:
        return 0
    return max(0, min(sel - visible // 2, n - visible))


def picker_line(category: str, count: int, width: int,
                active: bool) -> str:
    """One picker row, ``width`` wide: ``● testing ···· 1,234``.

    The dot marks the value in force, so it reads with the colour off; the
    count right-aligns so the column scans. A label too long for the row is
    cut, never the count.
    """
    num = format(count, ",")
    label = category or "all"
    room = max(0, width - 2 - 1 - len(num))
    head = ("●" if active else " ") + " " + label[:room]
    return (head.ljust(width - len(num)) + num)[:max(0, width)]


def picker_marks(query: str, value: str, count: int, width: int) -> list[int]:
    """Columns of :func:`picker_line` to highlight for ``query``.

    The same best-alignment positions the result list lights up
    (:func:`highlight_positions`), moved past the two-column ``● `` lead and
    dropped where :func:`picker_line` cut the label — a highlight past the cut
    would paint a letter of the count.
    """
    label = value or "all"
    room = max(0, width - 2 - 1 - len(format(count, ",")))
    return sorted(2 + p for p in highlight_positions(query, label)
                  if p < min(room, len(label)))


def _label_hit(ftoks: list[str], label: str) -> bool:
    """Whether every :func:`fold` ed token keeps a picker row.

    The browser's own label rule, not a new one: a value is a short label like
    a name or ``owner/repo``, so any subsequence matches (:func:`loose_text`
    for a label scope is the whole haystack) — ``as`` finds
    ``anthropics/skills`` the way it finds a name.
    """
    hay = fold(label)
    return all(token_matches(t, hay, hay) for t in ftoks)


@dataclass(frozen=True)
class Picker:
    """An open facet picker: everything a keypress can change, and nothing
    curses owns, so :func:`picker_step` is a pure reducer.

    ``rows`` are the value rows in ``order`` without the "all" row, which
    :func:`picker_visible` adds; ``sel`` indexes the *visible* rows.
    """
    facet: str
    rows: tuple[tuple[str, int], ...]
    total: int
    active: str = ""
    query: str = ""
    sel: int = 0
    order: str = "az"


def open_picker(facet: str, counts, total: int, active: str = "",
                order: str = "az") -> Picker:
    """A picker over ``counts`` (``(value, n)`` pairs), on the value in force.
    """
    p = Picker(facet=facet,
               rows=tuple(sort_facet_rows(list(counts), facet, order)),
               total=total, active=active.strip().lower(), order=order)
    return replace(p, sel=picker_index(picker_visible(p), p.active))


def picker_visible(p: Picker) -> list[tuple[str, int]]:
    """The rows on screen: every row under "all" with no query, else only the
    rows the query keeps, in the same order.

    The "all" row leaves while a query is typed. A query means "I am looking
    for a value", and the row whose label is ``all`` matched every ``a`` and
    ``l`` — typing ``a`` for ``ai`` landed on it. Esc empties the query and
    brings it back.
    """
    ftoks = [fold(t) for t in tokens(p.query)]
    if not ftoks:
        return [("", p.total), *p.rows]
    return [r for r in p.rows if _label_hit(ftoks, r[0])]


def picker_value(p: Picker) -> str | None:
    """The selected row's value (``""`` for "all"), or None when the query
    left no row to select."""
    vis = picker_visible(p)
    if not vis:
        return None
    return vis[max(0, min(p.sel, len(vis) - 1))][0]


def _requery(p: Picker, query: str) -> Picker:
    """``p`` with a new query: on the first match while one is typed, back on
    the value in force once it is emptied."""
    q = replace(p, query=query)
    return replace(q, sel=0 if tokens(query)
                   else picker_index(picker_visible(q), q.active))


_MOVES = {"up": -1, "down": 1}


def picker_step(p: Picker, key: str, page: int = 10
                ) -> tuple[Picker, str | None]:
    """One keypress: ``(new picker, action)``.

    ``key`` is a name — ``up`` ``down`` ``pgup`` ``pgdn`` ``enter`` ``esc``
    ``backspace`` ``next`` ``prev`` ``sort`` ``facet:<name>`` — or one
    printable character; the curses layer translates key codes and nothing
    else. ``action`` is None (stay open), ``apply`` (use
    :func:`picker_value`), ``cancel``, ``next``/``prev`` (switch facet) or
    ``facet:<name>``.

    Esc empties a non-empty query before it cancels: a typed filter is work
    in progress, and one key that threw it away *and* closed the picker
    punished the most common correction. Enter on a query that kept nothing
    does nothing — there is no value to apply. A facet's own key closes its
    picker, the way it opened it.
    """
    if key == "esc":
        return (_requery(p, ""), None) if p.query else (p, "cancel")
    if key == "enter":
        return (p, "apply") if picker_visible(p) else (p, None)
    if key in ("next", "prev"):
        return p, key
    if key.startswith("facet:"):
        return p, "cancel" if key[6:] == p.facet else key
    if key == "sort":
        cur = picker_value(p)
        order = ORDERS[(ORDERS.index(p.order) + 1) % len(ORDERS)
                       ] if p.order in ORDERS else ORDERS[0]
        q = replace(p, order=order,
                    rows=tuple(sort_facet_rows(list(p.rows), p.facet, order)))
        # The selection follows its value through the re-sort rather than
        # staying on a row number that now holds something else.
        return replace(q, sel=picker_index(picker_visible(q), cur or "")), None
    if key == "backspace":
        return _requery(p, p.query[:-1]), None
    step = _MOVES.get(key, 0) or {"pgup": -page, "pgdn": page}.get(key, 0)
    if step:
        n = len(picker_visible(p))
        return replace(p, sel=max(0, min(n - 1, p.sel + step))), None
    if len(key) == 1 and key.isprintable():
        return _requery(p, p.query + key), None
    return p, None


def picker_tail(p: Picker) -> str:
    """The picker's ``shown/values`` count. Values only — the "all" row is not
    a value, and counting it made an unfiltered picker read ``4/3``."""
    shown = sum(1 for v, _n in picker_visible(p) if v)
    return "%d/%d" % (shown, len(p.rows))


def picker_empty(query: str) -> list[tuple[str, str]]:
    """``(role, text)`` lines for a picker whose query kept no row — in the
    same ○/→ grammar as the list's :func:`empty_lines`, so an empty picker
    never reads as one that failed to draw."""
    return [("muted", "○ no match for '%s'" % " ".join(query.split())),
            ("muted", "→ backspace edits · esc clears")]


def facet_chip(facet: str, value: str) -> str:
    """One filter as the query row shows it — ``#testing``, ``@acme/quality``,
    ``kind:rule`` — or ``""`` for no filter."""
    if not value:
        return ""
    return _CHIP_PREFIX.get(facet, facet + ":") + value


def query_chips(filters) -> list[str]:
    """The query row's chips for every active filter, in :data:`FACETS`
    order."""
    return [facet_chip(f, (filters or {}).get(f, "")) for f in FACETS
            if (filters or {}).get(f)]


def query_chip(category: str) -> str:
    """The query row's category chip, ``#testing``, or ``""`` for none."""
    return facet_chip("category", category)


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
         "detail": "DETAIL", "picker": "FILTER"}

#: ``(key, label)`` hints per focus, most useful first, quitting always last.
HINTS = {
    "search": (("a-z", "filter"), ("↓", "scopes"), ("↵", "install"),
               ("^T", "scope"), ("^G", "category"), ("^R", "tap"),
               ("^K", "kind"), ("esc", "quit")),
    "scopes": (("← →", "pick"), ("↓", "list"), ("↑", "search"),
               ("esc", "quit")),
    "list": (("↑↓", "move"), ("⇥", "select"), ("↵", "install"),
             ("→", "detail"), ("^T", "scope"), ("^G", "category"),
             ("^R", "tap"), ("^K", "kind"), ("^D", "dupes"), ("esc", "quit")),
    "detail": (("↑↓", "scroll"), ("←", "list"), ("↵", "install"),
               ("esc", "quit")),
    # Not a pane in the focus ring — an overlay over the list — so Esc
    # closes it rather than quitting, and the bar has to say so. Typing
    # filters the rows (it used to jump to the next row starting with the
    # letter, which over 460 taps is most of a screen per keypress).
    "picker": (("a-z", "filter"), ("↑↓", "move"), ("↵", "apply"),
               ("⇥", "facet"), ("^T", "sort"), ("esc", "cancel")),
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
                 summary: tuple[str, str] | None = None,
                 mode: str | None = None) -> list[tuple[int, str, str]]:
    """``(x, role, text)`` spans for the status bar under the frame.

    Left: the mode pill, then the hints for that mode, keys and labels as
    separate spans so the draw layer can colour the key. Right: the session's
    install chip (:func:`session_summary`), which outranks the hints — it is
    news, and the hints are reference — so hints give way first.

    ``mode`` overrides the pill's word: the picker is one focus with one set
    of keys, but it says which facet it is picking (``TAP``, ``KIND``).
    """
    if width <= 0:
        return []
    pill = " %s " % (mode or MODES.get(focus, "LIST"))
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


@dataclass
class InstallSession:
    """What the browser's in-place installs did, handed back when it exits.

    The pane is the only report an in-place install gets while the browser is
    open, and it is gone the moment the browser closes. So everything the
    caller must say afterwards rides here: what landed (with its install
    result, which carries the scan and MCP facts the exit report needs), what
    was refused and why, what an interrupt cancelled, and the plan's notes.
    """
    installed: list = field(default_factory=list)   # [(entry, InstallResult)]
    failed: list = field(default_factory=list)      # [(entry, message, hint)]
    cancelled: list = field(default_factory=list)   # [entry]
    notes: list = field(default_factory=list)       # [(role, text)]
    interrupted: BaseException | None = None

    def landed(self) -> list[dict]:
        """The entries that installed, in install order."""
        return [e for e, _res in self.installed]

    def requested(self) -> bool:
        """True once anything was asked for — a quit with no Enter is None."""
        return bool(self.installed or self.failed or self.cancelled)

    def exit_code(self) -> int:
        """``boost install``'s answer: 1 when any requested install failed."""
        return 1 if self.failed else 0


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


def _wrap(text: str, width: int) -> list[str]:
    """Prose wrapped to ``width`` display columns (:func:`output.wrap_columns`).

    Not ``textwrap.wrap``: that counts codepoints, so a line of full-width CJK
    came back twice as wide as the pane and curses drew it over the list."""
    from . import output  # stdlib-only too; lazy to keep this module light
    return output.wrap_columns(text, width)


def clip_spans(line: Line, width: int) -> Line:
    """``line`` cut to ``width`` columns, spans after the cut dropped.

    Columns, not codepoints: a wide character costs two, so a chip row of CJK
    text cut by ``len`` still ran past the pane."""
    from . import output
    out: Line = []
    room = max(0, width)
    for role, text in line:
        if room <= 0:
            break
        part, used = "", 0
        for ch in text:
            cw = output.visible_len(ch)
            if used + cw > room:
                break
            part, used = part + ch, used + cw
        if text and not part:
            break                   # a wide character that no longer fits
        out.append((role, part))
        room -= used
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
    chunks = _wrap(value, vw) or [""]
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
                     _wrap(text, width) or [""])

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
                         else _wrap(chunk, width))
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
