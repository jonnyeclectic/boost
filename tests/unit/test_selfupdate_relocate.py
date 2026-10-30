# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""When boost offers to move a pipx or uv install to the recommended Python.

A plain `pipx install 'boost-skill-cli[rag]'` on Homebrew's 3.15 installs the
store and no model: onnxruntime has no cp315 wheel, and a wheel cannot run code
at install time. `boost self-update` and `boost quickstart` are the first
commands that can do something about it, and `selfupdate.relocation_reason` is
what decides whether they should. These tests pin each of its four conditions,
the argv the move runs, and the re-exec plumbing quickstart uses afterwards.

`tests/conftest.py` lifts the ONNX ceiling for every test; the fixtures here put
it back where a test needs this interpreter to count as too new.
"""
from __future__ import annotations

import importlib.util
import sys

import pytest

from boost_cli.core import embed, localembed, selfupdate

_real_find_spec = importlib.util.find_spec


def _specs(monkeypatch, *, onnx: bool, vec: bool) -> list[str]:
    """Answer `find_spec` for onnxruntime and sqlite_vec; record every ask."""
    asked: list[str] = []

    def find_spec(name, *a, **k):
        asked.append(name)
        if name == "onnxruntime":
            return object() if onnx else None
        if name == "sqlite_vec":
            return object() if vec else None
        return _real_find_spec(name, *a, **k)
    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    return asked


@pytest.fixture
def stranded(monkeypatch):
    """The state the move is for: past the ceiling, [rag] asked for, no key,
    installed with pipx."""
    monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING", (3, 0))
    _specs(monkeypatch, onnx=False, vec=True)
    for env in embed.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(selfupdate, "detect", lambda *a, **k: selfupdate.PIPX)


class TestRelocationReason:
    @pytest.mark.parametrize("method", [selfupdate.PIPX, selfupdate.UV_TOOL])
    def test_a_stranded_managed_install_has_a_reason(self, stranded, method):
        reason = selfupdate.relocation_reason(method)
        assert reason == ("Python %d.%d has no onnxruntime wheel, so the [rag] "
                          "extra's local model cannot run here"
                          % sys.version_info[:2])

    def test_the_method_defaults_to_detect(self, stranded):
        assert selfupdate.relocation_reason() is not None

    @pytest.mark.parametrize("method", [selfupdate.PIP, selfupdate.UV_PIP,
                                        selfupdate.GIT, selfupdate.UNKNOWN])
    def test_a_venv_boost_did_not_build_is_never_moved(self, stranded, method):
        assert selfupdate.relocation_reason(method) is None

    def test_detect_answering_pip_is_never_moved(self, stranded, monkeypatch):
        monkeypatch.setattr(selfupdate, "detect",
                            lambda *a, **k: selfupdate.PIP)
        assert selfupdate.relocation_reason() is None

    @pytest.mark.parametrize("env", ["VOYAGE_API_KEY", "OPENAI_API_KEY"])
    def test_a_key_needs_no_local_model(self, stranded, monkeypatch, env):
        monkeypatch.setenv(env, "k")
        assert selfupdate.relocation_reason(selfupdate.PIPX) is None

    def test_an_empty_key_is_no_key(self, stranded, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "")
        assert selfupdate.relocation_reason(selfupdate.PIPX) is not None

    def test_without_the_extra_there_is_nothing_to_rescue(self, stranded,
                                                         monkeypatch):
        _specs(monkeypatch, onnx=False, vec=False)
        assert selfupdate.relocation_reason(selfupdate.PIPX) is None

    @pytest.mark.parametrize("err", [ImportError, ValueError])
    def test_an_unreadable_spec_reads_as_no_extra(self, stranded, monkeypatch,
                                                  err):
        def find_spec(name, *a, **k):
            if name == "onnxruntime":
                return None
            raise err(name)
        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        assert selfupdate.relocation_reason(selfupdate.PIPX) is None

    def test_onnxruntime_present_past_the_ceiling_stays(self, stranded,
                                                        monkeypatch):
        # Built from source, or the first release with cp315 wheels.
        _specs(monkeypatch, onnx=True, vec=True)
        assert selfupdate.relocation_reason(selfupdate.PIPX) is None

    def test_below_the_ceiling_nothing_moves(self, stranded, monkeypatch):
        monkeypatch.setattr(localembed, "ONNX_WHEEL_CEILING", (99, 0))
        assert selfupdate.relocation_reason(selfupdate.PIPX) is None

    def test_it_never_opens_the_store_or_spawns(self, stranded, monkeypatch):
        from boost_cli.core import dense

        def forbidden(*a, **k):
            raise AssertionError("relocation_reason must stay cheap")
        monkeypatch.setattr(dense, "status", forbidden)
        monkeypatch.setattr(selfupdate.subprocess, "run", forbidden)
        assert selfupdate.relocation_reason() is not None

    def test_a_working_homebrew_python_is_not_a_reason(self, monkeypatch):
        # Homebrew's 3.13 with onnxruntime installed: a warning elsewhere,
        # never a move.
        _specs(monkeypatch, onnx=True, vec=True)
        monkeypatch.setattr(selfupdate, "detect",
                            lambda *a, **k: selfupdate.PIPX)
        assert selfupdate.relocation_reason() is None


class TestAnyKey:
    def test_no_key(self, monkeypatch):
        for env in embed.KEY_ENV.values():
            monkeypatch.delenv(env, raising=False)
        assert embed.any_key() is False

    @pytest.mark.parametrize("env", ["VOYAGE_API_KEY", "OPENAI_API_KEY"])
    def test_either_key(self, monkeypatch, env):
        for other in embed.KEY_ENV.values():
            monkeypatch.delenv(other, raising=False)
        monkeypatch.setenv(env, "k")
        assert embed.any_key() is True

    def test_the_kill_switch_does_not_hide_a_key(self, monkeypatch):
        # Narrower than `available`: a key still means "no local model needed".
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        assert embed.any_key() is True


class TestRelocationCommand:
    def test_pipx_reinstalls_on_the_recommended_python(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        monkeypatch.setattr(selfupdate, "pipx_version", lambda *a, **k: (1, 18))
        assert selfupdate.relocation_command(selfupdate.PIPX) == [
            "/opt/bin/pipx", "reinstall", "--python",
            localembed.RECOMMENDED_PYTHON, "--fetch-python=always",
            selfupdate.DIST]

    def test_uv_reinstalls_from_its_receipt(self, monkeypatch, tmp_path):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        monkeypatch.setattr(selfupdate.sys, "prefix", str(tmp_path))
        (tmp_path / "uv-receipt.toml").write_text(
            '[tool]\nrequirements = [{ name = "boost-skill-cli", '
            'extras = ["rag"] }]\n', encoding="utf-8")
        assert selfupdate.relocation_command(selfupdate.UV_TOOL) == [
            "/opt/bin/uv", "tool", "install", "--force", "--managed-python",
            "--python", "3.13", "boost-skill-cli[rag]"]


class TestFetchFlagHere:
    def test_no_pipx_gets_the_flag_a_new_pipx_takes(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which", lambda t: None)
        assert selfupdate.fetch_flag_here() == selfupdate.FETCH_ALWAYS

    @pytest.mark.parametrize("version,flag", [
        ((1, 18), selfupdate.FETCH_ALWAYS),
        ((1, 17), selfupdate.FETCH_MISSING),
        (None, selfupdate.FETCH_MISSING),
    ])
    def test_the_pipx_on_path_is_asked(self, monkeypatch, version, flag):
        asked = []
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)

        def probe(pipx, *a, **k):
            asked.append(pipx)
            return version
        monkeypatch.setattr(selfupdate, "pipx_version", probe)
        assert selfupdate.fetch_flag_here() == flag
        assert asked == ["/opt/bin/pipx"]

    def test_move_command_never_asks_pipx(self, monkeypatch):
        # It renders in the search hint, one fresh process per search.
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)

        def no_probe(*a, **k):
            raise AssertionError("pipx --version on the search hint")
        monkeypatch.setattr(selfupdate, "pipx_version", no_probe)
        assert selfupdate.move_command(selfupdate.PIP, "3.13") == (
            'pipx install --python 3.13 --fetch-python=always '
            '"boost-skill-cli[rag]"')


class TestRelocationOffer:
    def test_pipx_is_named_as_typed(self):
        assert selfupdate.relocation_offer(selfupdate.PIPX, "why") == (
            "why. boost can move itself to a Python 3.13 that pipx downloads "
            "and manages, and update in the same step")

    def test_uv_tool_is_named_uv(self):
        said = selfupdate.relocation_offer(selfupdate.UV_TOOL, "why")
        assert "that uv downloads" in said
        assert "uv-tool" not in said


class TestRelocated:
    @pytest.mark.parametrize("value,want", [
        ("1", True), ("", False), ("0", False)])
    def test_reads_the_guard(self, monkeypatch, value, want):
        monkeypatch.setenv(selfupdate.RELOCATED_ENV, value)
        assert selfupdate.relocated() is want

    def test_unset_is_not_relocated(self, monkeypatch):
        monkeypatch.delenv(selfupdate.RELOCATED_ENV, raising=False)
        assert selfupdate.relocated() is False

    def test_the_guard_name(self):
        assert selfupdate.RELOCATED_ENV == "BOOST_RELOCATED"


class TestReexecArgv:
    def test_runs_this_interpreter_not_the_boost_on_path(self, monkeypatch,
                                                         tmp_path):
        py = tmp_path / "python"
        py.write_text("", encoding="utf-8")
        monkeypatch.setattr(selfupdate.sys, "executable", str(py))
        assert selfupdate.reexec_argv(["quickstart", "--catalog"]) == [
            str(py), "-P", "-m", "boost_cli", "quickstart", "--catalog"]

    def test_a_venv_that_did_not_come_back_is_none(self, monkeypatch,
                                                   tmp_path):
        monkeypatch.setattr(selfupdate.sys, "executable",
                            str(tmp_path / "gone"))
        assert selfupdate.reexec_argv(["quickstart"]) is None


class TestPythonReport:
    def test_unobserved_names_no_python(self):
        assert selfupdate.python_report(selfupdate.PIPX, None) == (
            "reinstalled via pipx; run `boost --version` to confirm", None)

    def test_a_managed_python_is_reported_without_a_warning(self):
        ok, warn = selfupdate.python_report(
            selfupdate.UV_TOOL, ("3.13.9", "/x/uv/python/cpython-3.13.9"))
        assert ok == ("boost now runs on Python 3.13.9; `boost doctor` "
                      "checks semantic search")
        assert warn is None

    def test_a_homebrew_python_is_called_out(self):
        brew = "/opt/homebrew/opt/python@3.13/Frameworks/Python.framework"
        ok, warn = selfupdate.python_report(selfupdate.PIPX,
                                            ("3.13.18", brew))
        assert "Python 3.13.18" in ok
        assert warn == (
            "that Python is Homebrew's (%s), which the next `brew upgrade` "
            "past it deletes — upgrade pipx to 1.18 or later and re-run with "
            "a version, so boost fetches its own" % brew)
