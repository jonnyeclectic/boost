# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Terminal output helpers — colors, symbols, tables.

Conventions used across all commands:
  ok("copied to ...")    ->  "  ✓ copied to ..."           (green check)
  warn("...")            ->  "  ! ..."                     (yellow)
  err("...")             ->  "Error: ..." on stderr        (red)
  info("...")            ->  plain indented line
  heading("...")         ->  bold section header
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def harden_console_encoding() -> None:
    """Reconfigure stdout/stderr to UTF-8.

    boost's own output uses non-ASCII (checkmarks, em dashes, arrows); a
    console whose codepage isn't UTF-8 — chiefly Windows' legacy codepages —
    raises UnicodeEncodeError on that output otherwise. reconfigure() is
    missing on some wrapped/piped streams (e.g. under certain test harnesses),
    so skip a stream that doesn't have it rather than fail startup over it.
    """
    for stream in (sys.stdout, sys.stderr):
        # getattr, not hasattr+call: same guard, but it also gives the type
        # checkers a concrete optional to narrow (TextIO has no `reconfigure`).
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")


def use_color(stream=None) -> bool:
    """True when ANSI color should be emitted on `stream` (default stdout).

    BOOST_COLOR=always/never is boost's explicit override and beats
    NO_COLOR, CLICOLOR_FORCE and the TTY check.
    """
    # BOOST_COLOR is boost's own explicit override and wins over everything
    # else (most-specific-wins): always/never force it on/off regardless of
    # NO_COLOR, CLICOLOR_FORCE or the TTY check. Anything else (incl. "auto")
    # falls through to the standard detection below.
    override = os.environ.get("BOOST_COLOR", "").lower()
    if override in ("never", "off", "0"):
        return False
    if override in ("always", "force", "1"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def c(text: str, *styles: str) -> str:
    """Wrap text in the given SGR styles + RESET; plain when color is off."""
    if not styles or not use_color():
        return text
    return "".join(styles) + text + RESET


# --------------------------------------------------------------------------- #
# Aurora palette — bring the web design system (style/boost.css :root) into the
# terminal as 24-bit truecolor, degrading to 16-color then to plain text.
# Everything below builds on use_color(), so NO_COLOR / non-TTY still win.
# --------------------------------------------------------------------------- #

def color_level(stream=None) -> int:
    """Terminal color support: 0 = none, 1 = basic (16), 2 = truecolor.

    Builds on use_color(); truecolor is claimed only when the terminal
    advertises it via COLORTERM (truecolor/24bit), or when color is forced.
    """
    if not use_color(stream):
        return 0
    env = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in env or "24bit" in env:
        return 2
    if os.environ.get("CLICOLOR_FORCE"):
        return 2
    return 1


def rgb(r: int, g: int, b: int) -> str:
    """A 24-bit foreground SGR escape for the given color channels."""
    return "\033[38;2;%d;%d;%dm" % (r, g, b)


# Aurora palette — the single source of truth for boost's terminal colors.
# These RGB triples mirror the web design system's :root tokens in
# style/boost.css and must be kept in lockstep with it; everything else here
# (the gradient, brand tints, badges) is derived from them, never re-typed.
TOKENS = {
    "cyan":   (0x40, 0xcb, 0xe3),   # --cyan   #40cbe3
    "violet": (0xcc, 0x9e, 0xff),   # --violet #cc9eff
    "pink":   (0xf5, 0x8f, 0xd7),   # --pink   #f58fd7
    "green":  (0x4a, 0xde, 0x80),   # --green  #4ade80
    "yellow": (0xfa, 0xcc, 0x15),   # --yellow #facc15
}

# Each Aurora token pairs its truecolor value with a 16-color fallback, so the
# brand still reads on terminals without truecolor.
_AURORA = {
    "cyan":   (TOKENS["cyan"], CYAN),
    "violet": (TOKENS["violet"], MAGENTA),
    "pink":   (TOKENS["pink"], MAGENTA),
    "green":  (TOKENS["green"], GREEN),
    "yellow": (TOKENS["yellow"], YELLOW),
}

# The signature cyan -> violet -> pink gradient (style/boost.css --grad).
_GRAD_STOPS = (TOKENS["cyan"], TOKENS["violet"], TOKENS["pink"])


def aurora(text: str, name: str, stream=None) -> str:
    """Paint text in an Aurora brand color, degrading gracefully by level."""
    level = color_level(stream)
    if level == 0:
        return text
    triple, fallback = _AURORA[name]
    code = rgb(*triple) if level == 2 else fallback
    return code + text + RESET


# --------------------------------------------------------------------------- #
# Semantic color roles — name the *intent* (accent / brand / success / warn /
# danger / muted), never the raw code. Every surface resolves its color through
# this one table, so a re-theme is a single edit here instead of a repo-wide
# sweep, and each call site reads as meaning ("danger") rather than mechanics
# ("RED"). Brand hues resolve through the Aurora palette (truecolor -> 16-color
# -> plain); danger/muted map to base SGR attributes that have no Aurora token.
# --------------------------------------------------------------------------- #
ROLES = {
    "accent":  ("aurora", "cyan"),
    "brand":   ("aurora", "violet"),
    "success": ("aurora", "green"),
    "warn":    ("aurora", "yellow"),
    "danger":  ("sgr", RED),
    "muted":   ("sgr", DIM),
}


def role(text: str, name: str, bold: bool = False, stream=None) -> str:
    """Paint text by semantic role instead of a raw color code.

    Roles resolve through ROLES so re-theming is a one-file edit; they degrade
    truecolor -> 16-color -> plain exactly like the rest of this module. Pass
    bold=True for an emphasized variant (the weight, like color, is dropped
    when color is off).
    """
    if color_level(stream) == 0:
        return text
    kind, value = ROLES[name]
    painted = aurora(text, value, stream) if kind == "aurora" else value + text + RESET
    return BOLD + painted if bold else painted


def _lerp(a, b, t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(text: str, stream=None) -> str:
    """Paint text with the per-character Aurora gradient (cyan->violet->pink).

    Truecolor only; on 16-color terminals it falls back to a single brand
    color, and to plain text when color is off.
    """
    level = color_level(stream)
    if level == 0 or not text:
        return text
    if level == 1:
        return aurora(text, "violet", stream)
    stops = _GRAD_STOPS
    span = len(stops) - 1  # number of gradient segments
    n = len(text)
    out = []
    for i, ch in enumerate(text):
        t = i / (n - 1) if n > 1 else 0.0
        seg = min(int(t * span), span - 1)
        local = t * span - seg
        out.append(rgb(*_lerp(stops[seg], stops[seg + 1], local)) + ch)
    out.append(RESET)
    return "".join(out)


def _wrap_lines(msg: str, lead: int) -> list[str]:
    """Wrap `msg` for an emitter whose own prefix costs `lead` columns.

    Returns at least one line so an emitter never silently prints nothing for a
    message it was given; the emitter decides what its prefix and continuation
    padding look like.
    """
    return wrap(msg, term_width() - lead) or [msg]


def ok(msg: str) -> None:
    """Print msg as an indented success line with a green check mark."""
    print("  " + role("✓", "success") + " " + msg)


def warn(msg: str, stream=None, wrap: bool = False) -> None:
    """Print msg as an indented `!` warning line, all in the warn role.

    ``stream`` exists for the commands that also speak JSON on stdout: a notice
    about *which corpus answered* has to survive `--json`, and the old choice
    was between corrupting the JSON and suppressing the notice entirely. Passing
    ``sys.stderr`` keeps both.

    ``wrap`` is opt-in per call site rather than always-on, because not every
    long line is prose: `pulse`'s `source=` paths and `fingerprint`'s hash are
    data, and folding those destroys the information the line exists to carry.
    Prose hints pass it; data lines do not.
    """
    body = _wrap_lines(msg, 4) if wrap else [msg]
    for i, line in enumerate(body):
        lead = "  " + role("!", "warn") + " " if i == 0 else "    "
        print(lead + role(line, "warn"), file=stream)


def err(msg: str, hint: str | None = None) -> None:
    """Print `Error: msg` to stderr, plus a dim hint line when given."""
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def info(msg: str = "", stream=None, wrap: bool = False) -> None:
    """Print msg indented two spaces; a blank line when msg is empty.

    ``stream`` as in :func:`warn` — so a hint can accompany a stderr notice.
    ``wrap`` as in :func:`warn`, and it never turns the empty message into no
    output at all: a caller printing a blank spacer still gets its blank line.
    """
    if wrap and msg:
        for line in _wrap_lines(msg, 2):
            print("  " + line, file=stream)
        return
    print("  " + msg if msg else "", file=stream)


# C0 and C1 controls, minus the tab/newline the table layer already folds. ESC
# is the one that matters: `\x1b[1A\x1b[2K` moves the cursor up and erases, so a
# single crafted field can rewrite rows already printed above it.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def plain(text: object) -> str:
    """Strip terminal control characters from text boost did not author.

    Anything that arrives from a network response, a tapped repo's frontmatter,
    or a filename is untrusted for display purposes even when it is harmless as
    data. Rendering it into a table is what makes it executable-ish: the
    terminal, not boost, decides what an escape sequence means.

    Typed ``object`` rather than ``str`` because the callers are feeding it
    parsed JSON — a field that is documented as a string is still whatever the
    remote sent, and coercing here beats a TypeError at render time.
    """
    return _CONTROL_RE.sub("", str(text))


def dim(msg: str, wrap: bool = False) -> None:
    """Print msg in the muted role (dim when color is on).

    ``wrap`` as in :func:`warn`. `dim` prints flush left, so the wrapped
    continuations are flush left too — there is no marker to align under.
    """
    for line in (_wrap_lines(msg, 0) if wrap else [msg]):
        print(role(line, "muted"))


def heading(msg: str, stream=None) -> None:
    """Print a bold section header led by the accent `==>` marker.

    ``stream`` as in :func:`warn` — a report header must follow its content
    off stdout when a caller's stdout carries something else (e.g. `absorb`
    without ``--install`` writes the generated SKILL.md there).
    """
    # Brand the section marker in the accent role (Aurora cyan — truecolor,
    # 16-color fallback, plain under NO_COLOR) so every command's headers read
    # as one system.
    print(role("==>", "accent") + " " + c(msg, BOLD), file=stream)


def verdict(ok: bool, msg: str) -> None:
    """A dashboard verdict line: a success dot + text when healthy, warn when
    not — both the dot and the message resolve through the same role so the
    line reads as one on-theme unit."""
    name = "success" if ok else "warn"
    print("  " + role("●", name) + " " + role(msg, name))


def term_width(default: int = 80) -> int:
    """Best-effort terminal column count; a stable default when detached."""
    return shutil.get_terminal_size((default, 20)).columns


def pane_width(stream=None) -> int | None:
    """The pane to fit *data* to, or None when there is no pane.

    :func:`term_width` always answers a number — 80 when stdout is detached —
    which is right for chrome and wrong for data. A pipe has no pane, so
    fitting a table to an assumed 80 columns clips the NAME column that
    ``boost list | grep`` is matching on and that `untap`/`update` take as an
    argument. An explicit ``COLUMNS`` is a deliberate answer about width and is
    honored either way, TTY or not.
    """
    columns = os.environ.get("COLUMNS", "").strip()
    if columns.isdigit() and int(columns) > 0:
        return int(columns)
    stream = stream or sys.stdout
    if hasattr(stream, "isatty") and stream.isatty():
        return term_width()
    return None


def truncate(text: str, width: int, ellipsis: str = "…") -> str:
    """Collapse whitespace (including literal \\n / \\t escapes) to single
    spaces, then clip to at most `width` columns with a trailing ellipsis.

    Keeps list output to one tidy line each — a 2,000-char blob becomes a
    scannable snippet instead of blowing up the pane.
    """
    text = text.replace("\\n", " ").replace("\\t", " ").replace("\\r", " ")
    text = " ".join(text.split())
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= len(ellipsis):
        return ellipsis[:width]
    return text[:width - len(ellipsis)] + ellipsis


def badge(label: str, hue: str = "cyan") -> str:
    """A compact status pill for identity cards — an Aurora-tinted [label]
    (plain under NO_COLOR), echoing the web design system's .badge pills."""
    return aurora("[" + label + "]", hue)


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _char_width(ch: str) -> int:
    """Terminal display width of one character: 2 for wide/fullwidth CJK and
    most emoji, 0 for a combining mark, 1 otherwise.

    A pure-stdlib approximation of wcwidth via ``unicodedata`` — no dependency
    to earn just for column math, and the two classes it distinguishes
    (``unicodedata.east_asian_width`` returning "W"/"F") are exactly the ones
    that render two columns wide in every terminal this CLI targets.
    """
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def visible_len(s: str) -> int:
    """Column width of a string: ANSI escapes cost nothing, a wide character
    (CJK, most emoji) costs 2, everything else costs 1.

    ``len()`` alone undercounts any string holding a double-width character,
    which is what silently misaligned a table the moment a cell held an emoji
    or CJK text — the column budget was measured a codepoint short of what
    the terminal actually draws.
    """
    return sum(_char_width(ch) for ch in _ANSI_RE.sub("", s))


_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def _glued(text: str, i: int) -> bool:
    """True when `text[i]` exists, is not whitespace, and is not a backtick."""
    return i < len(text) and not text[i].isspace() and text[i] != "`"


def _wrap_tokens(text: str) -> list[str]:
    """Split text into wrap units, keeping each `code span` whole.

    A backtick span is one token even though it contains spaces, because the
    spans in boost's hints are shell commands the user is meant to select and
    paste — `pip install 'boost-skill-cli[rag]'`. Everything outside a span is
    split on whitespace, which collapses runs and newlines the way
    :func:`truncate` does; the span itself is copied verbatim, so a command
    that legitimately holds two spaces survives.

    The span also absorbs punctuation glued directly against its backticks
    with no whitespace between, so a source string like ``(see `x y`)``
    stays one token and `wrap()` never manufactures a space the source never
    had. That absorption is a pair of plain index scans (`_glued`), not a
    wider regex: a quantifier written to match it (``\\S*`[^`]*`\\S*``) lets
    the engine backtrack the leading run into the following literal backtick
    for every starting position, which is quadratic in the length of an
    unterminated glued run — worth avoiding even though nothing here reads
    from outside the process, since these are still user-composed strings
    (a skill name, a tap path) flowing into `out.warn`/`out.info`. The scan
    stops at a backtick on either side for the same reason the regex
    excluded one: an adjacent ``` `beta` ``` must start its own span, not
    fold into the one before it, or two spans separated only by ordinary
    prose (` `alpha` between `beta` `) would bridge into one unbreakable
    token.

    An unterminated backtick simply never matches, and its text wraps as
    ordinary words. That is the right failure: a half-open span is a typo in
    the message, not a reason to refuse to render it.
    """
    parts: list[str] = []
    pos = 0
    for m in _CODE_SPAN_RE.finditer(text):
        start, end = m.start(), m.end()
        if start < pos:
            continue  # already absorbed into the previous span's suffix
        while start > pos and _glued(text, start - 1):
            start -= 1
        while _glued(text, end):
            end += 1
        parts.extend(text[pos:start].split())
        parts.append(text[start:end])
        pos = end
    parts.extend(text[pos:].split())
    return parts


def wrap(text: str, width: int | None = None, indent: str = "") -> list[str]:
    """Greedy word-wrap to `width` visible columns, never splitting a code span.

    Returns one string per line: the first bare, the rest prefixed with
    `indent`, and every one measured with :func:`visible_len` so a coloured
    message is bounded by what the pane shows rather than by its byte count.
    ``width`` defaults to the live terminal.

    **A token wider than the line is emitted whole and overflows.** That is
    deliberate and it is the reason this is not `textwrap.wrap(break_long_words
    =True)`: the tokens that hit this case are the backticked commands, and a
    command chopped at column 80 is worse than useless — the user pastes it and
    it fails. One long line the terminal soft-wraps still yields the right text
    on a copy.

    Empty (or all-whitespace) text wraps to no lines at all, so a caller can
    tell "nothing to say" from "one blank line".
    """
    width = term_width() if width is None else width
    tokens = _wrap_tokens(text)
    if not tokens:
        return []
    pad = visible_len(indent)
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        # The first line spends the full width; every later one pays for the
        # indent. No floor under the subtraction: a pane narrower than its own
        # indent yields a limit no token can meet, and each token lands on its
        # own line — which is the same answer a floor of 1 gives, because the
        # fit test below is never satisfiable below 3 columns anyway.
        limit = width if not lines else width - pad
        if cur and visible_len(cur) + 1 + visible_len(tok) <= limit:
            cur += " " + tok
        else:
            if cur:
                lines.append(cur)
            cur = tok
    lines.append(cur)
    return [lines[0]] + [indent + ln for ln in lines[1:]]


#: Alias for callers that take a ``wrap`` keyword argument of their own, which
#: would otherwise shadow the function inside their own body.
wrap_text = wrap


def panel(lines, title: str | None = None, hue: str = "cyan") -> str:
    """A rounded box around one or more lines, with an Aurora-tinted border and
    an optional title set into the top rule — the terminal echo of the web
    design system's .glass / .window surfaces. Plain box under NO_COLOR.
    """
    if isinstance(lines, str):
        lines = [lines]
    # The border costs four columns — "\u2502 " on the left, " \u2502" on the right —
    # so that is what the content may not exceed. Without this the box sized
    # itself to its content and sailed past the pane: `boost count` drew 108
    # columns into an 80-column terminal, and a box whose border wraps is the
    # worst-looking overflow the CLI has, because the shape itself breaks.
    room = term_width() - 4
    if title:
        title = _clip_visible(title, room - 2)
    lines = [_clip_visible(x, room) for x in lines]
    widths = [visible_len(x) for x in lines]
    tw = visible_len(title) if title else 0
    # A titled rule needs a space each side, hence the +2 / -2. Clipping above
    # already bounds every width by `room`, so no second clamp is needed here.
    inner = max([*widths, tw + 2])

    def b(s: str) -> str:
        return aurora(s, hue)

    rows = []
    if title:
        rows.append(b("╭─ ") + c(title, BOLD) + b(" " + "─" * (inner - tw - 1) + "╮"))
    else:
        rows.append(b("╭" + "─" * (inner + 2) + "╮"))
    for x, xw in zip(lines, widths, strict=True):
        rows.append(b("│ ") + x + " " * (inner - xw) + b(" │"))
    rows.append(b("╰" + "─" * (inner + 2) + "╯"))
    return "\n".join(rows)


# macOS-style traffic-light dots (close/minimise/zoom), matching the web
# .window .bar dots — exact truecolor with a 16-color fallback each.
_TRAFFIC = ((0xff, 0x5f, 0x57, RED), (0xfe, 0xbc, 0x2e, YELLOW),
            (0x28, 0xc8, 0x40, GREEN))


def empty_state(message: str, hint: str | None = None, wrap: bool = False) -> str:
    """A standardized empty-state: a muted ○ bullet + message, with an optional
    dim → hint on the next line. One affordance so 'nothing here' always reads
    the same across commands.

    ``wrap`` as in :func:`warn`: opt-in, folding each block to the pane rather
    than always-on, so a call site with an atomic backtick-quoted command
    (e.g. cohort's create hint) still gets that command whole rather than
    split across lines. Both markers ("○ " / "→ ") are two visible columns,
    matching the module's other 4-column-lead emitters (2-space indent + a
    2-wide marker), so message and hint wrap to the same budget.
    """
    def _block(marker: str, text: str) -> list[str]:
        body = _wrap_lines(text, 4) if wrap else [text]
        return (["  " + c(marker + body[0], DIM)]
                + ["    " + c(ln, DIM) for ln in body[1:]])

    out_lines = _block("○ ", message)
    if hint:
        out_lines += _block("→ ", hint)
    return "\n".join(out_lines)


def titlebar(title: str) -> str:
    """A terminal window title bar: traffic-light dots + a bold title, the
    terminal echo of the web .window .bar. Plain dots under NO_COLOR."""
    level = color_level()
    if level == 0:
        dots = "● ● ●"
    else:
        dots = " ".join((rgb(r, g, bl) if level == 2 else fb) + "●" + RESET
                        for r, g, bl, fb in _TRAFFIC)
    return "  " + dots + "  " + c(title, BOLD)


def meter(fraction: float, width: int = 4) -> str:
    """A tiny proportional bar for a 0..1 fraction — filled ▰ vs empty ▱.

    Uncolored on purpose so callers can Aurora-tint it by magnitude.
    """
    if fraction < 0:
        fraction = 0.0
    elif fraction > 1:
        fraction = 1.0
    filled = round(fraction * width)
    return "▰" * filled + "▱" * (width - filled)


def meter_hue(frac: float) -> str:
    """Aurora tint name for a 0..1 relevance fraction.

    The search screen's one gradient moment: magnitude rides the brand ramp
    (cyan for the top third, violet for the middle, pink below), so the
    ranking itself is the gradient. Out-of-range fractions clamp to the ends.
    """
    if frac >= 0.66:
        return "cyan"
    if frac >= 0.33:
        return "violet"
    return "pink"


def kind_label(kind: str) -> str:
    """Bracketed display text for a catalog kind — ``[skill]`` / ``[rule]`` /
    ``[workflow]``, an unknown kind bracketed verbatim, a missing one shown as
    the default kind. The single vocabulary both search rows and the browse
    badges render, so the two surfaces cannot drift apart.
    """
    return "[%s]" % (kind or "skill")


#: Fixed cells of a search row before the name column: the 4-glyph meter, a
#: space, the 1-column installed mark, a space.
_SEARCH_FIXED = 7
#: out.info's lead-in, which the row itself never contains but must budget for.
_SEARCH_INDENT = 2
#: Visible width of the pinned curated tail, "  ★ curated".
_CURATED_TAIL_W = 11


@dataclass(frozen=True)
class SearchLayout:
    """Column plan for one search-result screen, in visible cells.

    Frozen so every row of a screen is measured against the same plan — a
    per-row recomputation is how columns come to wander.
    """
    cols: int            # full terminal width the plan was built for
    name_w: int
    kind_w: int          # 0 = the kind column is dropped
    tap_w: int           # 0 = the tap column is dropped
    desc_w: int          # room for an uncurated row's description


def search_layout(cols: int, names: Sequence[str], kinds: Sequence[str],
                  taps: Sequence[str]) -> SearchLayout:
    """Plan the search-result columns for a ``cols``-wide terminal.

    Sizing: the name column fits the widest shown name (capped at 32), the
    kind column the widest shown kind label (capped at ``[workflow]``'s 10),
    the tap column the widest shown tap (capped at 20). The description gets
    the remainder.

    Drop priority when narrow — provenance is the first luxury, prose the
    last: the tap goes below 84 columns or whenever it would leave the
    description under 24 cells; then the description shrinks toward its floor
    of 8; then the name cap tightens 32 → 24 → 16 → 12; the kind column is
    dropped outright below 48 columns. The meter, the mark column, the name
    and the curated tail are never dropped. Every row assembled from the plan
    measures within ``cols`` (indent included) for any terminal 40 cells wide
    or more.
    """
    avail = cols - _SEARCH_INDENT - _SEARCH_FIXED
    name_w = min(max((len(n) for n in names), default=1), 32)
    kind_w = 0
    if cols >= 48:
        kind_w = min(max((len(kind_label(k)) for k in kinds), default=0), 10)
    tap_w = 0
    if cols >= 84:
        tap_w = min(max((len(t) for t in taps), default=0), 20)

    def desc_room(nw: int) -> int:
        return (avail - nw - 2 - (kind_w + 2 if kind_w else 0)
                - (tap_w + 2 if tap_w else 0))

    if tap_w and desc_room(name_w) < 24:
        tap_w = 0
    for cap in (24, 16, 12):
        if desc_room(name_w) >= 8:
            break
        name_w = min(name_w, cap)
    return SearchLayout(cols=cols, name_w=name_w, kind_w=kind_w, tap_w=tap_w,
                        desc_w=max(8, desc_room(name_w)))


def format_search_row(name: str, desc: str, kind: str, tap: str, frac: float,
                      *, curated: bool, installed: bool,
                      lay: SearchLayout) -> str:
    """Assemble one search-result line (without the 2-space print indent).

    Everything resolves through roles, so the plain path (NO_COLOR, pipes) is
    byte-stable text and the colored path strips back to exactly it. The
    meter glyph count never varies with color state; the installed mark's
    column is reserved either way so names align; a curated row pays for its
    pinned ``  ★ curated`` tail out of its own description.
    """
    row = (aurora(meter(frac), meter_hue(frac)) + " "
           + (role("●", "success") if installed else " ") + " "
           + _pad(role(truncate(name, lay.name_w), "accent"), lay.name_w))
    if lay.kind_w:
        row += "  " + _pad(role(truncate(kind_label(kind), lay.kind_w),
                                "muted"), lay.kind_w)
    if lay.tap_w:
        row += "  " + _pad(role(truncate(tap, lay.tap_w), "muted"), lay.tap_w)
    dw = lay.desc_w - (_CURATED_TAIL_W if curated else 0)
    clipped = truncate(desc, dw)
    if clipped:
        row += "  " + clipped
    if curated:
        # At the description floor the 11-cell tail is one cell wider than
        # the 2 + desc_w budget it replaces, so its lead shrinks to a single
        # space there — the ★ and its word are pinned, the gutter is not.
        lead = "  " if clipped or lay.desc_w >= _CURATED_TAIL_W - 1 else " "
        row += lead + role("★ curated", "warn")
    return row.rstrip()


def kv(key: str, value: str, width: int = 14, wrap: bool = False) -> None:
    """Print an indented key/value line: dim key padded to width, then value.

    ``wrap`` as in :func:`warn`, and the continuations align under the *value*
    rather than the key — a value folded back to column 0 reads as a new row.
    """
    # The str() is NOT redundant despite the annotation: callers pass raw ints
    # (e.g. `boost impact` prints files_touched), which would raise TypeError.
    text = str(value)  # noqa: FURB123
    if not wrap:
        print("  " + c(key.ljust(width), DIM) + text)
        return
    lead = 2 + width
    lines = wrap_text(text, term_width() - lead) or [text]
    print("  " + c(key.ljust(width), DIM) + lines[0])
    for line in lines[1:]:
        print(" " * lead + line)


def _pad(cell: str, width: int) -> str:
    """Left-justify by *visible* width, so ANSI-colored cells still align
    (str.ljust counts the invisible escape bytes and under-pads)."""
    return cell + " " * (width - visible_len(cell))


def _rpad(cell: str, width: int) -> str:
    """Right-justify by *visible* width — the numeric-column counterpart to
    _pad, so counts line up on their ones digit like tabular figures."""
    return " " * (width - visible_len(cell)) + cell


_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")

# A count column's own "no data for this row" placeholder (e.g. `boost impact`'s
# COMMITS SINCE column when a skill's git activity is unavailable). Treated like
# a blank cell below so one placeholder row doesn't knock the whole column back
# to left-aligned text — the em dash would otherwise sit misaligned under the
# right-aligned numbers around it.
_NUMERIC_PLACEHOLDER = "—"


def _numeric_col(cells) -> bool:
    """True when every non-empty cell in a column is a plain number, so the
    column reads as a count and should be right-aligned. Blank cells and the
    "—" no-data placeholder are ignored; a column of only those is not
    numeric."""
    seen = False
    for cell in cells:
        v = _ANSI_RE.sub("", str(cell)).strip()
        if v in ("", _NUMERIC_PLACEHOLDER):
            continue
        seen = True
        if not _NUMERIC_RE.fullmatch(v):
            return False
    return seen


def _clip_visible(s: str, width: int, ellipsis: str = "…") -> str:
    """Truncate to `width` *visible* columns, preserving ANSI color runs and
    closing any open color with a RESET. A no-op when the cell already fits."""
    if visible_len(s) <= width:
        return s
    if width <= 0:
        return ""
    keep = width - len(ellipsis) if width > len(ellipsis) else 0
    out_chars, vis, i, had_escape = [], 0, 0, False
    while i < len(s) and vis < keep:
        m = _ANSI_RE.match(s, i)
        if m:
            out_chars.append(m.group(0))
            had_escape = True
            i = m.end()
            continue
        w = _char_width(s[i])
        if vis + w > keep:
            break  # a wide character never gets cut in half for the ellipsis
        out_chars.append(s[i])
        vis += w
        i += 1
    result = "".join(out_chars) + ellipsis
    if had_escape and not result.endswith(RESET):
        result += RESET
    return result


def _fit_widths(widths, numeric, avail: int, sep: int = 2, floor: int = 1,
                protected=()):
    """Shrink the widest non-numeric column one step at a time until the row
    fits `avail` columns (or nothing text-like is left to shrink). Numeric
    columns are never squeezed — a truncated number is a wrong number — and
    neither are the `protected` indexes, whose cells are identifiers rather
    than prose (see :func:`table`'s ``keep``), so a narrow pane spends its
    shrinking on chrome first."""
    widths = list(widths)
    if not widths:
        return widths
    protected = set(protected)
    text_cols = [i for i, is_num in enumerate(numeric)
                 if not is_num and i not in protected]

    def total():
        return sum(widths) + sep * (len(widths) - 1)

    while total() > avail:
        shrinkable = [i for i in text_cols if widths[i] > floor]
        if not shrinkable:
            break
        widths[max(shrinkable, key=lambda i: widths[i])] -= 1
    return widths


def _keep_indexes(keep, headers, ncols) -> set[int]:
    """Resolve `table`'s ``keep`` — column indexes, header names, or a mix —
    to indexes. An unknown name is ignored rather than raising: a call site
    naming a header it no longer emits should lose the protection, not the
    table."""
    names = {str(h): i for i, h in enumerate(headers or ())}
    out_idx = set()
    for item in keep:
        if isinstance(item, int) and not isinstance(item, bool):
            if 0 <= item < ncols:
                out_idx.add(item)
        elif item in names:
            out_idx.add(names[item])
    return out_idx


def table(rows, headers=None, stream=None, keep=()) -> None:
    """Print an aligned table. rows: list of tuples of strings.

    Column widths are measured by visible width (ignoring ANSI color codes),
    so colored cells line up the same as plain ones. The table is width-aware:
    numeric columns are right-aligned, and when a row would overflow the
    terminal the widest text column is shrunk (its cells clipped with an
    ellipsis) so wide catalogs stay on one line instead of wrapping.

    On a color terminal, columns are joined by a dim ``│`` separator — the
    terminal cousin of the web stat blocks' hairline borders. Non-color output
    (pipes, NO_COLOR, tests) keeps the plain two-space gutter byte-for-byte,
    so scripts that parse table output never see the ornament.

    ``stream`` as in :func:`warn` — a report a caller needs off stdout (e.g.
    a table printed alongside generated content on stdout) can be redirected
    as a whole.

    Fitting only happens when there is a pane to fit (:func:`pane_width`):
    piped output is emitted whole, because a clipped NAME is not the name.
    ``keep`` names the columns — by index or header — whose cells are
    identifiers rather than prose (a snapshot ID, a digest, a hook command),
    so a narrow pane shrinks the chrome beside them instead.
    """
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    ncols = max(len(r) for r in all_rows)
    widths = [max(visible_len(r[i]) for r in all_rows if i < len(r))
              for i in range(ncols)]
    numeric = [_numeric_col([r[i] for r in rows if i < len(r)])
               for i in range(ncols)]
    if use_color(stream):
        sep, sep_w = " " + DIM + "│" + RESET + " ", 3
    else:
        sep, sep_w = "  ", 2
    avail = pane_width(stream)
    if avail is not None:
        widths = _fit_widths(widths, numeric, avail, sep=sep_w,
                             protected=_keep_indexes(keep, headers, ncols))

    def fmt(cell: str, i: int) -> str:
        cell = _clip_visible(cell, widths[i])
        return _rpad(cell, widths[i]) if numeric[i] else _pad(cell, widths[i])

    if headers:
        # Bold each header cell individually: a whole-line wrap would be
        # cancelled at the first separator's RESET on color terminals.
        cells = [c(fmt(str(h), i), BOLD) for i, h in enumerate(headers)]
        print(sep.join(cells).rstrip(), file=stream)
    for r in rows:
        print(sep.join(fmt(cell, i) for i, cell in enumerate(r)).rstrip(),
              file=stream)


_CONFIRM_BYPASS_HINT = "pass -y or set BOOST_ASSUME_YES=1 to skip this prompt"


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question and return the answer as a bool.

    BOOST_ASSUME_YES or --yes/-y force True; non-TTY stdin and an empty
    answer return `default`; EOF or Ctrl-C returns False.

    Every path that resolves to a decline (as opposed to `default` being
    True) prints the bypass hint here, once, so callers inherit it instead
    of each command growing its own reminder — see the confirm-bypass-hints
    roadmap item.
    """
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        if not default:
            dim(_CONFIRM_BYPASS_HINT)
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        dim(_CONFIRM_BYPASS_HINT)
        return False
    result = answer in ("y", "yes") if answer else default
    if not result:
        dim(_CONFIRM_BYPASS_HINT)
    return result
