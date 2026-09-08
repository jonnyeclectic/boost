# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure logic behind ``boost cohort apply``'s reporting and ``--skills`` parsing.

Kept out of ``commands/team.py`` so the counting/exit-code decision that
audit-cohort-findings found broken is covered by the mutation gate — it
targets ``boost_cli/core``, not ``boost_cli/commands``.
"""
from __future__ import annotations


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
