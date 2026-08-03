"""Diagnostic logging & crash reporting."""
from __future__ import annotations

import json
import logging
import logging.handlers
import pathlib
import re
import time
from datetime import UTC, datetime

import pytest

from boost_cli.core import logs, paths


@pytest.fixture()
def env(sandbox):
    """A sandbox with logging reset; yields nothing but ensures isolation."""
    logs.reset()
    yield sandbox
    logs.reset()


def test_file_handler_records_at_debug(env):
    logs.configure()
    logs.get_logger().debug("hello-debug")
    logs.get_logger().info("hello-info")
    text = logs.log_path().read_text(encoding="utf-8")
    assert "hello-debug" in text  # file captures DEBUG even with quiet console
    assert "hello-info" in text
    assert "DEBUG" in text and "INFO" in text


def test_console_off_by_default(env, capsys):
    logs.configure()
    logs.get_logger().error("boom-should-not-print")
    err = capsys.readouterr().err
    assert "boom-should-not-print" not in err  # stderr stays clean


def test_verbose_surfaces_info_on_stderr(env, capsys):
    logs.configure(verbose=True)
    logs.get_logger().info("surfaced-line")
    assert "surfaced-line" in capsys.readouterr().err


def test_debug_flag_sets_is_debug(env):
    logs.configure(debug=True)
    assert logs.is_debug() is True
    logs.reset()
    logs.configure()
    assert logs.is_debug() is False


def test_env_log_level_controls_console(env, capsys, monkeypatch):
    monkeypatch.setenv("BOOST_LOG_LEVEL", "ERROR")
    logs.configure()
    logs.get_logger().warning("warn-hidden")
    logs.get_logger().error("err-shown")
    err = capsys.readouterr().err
    assert "warn-hidden" not in err
    assert "err-shown" in err


def test_no_log_env_disables_file(env, monkeypatch):
    monkeypatch.setenv("BOOST_NO_LOG", "1")
    logs.configure()
    logs.get_logger().info("nope")
    assert not logs.log_path().exists()


def test_config_level_opts_console_in(env, capsys):
    from boost_cli.core import config
    config.set_value("logging.level", "INFO")
    logs.configure()
    logs.get_logger().info("via-config")
    assert "via-config" in capsys.readouterr().err


def test_invocation_is_logged(env):
    logs.configure()
    logs.log_invocation(["install", "foo"])
    assert "invoke: boost install foo" in logs.log_path().read_text(encoding="utf-8")


def test_invocation_records_pid_ppid_and_interpreter(env):
    """PID/PPID + interpreter are logged so a native crash can be correlated
    against an OS crash report (and boost ruled in or out) by PID."""
    import os
    import sys
    logs.configure()
    logs.log_invocation(["mcp", "--stdio"])
    line = logs.log_path().read_text(encoding="utf-8")
    assert ("pid=%d" % os.getpid()) in line
    assert ("ppid=%d" % os.getppid()) in line
    assert ("py=%s" % sys.executable) in line


def test_completion_logs_rc_and_duration(env):
    logs.configure()
    logs.log_completion(["count"], 0, 12.7)
    line = logs.log_path().read_text(encoding="utf-8")
    assert "done: boost count -> rc=0 in 13ms" in line  # ms rounded
    assert "INFO" in line  # clean exit -> INFO


def test_completion_nonzero_rc_is_warning(env):
    logs.configure()
    logs.log_completion(["install", "nope"], 1, 5.0)
    line = logs.log_path().read_text(encoding="utf-8")
    assert "done: boost install nope -> rc=1 in 5ms" in line
    assert "WARNING" in line  # failing run stands out in the trail


def test_crash_report_written_with_context(env):
    logs.configure()
    try:
        raise ValueError("kaboom")
    except ValueError as e:
        report = logs.write_crash_report(e, ["install", "bad"])
    assert report is not None and report.exists()
    body = report.read_text(encoding="utf-8")
    assert "kaboom" in body
    assert "ValueError" in body
    assert "boost install bad" in body
    assert "traceback:" in body
    # crash is also recorded in the rotating trail
    assert "crash" in logs.log_path().read_text(encoding="utf-8")


def test_crash_report_prune_keeps_recent(env, monkeypatch):
    logs.configure()
    monkeypatch.setattr(logs, "KEEP_CRASH_REPORTS", 3)
    # write more reports than the cap, each with a distinct filename stamp
    stamps = iter("t%02d" % i for i in range(10))
    monkeypatch.setattr(logs, "_file_stamp", lambda: next(stamps))
    for _ in range(6):
        logs.write_crash_report(RuntimeError("x"), ["count"])
    remaining = sorted(paths.logs_dir().glob("crash-*.log"))
    assert len(remaining) == 3
    # the survivors are the most recent stamps
    assert remaining[-1].name == "crash-t05.log"


