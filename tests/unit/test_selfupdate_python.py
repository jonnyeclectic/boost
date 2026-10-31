# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost self-update --python VERSION` — rebuild the venv on another interpreter.

The reason it exists, measured 2026-10-28: Homebrew removed `python@3.14`, and
a pipx venv built on it kept a `bin/python` symlink into the deleted keg. The
same command is the way off 3.15, where the `[rag]` extra's onnxruntime has no
wheel. Each manager gets the argv its own help documents, and every install
boost did not build is refused rather than half-moved.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from boost_cli.core import selfupdate
from boost_cli.errors import BoostError

DIST = selfupdate.DIST
#: How both probes must call `subprocess.run`: captured, as text, decoded
#: leniently — the answer is parsed, and a stray byte must not raise.
_TEXT_KW = {"capture_output": True, "text": True, "encoding": "utf-8",
            "errors": "replace"}


@pytest.fixture
def on_path(monkeypatch, tmp_path):
    """Both managers on PATH, a pipx new enough for `always`, no uv receipt.

    ``sys.prefix`` points at an empty directory so the real interpreter's own
    receipt (a uv-tool runner) cannot pick the uv branch's shape.
    """
    monkeypatch.setattr(selfupdate.shutil, "which", lambda t: "/opt/bin/" + t)
    monkeypatch.setattr(selfupdate, "pipx_version", lambda *a, **k: (1, 18))
    monkeypatch.setattr(selfupdate.sys, "prefix", str(tmp_path))


def _receipt(prefix, body: str):
    (prefix / "uv-receipt.toml").write_text(body, encoding="utf-8")


