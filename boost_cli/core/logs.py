# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
  4. ``BOOST_LOG_LEVEL=OFF|DEBUG|INFO|…``   -> explicit console level
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
import io
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

from . import paths, typedvalue

LOGGER_NAME = "boost"
MAX_BYTES = 1_000_000  # ~1 MB per file …
BACKUP_COUNT = 3       # … times (N+1) files kept = ~4 MB ceiling
KEEP_CRASH_REPORTS = 20

_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_FORMATS = ("text", "json")
#: What `config set logging.level` / `logging.format` accept: ``OFF`` is the
#: default and silences the console, so it is a valid level even though
#: :mod:`logging` has no such name.
LEVEL_CHOICES = ("OFF", *_LEVELS)
FORMAT_CHOICES = _FORMATS
_TEXT_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Set by configure(); read by main()'s exception handler to decide whether to
# print a full traceback or a friendly one-liner.
_debug_console = False
_configured = False


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_stamp() -> str:
    """The unique part of a crash report's name: microsecond time plus pid.

    One-second resolution let two crashes in the same second share one file,
    the second overwriting the first while both runs printed its path. The pid
    separates concurrent processes; the microseconds keep sort order newest
    last for :func:`_prune_crash_reports` and doctor's "newest".
    """
    return "%s-%d" % (datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ"),
                      os.getpid())


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
    if debug or typedvalue.env_flag("BOOST_DEBUG"):
        return logging.DEBUG
    if verbose:
        return logging.INFO
    if quiet:
        return None
    # A set BOOST_LOG_LEVEL decides, whatever config says: `OFF` was missing
    # from the levels read here, so it fell through and a configured DEBUG
    # still printed — env silencing config is the documented order. An
    # unrecognised value silences too, and says so, rather than letting the
    # config level it was presumably meant to override win.
    env = (os.environ.get("BOOST_LOG_LEVEL") or "").strip().upper()
    if env in _LEVELS:
        return getattr(logging, env)
    if env:
        if env != "OFF":
            sys.stderr.write("! BOOST_LOG_LEVEL=%r is not one of %s — "
                             "treating it as OFF\n"
                             % (env, ", ".join(LEVEL_CHOICES)))
        return None
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
    if typedvalue.env_flag("BOOST_NO_LOG", unknown=True):
        return False
    from . import config
    return bool(config.get("logging.file", True))


#: ``os.O_BINARY`` where it exists (Windows), else no flag.
_O_BINARY: int = getattr(os, "O_BINARY", 0)


class _BestEffortFileHandler(logging.handlers.RotatingFileHandler):
    """A rotating file handler whose own I/O failures never reach the user.

    ``delay=True`` (below) defers the file open past construction — past the
    ``contextlib.suppress(OSError)`` in :func:`configure` — to the first
    ``emit()``, on a different stack frame with nothing catching it. Left at
    the default, ``logging.Handler.handleError`` prints ``--- Logging
    error ---`` and a full traceback to stderr for every failed write, which
    is exactly the noise the file handler exists to keep out of the user's
    way. Overriding ``handleError`` here scopes the swallow to this one
    handler, rather than flipping the module-global ``logging.raiseExceptions``
    for every logger in the process.
    """

    _rollover_failed = False

    def handleError(self, record: logging.LogRecord) -> None:
        pass

    def _open(self) -> io.TextIOWrapper:
        # Created 0600: the trail records every command line, and it is the
        # file users are asked to attach to bug reports — not one for every
        # account on the machine to read. A file left 0644 by an older boost
        # is tightened too, best-effort.
        # O_BINARY (Windows only): an fd os.open makes there is CRT text mode,
        # which would turn the TextIOWrapper's "\r\n" into "\r\r\n".
        fd = os.open(self.baseFilename,
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | _O_BINARY, 0o600)
        with contextlib.suppress(OSError):
            os.chmod(self.baseFilename, 0o600)
        # "a", not self.mode: a rotating handler with a size cap is always
        # append mode, and the literal keeps the return type a TextIOWrapper.
        return open(fd, "a", encoding=self.encoding, errors=self.errors)

    def doRollover(self) -> None:
        """Rotate, or keep appending to the current file when rotation fails.

        Rotation renames files, which needs a writable *directory*. When the
        logs dir is read-only the base class has already closed the stream
        when the rename raises, so every later record was dropped — the log
        stopped at ``MAX_BYTES`` for good, silently. Appending past the cap is
        the lesser harm; ``boost doctor`` names the unwritable directory.
        """
        if self._rollover_failed:
            return
        try:
            super().doRollover()
        except OSError:
            self._rollover_failed = True
            if self.stream is None:
                self.stream = self._open()


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

    _debug_console = bool(debug or typedvalue.env_flag("BOOST_DEBUG"))

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
            paths.logs_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
            fh = _BestEffortFileHandler(
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
        " ".join(redact_argv(argv)), os.getpid(), os.getppid(), sys.executable)


