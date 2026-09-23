#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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

Exit codes are three, not two, because "no denylisted module was imported" is
an assertion about a name being *absent* — the one shape that a run which never
happened satisfies perfectly. 0 is measured and clean, 1 is measured and
leaking, and 2 is *not measured*: a command exited non-zero, or produced a
module set that cannot be a boost startup. A gate that cannot measure must say
so rather than report the absence it would have reported anyway.

Usage:
    python scripts/import_budget.py           # 0 clean / 1 leak / 2 unmeasurable
    python scripts/import_budget.py --list     # also print each command's count
"""
from __future__ import annotations

import os
import shlex
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

# Every command in COMMANDS goes through `boost_cli.cli`, so a measurement that
# does not contain it did not measure boost starting up — whatever it measured,
# the absence of a denylisted module in it says nothing about boost.
ENTRY_MODULE = "boost_cli.cli"

# The measured command's argv. `raise SystemExit(main(...))` and not a bare
# `main(...)`: boost's `main` RETURNS its exit code (an unknown command returns
# 2 and raises nothing), so discarding it made a command that never dispatched
# look like a command that started up cleanly.
SNIPPET = "from boost_cli.cli import main; raise SystemExit(main(%r))"

# How many non-importtime stderr lines a failure report keeps.
STDERR_TAIL_LINES = 12


class MeasurementError(RuntimeError):
    """A measurement this gate must not draw a conclusion from.

    Raised rather than returned, because every caller's natural handling of an
    empty module set is to report no leaks. The failure mode this exists to
    prevent is silent: the gate keeps printing OK while measuring less and less
    of the surface it was written to watch.
    """


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


def diagnostic_stderr(importtime_stderr: str,
                      limit: int = STDERR_TAIL_LINES) -> str:
    """The last ``limit`` stderr lines that are not ``-X importtime`` rows.

    A failing run emits its traceback *interleaved with* a few hundred import
    rows, and the rows are the part nobody needs when the question is why it
    died. The tail and not the head, because a traceback ends with the line
    that names the error.
    """
    lines = [ln for ln in importtime_stderr.splitlines()
             if "import time:" not in ln and ln.strip()]
    if not lines:
        return "(no stderr beyond the import-time rows)"
    return "\n".join(lines[-limit:])


def imported_modules(command: list[str]) -> set[str]:
    """The set of modules imported when running ``boost <command>``.

    Runs in a subprocess with a throwaway ``$HOME`` so a real ``~/.boost`` can
    never influence which modules load (or leave state behind), and with
    ``PYTHONPATH`` pointed at the repo so no editable install is required.

    Raises ``MeasurementError`` when the run cannot be trusted — a non-zero
    exit, or a module set that does not contain ``ENTRY_MODULE``. Both are
    *vacuous passes* otherwise: `python -X importtime` writes ~74 stdlib rows
    before it can fail, so a subprocess that died importing nothing of boost's
    still parses into a large, entirely denylist-free module set.
    """
    env = dict(os.environ)
    argv = [sys.executable, "-X", "importtime", "-c", SNIPPET % (command,)]
    with tempfile.TemporaryDirectory(prefix="boost-import-budget-") as home:
        env["HOME"] = home
        env["PYTHONPATH"] = str(ROOT)
        env["BOOST_NO_AI"] = "1"
        env.pop("BOOST_HOME", None)
        proc = subprocess.run(
            argv, cwd=str(ROOT), env=env, capture_output=True, text=True,
        )
    if proc.returncode != 0:
        raise MeasurementError(
            "exited %d — nothing was measured, so no denylisted module was "
            "going to be found.\n    command: %s\n    stderr:\n%s"
            % (proc.returncode, shlex.join(argv),
               _indent(diagnostic_stderr(proc.stderr))))
    modules = parse_modules(proc.stderr)
    if ENTRY_MODULE not in modules:
        raise MeasurementError(
            "exited 0 but its %d imported modules do not include %s — whatever "
            "ran, it was not boost starting up.\n    command: %s\n    stderr:\n%s"
            % (len(modules), ENTRY_MODULE, shlex.join(argv),
               _indent(diagnostic_stderr(proc.stderr))))
    return modules


def _indent(text: str, prefix: str = "      ") -> str:
    return "\n".join(prefix + ln for ln in text.splitlines())


def leaks_for(modules: set[str]) -> list[str]:
    """Sorted denylisted modules present in ``modules`` (empty = clean)."""
    return sorted(DENYLIST & modules)


def check() -> dict[str, dict]:
    """Run every command; return ``{label: {"leaks": [...], "count": int}}``.

    A command that could not be measured gets an ``"error"`` key instead of a
    trustworthy count, and the remaining commands are still attempted: the
    realistic harm this gate guards against is *partial* darkness — one command
    stops being measured and the other three keep printing OK — so the report
    has to say how much of the surface went dark, not just that some of it did.
    """
    report: dict[str, dict] = {}
    for command in COMMANDS:
        label = "boost " + " ".join(command)
        try:
            mods = imported_modules(command)
        except MeasurementError as exc:
            report[label] = {"leaks": [], "count": 0, "error": str(exc)}
            continue
        report[label] = {"leaks": leaks_for(mods), "count": len(mods)}
    return report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    show_counts = "--list" in argv
    report = check()

    failed = False
    unmeasured = 0
    for label, data in report.items():
        if data.get("error"):
            unmeasured += 1
            print("import-budget: UNMEASURED %s %s" % (label, data["error"]))
            continue
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
    # Reported after any leak, and takes precedence over it: a leak found is a
    # true finding either way, but a command that never ran means this gate no
    # longer knows what it is asserting, and that is the more urgent repair.
    if unmeasured:
        print("\nimport-budget: %d of %d commands could not be measured. This "
              "gate asserts a module is ABSENT, which is exactly what a run "
              "that never happened reports — so it proves nothing until the "
              "command above runs again."
              % (unmeasured, len(report)))
        return 2
    if failed:
        return 1
    print("import-budget: OK — no heavy/optional module imported by %d common "
          "commands" % len(COMMANDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
