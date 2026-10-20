# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure logic behind ``boost cohort apply``'s reporting and ``--skills`` parsing.

Kept out of ``commands/team.py`` so the counting/exit-code decision that
audit-cohort-findings found broken is covered by the mutation gate — it
targets ``boost_cli/core``, not ``boost_cli/commands``.
"""
from __future__ import annotations

from pathlib import Path

from . import jsonstate


def parse_skills(values: list[str]) -> list[str]:
    """Merge one or more ``--skills`` flag values into one skill-name list.

    Each value may itself be a comma list, so ``--skills a,b --skills c`` and
    ``--skills a --skills b --skills c`` both produce ``["a", "b", "c"]``.
    Without this, argparse's plain default (one string, last flag wins) makes
    a repeated ``--skills`` silently discard every earlier occurrence instead
    of appending to it.
    """
    return [s.strip() for v in values for s in v.split(",") if s.strip()]


def apply_summary(installed: int, present: int, missing: int) -> str:
    """The one-line summary ``cohort apply`` prints after a rollout pass.

    ``missing`` (a cohort member not found in any tap) is reported alongside
    the other two counts rather than silently dropped — a cohort whose only
    member is missing used to report "0 installed, 0 already present" with
    the member accounted for nowhere. Suppressed when zero so an unaffected
    rollout keeps the original two-clause wording.
    """
    bits = ["%d installed" % installed, "%d already present" % present]
    if missing:
        bits.append("%d not found" % missing)
    return "applied: " + ", ".join(bits)


def apply_exit_code(installed: int, present: int, missing: int) -> int:
    """1 when a rollout pass found missing members and did nothing else.

    ``apply`` used to return 0 unconditionally, even when every member of
    the only cohort applied was missing from every tap — a rollout that
    silently did nothing looked identical to a clean, uneventful pass.
    """
    return 1 if missing and not installed and not present else 0


def shape_error(cohorts: dict) -> str | None:
    """Why a parsed ``cohorts.json`` can't be walked, or ``None`` if it can.

    Every action indexes ``spec["percent"]`` and iterates ``spec["skills"]``,
    so a cohort that is not an object, or that lacks either field in the
    right type, crashed ``list``/``status``/``apply`` with a TypeError (exit
    70). ``bool`` is refused as a percent even though it is an ``int``: a
    ``true`` rollout is a hand-edit, not a 1% one.
    """
    for name, spec in cohorts.items():
        if not isinstance(spec, dict):
            return "cohort %r is a %s, not an object" % (
                name, type(spec).__name__)
        skills = spec.get("skills")
        if not isinstance(skills, list) or not all(
                isinstance(s, str) for s in skills):
            return "cohort %r has no list of skill names" % name
        percent = spec.get("percent")
        if isinstance(percent, bool) or not isinstance(percent, int):
            return "cohort %r has no integer percent" % name
    return None


def load(path: Path) -> tuple[dict, str | None]:
    """``(cohorts, None)``, or ``({}, message)`` when ``path`` is unusable.

    A missing file is ``({}, None)`` — no cohorts yet. Anything else that is
    not a well-formed cohort map is an error naming the file, so a reader can
    refuse cleanly and a writer can quarantine rather than overwrite.
    """
    data, err = jsonstate.read_object(path)
    if err is not None:
        return {}, err
    if data is None:
        return {}, None
    bad = shape_error(data)
    if bad is not None:
        return {}, "%s: %s" % (path, bad)
    return data, None
