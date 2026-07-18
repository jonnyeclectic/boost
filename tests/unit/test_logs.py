"""Diagnostic logging & crash reporting."""
from __future__ import annotations

import logging
import pathlib

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
    text = logs.log_path().read_text()
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
    assert "invoke: boost install foo" in logs.log_path().read_text()


def test_invocation_records_pid_ppid_and_interpreter(env):
    """PID/PPID + interpreter are logged so a native crash can be correlated
    against an OS crash report (and boost ruled in or out) by PID."""
    import os
    import sys
    logs.configure()
    logs.log_invocation(["mcp", "--stdio"])
    line = logs.log_path().read_text()
    assert ("pid=%d" % os.getpid()) in line
    assert ("ppid=%d" % os.getppid()) in line
    assert ("py=%s" % sys.executable) in line


def test_completion_logs_rc_and_duration(env):
    logs.configure()
    logs.log_completion(["count"], 0, 12.7)
    line = logs.log_path().read_text()
    assert "done: boost count -> rc=0 in 13ms" in line  # ms rounded
    assert "INFO" in line  # clean exit -> INFO


def test_completion_nonzero_rc_is_warning(env):
    logs.configure()
    logs.log_completion(["install", "nope"], 1, 5.0)
    line = logs.log_path().read_text()
    assert "done: boost install nope -> rc=1 in 5ms" in line
    assert "WARNING" in line  # failing run stands out in the trail


def test_crash_report_written_with_context(env):
    logs.configure()
    try:
        raise ValueError("kaboom")
    except ValueError as e:
        report = logs.write_crash_report(e, ["install", "bad"])
    assert report is not None and report.exists()
    body = report.read_text()
    assert "kaboom" in body
    assert "ValueError" in body
    assert "boost install bad" in body
    assert "traceback:" in body
    # crash is also recorded in the rotating trail
    assert "crash" in logs.log_path().read_text()


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
    assert "boom" in report.read_text()


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
    assert "invoke: boost count" in logs.log_path().read_text()


def test_cli_logs_completion_with_duration(boost):
    boost("count")
    trail = logs.log_path().read_text()
    assert "done: boost count -> rc=0 in" in trail
    assert "ms" in trail  # duration is recorded


def test_cli_crash_still_logs_completion(boost, monkeypatch):
    from boost_cli import cli
    monkeypatch.setattr(cli, "_dispatch",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    boost("count", expect=70)
    trail = logs.log_path().read_text()
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
