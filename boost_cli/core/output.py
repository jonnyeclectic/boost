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


def ok(msg: str) -> None:
    print("  " + c("✓", GREEN) + " " + msg)


def warn(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, YELLOW))


def err(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def info(msg: str = "") -> None:
    print("  " + msg if msg else "")


def dim(msg: str) -> None:
    print(c(msg, DIM))


def heading(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(msg, BOLD))


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