class TestReinstallCommand:
    def test_pipx_reinstalls_on_its_own_download_of_the_version(self, on_path):
        # `always`, not `missing`: a Homebrew Mac has `python3.13` on PATH,
        # and `missing` binds the venv to it.
        assert selfupdate.reinstall_command(selfupdate.PIPX, "3.13") == [
            "/opt/bin/pipx", "reinstall", "--python", "3.13",
            "--fetch-python=always", DIST]

    @pytest.mark.parametrize("version", [(1, 17), None])
    def test_an_older_or_unreadable_pipx_gets_the_alias(
            self, on_path, monkeypatch, version):
        seen = []

        def probe(pipx, *a, **k):
            seen.append(pipx)
            return version
        monkeypatch.setattr(selfupdate, "pipx_version", probe)
        assert selfupdate.reinstall_command(selfupdate.PIPX, "3.13") == [
            "/opt/bin/pipx", "reinstall", "--python", "3.13",
            "--fetch-missing-python", DIST]
        assert seen == ["/opt/bin/pipx"]

    def test_pipx_given_a_path_fetches_nothing(self, on_path):
        assert selfupdate.reinstall_command(
            selfupdate.PIPX, "/usr/bin/python3.13") == [
            "/opt/bin/pipx", "reinstall", "--python", "/usr/bin/python3.13",
            DIST]

    def test_uv_reinstalls_the_receipts_requirement_on_its_own_python(
            self, on_path, tmp_path):
        # Install, not upgrade: only install rewrites the receipt's `python`.
        _receipt(tmp_path, '[tool]\nrequirements = [{ name = "%s", extras = '
                           '["rag"], specifier = ">=1.2" }]\npython = "3.15"\n'
                           % DIST)
        assert selfupdate.reinstall_command(selfupdate.UV_TOOL, "3.13.9") == [
            "/opt/bin/uv", "tool", "install", "--force", "--managed-python",
            "--python", "3.13.9", DIST + "[rag]>=1.2"]

    def test_uv_without_a_replayable_receipt_upgrades_in_place(self, on_path):
        assert selfupdate.reinstall_command(selfupdate.UV_TOOL, "3.13.9") == [
            "/opt/bin/uv", "tool", "upgrade", "--reinstall",
            "--managed-python", "--python", "3.13.9", DIST]

    def test_uv_given_a_name_is_not_forced_onto_a_managed_one(
            self, on_path, tmp_path):
        # `--managed-python` would refuse the interpreter it was pointed at.
        assert selfupdate.reinstall_command(
            selfupdate.UV_TOOL, "python3.13") == [
            "/opt/bin/uv", "tool", "upgrade", "--reinstall", "--python",
            "python3.13", DIST]
        _receipt(tmp_path, '[tool]\nrequirements = [{ name = "%s" }]\n' % DIST)
        assert selfupdate.reinstall_command(
            selfupdate.UV_TOOL, "python3.13") == [
            "/opt/bin/uv", "tool", "install", "--force", "--python",
            "python3.13", DIST]

    def test_surrounding_space_is_dropped(self, on_path):
        cmd = selfupdate.reinstall_command(selfupdate.PIPX, " 3.13 ")
        assert cmd[3] == "3.13" and "--fetch-python=always" in cmd

    @pytest.mark.parametrize("bad", ["", "   ", "-3.13", "--force"])
    def test_a_value_the_manager_would_read_as_a_flag_is_refused(
            self, on_path, bad):
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.PIPX, bad)
        assert err.value.message == (
            "--python needs a Python version or an interpreter path")
        assert err.value.hint == "e.g. `boost self-update --python 3.13`"

    def test_a_missing_manager_names_the_whole_manual_command(
            self, monkeypatch, tmp_path):
        # The manual command is the argv boost would have run, flags and all:
        # without them it lands on Homebrew's 3.13 again.
        monkeypatch.setattr(selfupdate.shutil, "which", lambda t: None)
        monkeypatch.setattr(selfupdate.sys, "prefix", str(tmp_path))

        def no_probe(*a, **k):
            raise AssertionError("no pipx to ask")
        monkeypatch.setattr(selfupdate, "pipx_version", no_probe)
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.PIPX, "3.13")
        assert err.value.message == (
            "boost was installed with pipx, but pipx is not on PATH")
        assert err.value.hint == (
            "install pipx, or upgrade manually with `pipx reinstall --python "
            "3.13 --fetch-python=always %s`" % DIST)
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.UV_TOOL, "3.13")
        assert err.value.hint == (
            "install uv, or upgrade manually with `uv tool upgrade --reinstall "
            "--managed-python --python 3.13 %s`" % DIST)
        # A requirement read off the receipt is quoted: pasted bare, `[rag]`
        # is a zsh glob and `>=1.2` a redirect.
        _receipt(tmp_path, '[tool]\nrequirements = [{ name = "%s", extras = '
                           '["rag"], specifier = ">=1.2" }]\n' % DIST)
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.UV_TOOL, "3.13")
        assert err.value.hint == (
            "install uv, or upgrade manually with `uv tool install --force "
            "--managed-python --python 3.13 '%s[rag]>=1.2'`" % DIST)

    @pytest.mark.parametrize("method, named", [
        (selfupdate.PIP, "pip"),
        (selfupdate.UV_PIP, "uv pip"),
        (selfupdate.UNKNOWN, "a method boost cannot identify"),
    ])
    def test_a_venv_boost_did_not_make_is_refused(self, on_path, method,
                                                  named):
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(method, "3.12")
        assert err.value.message == (
            "--python rebuilds a pipx or uv tool install, and this boost was "
            "installed with %s" % named)
        assert err.value.hint == (
            'pipx can own the interpreter for you: `pipx install --python '
            '3.12 --fetch-python=always "%s[rag]"`' % DIST)

    def test_a_refusal_given_a_path_names_the_recommended_version(
            self, on_path):
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.PIP, "/x/python")
        assert "`pipx install --python 3.13 " in err.value.hint

    def test_a_checkout_is_told_to_rebuild_its_own_venv(self, on_path):
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.GIT, "3.12")
        assert "installed with a git checkout" in err.value.message
        assert err.value.hint == (
            "recreate the checkout's venv on that interpreter: `python3.12 -m "
            "venv --clear .venv && .venv/bin/pip install -e '.[rag]'`")
        with pytest.raises(BoostError) as err:
            selfupdate.reinstall_command(selfupdate.GIT, "/x/python")
        assert "`python3.13 -m venv --clear .venv && " in err.value.hint


