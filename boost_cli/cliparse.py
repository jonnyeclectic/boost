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


class BoostArgumentParser(argparse.ArgumentParser):
    def error(self, message: str):
        """Print a branded error + dimmed usage, then exit 2 (argparse's code)."""
        out.err(message)
        sys.stderr.write(out.c(self.format_usage(), out.DIM))
        self.exit(2)


def parser(*args, **kwargs) -> BoostArgumentParser:
    """Drop-in replacement for ``argparse.ArgumentParser(...)``."""
    return BoostArgumentParser(*args, **kwargs)