def test_reset_detaches_handlers(env):
    logs.configure()
    assert logs.get_logger().handlers
    logs.reset()
    assert not logs.get_logger().handlers


def test_configure_is_idempotent(env):
    logs.configure()
    first = list(logs.get_logger().handlers)
    logs.configure()  # second call must not stack duplicate handlers
    assert logs.get_logger().handlers == first


def test_console_level_resolution(env, monkeypatch):
    # default (OFF) suppresses the console handler entirely
    assert logs._console_level(False, False, False) is None
    # explicit flags win over env/config
    assert logs._console_level(False, True, False) == logging.DEBUG   # debug
    assert logs._console_level(True, False, False) == logging.INFO    # verbose
    assert logs._console_level(False, False, True) is None            # quiet
    monkeypatch.setenv("BOOST_LOG_LEVEL", "warning")
    assert logs._console_level(False, False, False) == logging.WARNING
    monkeypatch.setenv("BOOST_LOG_LEVEL", "bogus")
    assert logs._console_level(False, False, False) is None


# --- defensive / best-effort error branches --------------------------------
# logs.py is the black-box recorder: a broken log must never break the CLI, so
# every filesystem/handler touchpoint swallows its own errors. Those `except`
# arms are the parts that matter most in a crash, yet are the least exercised —
# these tests force each failure so the swallow is real, not just declared.

def test_reset_swallows_a_handler_that_fails_to_close(env):
    logs.configure()
    logger = logs.get_logger()

    class BadHandler(logging.Handler):
        def close(self):
            raise RuntimeError("cannot close")

        def emit(self, record):
            pass

    bad = BadHandler()
    logger.addHandler(bad)
    logs.reset()                       # must not raise despite close() blowing up
    assert bad not in logger.handlers  # …and still detaches the handler
    assert not logger.handlers


