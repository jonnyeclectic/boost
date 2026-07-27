"""Unit tests: boost_cli/core/selfupdate.py — install-method detection.

Getting this wrong is worse than the bug it replaces: pointing pip at a pipx
install, or telling a user to upgrade a distribution no package manager has a
record of, both report success while changing nothing. So every branch is
pinned, including the ones that must refuse.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from boost_cli.core import selfupdate
from boost_cli.errors import BoostError


def _no_metadata():
    return None


def _metadata():
    return "1.2.3"


class TestDetect:
    def test_git_checkout_wins(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert selfupdate.detect(root=tmp_path) == selfupdate.GIT

    def test_editable_install_still_reads_as_git(self, tmp_path):
        # `pip install -e .` leaves package metadata behind too, but the user
        # means `git pull`, not a PyPI reinstall that would blow away their
        # working tree.
        (tmp_path / ".git").mkdir()
        prefix = tmp_path / "venv"
        prefix.mkdir()
        (prefix / "pipx_metadata.json").write_text("{}", encoding="utf-8")
        assert selfupdate.detect(root=tmp_path, prefix=prefix,
                                 metadata_version=_metadata) == selfupdate.GIT

    def test_pipx_marker(self, tmp_path):
        prefix = tmp_path / "venvs" / "boost-skill-cli"
        prefix.mkdir(parents=True)
        (prefix / "pipx_metadata.json").write_text("{}", encoding="utf-8")
        assert selfupdate.detect(root=tmp_path, prefix=prefix,
                                 metadata_version=_metadata) == selfupdate.PIPX

    def test_uv_tool_marker(self, tmp_path):
        prefix = tmp_path / "tools" / "boost-skill-cli"
        prefix.mkdir(parents=True)
        (prefix / "uv-receipt.toml").write_text("", encoding="utf-8")
        assert selfupdate.detect(root=tmp_path, prefix=prefix,
                                 metadata_version=_metadata) == selfupdate.UV_TOOL

    def test_plain_pip_when_metadata_exists(self, tmp_path):
        assert selfupdate.detect(root=tmp_path, prefix=tmp_path,
                                 metadata_version=_metadata) == selfupdate.PIP

    def test_unknown_when_nothing_has_a_record(self, tmp_path):
        # No .git, no venv receipt, and no installed metadata: nothing can
        # upgrade this copy, and saying "pip" would send the user chasing a
        # package pip never installed.
        assert selfupdate.detect(root=tmp_path, prefix=tmp_path,
                                 metadata_version=_no_metadata) == selfupdate.UNKNOWN

    def test_a_directory_named_like_the_marker_is_not_a_marker(self, tmp_path):
        (tmp_path / "pipx_metadata.json").mkdir()
        assert selfupdate.detect(root=tmp_path, prefix=tmp_path,
                                 metadata_version=_metadata) == selfupdate.PIP

    def test_defaults_read_the_live_process(self, monkeypatch, tmp_path):
        monkeypatch.setattr("boost_cli.core.paths.repo_root", lambda: tmp_path)
        monkeypatch.setattr(sys, "prefix", str(tmp_path))
        assert selfupdate.detect(metadata_version=_metadata) == selfupdate.PIP

    def test_the_metadata_lookup_is_resolved_at_call_time(self, monkeypatch,
                                                          tmp_path):
        # Binding it as a default argument freezes it at import, so swapping
        # the module attribute does nothing — which is how a test meant to
        # exercise the "nothing installed this" branch instead detected PIP and
        # ran a real `pip install` against PyPI.
        monkeypatch.setattr("boost_cli.core.paths.repo_root", lambda: tmp_path)
        monkeypatch.setattr(sys, "prefix", str(tmp_path))
        monkeypatch.setattr(selfupdate, "installed_version", lambda: None)
        assert selfupdate.detect() == selfupdate.UNKNOWN


class TestUpgradeCommand:
    def test_pipx(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        assert selfupdate.upgrade_command(selfupdate.PIPX) == [
            "/opt/bin/pipx", "upgrade", "boost-skill-cli"]

    def test_uv_tool(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        assert selfupdate.upgrade_command(selfupdate.UV_TOOL) == [
            "/opt/bin/uv", "tool", "upgrade", "boost-skill-cli"]

    def test_pip_uses_this_interpreter_not_the_pip_on_path(self):
        # A bare `pip` can belong to a different interpreter, in which case the
        # upgrade succeeds loudly and changes nothing about this install.
        cmd = selfupdate.upgrade_command(selfupdate.PIP)
        assert cmd == [sys.executable, "-m", "pip", "install", "--upgrade",
                       "boost-skill-cli"]

    def test_missing_manager_refuses_rather_than_substituting(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which", lambda t: None)
        with pytest.raises(BoostError) as err:
            selfupdate.upgrade_command(selfupdate.PIPX)
        assert err.value.message == (
            "boost was installed with pipx, but pipx is not on PATH")
        assert err.value.hint == (
            "install pipx, or upgrade manually with `pipx upgrade boost-skill-cli`")

    def test_unknown_method_has_no_command(self):
        with pytest.raises(BoostError) as err:
            selfupdate.upgrade_command(selfupdate.UNKNOWN)
        assert err.value.message == (
            "cannot work out how boost was installed, so it cannot update itself")
        assert err.value.hint == (
            "upgrade with your package manager, e.g. `pipx upgrade boost-skill-cli`")


def _proc(rc=0, out="", err=""):
    return subprocess.CompletedProcess(["x"], rc, out, err)


class _Recorder:
    """subprocess.run stand-in that records argv *and* kwargs.

    Recording the kwargs is the point: a fake that swallows them lets
    `capture_output`, `text` and `timeout` be dropped without any test
    noticing, and boost then reads bytes it expects to be str.
    """

    def __init__(self, proc):
        self.proc, self.calls = proc, []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return self.proc


class TestRunUpgrade:
    def test_captures_text_output_under_a_timeout(self, monkeypatch):
        rec = _Recorder(_proc(0, out="done"))
        monkeypatch.setattr(selfupdate.subprocess, "run", rec)
        assert selfupdate.run_upgrade(["pipx", "upgrade", "x"]).stdout == "done"
        assert rec.calls == [(["pipx", "upgrade", "x"],
                              {"capture_output": True, "text": True,
                               "timeout": 300.0})]

    def test_caller_timeout_is_passed_through(self, monkeypatch):
        rec = _Recorder(_proc(0))
        monkeypatch.setattr(selfupdate.subprocess, "run", rec)
        selfupdate.run_upgrade(["pip"], timeout=12.5)
        assert rec.calls[0][1]["timeout"] == 12.5

    def test_failure_surfaces_the_managers_own_last_line(self, monkeypatch):
        # Three lines, so "the last one" is distinguishable from "the second".
        monkeypatch.setattr(
            selfupdate.subprocess, "run",
            lambda *a, **k: _proc(
                1, err="Traceback\n  File x\nERROR: No matching dist"))
        with pytest.raises(BoostError) as err:
            selfupdate.run_upgrade(["/usr/bin/pipx", "upgrade", "x"])
        assert err.value.message == "upgrade failed (pipx exited 1)"
        assert err.value.hint == "ERROR: No matching dist"

    def test_error_text_falls_back_to_stdout(self, monkeypatch):
        # pip writes its resolution failures to stdout, not stderr.
        monkeypatch.setattr(
            selfupdate.subprocess, "run",
            lambda *a, **k: _proc(1, out="Collecting\nERROR: from stdout\n"))
        with pytest.raises(BoostError) as err:
            selfupdate.run_upgrade(["/usr/bin/pip"])
        assert err.value.hint == "ERROR: from stdout"

    def test_failure_with_no_output_still_explains_itself(self, monkeypatch):
        monkeypatch.setattr(selfupdate.subprocess, "run",
                            lambda *a, **k: _proc(2))
        with pytest.raises(BoostError) as err:
            selfupdate.run_upgrade(["/usr/bin/pip"])
        assert err.value.message == "upgrade failed (pip exited 2)"
        assert err.value.hint == "re-run the command by hand to see why"

    def test_a_missing_binary_is_a_boost_error_not_a_traceback(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("No such file or directory")
        monkeypatch.setattr(selfupdate.subprocess, "run", boom)
        with pytest.raises(BoostError) as err:
            selfupdate.run_upgrade(["nope", "upgrade"])
        assert err.value.message == "could not run nope upgrade"
        assert err.value.hint == "No such file or directory"

    def test_a_timeout_is_a_boost_error(self, monkeypatch):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(["pip"], 1)
        monkeypatch.setattr(selfupdate.subprocess, "run", boom)
        with pytest.raises(BoostError) as err:
            selfupdate.run_upgrade(["pip"], timeout=1)
        assert err.value.message == "could not run pip"


class TestObservedVersion:
    def test_parses_the_version_line(self, monkeypatch):
        monkeypatch.setattr(selfupdate.subprocess, "run",
                            lambda *a, **k: _proc(0, out="boost 9.9.9\n"))
        assert selfupdate.observed_version() == "9.9.9"

    def test_none_when_the_probe_fails(self, monkeypatch):
        monkeypatch.setattr(selfupdate.subprocess, "run",
                            lambda *a, **k: _proc(1, out="boost 9.9.9\n"))
        assert selfupdate.observed_version() is None

    def test_none_when_the_output_is_not_a_version_line(self, monkeypatch):
        # Better to report nothing than to invent a version we never saw.
        monkeypatch.setattr(selfupdate.subprocess, "run",
                            lambda *a, **k: _proc(0, out="command not found"))
        assert selfupdate.observed_version() is None

    def test_none_when_the_launcher_cannot_be_run(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("nope")
        monkeypatch.setattr(selfupdate.subprocess, "run", boom)
        assert selfupdate.observed_version() is None

    def test_asks_the_launcher_on_path_for_captured_text(self, monkeypatch,
                                                         tmp_path):
        rec = _Recorder(_proc(0, out="boost 1.0\n"))
        monkeypatch.setattr("boost_cli.core.paths.launcher",
                            lambda: tmp_path / "boost")
        monkeypatch.setattr(selfupdate.subprocess, "run", rec)
        assert selfupdate.observed_version() == "1.0"
        assert rec.calls == [([str(tmp_path / "boost"), "--version"],
                              {"capture_output": True, "text": True,
                               "timeout": 30.0})]

    def test_caller_timeout_is_passed_through(self, monkeypatch):
        rec = _Recorder(_proc(0, out="boost 1.0\n"))
        monkeypatch.setattr(selfupdate.subprocess, "run", rec)
        selfupdate.observed_version(timeout=3.0)
        assert rec.calls[0][1]["timeout"] == 3.0


class TestInstalledVersion:
    def test_asks_metadata_for_the_pypi_distribution_by_name(self, monkeypatch):
        import importlib.metadata as md
        seen = []
        monkeypatch.setattr(md, "version",
                            lambda name: seen.append(name) or "7.7.7")
        assert selfupdate.installed_version() == "7.7.7"
        assert seen == ["boost-skill-cli"]

    def test_none_when_no_manager_has_a_record(self, monkeypatch):
        import importlib.metadata as md

        def missing(name):
            raise md.PackageNotFoundError(name)
        monkeypatch.setattr(md, "version", missing)
        assert selfupdate.installed_version() is None
