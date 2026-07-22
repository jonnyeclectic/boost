"""One command, every env: run boost's quality gate in isolated venvs.

`nox` runs the default gate (lint + tests); `nox -s <session>` runs one; and
the multi-version `tests` session fans out across the supported interpreters:

    nox                     # lint + tests across every installed interpreter
    nox -s lint             # ruff / mypy / import-linter / codespell + drift checks
    nox -s tests            # unit + functional on 3.9, 3.12, 3.14 (skips absent ones)
    nox -s "tests-3.12"     # just one interpreter
    nox -s smoke -s mutation

Each session installs the SAME tools and runs the SAME commands as `make` and
the CI jobs, so "green on my machine" and "green in CI" finally mean the same
thing — a contributor can reproduce the exact gate before pushing. nox itself
is the only thing to install first: `pipx install nox` (or `pip install nox`).
"""

import nox

# Match the CI matrix and the >=3.9 floor in pyproject.toml.
PYTHONS = ["3.9", "3.12", "3.14"]

# `nox` with no -s runs these; the rest are opt-in.
nox.options.sessions = ["lint", "tests"]
# Reuse venvs between runs for speed; a contributor rarely wants a cold rebuild.
nox.options.reuse_existing_virtualenvs = True
# Local machines rarely have all of 3.9/3.12/3.14 — skip the missing ones
# instead of erroring, so `nox` is useful with a single interpreter too.
nox.options.error_on_missing_interpreters = False


@nox.session
def lint(session: nox.Session) -> None:
    """ruff + mypy + import-linter + codespell + the generated-file drift checks."""
    session.install("ruff", "mypy", "codespell", "import-linter")
    session.install("-e", ".")
    session.run("ruff", "check", "boost_cli", "tests")
    session.run("mypy")
    session.run("lint-imports")
    session.run("codespell", "boost_cli", "docs", "README.md")
    session.run("python", "scripts/build_registries.py", "--check")
    session.run("python", "scripts/build_roadmap.py", "--check")
    session.run("python", "scripts/import_budget.py")


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    """Unit + functional suites with the 80% line-coverage gate."""
    session.install("pytest", "pytest-cov", "coverage", "hypothesis")
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
    session.install("mutmut", "pytest", "pytest-cov", "coverage", "hypothesis")
    session.install("-e", ".")
    session.run("python", "scripts/mutation_gate.py", "--run", "--min", "80")