def test_configure_survives_file_handler_oserror(env, monkeypatch):
    def _boom(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(logs.logging.handlers, "RotatingFileHandler", _boom)
    logs.reset()
    logger = logs.configure()          # the OSError is swallowed, CLI proceeds
    assert logger is logs.get_logger()
    # no file handler was attached, and logging still works without raising
    assert not any(isinstance(h, logging.handlers.RotatingFileHandler)
                   for h in logger.handlers)
    logger.info("still-alive")


def test_boost_version_falls_back_to_unknown(env, monkeypatch):
    import boost_cli
    # simulate a build with no resolvable version (the `from .. import` fails)
    monkeypatch.delattr(boost_cli, "__version__", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "boost_cli._version", None)
    assert logs._boost_version() == "unknown"


def test_crash_report_swallows_trail_write_failure(env, monkeypatch):
    """A broken logger must not stop the on-disk crash file from being written."""
    real = logs.get_logger()

    class BadLogger:
        def error(self, *a, **k):
            raise RuntimeError("logger is wedged")

    monkeypatch.setattr(logs, "get_logger", lambda: BadLogger())
    report = logs.write_crash_report(ValueError("boom"), ["x"])
    monkeypatch.setattr(logs, "get_logger", lambda: real)   # restore for teardown
    assert report is not None and report.exists()
    assert "boom" in report.read_text(encoding="utf-8")


def test_crash_report_returns_none_when_file_write_fails(env, monkeypatch):
    class BadDir:
        def mkdir(self, *a, **k):
            raise OSError("no space left on device")

    monkeypatch.setattr(logs.paths, "logs_dir", lambda: BadDir())
    assert logs.write_crash_report(ValueError("boom"), ["x"]) is None


def test_prune_returns_early_when_glob_fails(env, monkeypatch):
    class BadDir:
        def glob(self, pattern):
            raise OSError("cannot list directory")

    monkeypatch.setattr(logs.paths, "logs_dir", lambda: BadDir())
    logs._prune_crash_reports()        # must return quietly, not raise


def test_prune_swallows_unlink_failure_and_keeps_files(env, monkeypatch):
    logs.configure()
    monkeypatch.setattr(logs, "KEEP_CRASH_REPORTS", 1)
    d = paths.logs_dir()
    d.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (d / ("crash-t%02d.log" % i)).write_text("x", encoding="utf-8")

    def _locked(self, *a, **k):
        raise OSError("file is locked")

    monkeypatch.setattr(pathlib.Path, "unlink", _locked)
    logs._prune_crash_reports()        # unlink raises for each stale file…
    # …swallowed, so all four files survive (nothing deleted)
    assert len(sorted(d.glob("crash-*.log"))) == 4


# --- CLI integration -------------------------------------------------------

def test_cli_logs_invocation(boost):
    boost("count")
    assert "invoke: boost count" in logs.log_path().read_text(encoding="utf-8")


def test_cli_logs_completion_with_duration(boost):
    boost("count")
    trail = logs.log_path().read_text(encoding="utf-8")
    assert "done: boost count -> rc=0 in" in trail
    assert "ms" in trail  # duration is recorded


def test_cli_crash_still_logs_completion(boost, monkeypatch):
    from boost_cli import cli
    monkeypatch.setattr(cli, "_dispatch",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    boost("count", expect=70)
    trail = logs.log_path().read_text(encoding="utf-8")
    assert "done: boost count -> rc=70 in" in trail  # finally-block bookend fires


def test_cli_global_flags_stripped_before_dispatch(boost):
    # --verbose is consumed globally; the command still runs normally
    res = boost("--verbose", "count")
    assert res.rc == 0
    assert "invoke: boost count" in res.err  # INFO surfaced on stderr


def test_cli_global_flag_only_before_command(boost, monkeypatch):
    # a trailing -q is NOT a global flag; it belongs to the subcommand's argv
    from boost_cli import cli
    seen = {}

    def fake_dispatch(name, rest, soft=False):
        seen["name"], seen["rest"] = name, rest
        return 0

    monkeypatch.setattr(cli, "_dispatch", fake_dispatch)
    boost("count", "-q")
    assert seen == {"name": "count", "rest": ["-q"]}


def test_cli_crash_writes_report_and_friendly_message(boost, monkeypatch):
    from boost_cli import cli
    monkeypatch.setattr(cli, "_dispatch",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    res = boost("count", expect=70)
    assert "unexpected error" in res.err
    assert "RuntimeError: boom" in res.err
    assert "boom" not in res.out  # never leaks a raw traceback to stdout
    assert sorted(paths.logs_dir().glob("crash-*.log"))


def test_cli_debug_reraises_traceback(boost, monkeypatch):
    from boost_cli import cli
    monkeypatch.setattr(cli, "_dispatch",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        boost("--debug", "count", expect=None)
    # even on a re-raise, the crash report is captured first
    assert sorted(paths.logs_dir().glob("crash-*.log"))


def test_log_diagnostics_subcommand(boost):
    boost("count")  # generate a line
    res = boost("log", "--diagnostics")
    assert "diagnostic log" in res.out
    assert "invoke: boost count" in res.out


def test_log_crashes_subcommand_empty(boost):
    res = boost("log", "--crashes")
    assert "no crash reports" in res.out


def test_doctor_reports_log_location(boost):
    boost("count")
    res = boost("doctor", expect=None)
    assert "diagnostic log at" in res.out


def _file_formatter():
    """The formatter attached to the configured file handler."""
    for h in logs.get_logger().handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            return h.formatter
    raise AssertionError("no file handler configured")


class TestUtcTimestamps:
    def test_formatter_uses_gmtime_converter(self, env):
        # datefmt stamps a literal ``Z`` (UTC) suffix, so the converter MUST be
        # gmtime; the default (localtime) would mislabel every line.
        logs.configure()
        assert _file_formatter().converter is time.gmtime

    def test_asctime_is_utc_regardless_of_local_zone(self, env, monkeypatch):
        # Force a non-UTC local zone; the rendered stamp must still be UTC.
        if not hasattr(time, "tzset"):
            pytest.skip("time.tzset unavailable on this platform")
        monkeypatch.setenv("TZ", "America/New_York")  # UTC-5/-4, never UTC
        time.tzset()
        try:
            logs.configure()
            fmt = _file_formatter()
            record = logging.LogRecord(
                "boost", logging.INFO, __file__, 1, "msg", None, None
            )
            record.created = 0.0  # 1970-01-01T00:00:00Z
            assert fmt.formatTime(record, fmt.datefmt) == "1970-01-01T00:00:00Z"
        finally:
            monkeypatch.delenv("TZ", raising=False)
            time.tzset()


# ── `boost log --crashes`, the listing branch ────────────────────────────────
#
# Only the empty state was covered. Everything below it — the glob's reverse
# sort, the `command:` summary extraction, the OSError fallback and the --limit
# cut — could regress without a single test noticing.

def _seed_crash(stamp: str, command: str = "boost install foo") -> pathlib.Path:
    """Write a crash report shaped like the real one logs.py produces."""
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    report = paths.logs_dir() / ("crash-%s.log" % stamp)
    report.write_text(
        "boost crash report\n"
        "version:  0.0.0\n"
        "command:  %s\n"
        "\ntraceback:\nRuntimeError: boom\n" % command,
        encoding="utf-8")
    return report


def test_log_crashes_lists_each_report_with_its_command(boost):
    _seed_crash("20260101-101010", "boost install foo")
    _seed_crash("20260102-202020", "boost tap o/r")
    res = boost("log", "--crashes")

    assert "crash reports in" in res.out
    assert "crash-20260101-101010.log  command:  boost install foo" in res.out
    assert "crash-20260102-202020.log  command:  boost tap o/r" in res.out
    assert "view one with:  cat " in res.out
    assert "no crash reports" not in res.out


def test_log_crashes_lists_newest_first(boost):
    _seed_crash("20260101-101010")
    _seed_crash("20260303-303030")
    out_lines = [ln for ln in boost("log", "--crashes").out.splitlines()
                 if "crash-2026" in ln]
    assert [ln.split()[0] for ln in out_lines] == [
        "crash-20260303-303030.log", "crash-20260101-101010.log"]


def test_log_crashes_honours_the_limit(boost):
    for stamp in ("20260101-010101", "20260202-020202", "20260303-030303"):
        _seed_crash(stamp)
    res = boost("log", "--crashes", "-n", "2")
    assert res.out.count("crash-2026") == 2
    # The two kept are the newest, not simply the first two the glob returned.
    assert "crash-20260303-030303.log" in res.out
    assert "crash-20260202-020202.log" in res.out
    assert "crash-20260101-010101.log" not in res.out


def test_log_crashes_tolerates_a_report_with_no_command_line(boost):
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    (paths.logs_dir() / "crash-20260404-040404.log").write_text(
        "truncated before the command line got written\n", encoding="utf-8")
    res = boost("log", "--crashes")
    assert "crash-20260404-040404.log" in res.out


def test_log_crashes_survives_an_unreadable_report(boost):
    # A directory where a file should be: read_text raises IsADirectoryError on
    # POSIX and PermissionError on Windows — both OSError, which is exactly the
    # fallback's contract. It must still list the entry, not abort the command.
    _seed_crash("20260505-050505")
    (paths.logs_dir() / "crash-20260606-060606.log").mkdir(parents=True)
    res = boost("log", "--crashes")
    assert "crash-20260606-060606.log" in res.out
    assert "crash-20260505-050505.log  command:  boost install foo" in res.out


def test_a_real_crash_shows_up_in_the_listing(boost, monkeypatch):
    # End-to-end across the writer and the reader: whatever logs.py records is
    # what `--crashes` has to be able to parse back out.
    from boost_cli import cli
    real_dispatch = cli._dispatch
    crashed = []

    def crash_once(name, argv, soft=False):
        # Only the first invocation blows up; `log --crashes` still has to run
        # for real. monkeypatch.undo() is not an option here — it would also
        # revert the sandbox fixture's $HOME and read the developer's own logs.
        if not crashed:
            crashed.append(name)
            raise RuntimeError("boom")
        return real_dispatch(name, argv, soft=soft)

    monkeypatch.setattr(cli, "_dispatch", crash_once)
    boost("count", expect=70)
    res = boost("log", "--crashes")
    assert crashed == ["count"]
    assert "command:  boost count" in res.out


# ── BOOST_LOG_FORMAT=json ────────────────────────────────────────────────────

class TestLogFormatResolution:
    """Env beats config beats the `text` default — same shape as the level."""

    def test_defaults_to_text(self, env):
        assert logs.log_format() == "text"

    def test_env_selects_json(self, env, monkeypatch):
        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        assert logs.log_format() == "json"

    def test_env_is_case_and_space_insensitive(self, env, monkeypatch):
        monkeypatch.setenv("BOOST_LOG_FORMAT", "  JSON ")
        assert logs.log_format() == "json"

    def test_an_unknown_env_value_falls_back_to_text(self, env, monkeypatch):
        # A typo must not silently disable logging or crash configure().
        monkeypatch.setenv("BOOST_LOG_FORMAT", "yaml")
        assert logs.log_format() == "text"

    def test_config_selects_json_when_env_is_unset(self, env, monkeypatch):
        from boost_cli.core import config
        monkeypatch.delenv("BOOST_LOG_FORMAT", raising=False)
        config.set_value("logging.format", "json")
        assert logs.log_format() == "json"

    def test_env_wins_over_config(self, env, monkeypatch):
        from boost_cli.core import config
        config.set_value("logging.format", "json")
        monkeypatch.setenv("BOOST_LOG_FORMAT", "text")
        assert logs.log_format() == "text"


class TestJsonFileOutput:
    def _records(self, env, monkeypatch):
        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        logs.configure()
        logs.get_logger().info("hello %s", "world")
        text = logs.log_path().read_text(encoding="utf-8")
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()]

    def test_one_json_object_per_line(self, env, monkeypatch):
        recs = self._records(env, monkeypatch)
        assert len(recs) == 1
        assert recs[0]["msg"] == "hello world", "args must be interpolated"
        assert recs[0]["level"] == "INFO"
        assert recs[0]["logger"] == "boost"

    def test_the_timestamp_is_utc_with_a_z(self, env, monkeypatch):
        ts = self._records(env, monkeypatch)[0]["ts"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), ts
        # Parsed as UTC it must be within a minute of now; a local-time stamp
        # wearing a Z would be off by the machine's offset.
        parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC)
        assert abs((datetime.now(UTC) - parsed).total_seconds()) < 60

    def test_an_exception_is_carried_in_its_own_field(self, env, monkeypatch):
        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        logs.configure()
        try:
            raise ValueError("boom")
        except ValueError:
            logs.get_logger().exception("caught it")
        rec = [json.loads(ln) for ln in
               logs.log_path().read_text(encoding="utf-8").splitlines()][-1]
        assert rec["msg"] == "caught it"
        assert "ValueError: boom" in rec["exc"]
        assert "\n" not in json.dumps(rec), "one physical line per record"

    def test_an_unserializable_arg_degrades_instead_of_losing_the_line(
            self, env, monkeypatch):
        # A formatter that raises loses the trail it exists to keep.
        class Weird:
            def __repr__(self):
                return "<weird>"

        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        logs.configure()
        logs.get_logger().info("got %r", Weird())
        rec = [json.loads(ln) for ln in
               logs.log_path().read_text(encoding="utf-8").splitlines()][-1]
        assert rec["msg"] == "got <weird>"

    def test_text_mode_is_unchanged(self, env, monkeypatch):
        monkeypatch.delenv("BOOST_LOG_FORMAT", raising=False)
        logs.configure()
        logs.get_logger().info("plain line")
        text = logs.log_path().read_text(encoding="utf-8")
        assert "INFO" in text and "boost: plain line" in text
        assert not text.lstrip().startswith("{")


class TestJsonConsoleOutput:
    def test_the_console_handler_uses_the_same_format(self, env, monkeypatch,
                                                      capsys):
        # A `--debug` stream that disagrees with the file it is showing would
        # be its own bug report.
        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        logs.configure(debug=True)
        logs.get_logger().error("stderr line")
        err = capsys.readouterr().err.strip().splitlines()[-1]
        assert json.loads(err)["msg"] == "stderr line"


class TestDiagnosticsViewerReadsBothFormats:
    """`boost log --diagnostics` is the human view of that same file."""

    def _diag(self):
        from boost_cli.commands import info
        return info._diag_line

    def test_a_json_line_is_rendered_back_as_text(self):
        line = json.dumps({"ts": "2026-07-27T00:00:00Z", "level": "INFO",
                           "logger": "boost", "msg": "invoke: boost count"})
        assert self._diag()(line) == \
            "2026-07-27T00:00:00Z INFO    boost: invoke: boost count"

    def test_a_plain_text_line_passes_through(self):
        line = "2026-07-27T00:00:00Z INFO    boost: invoke: boost count"
        assert self._diag()(line) == line

    def test_a_line_that_only_looks_like_json_passes_through(self):
        # A mixed file (the format changed mid-life) has to read end to end.
        for line in ("{not json at all", json.dumps({"other": "shape"}),
                     json.dumps([1, 2, 3])):
            assert self._diag()(line) == line

    def test_the_command_renders_a_json_trail(self, boost, monkeypatch):
        monkeypatch.setenv("BOOST_LOG_FORMAT", "json")
        boost("count")
        res = boost("log", "--diagnostics")
        assert "invoke: boost count" in res.out
        assert "{" not in res.out, "raw JSONL is not the human view"