class TestObservedPython:
    def _run(self, monkeypatch, *, rc=0, stdout="", exc=None):
        seen = []

        def run(cmd, **kw):
            seen.append((cmd, kw))
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, rc, stdout, "")
        monkeypatch.setattr(selfupdate.subprocess, "run", run)
        return seen

    def test_asks_a_fresh_process_at_this_interpreter(self, monkeypatch):
        seen = self._run(monkeypatch, stdout="3.13.9\n/x/cpython-3.13.9\n")
        assert selfupdate.observed_python() == ("3.13.9", "/x/cpython-3.13.9")
        cmd, kw = seen[0]
        assert cmd[:3] == [sys.executable, "-I", "-c"]
        assert kw["timeout"] == 30.0
        # Text, decoded leniently: a non-UTF-8 prefix must not raise here.
        assert {k: kw.get(k) for k in _TEXT_KW} == _TEXT_KW
        selfupdate.observed_python(timeout=4.0)
        assert seen[1][1]["timeout"] == 4.0

    def test_a_failed_process_reports_nothing(self, monkeypatch):
        self._run(monkeypatch, rc=1, stdout="3.13.9\n/x\n")
        assert selfupdate.observed_python() is None

    @pytest.mark.parametrize("stdout", ["bad interpreter\n/x\n", "3.13.9\n",
                                        "3.13.9\n/x\nmore\n"])
    def test_output_that_is_not_a_version_and_prefix_reports_nothing(
            self, monkeypatch, stdout):
        self._run(monkeypatch, stdout=stdout)
        assert selfupdate.observed_python() is None

    @pytest.mark.parametrize("exc", [OSError("gone"),
                                     subprocess.TimeoutExpired("py", 30)])
    def test_a_process_that_cannot_run_reports_nothing(self, monkeypatch, exc):
        self._run(monkeypatch, exc=exc)
        assert selfupdate.observed_python() is None

    def test_the_real_interpreter_answers_with_its_own_version(self):
        assert selfupdate.observed_python() == (
            "%d.%d.%d" % sys.version_info[:3], sys.base_prefix)


class TestPipxVersion:
    def _run(self, monkeypatch, *, rc=0, stdout="", exc=None):
        seen = []

        def run(cmd, **kw):
            seen.append((cmd, kw))
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, rc, stdout, "")
        monkeypatch.setattr(selfupdate.subprocess, "run", run)
        return seen

    def test_reads_major_and_minor(self, monkeypatch):
        seen = self._run(monkeypatch, stdout="1.18.5\n")
        assert selfupdate.pipx_version("/opt/bin/pipx") == (1, 18)
        assert seen[0][0] == ["/opt/bin/pipx", "--version"]
        assert seen[0][1]["timeout"] == 10.0
        assert {k: seen[0][1].get(k) for k in _TEXT_KW} == _TEXT_KW

    @pytest.mark.parametrize("rc, stdout", [(1, "1.18.5"), (0, "pipx\n"),
                                            (0, "")])
    def test_an_unreadable_answer_is_none(self, monkeypatch, rc, stdout):
        self._run(monkeypatch, rc=rc, stdout=stdout)
        assert selfupdate.pipx_version("pipx") is None

    def test_a_pipx_that_cannot_run_is_none(self, monkeypatch):
        self._run(monkeypatch, exc=OSError("gone"))
        assert selfupdate.pipx_version("pipx") is None

    @pytest.mark.parametrize("version, flag", [
        ((1, 18), "--fetch-python=always"), ((2, 0), "--fetch-python=always"),
        ((1, 17), "--fetch-missing-python"), (None, "--fetch-missing-python")])
    def test_the_flag_follows_the_version(self, version, flag):
        assert selfupdate.pipx_fetch_flag(version) == flag


