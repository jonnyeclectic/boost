"""Diagnostic logging & crash reporting — boost's black box recorder.

This is separate from two neighbouring concerns:

  * ``core.output`` is the *human* channel — the pretty stdout a user reads.
  * ``core.journal`` is the *activity* feed — semantic events (`install`,
    `uninstall`) that power `boost pulse`/`trending`/`who`.

``core.logs`` is the *diagnostic* channel: a rotating, machine-greppable trail
of what boost did and why, written to ``~/.boost/logs/boost.log``, plus full
crash reports when an unexpected exception escapes. Nothing here is meant for
normal reading — it exists so that when something breaks, there is a trail.

Verbosity is resolved once, in this order (first wins):

  1. ``--debug`` flag / ``BOOST_DEBUG=1``      -> console shows DEBUG + tracebacks
  2. ``--verbose`` / ``-v`` flag              -> console shows INFO
  3. ``--quiet`` / ``-q`` flag                -> console stays silent
  4. ``BOOST_LOG_LEVEL=DEBUG|INFO|WARNING|…`` -> explicit console level
  5. config ``logging.level`` (default ``OFF`` -> console silent)

The console diagnostic channel is *off by default* — user-facing messages
already go through ``core.output``. The *file* handler always records at DEBUG
regardless of console verbosity, so a plain run still leaves a complete trail to
inspect after the fact. Set ``BOOST_NO_LOG=1`` (or config ``logging.file=false``)
to disable the file.

Each invocation bookends the trail with an ``invoke:`` line and a ``done:`` line
that carries the exit code and wall-clock duration, so the log doubles as a
lightweight timing record for spotting slow commands after the fact.

Line *format* is resolved separately from verbosity, same precedence shape:

  1. ``BOOST_LOG_FORMAT=json|text``
  2. config ``logging.format`` (default ``text``)

``json`` emits one JSON object per line — the same fields the text formatter
renders — so ``~/.boost/logs/boost.log`` pipes straight into ``jq`` or a log
collector instead of needing a regex. It is the same JSONL shape
``core.journal`` already writes for the pulse feed.
"""
from __future__ import annotations

import contextlib
import json
import logging
import logging.handlers
import os
import platform
import re
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from . import paths

LOGGER_NAME = "boost"
MAX_BYTES = 1_000_000  # ~1 MB per file …
BACKUP_COUNT = 3       # … times (N+1) files kept = ~4 MB ceiling
KEEP_CRASH_REPORTS = 20

_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_FORMATS = ("text", "json")
_TEXT_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Set by configure(); read by main()'s exception handler to decide whether to
# print a full traceback or a friendly one-liner.
_debug_console = False
_configured = False


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def log_path() -> Path:
    """Return the rotating diagnostic log's path (``~/.boost/logs/boost.log``)."""
    return paths.logs_dir() / "boost.log"


def is_debug() -> bool:
    """True when the user asked for debug output (flag or env)."""
    return _debug_console


def _console_level(verbose: bool, debug: bool, quiet: bool) -> int | None:
    """Resolve the stderr diagnostic-handler level, or None to suppress it.

    The console diagnostic channel is *off by default* — user-facing messages
    already go through ``core.output``. It turns on only when explicitly asked
    for, so a normal run leaves stderr clean while the file keeps the full
    DEBUG trail.
    """
    if debug or os.environ.get("BOOST_DEBUG"):
        return logging.DEBUG
    if verbose:
        return logging.INFO
    if quiet:
        return None
    env = (os.environ.get("BOOST_LOG_LEVEL") or "").strip().upper()
    if env in _LEVELS:
        return getattr(logging, env)
    from . import config
    cfg = str(config.get("logging.level", "OFF") or "OFF").upper()
    return getattr(logging, cfg) if cfg in _LEVELS else None


