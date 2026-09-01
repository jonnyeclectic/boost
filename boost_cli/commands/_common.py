# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Helpers shared across the split quality/health command modules.

These were private helpers inside ``quality.py`` when it held every check
command; lifting the two that both ``quality`` and ``safety`` need into one
place lets the modules split without either importing back into the other.
"""
from __future__ import annotations

from ..core import lockfile, store
from ..errors import BoostError


def _s(n: int) -> str:
    """Plural suffix: "" for one, "s" otherwise."""
    return "" if n == 1 else "s"


def _require_lock_integrity() -> None:
    """Fail loudly, before iterating, if the lock file itself is broken.

    `lockfile.read()` collapses a missing/corrupt/wrong-schema lock into an
    empty skeleton so ordinary reads degrade cleanly — but that means
    `cmd_verify`/`cmd_drift` would iterate zero entries and report "nothing
    installed" for exactly the state they exist to catch: a store with real
    skills in it and no record of them. A missing lock over an empty store is
    a fresh install, not a fault, so only that combination passes silently;
    corrupt or wrong-schema is always reported, store empty or not, matching
    `boost doctor`'s wording so the two commands never disagree.
    """
    integ = lockfile.check()
    if integ.ok:
        return
    if integ.problem == "missing":
        if not store.has_content():
            return
        raise BoostError(
            "lock file missing — the store has skills but nothing is recorded",
            hint="run `boost sync`")
    if integ.problem == "corrupt":
        raise BoostError("lock file is corrupt — restore with `boost replay`")
    raise BoostError(
        "lock file schema is v%s, expected v%d" % (integ.version, lockfile.SCHEMA_VERSION),
        hint="restore with `boost replay`")


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
