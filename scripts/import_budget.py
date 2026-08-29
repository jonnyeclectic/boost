#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Startup import-time budget — the lazy-import guard.

For a CLI, cold-start latency *is* the UX: every command pays it before it does
anything. This gate runs ``python -X importtime`` for a set of common, fully
offline commands and asserts that a denylist of heavy or optional-only modules
never gets imported at startup.

The classic regression it catches is the accidental *top-level* import of an
optional dependency — the ``[rag]`` stack (``sqlite_vec``), an embedding/AI SDK,
or a scientific-python tree — that a hot path only ever needs lazily. boost is
architected so those load inside the one function that needs them (e.g.
``search --dense``); this gate keeps it that way.

Deliberately name-based, not timing-based: a denylisted module is either
imported or it isn't, identically on a fast laptop and a slow, differently
CPU-throttled CI runner across every Python version — so the gate is
deterministic and never flakes. A coarse module-count ceiling is reported as an
advisory only (stdlib import graphs differ across Python versions), never a hard
failure.

Usage:
    python scripts/import_budget.py           # exit 1 if anything leaked
    python scripts/import_budget.py --list     # also print each command's count
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Common commands that must stay lean. All are fully offline and touch the core
# dispatch + store/catalog paths, so a leak anywhere in that surface is caught.
COMMANDS: list[list[str]] = [["--help"], ["--version"], ["list"], ["count"]]

# Modules that must NEVER load for the commands above. Heavy C extensions,
# scientific-python, and the embedding/AI SDKs — plus boost's own optional-only
# engines, which stay lazy behind `search --dense`. A leak means a hot path grew
# a top-level import of an optional dependency.
DENYLIST: set[str] = {
    # the [rag] extra's native dependency
    "sqlite_vec",
    # scientific-python / vector libs an embedding backend might drag in
    "numpy", "scipy", "pandas", "torch", "transformers",
    "sentence_transformers", "faiss",
    # embedding / LLM provider SDKs (boost talks to them over stdlib urllib,
    # so none of these should ever import at startup)
    "openai", "voyageai", "anthropic", "cohere",
    "langchain", "langchain_core", "langchain_community",
    "ragas", "ranx",
    # boost's own optional-only engines
    "boost_cli.core.dense", "boost_cli.core.embed",
}

# Advisory ceiling on total modules imported by a single command — reported, not
# enforced (import graphs legitimately differ across Python versions/platforms).
SOFT_MODULE_CEILING = 260


def parse_modules(importtime_stderr: str) -> set[str]:
    """Module names from ``python -X importtime`` stderr.

    Each line is ``import time: <self> | <cumulative> | <indent><module>``; the
    module name is the third ``|``-delimited field with its nesting indent
    stripped. The header line (``self [us] | cumulative | imported package``)
    has no numeric first field and is skipped.
    """
    modules: set[str] = set()
    for line in importtime_stderr.splitlines():
        if "import time:" not in line:
            continue
        _, _, rest = line.partition("import time:")
        parts = rest.split("|")
        if len(parts) != 3:
            continue
        if not parts[0].strip().isdigit():   # the header row
            continue
        name = parts[2].strip()
        if name:
            modules.add(name)
    return modules


def imported_modules(command: list[str]) -> set[str]:
    """The set of modules imported when running ``boost <command>``.

    Runs in a subprocess with a throwaway ``$HOME`` so a real ``~/.boost`` can
    never influence which modules load (or leave state behind), and with
    ``PYTHONPATH`` pointed at the repo so no editable install is required.
    """
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="boost-import-budget-") as home:
        env["HOME"] = home
        env["PYTHONPATH"] = str(ROOT)
        env["BOOST_NO_AI"] = "1"
        env.pop("BOOST_HOME", None)
        proc = subprocess.run(
            [sys.executable, "-X", "importtime", "-c",
             "from boost_cli.cli import main; main(%r)" % (command,)],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
        )
    return parse_modules(proc.stderr)


def leaks_for(modules: set[str]) -> list[str]:
    """Sorted denylisted modules present in ``modules`` (empty = clean)."""
    return sorted(DENYLIST & modules)


def check() -> dict[str, dict]:
    """Run every command; return ``{label: {"leaks": [...], "count": int}}``."""
    report: dict[str, dict] = {}
    for command in COMMANDS:
        mods = imported_modules(command)
        report["boost " + " ".join(command)] = {
            "leaks": leaks_for(mods),
            "count": len(mods),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    show_counts = "--list" in argv
    report = check()

    failed = False
    for label, data in report.items():
        if data["leaks"]:
            failed = True
            print("import-budget: FAIL %s imported %s"
                  % (label, ", ".join(data["leaks"])))
        if show_counts:
            print("  %-16s %d modules" % (label, data["count"]))
        if data["count"] > SOFT_MODULE_CEILING:
            print("import-budget: note — %s imported %d modules (advisory "
                  "ceiling %d); check for a new heavy dependency"
                  % (label, data["count"], SOFT_MODULE_CEILING))

    if failed:
        print("\nimport-budget: heavy/optional modules must stay lazy — move "
              "the import inside the function that needs it (see "
              "scripts/import_budget.py DENYLIST).")
        return 1
    print("import-budget: OK — no heavy/optional module imported by %d common "
          "commands" % len(COMMANDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
