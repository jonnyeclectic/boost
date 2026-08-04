"""Helpers shared across the split quality/health command modules.

These were private helpers inside ``quality.py`` when it held every check
command; lifting the two that both ``quality`` and ``safety`` need into one
place lets the modules split without either importing back into the other.
"""
from __future__ import annotations

from ..core import lockfile
from ..errors import BoostError


def _s(n: int) -> str:
    """Plural suffix: "" for one, "s" otherwise."""
    return "" if n == 1 else "s"


def _iter_installed(names: list[str] | None = None) -> list[tuple[str, dict]]:
    """[(name, lock_entry)] — all installed skills, or the given names.

    A named item that exists in another lock section is declined with the
    truth ("X is a rule — this command applies to skills") instead of the
    "not installed" every skill-only accessor used to answer — the user can
    see it in `boost list`, so denying it exists reads as data loss.
    """
    skills = lockfile.installed()
    if names:
        missing, other_kind = [], []
        for n in names:
            if n in skills:
                continue
            found = lockfile.find_any(n)
            if found is not None:
                other_kind.append((n, found[0]))
            else:
                missing.append(n)
        if other_kind:
            raise BoostError(
                "; ".join("%s is a %s — this command applies to skills"
                          % (n, kind) for n, kind in other_kind),
                hint="rules and workflows are governed by pin / quarantine / "
                     "verify / update")
        if missing:
            raise BoostError("not installed: %s" % ", ".join(missing),
                            hint="see what is with `boost list`")
        return [(n, skills[n]) for n in names]
    return sorted(skills.items())


def _shadowed_kinds(name: str, acted_kind: str) -> list[str]:
    """Other lock sections also holding ``name``.

    `find_any` resolves a bare name skill-first, which is right for reads but
    silently wrong for governance: acting on the skill while a same-named rule
    stays live in CLAUDE.md must at least be *said*. Callers warn with this.
    """
    return [k for k, section in lockfile.all_installed().items()
            if k != acted_kind and name in section]


def _iter_installed_all(
        names: list[str] | None = None) -> list[tuple[str, str, dict]]:
    """[(kind, name, lock_entry)] across every section, or the given names."""
    if names:
        out, missing = [], []
        for n in names:
            found = lockfile.find_any(n)
            if found is None:
                missing.append(n)
            else:
                out.append((found[0], n, found[1]))
        if missing:
            raise BoostError("not installed: %s" % ", ".join(missing),
                            hint="see what is with `boost list`")
        return out
    return [(kind, n, e)
            for kind, section in lockfile.all_installed().items()
            for n, e in sorted(section.items())]