def log_completion(argv: list[str], rc: int, elapsed_ms: float) -> None:
    """Close out an invocation with its exit code and wall-clock duration.

    A clean exit logs at INFO; any non-zero code logs at WARNING so a failing
    run stands out when scanning the trail (and surfaces with ``--verbose``).
    """
    level = logging.INFO if rc == 0 else logging.WARNING
    get_logger().log(level, "done: boost %s -> rc=%d in %dms",
                     " ".join(redact_argv(argv)), rc, round(elapsed_ms))


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
    return redact_url(value)


#: ``scheme://user:pass@`` — greedy up to the last ``@`` before the path, so a
#: password that itself contains ``@`` is withheld whole. Not anchored: argv
#: tokens carry URLs after a ``--flag=``.
_URL_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s]+@", re.IGNORECASE)
#: A query parameter whose name says it carries a credential (``?token=``,
#: ``&api_key=``, ``&X-Amz-Signature=``).
_URL_QUERY_SECRET = re.compile(
    r"([?&][^=&#\s]*(?:key|token|secret|password|passwd|auth|sig)[^=&#\s]*=)"
    r"[^&#\s]*", re.IGNORECASE)


def redact_url(value: str) -> str:
    """``value`` with URL userinfo and credential query parameters withheld.

    Host and path survive: they are what a bug report needs, and the
    credential is what it must not carry.
    """
    value = _URL_USERINFO.sub(r"\1" + REDACTED + "@", value)
    return _URL_QUERY_SECRET.sub(r"\1" + REDACTED, value)


def redact_argv(argv: list[str]) -> list[str]:
    """``argv`` as it may be written to the log or a crash report.

    The terminal never shows what a log keeps: git strips userinfo from the
    URL it echoes, so ``boost tap https://user:ghp_…@host/x`` left the token in
    exactly one place — ``boost.log``, the file users attach to bug reports.
    Withheld per token: a credential-shaped value, the value of a
    ``--token=``/``--api-key`` style option (both ``=`` and next-token forms),
    and URL userinfo or query secrets anywhere. The env snapshot's 40-char
    opaque-run rule is deliberately not applied — ``boost tap --at <sha>`` is a
    documented command and a pinned SHA is exactly what a trail should keep.
    """
    out: list[str] = []
    secret_next = False
    for tok in argv:
        if secret_next:
            secret_next = False
            out.append(REDACTED)
            continue
        # A length floor: a credential is long, and `sk-`/`pa-` are also how
        # a short skill name can start.
        if len(tok) >= 20 and _SECRET_VALUE.match(tok):
            out.append(REDACTED)
            continue
        name, eq, _ = tok.partition("=")
        if tok.startswith("-") and _SECRET_NAME.search(name):
            if eq:
                out.append(name + "=" + REDACTED)
                continue
            secret_next = True
        out.append(redact_url(tok))
    return out


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
        "command:  boost %s" % " ".join(redact_argv(argv)),
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
        paths.logs_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
        report = _create_exclusive(paths.logs_dir(), _file_stamp(),
                                   body.encode("utf-8"))
    except OSError:
        return None
    _prune_crash_reports()
    return report


def _create_exclusive(ldir: Path, stamp: str, data: bytes) -> Path:
    """Write ``data`` to a new ``crash-<stamp>[-N].log``, never over another.

    ``O_EXCL`` makes a name collision an error instead of an overwrite, so a
    report a user was told about is still there to attach. Created 0600, like
    the log: a traceback carries local paths and argument values.
    """
    for n in range(100):
        report = ldir / ("crash-%s%s.log" % (stamp, "-%d" % n if n else ""))
        try:
            fd = os.open(report,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_BINARY,
                         0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return report
    raise FileExistsError(str(ldir / ("crash-%s.log" % stamp)))


def dir_writable() -> bool:
    """Whether new files can be created in the logs dir (and so renamed there).

    Log rotation and crash reports both need this, and an append-open of
    ``boost.log`` — doctor's other check — succeeds without it. A missing dir
    counts as writable: it is created on demand, and a refusal to create it
    is reported by doctor's own directory check.
    """
    ldir = paths.logs_dir()
    if not ldir.is_dir():
        return True
    probe = ldir / (".probe-%d" % os.getpid())
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return True
    except OSError:
        return False
    os.close(fd)
    with contextlib.suppress(OSError):
        probe.unlink()
    return True


def _prune_crash_reports() -> None:
    """Keep only the most recent KEEP_CRASH_REPORTS crash files."""
    try:
        reports = sorted(paths.logs_dir().glob("crash-*.log"))
    except OSError:
        return
    for stale in reports[:-KEEP_CRASH_REPORTS]:
        with contextlib.suppress(OSError):
            stale.unlink()
