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
            "/opt/bin/pipx", "upgrade", "boost-skill-cli",
            "--pip-args=--no-cache-dir"]

    def test_uv_tool(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        assert selfupdate.upgrade_command(selfupdate.UV_TOOL) == [
            "/opt/bin/uv", "tool", "upgrade", "--refresh", "boost-skill-cli"]

    def test_pip_uses_this_interpreter_not_the_pip_on_path(self):
        # A bare `pip` can belong to a different interpreter, in which case the
        # upgrade succeeds loudly and changes nothing about this install.
        cmd = selfupdate.upgrade_command(selfupdate.PIP)
        assert cmd == [sys.executable, "-m", "pip", "install", "--no-cache-dir",
                       "--upgrade", "boost-skill-cli"]

    def test_every_manager_is_told_to_refresh_its_index(self, monkeypatch):
        # The bug this pins: PyPI serves the simple index with
        # `Cache-Control: max-age=600`, and pip honours it. A self-update run
        # inside ten minutes of an earlier one is answered from pip's HTTP
        # cache, so a release published in between is invisible and pip reports
        # "Requirement already satisfied". Observed on 1.0.422 -> 1.0.423:
        # three consecutive `pipx upgrade` runs all no-opped against a cached
        # index. Each manager gets its own idiom — pip has no index-only
        # refresh, uv does — so the assertion is per-manager, not one shape.
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        refresh = {selfupdate.PIPX: "--pip-args=--no-cache-dir",
                   selfupdate.UV_TOOL: "--refresh",
                   selfupdate.PIP: "--no-cache-dir"}
        for method, flag in refresh.items():
            assert flag in selfupdate.upgrade_command(method), method

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


class TestForceCommand:
    """The escape hatch offered when the manager exits 0 and changes nothing.

    It must pin an exact version and bypass the resolver, because the whole
    reason it is being suggested is that the resolver already declined to move.
    """

    def test_pipx(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        assert selfupdate.force_command(selfupdate.PIPX, "1.0.423") == [
            "/opt/bin/pipx", "install", "--force", "boost-skill-cli==1.0.423"]

    def test_uv_tool(self, monkeypatch):
        monkeypatch.setattr(selfupdate.shutil, "which",
                            lambda t: "/opt/bin/" + t)
        assert selfupdate.force_command(selfupdate.UV_TOOL, "1.0.423") == [
            "/opt/bin/uv", "tool", "install", "--force",
            "boost-skill-cli==1.0.423"]

    def test_pip(self):
        assert selfupdate.force_command(selfupdate.PIP, "1.0.423") == [
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "--force-reinstall", "boost-skill-cli==1.0.423"]

    def test_unknown_method_has_no_command(self):
        with pytest.raises(BoostError) as err:
            selfupdate.force_command(selfupdate.UNKNOWN, "1.0.423")
        assert err.value.message == (
            "cannot work out how boost was installed, so it cannot update itself")
        # The hint has to carry the version, or it is the same dead end as the
        # `upgrade` that already declined.
        assert err.value.hint == (
            "install the version by hand, e.g. "
            "`pipx install --force boost-skill-cli==1.0.423`")


class TestIsBehind:
    """`is_behind` decides whether boost is allowed to say "already up to date".

    Every uncertain case must be False. A false "you are behind" turns a
    perfectly good upgrade into an alarm, and there is no version string worth
    that.
    """

    def test_a_later_patch_is_newer(self):
        assert selfupdate.is_behind("1.0.422", "1.0.423") is True

    def test_the_same_version_is_not_behind(self):
        assert selfupdate.is_behind("1.0.423", "1.0.423") is False

    def test_an_older_pypi_is_not_behind(self):
        assert selfupdate.is_behind("1.0.423", "1.0.422") is False

    def test_numeric_not_lexicographic(self):
        # "1.0.9" > "1.0.10" as strings, which is how a version check that
        # compares text ships an upgrade prompt that never goes away.
        assert selfupdate.is_behind("1.0.9", "1.0.10") is True
        assert selfupdate.is_behind("1.0.10", "1.0.9") is False

    def test_a_shorter_release_is_behind_a_longer_one(self):
        assert selfupdate.is_behind("1.0", "1.0.1") is True

    def test_a_setuptools_scm_dev_build_is_ahead_of_the_release(self):
        # A git checkout reports `1.0.424.dev3+g36b74ba`; PyPI's newest release
        # is 1.0.423. That install is ahead, not behind.
        assert selfupdate.is_behind("1.0.424.dev3+g36b74ba", "1.0.423") is False

    def test_a_dev_build_behind_pypi_still_reads_as_behind(self):
        assert selfupdate.is_behind("1.0.420.dev1+gabc", "1.0.423") is True

    def test_a_leading_v_is_tolerated(self):
        assert selfupdate.is_behind("v1.0.422", "v1.0.423") is True

    def test_an_unknown_latest_is_never_behind(self):
        # None means "PyPI did not tell us", which must not become a claim in
        # either direction.
        assert selfupdate.is_behind("1.0.422", None) is False

    def test_an_unknown_installed_is_never_behind(self):
        assert selfupdate.is_behind(None, "1.0.423") is False

    def test_an_unparseable_version_is_never_behind(self):
        assert selfupdate.is_behind("nightly", "1.0.423") is False
        assert selfupdate.is_behind("1.0.422", "nightly") is False


class _Resp:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, body: bytes, status: int = 200):
        self._body, self.status = body, status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestLatestVersion:
    def _serve(self, monkeypatch, resp):
        """Replace nethttp.urlopen and record the Request objects it is given.

        Recording the whole Request, not just its URL, is the point: a fake that
        keeps only the URL lets the headers be dropped or misspelled without any
        test noticing.
        """
        seen = []

        def fake(req, timeout):
            seen.append((req, timeout))
            if isinstance(resp, Exception):
                raise resp
            return resp
        monkeypatch.setattr(selfupdate.nethttp, "urlopen", fake)
        return seen

    def test_reads_info_version_from_the_pypi_json_api(self, monkeypatch):
        seen = self._serve(monkeypatch,
                           _Resp(b'{"info": {"version": "1.0.423"}}'))
        assert selfupdate.latest_version() == "1.0.423"
        assert seen[0][0].full_url == "https://pypi.org/pypi/boost-skill-cli/json"

    def test_the_request_identifies_itself_and_asks_for_json(self, monkeypatch):
        # A named User-Agent is what lets PyPI (and any proxy in between)
        # attribute the traffic, and Accept is the documented way to ask the
        # JSON API for JSON rather than whatever a content negotiator prefers.
        seen = self._serve(monkeypatch,
                           _Resp(b'{"info": {"version": "1.0.423"}}'))
        selfupdate.latest_version()
        req = seen[0][0]
        assert req.get_header("Accept") == "application/json"
        assert req.get_header("User-agent") == "boost-self-update"

    def test_the_request_carries_a_timeout(self, monkeypatch):
        seen = self._serve(monkeypatch,
                           _Resp(b'{"info": {"version": "1.0.423"}}'))
        selfupdate.latest_version(timeout=2.5)
        assert seen[0][1] == 2.5

    def test_a_body_with_undecodable_bytes_is_still_read(self, monkeypatch):
        # PyPI's response is ~735 KB of mostly-ASCII JSON; a byte mangled in
        # transit must not lose the whole answer, so the decode replaces rather
        # than raises. Without errors="replace" this returns None instead.
        self._serve(monkeypatch,
                    _Resp(b'{"info": {"version": "1.0.423", "x": "\xff"}}'))
        assert selfupdate.latest_version() == "1.0.423"

    def test_none_when_pypi_is_unreachable(self, monkeypatch):
        self._serve(monkeypatch, OSError("no route to host"))
        assert selfupdate.latest_version() is None

    def test_none_on_a_url_error(self, monkeypatch):
        import urllib.error
        self._serve(monkeypatch, urllib.error.URLError("dns"))
        assert selfupdate.latest_version() is None

    def test_none_on_a_timeout(self, monkeypatch):
        self._serve(monkeypatch, TimeoutError())
        assert selfupdate.latest_version() is None

    def test_none_on_a_truncated_response(self, monkeypatch):
        # Found by pointing this at real PyPI: the payload is ~735 KB (every
        # release's file list), and a connection that drops mid-body raises
        # http.client.IncompleteRead. On CPython <= 3.13 that was also a
        # ValueError and the JSON handler caught it by accident; on 3.14 its
        # bases are (HTTPException,) alone, so it escaped as a traceback out of
        # a version check that is supposed to be unable to fail.
        import http.client
        self._serve(monkeypatch, http.client.IncompleteRead(b"{", 99))
        assert selfupdate.latest_version() is None

    def test_none_on_any_http_protocol_error(self, monkeypatch):
        import http.client
        self._serve(monkeypatch, http.client.BadStatusLine("garbage"))
        assert selfupdate.latest_version() is None

    def test_none_on_a_non_2xx_status(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b"nope", status=503))
        assert selfupdate.latest_version() is None

    def test_the_2xx_window_is_bounded_at_both_ends(self, monkeypatch):
        # Boundaries, not just a 503: a 503 is outside the window whichever way
        # the comparison operators are mutated, so it alone pins nothing about
        # where the window ends.
        body = b'{"info": {"version": "1.0.423"}}'
        for status, expected in ((199, None), (200, "1.0.423"),
                                 (299, "1.0.423"), (300, None)):
            self._serve(monkeypatch, _Resp(body, status=status))
            assert selfupdate.latest_version() == expected, status

    def test_a_missing_status_attribute_is_not_a_success(self, monkeypatch):
        # `getattr(resp, "status", 0)` defaults to 0, which must fail the check
        # rather than fall through as if the response were fine.
        class _NoStatus:
            def read(self):
                return b'{"info": {"version": "1.0.423"}}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        self._serve(monkeypatch, _NoStatus())
        assert selfupdate.latest_version() is None

    def test_none_on_unparseable_json(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b"<html>maintenance</html>"))
        assert selfupdate.latest_version() is None

    def test_none_when_the_payload_has_no_version(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b'{"info": {}}'))
        assert selfupdate.latest_version() is None

    def test_none_when_info_is_not_an_object(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b'{"info": null}'))
        assert selfupdate.latest_version() is None

    def test_none_when_the_version_is_not_a_string(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b'{"info": {"version": 423}}'))
        assert selfupdate.latest_version() is None

    def test_none_when_the_version_is_blank(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b'{"info": {"version": "  "}}'))
        assert selfupdate.latest_version() is None

    def test_boost_no_net_skips_the_call_entirely(self, monkeypatch):
        # Same contract as BOOST_NO_AI/BOOST_NO_SEED: a test (or an air-gapped
        # user) must be able to guarantee no request leaves the machine.
        def never(req, timeout):
            raise AssertionError("BOOST_NO_NET must prevent the request")
        monkeypatch.setattr(selfupdate.nethttp, "urlopen", never)
        monkeypatch.setenv("BOOST_NO_NET", "1")
        assert selfupdate.latest_version() is None

    def test_an_empty_boost_no_net_does_not_count_as_set(self, monkeypatch):
        self._serve(monkeypatch, _Resp(b'{"info": {"version": "1.0.423"}}'))
        monkeypatch.setenv("BOOST_NO_NET", "")
        assert selfupdate.latest_version() == "1.0.423"
