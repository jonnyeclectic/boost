# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure decisions behind ``boost profile use``'s outcome and exit code.

Kept out of ``commands/team.py`` for the same reason as :mod:`cohort`: the
mutation gate targets ``boost_cli/core``, and these are the calls that went
wrong — a switch that skipped members printed "switched" with exit 0, after
setting aside every skill the user had.
"""
from __future__ import annotations


def _n(count: int, noun: str = "skill") -> str:
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


def use_exit_code(not_found: int, failed: int) -> int:
    """1 when any profile member was not found or failed to install.

    A version drift alone stays 0: the skill is there, just not at the
    recorded version, and ``use`` already warns about it.
    """
    return 1 if not_found or failed else 0


def sideline_allowed(resolved: int, not_found: int, failed: int) -> bool:
    """Whether ``use`` may set aside the skills the profile does not name.

    ``resolved`` counts profile members installed once the install pass is
    over. When members were skipped and not one of them is installed, the
    switch would trade the user's whole working setup for nothing — so the
    extras stay linked. An empty profile skips nothing and still switches.
    """
    return resolved > 0 or not (not_found or failed)


def use_summary(name: str, not_found: int, failed: int,
                changed: int) -> str | None:
    """The warning ``use`` ends on, or ``None`` when it may say "switched".

    "switched" claims the machine now is the profile; a member that was not
    found, failed to install, or sits at another version means it is not.
    """
    bits = []
    if not_found:
        bits.append("%s not found" % _n(not_found))
    if failed:
        bits.append("%s failed to install" % _n(failed))
    if changed:
        bits.append("%s differ%s from it" % (_n(changed),
                                             "s" if changed == 1 else ""))
    if not bits:
        return None
    return ("applied profile %s, but %s — compare with `boost profile diff %s`"
            % (name, ", ".join(bits), name))
