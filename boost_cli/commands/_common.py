"""Helpers shared across the split quality/health command modules.

These were private helpers inside ``quality.py`` when it held every check
command; lifting the two that both ``quality`` and ``safety`` need into one
place lets the modules split without either importing back into the other.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from ..core import lockfile
from ..errors import BoostError


def _s(n: int) -> str:
    """Plural suffix: "" for one, "s" otherwise."""
    return "" if n == 1 else "s"


def _iter_installed(names: Optional[List[str]] = None) -> List[Tuple[str, dict]]:
    """[(name, lock_entry)] — all installed, or the given names (validated)."""
    skills = lockfile.installed()
    if names:
        missing = [n for n in names if n not in skills]
        if missing:
            raise BoostError("not installed: %s" % ", ".join(missing),
                            hint="see what is with `boost list`")
        return [(n, skills[n]) for n in names]
    return sorted(skills.items())