class JsonFormatter(logging.Formatter):
    """One JSON object per line, carrying the text formatter's own fields.

    Hand-rolled rather than pulled from a dependency: the runtime is
    stdlib-only, ``core.journal`` already writes JSONL by hand for the pulse
    feed, and a formatter that can raise is a formatter that loses the trail it
    exists to keep — hence ``default=str``, so an unexpected object in a record
    degrades to its repr instead of killing the handler.

    ``converter`` is set on the instance by :func:`_formatter`, not here: as a
    class attribute mypy binds it as a method and the signature stops matching
    the base class's.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, _DATE_FMT),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_format() -> str:
    """Resolve the log line format: env first, then config, else ``text``."""
    env = (os.environ.get("BOOST_LOG_FORMAT") or "").strip().lower()
    if env in _FORMATS:
        return env
    from . import config
    cfg = str(config.get("logging.format", "text") or "text").strip().lower()
    return cfg if cfg in _FORMATS else "text"


def _formatter(fmt_name: str) -> logging.Formatter:
    """Build the formatter both handlers share."""
    fmt: logging.Formatter = (JsonFormatter() if fmt_name == "json"
                              else logging.Formatter(_TEXT_FMT,
                                                     datefmt=_DATE_FMT))
    # Both stamp a literal ``Z`` (UTC) suffix, so the timestamp has to be
    # rendered in UTC — otherwise it uses local time and every line is
    # mislabelled by the machine's offset. gmtime keeps it honest.
    fmt.converter = time.gmtime
    return fmt


def _file_enabled() -> bool:
    if os.environ.get("BOOST_NO_LOG"):
        return False
    from . import config
    return bool(config.get("logging.file", True))


def get_logger() -> logging.Logger:
    """Return the shared ``boost`` logger; :func:`configure` attaches handlers."""
    return logging.getLogger(LOGGER_NAME)


def reset() -> None:
    """Detach all handlers and forget configuration.

    Real runs configure logging exactly once, but an in-process test suite
    reconfigures against a fresh sandbox $HOME each test; without this the
    first test's file handler would linger and write to a stale path.
    """
    global _configured, _debug_console
    logger = logging.getLogger(LOGGER_NAME)
    for h in logger.handlers.copy():
        with contextlib.suppress(Exception):
            h.close()
        logger.removeHandler(h)
    _configured = False
    _debug_console = False


def configure(verbose: bool = False, debug: bool = False,
              quiet: bool = False) -> logging.Logger:
    """Install handlers on the ``boost`` logger. Idempotent within a process."""
    global _debug_console, _configured
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)  # handlers do the real filtering
    logger.propagate = False

    _debug_console = bool(debug or os.environ.get("BOOST_DEBUG"))

    if _configured:
        return logger
    _configured = True

    # One formatter for both handlers: a user who asked for JSON asked for it
    # everywhere, and a file/console split would make `--debug` disagree with
    # the file it is meant to be showing.
    fmt = _formatter(log_format())

    # File handler — always DEBUG, best-effort (never break the CLI over a log).
    if _file_enabled():
        with contextlib.suppress(OSError):
            paths.logs_dir().mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                log_path(), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
                encoding="utf-8", delay=True,
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    # Console handler — only attached when something should surface on stderr.
    level = _console_level(verbose, debug, quiet)
    if level is not None:
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(level)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def log_invocation(argv: list[str]) -> None:
    """Record a command invocation at the head of the trail.

    Includes ``pid``/``ppid`` and the interpreter path so a *native* crash —
    which Python can't catch, so it never reaches :func:`write_crash_report` —
    can still be correlated against an OS crash report by PID. If an OS report
    names a PID that never appears here, boost is ruled out as that process.
    """
    get_logger().info(
        "invoke: boost %s [pid=%d ppid=%d py=%s]",
        " ".join(argv), os.getpid(), os.getppid(), sys.executable)


def log_completion(argv: list[str], rc: int, elapsed_ms: float) -> None:
    """Close out an invocation with its exit code and wall-clock duration.

    A clean exit logs at INFO; any non-zero code logs at WARNING so a failing
    run stands out when scanning the trail (and surfaces with ``--verbose``).
    """
    level = logging.INFO if rc == 0 else logging.WARNING
    get_logger().log(level, "done: boost %s -> rc=%d in %dms",
                     " ".join(argv), rc, round(elapsed_ms))


def _boost_version() -> str:
    try:
        from .. import __version__
        return __version__
    except Exception:
        return "unknown"


#: Variable names whose value is a credential by definition. Matched on the
#: trailing word so ``BOOST_ANTHROPIC_API_KEY``, ``BOOST_GITHUB_TOKEN`` and
#: ``BOOST_TAP_PASSWORD`` are all caught without enumerating providers.
_SECRET_NAME = re.compile(
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|AUTH)$", re.IGNORECASE)

#: Value prefixes that are unmistakably a credential whatever the variable is
#: called. A name denylist alone always trails the next provider someone adds,
#: and the leak this guards against cost nothing to introduce: boost documents
#: ``BOOST_ANTHROPIC_API_KEY``, so the variable most likely to be *set* was also
#: the one most likely to be secret.
_SECRET_VALUE = re.compile(
    r"^(?:sk-|pk-|rk-|voy-|pa-|ghp_|gho_|ghu_|ghs_|ghr_|github_pat_"
    r"|xox[abprs]-|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})")

REDACTED = "<REDACTED>"


def _redact(name: str, value: str) -> str:
    """The value to print for ``name``, with credentials withheld.

    Redacts rather than drops. A missing line reads as "unset", which sends
    whoever is reading the crash report down the wrong path — the fact that a
    key *was* configured is exactly what they need to know.
    """
    if _SECRET_NAME.search(name) or _SECRET_VALUE.match(value):
        return REDACTED
    # Belt and braces for the shape a credential takes even when it carries no
    # recognised prefix: one long opaque run with no separators. Excluding
    # anything path-like keeps ordinary debug values (dirs, URLs) readable.
    if (len(value) >= 40 and not set(value) & set(" \t/\\")
            and re.fullmatch(r"[A-Za-z0-9_.+=-]+", value)):
        return REDACTED
    return value


def _env_snapshot() -> list[str]:
    keys = sorted(k for k in os.environ
                  if k.startswith("BOOST_") or k in ("NO_COLOR", "CLICOLOR_FORCE"))
    return ["%s=%s" % (k, _redact(k, os.environ[k])) for k in keys]


def write_crash_report(exc: BaseException, argv: list[str]) -> Path | None:
    """Dump a full crash report and return its path (or None if it can't).

    Captures the traceback, invocation, versions and boost-relevant env so a
    user can attach one file to a bug report instead of reproducing by hand.
    """
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    body = "\n".join([
        "boost crash report",
        "==================",
        "time:     %s" % _stamp(),
        "version:  %s" % _boost_version(),
        "python:   %s" % sys.version.split()[0],
        "platform: %s" % platform.platform(),
        "command:  boost %s" % " ".join(argv),
        "",
        "environment:",
        *("  " + line for line in (_env_snapshot() or ["  (none)"])),
        "",
        "traceback:",
        tb.rstrip(),
        "",
    ])
    # Always try to get it into the rotating trail, even if the file write fails.
    with contextlib.suppress(Exception):
        get_logger().error("crash: %s: %s", type(exc).__name__, exc)
    try:
        paths.logs_dir().mkdir(parents=True, exist_ok=True)
        report = paths.logs_dir() / ("crash-%s.log" % _file_stamp())
        report.write_text(body, encoding="utf-8")
        _prune_crash_reports()
        return report
    except OSError:
        return None


def _prune_crash_reports() -> None:
    """Keep only the most recent KEEP_CRASH_REPORTS crash files."""
    try:
        reports = sorted(paths.logs_dir().glob("crash-*.log"))
    except OSError:
        return
    for stale in reports[:-KEEP_CRASH_REPORTS]:
        with contextlib.suppress(OSError):
            stale.unlink()
