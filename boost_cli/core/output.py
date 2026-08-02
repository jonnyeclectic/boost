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


def ok(msg: str) -> None:
    """Print msg as an indented success line with a green check mark."""
    print("  " + role("✓", "success") + " " + msg)


def warn(msg: str) -> None:
    """Print msg as an indented `!` warning line, all in the warn role."""
    print("  " + role("!", "warn") + " " + role(msg, "warn"))


def err(msg: str, hint: str | None = None) -> None:
    """Print `Error: msg` to stderr, plus a dim hint line when given."""
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def info(msg: str = "") -> None:
    """Print msg indented two spaces; a blank line when msg is empty."""
    print("  " + msg if msg else "")


def dim(msg: str) -> None:
    """Print msg in the muted role (dim when color is on)."""
    print(role(msg, "muted"))


def heading(msg: str) -> None:
    """Print a bold section header led by the accent `==>` marker."""
    # Brand the section marker in the accent role (Aurora cyan — truecolor,
    # 16-color fallback, plain under NO_COLOR) so every command's headers read
    # as one system.
    print(role("==>", "accent") + " " + c(msg, BOLD))


def verdict(ok: bool, msg: str) -> None:
    """A dashboard verdict line: a success dot + text when healthy, warn when
    not — both the dot and the message resolve through the same role so the
    line reads as one on-theme unit."""
    name = "success" if ok else "warn"
    print("  " + role("●", name) + " " + role(msg, name))


def term_width(default: int = 80) -> int:
    """Best-effort terminal column count; a stable default when detached."""
    return shutil.get_terminal_size((default, 20)).columns


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


def visible_len(s: str) -> int:
    """Length of a string ignoring ANSI color escapes — its column width."""
    return len(_ANSI_RE.sub("", s))


def panel(lines, title: str | None = None, hue: str = "cyan") -> str:
    """A rounded box around one or more lines, with an Aurora-tinted border and
    an optional title set into the top rule — the terminal echo of the web
    design system's .glass / .window surfaces. Plain box under NO_COLOR.
    """
    if isinstance(lines, str):
        lines = [lines]
    widths = [visible_len(x) for x in lines]
    tw = visible_len(title) if title else 0
    inner = max([*widths, tw + 2])  # a titled rule needs a space each side

    def b(s: str) -> str:
        return aurora(s, hue)

    rows = []
    if title:
        rows.append(b("╭─ ") + c(title, BOLD) + b(" " + "─" * (inner - tw - 1) + "╮"))
    else:
        rows.append(b("╭" + "─" * (inner + 2) + "╮"))
    for x, xw in zip(lines, widths):
        rows.append(b("│ ") + x + " " * (inner - xw) + b(" │"))
    rows.append(b("╰" + "─" * (inner + 2) + "╯"))
    return "\n".join(rows)


# macOS-style traffic-light dots (close/minimise/zoom), matching the web
# .window .bar dots — exact truecolor with a 16-color fallback each.
_TRAFFIC = ((0xff, 0x5f, 0x57, RED), (0xfe, 0xbc, 0x2e, YELLOW),
            (0x28, 0xc8, 0x40, GREEN))


def empty_state(message: str, hint: str | None = None) -> str:
    """A standardized empty-state: a muted ○ bullet + message, with an optional
    dim → hint on the next line. One affordance so 'nothing here' always reads
    the same across commands."""
    out_lines = ["  " + c("○ " + message, DIM)]
    if hint:
        out_lines.append("  " + c("→ " + hint, DIM))
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


def kv(key: str, value: str, width: int = 14) -> None:
    """Print an indented key/value line: dim key padded to width, then value."""
    # The str() is NOT redundant despite the annotation: callers pass raw ints
    # (e.g. `boost impact` prints files_touched), which would raise TypeError.
    print("  " + c(key.ljust(width), DIM) + str(value))  # noqa: FURB123


def _pad(cell: str, width: int) -> str:
    """Left-justify by *visible* width, so ANSI-colored cells still align
    (str.ljust counts the invisible escape bytes and under-pads)."""
    return cell + " " * (width - visible_len(cell))


def _rpad(cell: str, width: int) -> str:
    """Right-justify by *visible* width — the numeric-column counterpart to
    _pad, so counts line up on their ones digit like tabular figures."""
    return " " * (width - visible_len(cell)) + cell


_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _numeric_col(cells) -> bool:
    """True when every non-empty cell in a column is a plain number, so the
    column reads as a count and should be right-aligned. Blank cells are
    ignored; a column of only blanks is not numeric."""
    seen = False
    for cell in cells:
        v = _ANSI_RE.sub("", str(cell)).strip()
        if v == "":
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
        out_chars.append(s[i])
        vis += 1
        i += 1
    result = "".join(out_chars) + ellipsis
    if had_escape and not result.endswith(RESET):
        result += RESET
    return result


def _fit_widths(widths, numeric, avail: int, sep: int = 2, floor: int = 1):
    """Shrink the widest non-numeric column one step at a time until the row
    fits `avail` columns (or nothing text-like is left to shrink). Numeric
    columns are never squeezed — a truncated number is a wrong number."""
    widths = list(widths)
    if not widths:
        return widths
    text_cols = [i for i, is_num in enumerate(numeric) if not is_num]

    def total():
        return sum(widths) + sep * (len(widths) - 1)

    while total() > avail:
        shrinkable = [i for i in text_cols if widths[i] > floor]
        if not shrinkable:
            break
        widths[max(shrinkable, key=lambda i: widths[i])] -= 1
    return widths


def table(rows, headers=None) -> None:
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
    if use_color():
        sep, sep_w = " " + DIM + "│" + RESET + " ", 3
    else:
        sep, sep_w = "  ", 2
    widths = _fit_widths(widths, numeric, term_width(), sep=sep_w)

    def fmt(cell: str, i: int) -> str:
        cell = _clip_visible(cell, widths[i])
        return _rpad(cell, widths[i]) if numeric[i] else _pad(cell, widths[i])

    if headers:
        # Bold each header cell individually: a whole-line wrap would be
        # cancelled at the first separator's RESET on color terminals.
        cells = [c(fmt(str(h), i), BOLD) for i, h in enumerate(headers)]
        print(sep.join(cells).rstrip())
    for r in rows:
        print(sep.join(fmt(cell, i) for i, cell in enumerate(r)).rstrip())


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question and return the answer as a bool.

    BOOST_ASSUME_YES or --yes/-y force True; non-TTY stdin and an empty
    answer return `default`; EOF or Ctrl-C returns False.
    """
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")
