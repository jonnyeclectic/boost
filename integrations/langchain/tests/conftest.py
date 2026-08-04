"""Fixtures for boost-langchain's end-to-end tests.

No mocks of boost internals: every test runs against a throwaway $HOME, taps a
real git fixture repo through ``registry.add``, indexes it with the real
catalog + BM25 pipeline, and only then exercises the LangChain surface. That
is the whole value of the suite — it proves the two packages actually meet,
which a mocked ``retrieve_any`` cannot.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# integrations/langchain/tests/conftest.py -> the boost repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# The stock fixture tap is skills-only; the kind-filter tests need all three
# item kinds, so the session fixture appends one rule and one workflow before
# committing. Content is distinctive on purpose — each kind's test query must
# not accidentally rank a skill above it.
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


@pytest.fixture(autouse=True)
def _reset_logging():
    """Rebind boost's diagnostic logger to each test's sandbox HOME."""
    from boost_cli.core import logs
    logs.reset()
    yield
    logs.reset()


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A fresh fake $HOME; returns its Path.

    Mirrors the main repo's sandbox fixture: boost resolves all state from
    $HOME/$BOOST_HOME at call time, so pointing HOME at a tempdir is the whole
    isolation story. BOOST_NO_AI and the deleted embed keys keep retrieval
    deterministic — BM25 only, no network, no confirm prompts.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in ("BOOST_HOME", "BOOST_AGENTS_STORE", "BOOST_DEBUG",
                "VOYAGE_API_KEY", "OPENAI_API_KEY", "BOOST_NO_EMBED"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BOOST_NO_AI", "1")
    monkeypatch.setenv("BOOST_ASSUME_YES", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    return home


def _load_make_fixture():
    """Import tests/make_fixture.py from the repo root, by path.

    It is not an installed module — importing by file location keeps this
    suite runnable from any venv without putting the repo's tests/ dir on
    sys.path (where its conftest would collide with this one).
    """
    src = REPO_ROOT / "tests" / "make_fixture.py"
    spec = importlib.util.spec_from_file_location("boost_tests_make_fixture", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def fixture_tap_src(tmp_path_factory):
    """The sample git tap, built once per session, with all three item kinds."""
    dest = tmp_path_factory.mktemp("fixture") / "fixture-tap"
    mod = _load_make_fixture()
    argv, sys.argv = sys.argv, ["make_fixture.py", str(dest)]
    try:
        mod.main()
    finally:
        sys.argv = argv
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
