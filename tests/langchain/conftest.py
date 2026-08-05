"""Fixtures for the LangChain integration suite.

No mocks of boost internals: every test runs against a throwaway $HOME, taps a
real git fixture repo through ``registry.add``, indexes it with the real
catalog + BM25 pipeline, and only then exercises the LangChain surface. That
is the whole value of the suite — it proves the two packages actually meet,
which a mocked ``retrieve_any`` cannot.

The suite lives under tests/, so the root conftest already supplies
``sandbox`` and the logging reset. ``fixture_tap_src`` is deliberately
SHADOWED here: the stock fixture tap is skills-only, and the kind-filter
tests need all three item kinds, so this one appends a rule and a workflow
before committing. Content is distinctive on purpose — each kind's test
query must not accidentally rank a skill above it.

The test modules themselves guard their langchain imports with
``pytest.importorskip``, so a venv without the [langchain] extra skips the
suite visibly instead of erroring at collection.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

RULE_MD = """---
name: python-style
description: Pin the Python formatting conventions for generated code
---
Always run the formatter before committing. Prefer explicit imports and
keep line length at 88 characters.
"""

WORKFLOW_MD = """---
name: release-checklist
description: Walk the release checklist before tagging
---
# Release checklist

Verify the changelog, run the full gate, and tag the release.
"""


@pytest.fixture(scope="session")
def fixture_tap_src(tmp_path_factory):
    """The sample git tap with all three item kinds, built once per session."""
    dest = tmp_path_factory.mktemp("fixture") / "fixture-tap"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "make_fixture.py"), str(dest)],
        check=True, capture_output=True)
    (dest / "rules").mkdir()
    (dest / "rules" / "python-style.mdc").write_text(RULE_MD, encoding="utf-8")
    (dest / "commands").mkdir()
    (dest / "commands" / "release-checklist.md").write_text(
        WORKFLOW_MD, encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=dest, check=True, capture_output=True)
    run("git", "add", "-A")
    run("git", "commit", "-qm", "add rule + workflow fixtures")
    return dest


@pytest.fixture()
def indexed(sandbox, fixture_tap_src):
    """Sandbox with the fixture tap added, catalogued, and BM25-indexed."""
    from boost_cli.core import catalog, rag, registry
    tap = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(tap)
    assert rag.ensure(), "BM25 index failed to build over the fixture tap"
    return sandbox
