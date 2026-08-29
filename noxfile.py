# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One command, every env: run boost's quality gate in isolated venvs.

`nox` runs the default gate (lint + tests); `nox -s <session>` runs one; and
the multi-version `tests` session fans out across the supported interpreters:

    nox                     # lint + tests across every installed interpreter
    nox -s lint             # ruff / mypy / import-linter / codespell + drift checks
    nox -s tests            # unit + functional on 3.12, 3.13, 3.14 (skips absent ones)
    nox -s "tests-3.12"     # just one interpreter
    nox -s smoke -s mutation

Each session installs the SAME tools and runs the SAME commands as `make` and
the CI jobs, so "green on my machine" and "green in CI" finally mean the same
thing — a contributor can reproduce the exact gate before pushing. nox itself
is the only thing to install first: `pipx install nox` (or `pip install nox`).
"""

import nox

# Match the CI matrix and the >=3.12 floor in pyproject.toml.
PYTHONS = ["3.12", "3.13", "3.14"]

# `nox` with no -s runs these; the rest are opt-in.
nox.options.sessions = ["lint", "tests"]
# Reuse venvs between runs for speed; a contributor rarely wants a cold rebuild.
nox.options.reuse_existing_virtualenvs = True
# Local machines rarely have all of 3.12/3.13/3.14 — skip the missing ones
# instead of erroring, so `nox` is useful with a single interpreter too.
nox.options.error_on_missing_interpreters = False


@nox.session
def lint(session: nox.Session) -> None:
    """Every linter and generated-file drift check `make lint` and CI run."""
    # The same hash-pinned set CI's lint job installs, so this session can't
    # drift from the real gate the way a hand-listed set did.
    session.install("-r", "requirements/lint-tools.txt")
    session.install("uv")  # lock_toolchain.py's resolver
    session.install("-e", ".")
    session.run("ruff", "check", "boost_cli", "tests")
    session.run("mypy")
    session.run("pyright")
    session.run("lint-imports")
    session.run("vulture", "boost_cli", "--min-confidence", "80")
    session.run("xenon", "--max-absolute", "F", "--max-modules", "E",
                "--max-average", "B", "boost_cli")
    session.run("interrogate", "boost_cli/core")
    session.run("refurb", "boost_cli")
    session.run("codespell", "boost_cli", "docs", "README.md")
    session.run("python", "scripts/build_registries.py", "--check")
    session.run("python", "scripts/build_roadmap.py", "--check")
    session.run("python", "scripts/build_command_reference.py", "--check")
    session.run("python", "scripts/lock_toolchain.py", "--check")
    session.run("python", "scripts/import_budget.py")


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    """Unit + functional suites with the 80% line-coverage gate."""
    session.install("-r", "requirements/test-tools.txt")
    session.install("-e", ".")
    session.run(
        "pytest", "tests/unit", "tests/functional",
        "--cov=boost_cli", "--cov-report=term-missing", "-q",
    )


@nox.session
def smoke(session: nox.Session) -> None:
    """The shell-level smoke suite through the real ./boost shim."""
    session.install("-e", ".")
    session.run("bash", "tests/smoke.sh", external=True)


@nox.session
def mutation(session: nox.Session) -> None:
    """Mutation testing over boost_cli/core with the 80% kill gate."""
    session.install("-r", "requirements/mutation-tools.txt")
    session.install("-e", ".")
    session.run("python", "scripts/mutation_gate.py", "--run", "--min", "80")
