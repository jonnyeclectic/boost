# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The diagnostic trail and crash reports are files users attach to bug reports.

`boost tap https://alice:ghp_…@host/x` left the token in boost.log twice
(``invoke:`` and ``done:``) and in the crash report's ``command:`` line, while
git had already stripped it from the terminal. Both files were 0644. Two
crashes in one second shared a report file, a read-only logs dir froze the log
for good once it reached ``MAX_BYTES``, and ``boost log --diagnostics`` crashed
on an unreadable log.
"""
from __future__ import annotations

import logging
import os
import re
import stat
import sys
import time

import pytest

from boost_cli.core import logs, paths

R = logs.REDACTED
TOKEN = "ghp_" + "A" * 36

posix_only = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX permission bits; root ignores them")


@pytest.fixture()
def env(sandbox):
    logs.reset()
    yield sandbox
    logs.reset()


class TestRedactUrl:
    @pytest.mark.parametrize("value, want", [
        ("https://alice:s3cret@host/x/y", "https://%s@host/x/y" % R),
        ("https://tok@host", "https://%s@host" % R),
        ("ssh://git:p@ss@host:22/r", "ssh://%s@host:22/r" % R),
        ("--manifest=https://u:p@h/m.json", "--manifest=https://%s@h/m.json" % R),
        ("https://h/x?token=abc&page=2", "https://h/x?token=%s&page=2" % R),
        ("https://h/x?page=2&API_KEY=abc#f", "https://h/x?page=2&API_KEY=%s#f" % R),
        ("https://h/x?X-Amz-Signature=ff", "https://h/x?X-Amz-Signature=%s" % R),
        ("https://h/x/y?page=2", "https://h/x/y?page=2"),
        ("user@example.com", "user@example.com"),
        ("plain", "plain"),
        ("xhttps://u:p@h/x", "xhttps://%s@h/x" % R),
        (" https://u:p@h/x", " https://%s@h/x" % R),
        ("https://h/x?a=b?token=t&c=d", "https://h/x?a=b?token=%s&c=d" % R),
        ("https://h/x?token=a?b&c=d", "https://h/x?token=%s&c=d" % R),
        ("https://h/x?token=&auth=z", "https://h/x?token=%s&auth=%s" % (R, R)),
        ("https://h/x?page=1 ?sig=s", "https://h/x?page=1 ?sig=%s" % R),
        ("?token", "?token"),
        # A run opening with a non-letter scheme character still redacts.
        ("1https://u:p@h/x", "1https://%s@h/x" % R),
        ("--x=2git+https://u:p@h", "--x=2git+https://%s@h" % R),
        ("-https://u:p@h", "-https://%s@h" % R),
        (".https://u:p@h", ".https://%s@h" % R),
    ])
    def test_masks_credentials_and_keeps_host_and_path(self, value, want):
        assert logs.redact_url(value) == want

    # Built inside the test, not passed as the parameter: pytest exports each
    # test's id as PYTEST_CURRENT_TEST, and Windows refuses an environment
    # variable past 32,767 characters — a 100,000-character id failed setup.
    @pytest.mark.parametrize("prefix,unit,count", [
        ("", "x", 100_000),          # one search term, no `://` anywhere
        ("", "keykey", 20_000),      # scheme-class run that never reaches `://`
        ("", "?a", 50_000),          # a query name may not span the next `?`
        ("", "&token", 20_000),      # secret names, none followed by `=`
        ("https://", "a", 100_000),  # userinfo scan with no `@`
        ("", "1", 100_000),          # a scheme-class run with no letter
        ("", "a1", 50_000),          # letters after non-letters, no `://`
    ], ids=["x", "keykey", "query-a", "amp-token", "https-a", "digits", "a1"])
    def test_is_linear_on_one_long_token(self, prefix, unit, count):
        # Both patterns were quadratic here: 40,000 characters took 3.9 s and
        # `boost search <200,000 x's>` never finished. Linear is milliseconds.
        value = prefix + unit * count
        start = time.perf_counter()
        assert logs.redact_url(value) == value
        assert time.perf_counter() - start < 1.0


class TestRedactArgv:
    def test_userinfo_url(self):
        assert logs.redact_argv(["tap", "https://alice:%s@127.0.0.1:9/x/y" % TOKEN]) \
            == ["tap", "https://%s@127.0.0.1:9/x/y" % R]

    def test_credential_shaped_token(self):
        assert logs.redact_argv(["config", "set", "k", TOKEN]) == ["config", "set", "k", R]

    def test_short_prefixed_name_is_kept(self):
        # `sk-`/`pa-` also start short skill names; a credential is long.
        assert logs.redact_argv(["install", "sk-helper", "pa-1234567890123456"]) \
            == ["install", "sk-helper", "pa-1234567890123456"]
        assert logs.redact_argv(["pa-12345678901234567"]) == [R]

    def test_secret_option_equals_form(self):
        assert logs.redact_argv(["x", "--api-key=hunter2", "--token=t"]) \
            == ["x", "--api-key=%s" % R, "--token=%s" % R]

    def test_secret_option_next_token_form(self):
        assert logs.redact_argv(["x", "--token", "hunter2", "after"]) \
            == ["x", "--token", R, "after"]

    def test_secret_name_without_dash_is_a_positional(self):
        assert logs.redact_argv(["config", "get", "token", "x"]) \
            == ["config", "get", "token", "x"]

    def test_a_pinned_sha_survives(self):
        sha = "0123456789abcdef0123456789abcdef01234567"
        assert logs.redact_argv(["tap", "o/r", "--at", sha]) == ["tap", "o/r", "--at", sha]

    def test_does_not_mutate_input(self):
        argv = ["--token", "x"]
        logs.redact_argv(argv)
        assert argv == ["--token", "x"]


def test_env_snapshot_masks_url_userinfo(monkeypatch):
    monkeypatch.setenv("BOOST_SHARD_MANIFEST",
                       "https://bob:s3cr3tpassw0rd@shards.example.com/manifest.json")
    line = next(x for x in logs._env_snapshot() if x.startswith("BOOST_SHARD_MANIFEST"))
    assert line == "BOOST_SHARD_MANIFEST=https://%s@shards.example.com/manifest.json" % R


def test_invoke_and_done_lines_carry_no_credential(env):
    logs.configure()
    argv = ["tap", "https://alice:%s@127.0.0.1:9/x/y" % TOKEN]
    logs.log_invocation(argv)
    logs.log_completion(argv, 1, 3.0)
    text = logs.log_path().read_text(encoding="utf-8")
    assert TOKEN not in text
    assert "invoke: boost tap https://%s@127.0.0.1:9/x/y [pid=" % R in text
    assert "done: boost tap https://%s@127.0.0.1:9/x/y -> rc=1 in 3ms" % R in text


def test_crash_report_command_line_is_redacted(env):
    report = logs.write_crash_report(
        RuntimeError("boom"), ["browse", "--category", "https://u:%s@h/x" % TOKEN])
    assert report is not None
    body = report.read_text(encoding="utf-8")
    assert TOKEN not in body
    assert "command:  boost browse --category https://%s@h/x\n" % R in body


@posix_only
def test_log_and_crash_report_are_created_owner_only(env):
    logs.configure()
    logs.get_logger().info("hello")
    report = logs.write_crash_report(RuntimeError("x"), ["count"])
    assert report is not None
    assert stat.S_IMODE(logs.log_path().stat().st_mode) == 0o600
    assert stat.S_IMODE(report.stat().st_mode) == 0o600


@posix_only
def test_an_existing_world_readable_log_is_tightened(env):
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    logs.log_path().write_text("old\n", encoding="utf-8")
    os.chmod(logs.log_path(), 0o644)
    logs.configure()
    logs.get_logger().info("hello")
    assert stat.S_IMODE(logs.log_path().stat().st_mode) == 0o600
    assert logs.log_path().read_text(encoding="utf-8").startswith("old\n")


class TestCrashReportNames:
    def test_name_is_microsecond_stamp_and_pid(self, env):
        report = logs.write_crash_report(RuntimeError("x"), ["count"])
        assert report is not None
        assert re.fullmatch(r"crash-\d{8}T\d{6}\.\d{6}Z-%d\.log" % os.getpid(),
                            report.name)

    def test_same_stamp_never_overwrites(self, env, monkeypatch):
        monkeypatch.setattr(logs, "_file_stamp", lambda: "20260101T000000.000000Z-7")
        first = logs.write_crash_report(RuntimeError("FIRST"), ["count"])
        second = logs.write_crash_report(RuntimeError("SECOND"), ["count"])
        third = logs.write_crash_report(RuntimeError("THIRD"), ["count"])
        assert first is not None and second is not None and third is not None
        assert first.name == "crash-20260101T000000.000000Z-7.log"
        assert second.name == "crash-20260101T000000.000000Z-7-1.log"
        assert third.name == "crash-20260101T000000.000000Z-7-2.log"
        assert "FIRST" in first.read_text(encoding="utf-8")
        assert "SECOND" in second.read_text(encoding="utf-8")
        assert "THIRD" in third.read_text(encoding="utf-8")

    def test_gives_up_after_bounded_collisions(self, env, monkeypatch):
        monkeypatch.setattr(logs, "_file_stamp", lambda: "s")
        d = paths.logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / "crash-s.log").write_text("keep", encoding="utf-8")
        for n in range(1, 100):
            (d / ("crash-s-%d.log" % n)).write_text("keep", encoding="utf-8")
        assert logs.write_crash_report(RuntimeError("x"), ["count"]) is None
        assert (d / "crash-s.log").read_text(encoding="utf-8") == "keep"
        assert not (d / "crash-s-100.log").exists()


class TestReadOnlyLogsDir:
    @posix_only
    def test_full_log_keeps_recording_when_rotation_fails(self, env, monkeypatch):
        monkeypatch.setattr(logs, "MAX_BYTES", 200)
        d = paths.logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        logs.log_path().write_text("x" * 300 + "\n", encoding="utf-8")
        os.chmod(d, 0o500)
        try:
            logs.configure()
            logs.get_logger().info("first after full")
            logs.get_logger().info("second after full")
        finally:
            os.chmod(d, 0o700)
        text = logs.log_path().read_text(encoding="utf-8")
        assert "first after full" in text
        assert "second after full" in text
        assert not (d / "boost.log.1").exists()

    def test_rollover_is_not_retried_after_it_failed(self, env, monkeypatch):
        logs.configure()
        fh = next(h for h in logs.get_logger().handlers
                  if isinstance(h, logs._BestEffortFileHandler))
        calls = []

        def boom(self):
            calls.append(1)
            self.stream = None
            raise PermissionError("ro")

        monkeypatch.setattr(logging.handlers.RotatingFileHandler, "doRollover", boom)
        fh.doRollover()
        fh.doRollover()
        assert calls == [1]
        assert fh.stream is not None

    def test_dir_writable_true_for_a_missing_dir(self, env):
        assert not paths.logs_dir().exists()
        assert logs.dir_writable() is True

    def test_dir_writable_leaves_no_probe(self, env):
        paths.logs_dir().mkdir(parents=True, exist_ok=True)
        assert logs.dir_writable() is True
        assert list(paths.logs_dir().iterdir()) == []

    @posix_only
    def test_dir_writable_false_for_read_only_dir(self, env):
        d = paths.logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o500)
        try:
            assert logs.dir_writable() is False
        finally:
            os.chmod(d, 0o700)

    @posix_only
    def test_doctor_flags_a_read_only_logs_dir(self, boost):
        boost("count")
        logs.reset()
        d = paths.logs_dir()
        os.chmod(d, 0o500)
        try:
            res = boost("doctor", expect=None)
        finally:
            os.chmod(d, 0o700)
        assert ("logs directory %s is not writable — crash reports and log "
                "rotation cannot be written; fix its permissions (chmod u+w)"
                % paths.tilde(d)) in " ".join(res.out.split())

    def test_doctor_quiet_about_a_writable_logs_dir(self, boost):
        boost("count")
        res = boost("doctor", expect=None)
        assert "logs directory" not in res.out


@posix_only
def test_log_diagnostics_on_unreadable_log_is_a_clean_error(boost):
    boost("count")
    logs.reset()
    lp = logs.log_path()
    os.chmod(lp, 0)
    try:
        res = boost("log", "--diagnostics", expect=1)
        res_json = boost("log", "--diagnostics", "--json", expect=1)
    finally:
        os.chmod(lp, 0o600)
    msg = " ".join(res.err.split())
    assert "cannot read diagnostic log %s: Permission denied" % paths.tilde(lp) in msg
    assert "chmod u+rw" in msg
    assert "unexpected error" not in res.err + res_json.err
    assert not list(paths.logs_dir().glob("crash-*.log"))
