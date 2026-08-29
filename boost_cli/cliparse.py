# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A branded ArgumentParser.

Argparse's default failure output is a raw, unstyled ``usage:`` block with a
bare ``prog: error: …`` line — nothing like boost's branded top-level dispatch
(which routes through :func:`output.err` and offers a "did you mean"). This
subclass routes a parser's own errors through the same Aurora output layer, so
a wrong invocation looks as designed as a right one.

Adopt it via :func:`parser` in place of ``argparse.ArgumentParser``. Sub-parsers
created with ``add_subparsers()`` inherit this class automatically, so a single
top-level swap brands a command's whole tree.
"""
from __future__ import annotations

import argparse
import sys

from .core import output as out


class _BoostHelpFormatter(argparse.HelpFormatter):
    """Wraps help/description text the way :func:`output.wrap` does,
    keeping a backtick-quoted command atomic instead of splitting it across
    lines — the same rule every other long line in this CLI follows.

    argparse's own ``HelpFormatter`` wraps with plain ``textwrap``, which
    knows nothing about a backtick span (``doctor``/``search`` interpolate
    hints ending in a pasteable ``pip install '...'``-style command; several
    ``help=`` strings quote a ``boost`` invocation the same way) — so a
    narrow terminal could split one across two lines, handing the user a
    command that does not run. Only the two text-filling hooks are
    overridden; ``_format_usage``'s own line-splitting already treats a
    metavar as one atomic part and is left alone.
    """

    def _split_lines(self, text: str, width: int) -> list[str]:
        text = self._whitespace_matcher.sub(" ", text).strip()
        return out.wrap(text, width) or [text]

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        text = self._whitespace_matcher.sub(" ", text).strip()
        lines = out.wrap(text, max(width - len(indent), 1)) or [text]
        return "\n".join(indent + ln for ln in lines)


class BoostArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        # add_subparsers() creates each sub-parser via type(self)(**kwargs)
        # without forwarding formatter_class, so defaulting it here (rather
        # than in parser() below) is what brands every subcommand's --help
        # too, not just the top-level one.
        kwargs.setdefault("formatter_class", _BoostHelpFormatter)
        super().__init__(*args, **kwargs)

    def error(self, message: str):
        """Print a branded error + dimmed usage, then exit 2 (argparse's code)."""
        out.err(message)
        sys.stderr.write(out.c(self.format_usage(), out.DIM))
        self.exit(2)


def parser(*args, **kwargs) -> BoostArgumentParser:
    """Drop-in replacement for ``argparse.ArgumentParser(...)``."""
    return BoostArgumentParser(*args, **kwargs)