class TestUvRequirement:
    @pytest.mark.parametrize("body, want", [
        ('requirements = [{ name = "boost-skill-cli" }]', DIST),
        ('requirements = [{ name = "Boost_Skill_CLI", extras = ["rag", "x"] }]',
         DIST + "[rag,x]"),
        ('requirements = [{ name = "boost-skill-cli", specifier = "==1.0" }]\n'
         'python = "3.15"\nentrypoints = []', DIST + "==1.0"),
    ])
    def test_a_plain_index_requirement_is_replayed(self, tmp_path, body, want):
        _receipt(tmp_path, "[tool]\n" + body + "\n")
        assert selfupdate.uv_requirement(tmp_path) == want

    @pytest.mark.parametrize("body", [
        'requirements = [{ name = "boost-skill-cli", directory = "/src" }]',
        'requirements = [{ name = "other" }]',
        'requirements = [{ name = "boost-skill-cli" }, { name = "x" }]',
        'requirements = []',
        'requirements = ["boost-skill-cli"]',
        'requirements = "boost-skill-cli"',
        'requirements = [{ name = "boost-skill-cli" }]\n'
        'constraints = [{ name = "x" }]',
        'python = "3.15"',
    ])
    def test_anything_install_would_drop_is_not(self, tmp_path, body):
        _receipt(tmp_path, "[tool]\n" + body + "\n")
        assert selfupdate.uv_requirement(tmp_path) is None

    @pytest.mark.parametrize("body", ["", "not = [toml", "tool = 1\n"])
    def test_a_missing_or_broken_receipt_is_none(self, tmp_path, body):
        if body:
            _receipt(tmp_path, body)
        assert selfupdate.uv_requirement(tmp_path) is None

    def test_the_default_is_this_interpreters_prefix(self, tmp_path,
                                                     monkeypatch):
        _receipt(tmp_path, '[tool]\nrequirements = [{ name = "%s" }]\n' % DIST)
        monkeypatch.setattr(selfupdate.sys, "prefix", str(tmp_path))
        assert selfupdate.uv_requirement() == DIST


class TestHomebrewPython:
    @pytest.mark.parametrize("prefix", [
        "/opt/homebrew/opt/python@3.13/Frameworks/Python.framework/"
        "Versions/3.13",
        "/usr/local/opt/python@3.13/Frameworks/Python.framework",
        "/opt/homebrew/Cellar/python@3.13/3.13.18/Frameworks",
        "/home/linuxbrew/.linuxbrew/opt/python@3.13"])
    def test_a_formula_is_homebrews(self, prefix):
        assert selfupdate.homebrew_python(prefix)

    @pytest.mark.parametrize("prefix", [
        "/Users/u/Library/Application Support/pipx/py/cpython-3.13.18",
        "/Users/u/.local/share/uv/python/cpython-3.13.18-macos-aarch64-none",
        "/usr"])
    def test_a_managers_own_build_is_not(self, prefix):
        assert not selfupdate.homebrew_python(prefix)


def test_a_reinstall_gets_longer_than_an_upgrade():
    # It may download an interpreter and every dependency into an empty venv.
    assert selfupdate.REINSTALL_TIMEOUT == 900.0


class TestMoveCommand:
    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.UV_PIP,
                                        selfupdate.UNKNOWN])
    def test_others_get_a_pipx_install_on_its_own_python(self, method):
        assert selfupdate.move_command(method, "3.13") == (
            'pipx install --python 3.13 --fetch-python=always "%s[rag]"'
            % DIST)

    def test_a_checkout_rebuilds_its_venv(self):
        assert selfupdate.move_command(selfupdate.GIT, "/x/py") == (
            "python3.13 -m venv --clear .venv && .venv/bin/pip install -e "
            "'.[rag]'")
