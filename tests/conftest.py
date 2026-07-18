"""Shared fixtures for the boost test suite.

Every test runs against a throwaway $HOME so nothing can touch the real
environment. Functional tests drive the CLI IN-PROCESS via boost_cli.cli.main
so the command modules count toward coverage.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _reset_logging():
    """Rebind the diagnostic logger to each test's sandbox HOME."""
    from boost_cli.core import logs
    logs.reset()
    yield
    logs.reset()


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A fresh fake $HOME; returns its Path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("BOOST_HOME", raising=False)
    monkeypatch.delenv("BOOST_AGENTS_STORE", raising=False)
    monkeypatch.delenv("BOOST_DEBUG", raising=False)
    monkeypatch.delenv("BOOST_LOG_LEVEL", raising=False)
    monkeypatch.delenv("BOOST_NO_LOG", raising=False)
    monkeypatch.setenv("BOOST_NO_AI", "1")       # deterministic: no AI calls
    monkeypatch.setenv("NO_COLOR", "1")         # plain output for assertions
    monkeypatch.setenv("BOOST_ASSUME_YES", "1")  # never block on confirm()
    return home


class CliResult:
    def __init__(self, rc: int, out: str, err: str):
        self.rc, self.out, self.err = rc, out, err

    def __repr__(self):
        return "CliResult(rc=%r, out=%r, err=%r)" % (self.rc, self.out, self.err)


@pytest.fixture()
def boost(sandbox, capsys):
    """In-process CLI runner: boost('install', 'x') -> CliResult.

    Asserts the exit code (default 0); pass expect=None to skip the assert,
    or expect=<n> for error-path tests.
    """
    from boost_cli.cli import main

    def run(*argv, expect=0):
        argv = [str(a) for a in argv]
        try:
            rc = main(argv)
        except SystemExit as e:  # argparse --help / usage errors
            rc = e.code if isinstance(e.code, int) else 0
        cap = capsys.readouterr()
        res = CliResult(int(rc or 0), cap.out, cap.err)
        if expect is not None:
            assert res.rc == expect, (
                "boost %s -> rc=%d (want %d)\n--- stdout ---\n%s--- stderr ---\n%s"
                % (" ".join(argv), res.rc, expect, cap.out, cap.err))
        return res

    return run


@pytest.fixture(scope="session")
def fixture_tap_src(tmp_path_factory):
    """The sample-skill git repo, built once per session (read-only)."""
    dest = tmp_path_factory.mktemp("fixture") / "fixture-tap"
    subprocess.run(
        [sys.executable, str(ROOT / "tests" / "make_fixture.py"), str(dest)],
        check=True, capture_output=True)
    return dest


@pytest.fixture()
def tapped(boost, fixture_tap_src):
    """Sandbox with the fixture tap added. Returns the tap's source path."""
    boost("tap", fixture_tap_src)
    return fixture_tap_src


@pytest.fixture()
def installed(boost, tapped):
    """Sandbox with brainstorming installed. Returns the skill name."""
    boost("install", "brainstorming")
    return "brainstorming"
