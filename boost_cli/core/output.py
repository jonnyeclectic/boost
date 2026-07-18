"""Terminal output helpers — colors, symbols, tables.

Conventions used across all commands:
  ok("copied to ...")    ->  "  ✓ copied to ..."           (green check)
  warn("...")            ->  "  ! ..."                     (yellow)
  err("...")             ->  "Error: ..." on stderr        (red)
  info("...")            ->  plain indented line
  heading("...")         ->  bold section header
"""
from __future__ import annotations

import os
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


def use_color(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def c(text: str, *styles: str) -> str:
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


# Each Aurora token pairs its exact truecolor value with a 16-color fallback,
# so the brand still reads on terminals without truecolor. Hexes mirror
# style/boost.css: --cyan #22d3ee, --violet #a855f7, --pink #f472d0,
# --green #4ade80, --yellow #facc15.
_AURORA = {
    "cyan":   ((0x22, 0xd3, 0xee), CYAN),
    "violet": ((0xa8, 0x55, 0xf7), MAGENTA),
    "pink":   ((0xf4, 0x72, 0xd0), MAGENTA),
    "green":  ((0x4a, 0xde, 0x80), GREEN),
    "yellow": ((0xfa, 0xcc, 0x15), YELLOW),
}

# The signature cyan -> violet -> pink gradient (style/boost.css --grad).
_GRAD_STOPS = ((0x22, 0xd3, 0xee), (0xa8, 0x55, 0xf7), (0xf4, 0x72, 0xd0))


def aurora(text: str, name: str, stream=None) -> str:
    """Paint text in an Aurora brand color, degrading gracefully by level."""
    level = color_level(stream)
    if level == 0:
        return text
    triple, fallback = _AURORA[name]
    code = rgb(*triple) if level == 2 else fallback
    return code + text + RESET


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
    print("  " + c("✓", GREEN) + " " + msg)


def warn(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, YELLOW))


def err(msg: str, hint: str | None = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def info(msg: str = "") -> None:
    print("  " + msg if msg else "")


def dim(msg: str) -> None:
    print(c(msg, DIM))


def heading(msg: str) -> None:
    # Brand the section marker in Aurora cyan (truecolor, 16-color fallback,
    # plain under NO_COLOR) so every command's headers read as one system.
    print(aurora("==>", "cyan") + " " + c(msg, BOLD))


def verdict(ok: bool, msg: str) -> None:
    """A dashboard verdict line: a green dot when healthy, amber when not."""
    dot = aurora("●", "green" if ok else "yellow")
    print("  " + dot + " " + c(msg, GREEN if ok else YELLOW))


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
    print("  " + c(key.ljust(width), DIM) + str(value))


def table(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def confirm(prompt: str, default: bool = False) -> bool:
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
