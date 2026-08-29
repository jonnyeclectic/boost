#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Stamp the copyright + SPDX header onto every source file, idempotently.

Why per-file, when LICENSE is right there at the root: a file that travels out
of this repository -- vendored, pasted into an issue, mirrored by one of the
hundreds of registries boost taps -- carries its own licence with it, so a
reader never has to guess which project it came from or what they may do with
it. OpenSSF Best Practices gold asks for exactly this (``copyright_per_file``,
``license_per_file``).

The expression is ``Apache-2.0``. boost moved off GPL-3.0 deliberately: the
copyleft protected nothing where boost is actually used -- running the CLI is
not distribution and an installed skill is not a derivative work -- while
costing everything on ``boost_langchain``, which exists to be imported into
other people's applications and whose licence therefore decided theirs. Every
comparable tool is permissive (pip, poetry, uv, pipx, ruff, mypy are MIT;
Homebrew, which boost names itself after, is BSD-2-Clause). Apache-2.0 adds an
explicit patent grant on top of that.

Changing it again is one edit: set ``SPDX_ID`` below and re-run. The sweep
*migrates* a header carrying a different expression rather than only adding a
missing one, so the constant stays the single source of truth.

Usage::

    python3 scripts/add_spdx_headers.py            # write
    python3 scripts/add_spdx_headers.py --check    # report, change nothing
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COPYRIGHT = "Copyright the boost contributors."
SPDX_ID = "Apache-2.0"
SPDX_LINE = f"SPDX-License-Identifier: {SPDX_ID}"
HEADER = f"# {COPYRIGHT}\n# {SPDX_LINE}\n"

# Trees walked for sources -- every tree `make lint` lints, plus the tests.
# `docs/` holds no code; `.venv`, `build/` and `mutants/` are not tracked.
TREES = ("boost_cli", "boost_langchain", "evals", "scripts", "tests")

# Source files that sit at the repository root rather than in a tree.
ROOT_FILES = ("boost", "noxfile.py")

# `_version.py` is written by setuptools-scm at build time and gitignored, so a
# header committed to it would not survive a rebuild.
EXCLUDE = frozenset({"boost_cli/_version.py"})


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_files() -> list[Path]:
    """Every file the header must cover, in a stable order."""
    found: list[Path] = []
    for tree in TREES:
        for path in sorted((ROOT / tree).rglob("*")):
            if path.suffix not in (".py", ".sh") or not path.is_file():
                continue
            if relative(path) in EXCLUDE:
                continue
            found.append(path)
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            found.append(path)
    return found


_SPDX_ANY = re.compile(r"^(\s*#\s*)SPDX-License-Identifier:\s*(\S+)\s*$", re.M)


def needs_header(text: str) -> bool:
    head = "\n".join(text.splitlines()[:10])
    return COPYRIGHT not in head or SPDX_LINE not in head


def stale_expression(text: str) -> str | None:
    """The wrong SPDX id already in the header, if there is one.

    A file that carries `SPDX-License-Identifier: <something else>` must be
    rewritten, not stamped a second time -- otherwise a relicence would leave
    every file declaring two licences at once, which is worse than declaring
    none.
    """
    head = "\n".join(text.splitlines()[:10])
    found = _SPDX_ANY.search(head)
    if found and found.group(2) != SPDX_ID:
        return found.group(2)
    return None


def stamp(text: str) -> str:
    """Insert the header, keeping any shebang on line 1.

    A ``#!`` line that stops being the first byte of the file stops being a
    shebang, and the kernel refuses to run the script. Everything else takes
    the header at the very top, above the module docstring.
    """
    stale = stale_expression(text)
    if stale is not None:
        return _SPDX_ANY.sub(lambda m: f"{m.group(1)}{SPDX_LINE}", text, count=1)
    if text.startswith("#!"):
        shebang, _, rest = text.partition("\n")
        return f"{shebang}\n{HEADER}{rest}"
    return HEADER + text


def main(argv: list[str]) -> int:
    check = "--check" in argv
    changed = [p for p in source_files()
               if needs_header(p.read_text(encoding="utf-8"))
               or stale_expression(p.read_text(encoding="utf-8")) is not None]
    if not check:
        for path in changed:
            path.write_text(stamp(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{'would stamp' if check else 'stamped'} {len(changed)} file(s)")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
