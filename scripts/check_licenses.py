#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Fail when a resolved dependency's licence is incompatible with GPL-3.0.

`pip-audit` gates known CVEs; nothing gated licence *terms*. boost's shipped
runtime is stdlib-only, so the exposure is entirely in the opt-in extras —
`[eval]` alone resolves to 94 packages, including the pinned langchain stack —
and none of them had ever been checked against the project's own GPL-3.0.

Reads ``pip-licenses --format=json`` (stdin, or a path) rather than shelling out,
so the check is a pure function of its input and can be unit-tested without a
resolved environment.

Why not ``pip-licenses --fail-on``: it compares the declared licence string
exactly, and that string is not a well-formed identifier. Real values observed
in boost's own `[eval]` closure:

    ragas      -> "UNKNOWN"                     (no licence metadata at all)
    tiktoken   -> "MIT License\\n\\nCopyright (c) 2022 OpenAI, …"  (the whole text)
    sqlite-vec -> "MIT License, Apache License, Version 2.0"       (two, comma-joined)

so matching is done here by regex over the whole field instead.

Usage:
    pip-licenses --format=json | python3 scripts/check_licenses.py
    python3 scripts/check_licenses.py licenses.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# (pattern, why). Matched case-insensitively against the whole declared licence
# string. Deliberately short: the aim is high-confidence incompatibility, not a
# taxonomy. LGPL, MPL and EPL are all fine to *consume* from a GPL-3.0 project
# and are not listed.
DENIED: tuple[tuple[str, str], ...] = (
    (r"affero|\bagpl\b",
     "AGPL adds network-use copyleft that GPL-3.0 does not carry"),
    # GPLv2-*only* cannot be combined with GPL-3.0. "v2 or later" / "GPLv2+"
    # can (it permits taking v3), so both spellings are excluded explicitly.
    (r"gplv2(?!\+)|gpl-2\.0(?!-or-later)|general public license v2 \(",
     "GPLv2-only is incompatible with GPL-3.0"),
    (r"proprietary|all rights reserved|\bsspl\b|commons clause|\bbusl\b",
     "not an open-source licence"),
)

# Packages whose *metadata* omits a licence even though the project has one.
# Each needs the upstream licence named, so the exception is auditable rather
# than a silence. Anything undeclared and unlisted fails.
UNDECLARED_OK = {
    # https://github.com/explodinggradients/ragas — Apache-2.0 in the repo;
    # the published wheel carries no License field or classifier.
    "ragas": "Apache-2.0 upstream; wheel metadata omits it",
    # https://github.com/milesgranger/pyrus-cramjam — MIT in the repo. This one
    # is a regression, not a package that never declared: 2.11.0 published
    # `License: MIT`, 2.12.0 dropped the field, and the 2.12.1 wheel carries
    # `License-File: LICENSE` with no `License:` and no `License-Expression:`.
    # So there is nothing for a metadata reader to resolve — pip-licenses is
    # right, and this is not the checker missing PEP 639. Reached through
    # ranx -> fastparquet -> cramjam, so "drop the dependency" would mean
    # dropping the [eval] extra.
    "cramjam": "MIT upstream; wheel metadata omits it",
}

_UNDECLARED = re.compile(r"^\s*(unknown|none|)\s*$", re.IGNORECASE)


def is_undeclared(licence: str) -> bool:
    """True when the package declared no licence at all."""
    return bool(_UNDECLARED.match(licence or ""))


def violations(rows: list[dict]) -> list[str]:
    """Human-readable problems in a ``pip-licenses --format=json`` payload."""
    problems = []
    for row in rows:
        name = str(row.get("Name", "?"))
        licence = str(row.get("License", ""))
        if is_undeclared(licence):
            if name.lower() not in UNDECLARED_OK:
                problems.append(
                    "%s declares no licence — add it to UNDECLARED_OK with the "
                    "upstream licence, or drop the dependency" % name)
            continue
        for pattern, why in DENIED:
            if re.search(pattern, licence, re.IGNORECASE):
                problems.append("%s: %s (%s)" % (
                    name, why, licence.splitlines()[0][:60]))
                break
    return problems


def main(argv: list[str]) -> int:
    raw = (Path(argv[0]).read_text(encoding="utf-8") if argv
           else sys.stdin.read())
    try:
        rows = json.loads(raw)
    except ValueError as e:
        print("::error::could not parse pip-licenses JSON: %s" % e)
        return 2
    if not isinstance(rows, list) or not rows:
        # An empty scan is not a pass: it means the environment was never
        # populated, which is how a licence gate quietly stops gating.
        print("::error::no packages in the licence report — nothing was scanned")
        return 2

    problems = violations(rows)
    for p in problems:
        print("::error::%s" % p)
    print("checked %d package(s): %d problem(s)" % (len(rows), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
