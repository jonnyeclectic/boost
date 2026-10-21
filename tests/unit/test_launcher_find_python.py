# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which interpreter the `./boost` checkout launcher picks, and how it runs it.

Two first-run failures, both in the shim rather than in boost_cli:

* It tried only `python3` and `python`. `brew install python@3.13` and
  `apt install python3.13` — README's own remedy for a too-old Python — link
  only `python3.13`, so with the system 3.9 `python3` first on PATH the shim
  said "Python 3.12+ is required but was not found" with a 3.13 right there.
* It ran `python -S`, so site-packages were invisible: `boost doctor`'s
  `[rag]` hint names `<this python> -m pip install -e ...`, and the extra it
  installs could never be imported through `./boost`.

Each test runs the real shim on a PATH holding only stubs it controls, so a
system interpreter can't make it pass by accident.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "boost"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX shell stubs on a stub-only PATH")


def _bin(tmp_path: Path) -> Path:
    """A PATH directory holding the shim's own tools and nothing else."""
    d = tmp_path / "bin"
    d.mkdir()
    for tool in ("dirname", "readlink"):
        found = shutil.which(tool)
        assert found, tool
        (d / tool).symlink_to(found)
    return d


def _stub(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    p.chmod(0o755)
    return p


def _recording_python(d: Path, name: str, log: Path) -> None:
    """``name`` runs this test's interpreter, logging each call's first arg."""
    _stub(d, name, 'printf "%%s\\n" "$1" >> "%s"\nexec "%s" "$@"'
          % (log, sys.executable))


def _run(d: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PATH"] = str(d)
    return subprocess.run([shutil.which("bash") or "/bin/bash", str(LAUNCHER),
                           *args], env=env, cwd=str(ROOT), capture_output=True,
                          text=True, timeout=120)


class TestFindPython:
    def test_versioned_name_wins_over_a_too_old_python3(self, sandbox,
                                                         tmp_path):
        d = _bin(tmp_path)
        _stub(d, "python3", "exit 1")         # the system 3.9: fails the probe
        log = tmp_path / "argv.log"
        _recording_python(d, "python3.12", log)
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("boost ")
        assert "is required" not in r.stderr

    def test_python3_that_passes_wins_over_versioned_names(self, sandbox,
                                                            tmp_path):
        """An activated venv shadows `python3`, not `python3.14`: a versioned
        name tried first would skip the venv the `[rag]` extra went into."""
        d = _bin(tmp_path)
        logs = {}
        for name in ("python3", "python3.15", "python3.14", "python3.13",
                     "python3.12", "python"):
            logs[name] = tmp_path / ("%s.log" % name)
            _recording_python(d, name, logs[name])
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        assert logs["python3"].is_file()
        assert not any(logs[n].exists() for n in logs if n != "python3")

    def test_versioned_names_are_tried_newest_first(self, sandbox, tmp_path):
        d = _bin(tmp_path)
        _stub(d, "python3", "exit 1")
        logs = {}
        for name in ("python3.15", "python3.14", "python3.13", "python3.12"):
            logs[name] = tmp_path / ("%s.log" % name)
            _recording_python(d, name, logs[name])
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        assert logs["python3.15"].is_file()
        assert not any(logs[n].exists()
                       for n in ("python3.14", "python3.13", "python3.12"))

    def test_each_too_old_candidate_is_skipped_in_order(self, sandbox,
                                                        tmp_path):
        d = _bin(tmp_path)
        seen = tmp_path / "seen.log"
        order = ["python3", "python3.15", "python3.14", "python3.13",
                 "python3.12"]
        for name in order:
            _stub(d, name, 'echo %s >> "%s"; exit 1' % (name, seen))
        _recording_python(d, "python", tmp_path / "python.log")
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        assert seen.read_text(encoding="utf-8").split() == order
        assert (tmp_path / "python.log").is_file()

    def test_none_found_hint_matches_readme(self, sandbox, tmp_path):
        d = _bin(tmp_path)
        _stub(d, "python3", "exit 1")
        r = _run(d, "--version")
        assert r.returncode == 1
        assert r.stdout == ""
        assert r.stderr == (
            "boost: Python 3.12+ is required but was not found on PATH\n"
            "  hint: brew install python@3.13 (or: sudo apt install python3.13)\n")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "brew install python@3.13" in readme
        assert "sudo apt install python3.13" in readme


class TestSitePackagesVisible:
    def test_shim_runs_python_without_dash_s(self, sandbox, tmp_path):
        d = _bin(tmp_path)
        log = tmp_path / "argv.log"
        _recording_python(d, "python3.14", log)
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        # The version probe, then the launch: both lead with -c. Under the
        # old shim the launch line was "-S".
        assert log.read_text(encoding="utf-8").splitlines() == ["-c", "-c"]

    def test_site_runs_so_installed_extras_are_importable(self, sandbox,
                                                           tmp_path):
        """`site` is what puts a venv's site-packages (where the `[rag]` hint
        installs) on sys.path; -S skips it. `sitecustomize` is imported by
        `site` alone, so it marks whether `site` ran."""
        hook = tmp_path / "hook"
        hook.mkdir()
        marker = tmp_path / "site-ran"
        (hook / "sitecustomize.py").write_text(
            "open(%r, 'w').close()\n" % str(marker), encoding="utf-8")
        d = _bin(tmp_path)
        _stub(d, "python3.14", 'PYTHONPATH="%s" exec "%s" "$@"'
              % (hook, sys.executable))
        r = _run(d, "--version")
        assert r.returncode == 0, r.stderr
        assert marker.is_file()
