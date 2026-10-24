# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Small shared utilities: time, hashing, versions, skill quality scoring."""
from __future__ import annotations

import contextlib
import getpass
import hashlib
import os
import re
import shlex
import shutil
import stat
import sys
import tempfile
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from ..errors import BoostError, NotUTF8Error
from . import output as out
from . import paths

IGNORED = {".git", "__pycache__", ".DS_Store"}


def _clear_readonly_and_retry(func, path, exc, root=None) -> None:
    """Clear a read-only bit and retry the failed operation — never on a link.

    ``os.chmod`` follows symlinks, and the path handed to this hook is the one
    that failed, so chmod-ing it blind changes the mode of whatever the link
    points at — a file outside the tree being deleted, which nothing asked to
    modify. A link's own mode never blocked the operation anyway: on POSIX,
    unlinking is gated by the *parent* directory's write bit, so the retry
    fails a second time and the permission change is the only lasting effect.

    ``follow_symlinks=False`` is the obvious repair and is the wrong one on
    both counts. It is not portable — ``os.chmod`` supports the keyword only
    where the platform has ``lchmod``. ``os.supports_follow_symlinks`` is what
    reports that, it is not True everywhere this runs (measured True on
    darwin), and where the call does work it changes a mode that
    was never the problem. Re-raising needs no platform branch, and a branch
    that cannot be taken on the runner is a mutant that cannot be killed.

    The worse instance is a symlink passed to :func:`rmtree` *as its argument*.
    ``shutil.rmtree`` refuses one by calling this hook with ``func`` set to
    ``os.path.islink``; the old body chmod-ed straight through the link, then
    called ``os.path.islink(path)``, which answers True without raising — so
    the hook returned, ``rmtree`` returned, and the caller was told a tree had
    been removed when nothing had. Measured: the link survived, its target
    directory survived with its contents, and the target's mode went 0o755 to
    0o200. Re-raising restores ``shutil``'s own "Cannot call rmtree on a
    symbolic link" instead of that silent success.

    Only a removal is retried. ``shutil.rmtree`` also reports a failed
    ``os.open`` or ``os.scandir`` here — a subdir it may not list — and
    calling ``os.open(path)`` again raised ``TypeError`` (it needs flags),
    which no caller catches: `boost sync --prune` exited 70 halfway through a
    delete. A read-only bit is never why those fail, so the error is raised.
    """
    if os.path.islink(path) or func not in _RETRYABLE:
        raise exc
    # On POSIX the *parent's* write bit is what gates an unlink or rmdir, so
    # a skill copied from a read-only package (a 0o555 ``assets/``) could not
    # be uninstalled: chmod-ing the file it held changed nothing and the retry
    # failed again. Only a parent inside ``root``, the tree being deleted: the
    # directory that *holds* the tree is not this delete's to unlock (a
    # read-only skill store is a refusal doctor reports, not a mode to undo),
    # and never through a link.
    parent = os.path.normpath(os.path.dirname(path))
    if (root is not None and _inside_tree(parent, root)
            and not os.path.islink(parent)):
        os.chmod(parent, os.lstat(parent).st_mode | stat.S_IWUSR)
    # OR the bit in: setting the mode to exactly S_IWRITE also stripped read
    # and search, so a retry that failed anyway (a read-only *parent*) left a
    # ``d-w-------`` directory behind that every later walk of it crashed on.
    os.chmod(path, os.lstat(path).st_mode | stat.S_IWRITE)
    func(path)


#: The removals a cleared read-only bit can unblock.
_RETRYABLE = (os.unlink, os.remove, os.rmdir)


def _inside_tree(path: str, root: str) -> bool:
    """True if ``path`` is ``root`` or under it, compared as spelled.

    Lexical on purpose: ``shutil.rmtree`` builds every path it reports by
    joining onto the ``root`` it was given, so no resolving is needed.
    """
    root = os.path.normpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def rmtree(path) -> None:
    """``shutil.rmtree`` that survives read-only files.

    Git writes objects under ``.git/objects/`` read-only; POSIX still lets the
    owner unlink a read-only file (permission lives on the directory), but
    Windows refuses outright. Clear the read-only bit and retry once per
    failure. ``onexc`` is the 3.12+ spelling; the ``onerror`` branch this used
    to carry was dead the moment the floor moved to 3.12. A read-only
    directory *inside* the tree is unlocked too; the one holding it is not.
    """
    root = str(path)
    shutil.rmtree(root, onexc=lambda func, p, exc:
                  _clear_readonly_and_retry(func, p, exc, root=root))


def remove_path(path) -> bool:
    """Remove whatever is at ``path`` — a link as a link, a tree as a tree.

    Returns True when something was removed and False when the path did not
    exist. Raises ``OSError`` like the calls it wraps; a caller that must not
    fail on a leftover catches it.

    The naive guard is ``if path.is_dir(): rmtree(path)``, and it is wrong in
    both directions, because every ``Path`` predicate except ``is_symlink``
    answers *through* the link rather than about it:

    * A **symlink to a directory** answers True to ``is_dir()`` and
      ``exists()`` and goes to :func:`rmtree`, which refuses a link as its
      argument — so the caller takes an ``OSError`` out of a delete it had
      already guarded. The guard it wrote is the reason it believed it could
      not raise.
    * A **dangling symlink** answers False to both, so the guard skips it and
      the link survives. Nothing reports it, and the next writer to that path
      fails with ``FileExistsError`` for a path that "does not exist".

    Neither case is exotic: a skill directory or a tap clone symlinked to a
    checkout the user is editing, and the dangling link left behind when that
    checkout moves. ``is_symlink`` first is the whole fix — it is the one
    predicate that reads the link itself, so a link is unlinked and only a real
    directory is recursed into.

    A path that means *the working directory* raises ``ValueError`` rather
    than being obeyed. ``Path("")`` is ``PosixPath(".")`` — the normalisation
    happens in the constructor, so by the time any callee sees it the empty
    string and ``"."`` are the same value and neither can be told from the
    other. ``"."`` is a directory, so an empty path fell straight through to
    ``rmtree(".")`` and emptied whatever directory boost happened to be run
    from. No caller can currently produce one — ``resolve_in_base`` returns
    None for an empty relative path, bmad checks the name, and a tap path
    always carries a ``safe_name`` — but this is now the single place every
    one of those deletes goes through, and every real caller names a child.
    Refusing "here" costs nothing and closes the one argument whose blast
    radius is unbounded.
    """
    path = Path(path)
    if path == Path():          # `Path()`, `Path("")` and `Path(".")` are one
        raise ValueError("remove_path() will not remove the working "
                         "directory; pass the path to remove")
    if path.is_symlink() or path.is_file():
        path.unlink()
        return True
    if path.is_dir():
        rmtree(path)
        return True
    return False


def remove_items(
        items: list[tuple[Path, str, int]]) -> tuple[int, int, list[tuple[Path, str]]]:
    """Delete each ``(path, kind, size)`` triple; report only what actually went.

    Returns ``(removed_count, freed_bytes, failures)`` where ``failures`` pairs
    a path with the ``OSError`` text that stopped its removal. A caller must
    size its summary from ``removed_count``, never from ``len(items)`` — that
    was the bug this function exists to make impossible: a partial run used to
    report every candidate as removed and still exit 0.
    """
    removed = 0
    freed = 0
    failures: list[tuple[Path, str]] = []
    for pth, _kind, size in items:
        try:
            if not remove_path(pth):
                continue
        except OSError as e:
            failures.append((pth, str(e)))
            continue
        removed += 1
        freed += size
    return removed, freed, failures


def _lock_is_stale(path: Path, stale_after: float) -> bool:
    """True when a lock file is old enough to have been abandoned."""
    try:
        return (time.time() - path.stat().st_mtime) > stale_after
    except OSError:
        return True     # it vanished under us — treat it as free


@contextlib.contextmanager
def try_lock(path, stale_after: float = 300.0):
    """Best-effort exclusive lock, yielding whether it was actually taken.

    An `O_CREAT | O_EXCL` create is atomic on every filesystem boost targets,
    and needs neither `fcntl` (missing on Windows) nor `msvcrt` (missing
    everywhere else). Yields True to the holder and **False** to everyone
    else — this does not wait, because its callers are jobs where "another
    process is already doing it" is a perfectly good outcome, and blocking
    would trade a rare lost update for a common stall.

    A lock file older than `stale_after` is stolen: a process killed
    mid-operation must not wedge the operation forever. Any error acquiring
    it yields False rather than raising — failing to take a lock must never
    be worse than the problem it guards.
    """
    path = Path(path)
    fd = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if not _lock_is_stale(path, stale_after):
                yield False
                return
            with contextlib.suppress(OSError):
                path.unlink()
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError:
        yield False
        return
    try:
        with contextlib.suppress(OSError), os.fdopen(
                fd, "w", encoding="utf-8") as f:
            fd = None                      # fdopen owns it now
            f.write(str(os.getpid()))
        yield True
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(OSError):
            path.unlink()


#: How long :func:`file_lock` waits before giving up, in seconds. What it
#: guards is a read-modify-write of one small file (or one `git
#: sparse-checkout add`), so a wait this long means a stuck process.
FILE_LOCK_TIMEOUT = 30.0
_FILE_LOCK_POLL = 0.05


def _os_lock(fd: int) -> bool:
    """Try once to take an exclusive lock on ``fd``; True when taken."""
    if sys.platform == "win32":
        import msvcrt
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _os_unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def file_lock(path, timeout: float | None = None, *, what: str = "it",
              strict: bool = True):
    """Hold an exclusive advisory lock on ``path`` for the ``with`` body.

    Unlike :func:`try_lock` this **waits**, up to ``timeout`` seconds
    (:data:`FILE_LOCK_TIMEOUT` by default), and then raises a BoostError
    naming ``what``: its callers are read-modify-writes that must not be
    skipped, where two boost processes overlapping used to drop one update
    while both reported success.

    The lock is the OS's — ``flock`` on POSIX, ``msvcrt.locking`` on
    Windows — so it dies with its process and a killed boost can never leave
    it wedged. ``path`` is a dedicated sidecar, never the file being
    guarded: that one is swapped by ``os.replace``, which would leave the
    lock on an orphaned inode. The sidecar is never deleted either; unlinking
    it while another process waits on it would hand the next process a
    fresh, unlocked file. Not re-entrant: a nested ``file_lock`` on the same
    path in one process waits on itself.

    ``strict=False`` runs the body unlocked when the sidecar cannot be
    created at all (a read-only dir): the write it guards then fails with
    its own, better-worded error, and a lock that cannot be taken must not
    be what reports it.
    """
    path = Path(path)
    wait = FILE_LOCK_TIMEOUT if timeout is None else timeout
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        if strict:
            raise
        yield
        return
    try:
        deadline = time.monotonic() + wait
        while not _os_lock(fd):
            if time.monotonic() >= deadline:
                raise BoostError(
                    "another boost process has held %s for over %gs"
                    % (what, wait),
                    hint="wait for the other boost command to finish, then "
                         "retry (the lock is %s)" % paths.tilde(path))
            time.sleep(_FILE_LOCK_POLL)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                _os_unlock(fd)
    finally:
        os.close(fd)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` so a reader never sees a partial file.

    The bytes go to a temp file in the *same* directory (so the rename stays on
    one filesystem and is atomic), get flushed and fsynced to disk, then swap
    into place with ``os.replace``. An interrupted or concurrent write can no
    longer truncate the target: the previous file survives intact until the
    complete new one atomically replaces it. This is the corruption-safe
    substitute for a bare ``Path.write_text`` on any file boost must not lose —
    the lock file, the config, the pulse journal.

    ``newline="\\n"`` is load-bearing, and it is the one line here that a
    Linux run cannot check. Text mode translates ``"\\n"`` to the platform
    separator on write, so on Windows this wrote CRLF into seventeen of the
    nineteen — measured, not predicted: ``tests (windows-latest, 3.14)`` on
    this branch's parent commit reported ``assert b'\\r' not in
    b'a\\r\\nb\\r\\n'`` against the test below. The other two
    (``rag.py``'s BM25 index and rerank cache) pass bare ``json.dumps`` and
    emit no literal newline at all, so the pin is inert for them.

    **The reader that makes it matter is git, and only one call site hands
    it anything.** ``projectlock.write`` stamps
    ``<repo>/.boost/skill-lock.json``, which that module's own docstring
    says "is meant to be **committed** … git is its history". Everything
    else here is read back through ``json`` or ``read_text``, both of which
    fold. It is explicitly **not** ``sha256_dir``: all eighteen of those
    call sites hash a ``copytree``-populated skill dir or a tap clone, never
    a file this function wrote — an earlier draft of this paragraph claimed
    otherwise and was wrong.

    ``tests/unit/test_text_io_names_its_encoding.py``'s
    ``TestAPinnedWriterReallyEmitsLF`` asserts on bytes rather than on the
    presence of this keyword, because an AST check proves only that it is
    spelled. That test arrived with this change, so it corroborates the pin
    rather than independently motivating it.
    """
    _replace_atomically(Path(path), text, encoding, mode=None)


#: How often, and how far apart, :func:`replace` retries on Windows.
REPLACE_ATTEMPTS = 20
REPLACE_PAUSE = 0.05


def replace(src: str | Path, dst: str | Path) -> None:
    """``os.replace``, retried briefly where Windows refuses it.

    Windows will not replace a file another process holds open without
    ``FILE_SHARE_DELETE`` -- which is every plain ``open()`` -- and says
    ``PermissionError`` (WinError 5) for what is only a reader of the old
    lock mid-``read``. Two boost processes, one reading the project lock and
    one rewriting it, failed the write outright. The reader lets go within
    milliseconds, so wait for it rather than fail; anywhere else the error
    is real and raised at once.
    """
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if sys.platform != "win32" or attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_PAUSE)


def _replace_atomically(path: Path, text: str, encoding: str,
                        mode: int | None) -> None:
    """The temp-file + fsync + ``os.replace`` core of both writers.

    ``mode`` of ``None`` keeps ``mkstemp``'s 0600, which is right for the
    files boost owns; :func:`write_user_file` passes the mode to keep.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # A short fixed prefix, not the file's own name: ``.<name>.XXXXXXXX.tmp``
    # is 14 bytes longer than ``<name>``, so a name that fits the 255-byte
    # component limit as a final path still failed here with ENAMETOOLONG —
    # out of the CLI as a crash, rc 70, for a 246-character workflow.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix=TEMP_PREFIX, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        replace(tmp, str(path))
    except BaseException:
        # Never leave a temp turd behind, and never mask the original error.
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def current_umask() -> int:
    """The process umask, read the only way POSIX offers: set it and put it
    back. Used for the mode a file *created* on the user's behalf gets."""
    mask = os.umask(0)
    os.umask(mask)
    return mask


def user_file_target(path: Path, base=None) -> Path:
    """The file :func:`write_user_file` would write for ``path``, checked.

    A symlink resolves through every hop; a plain path is itself. With
    ``base``, a target outside the repo raises :class:`BoostError` here, so a
    caller changing several files can ask about every one before it changes
    the first: raising at the write itself left an uninstall half-applied.
    """
    path = Path(path)
    target = Path(os.path.realpath(path)) if path.is_symlink() else path
    if base is not None:
        from . import scopes  # local: scopes -> projectlock -> util
        scopes.ensure_in_base(base, target)
    return target


def read_user_text(path: Path) -> str:
    """Read a file the *user* owns exactly as it is on disk.

    The reading half of :func:`write_user_file`. ``read_text`` opens in
    universal-newline mode, which folds every CRLF to LF, so a rule install
    that read ``AGENTS.md`` that way and wrote it back turned a Windows
    checkout's committed file into a whole-file diff. ``newline=""`` keeps
    the line endings, and the writer emits the text unchanged.

    Bytes that are not UTF-8 raise :class:`NotUTF8Error`, a `BoostError`
    naming the file, rather than a ``UnicodeDecodeError`` no caller stops.
    """
    with Path(path).open(encoding="utf-8", newline="") as f:
        try:
            return f.read()
        except UnicodeDecodeError as err:
            raise NotUTF8Error(path, err) from None


def write_user_file(path: Path, text: str, base=None) -> Path:
    """Atomically rewrite a file the *user* owns, keeping its link and mode.

    :func:`atomic_write_text` is for boost's own files, and two of its
    properties are wrong for a context file such as ``~/.claude/CLAUDE.md``
    or a repo's ``GEMINI.md``. ``os.replace`` swaps out the path itself, so
    a symlink to a dotfiles checkout (or ``GEMINI.md -> AGENTS.md``) became a
    detached regular copy, the rule never reached the file the user edits,
    and uninstall could not restore the link. And ``mkstemp`` is always
    0600, so a 0644 ``AGENTS.md`` came back private — a mode change git
    reports on a committed file.

    So a symlink is followed and the write lands on its target, through
    every hop, and the link stays a link. The target keeps its existing
    permission bits; a new file gets ``0o666 & ~umask``, what a plain
    ``open()`` would have given it. With ``base`` (project scope), the
    *resolved* target must still sit inside the repo: a committed link
    pointing out of it is refused rather than written through, the same
    boundary :func:`scopes.ensure_in_base` holds for every project write.
    Returns the path actually written.
    """
    target = user_file_target(path, base)
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = 0o666 & ~current_umask()
    _replace_atomically(target, text, "utf-8", mode=mode)
    return target


def positive_int(s: str) -> int:
    """argparse ``type=`` for count flags (``-n``/``--limit``): an int >= 1.

    A bare ``type=int`` lets a negative through, and every count flag in boost
    ends up as a slice bound or a ``git log -n`` argument — where a negative
    silently *inverts* the request instead of failing it. Rejecting it at parse
    time is the only place the user still sees a usable error.
    """
    # Local import: argparse is not on the `boost --help` startup path, and
    # util is (via core.logs). Every caller of this function is a command
    # module that has already imported argparse through cliparse.
    import argparse

    try:
        v = int(s)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("invalid int value: %r" % s) from None
    if v < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return v


def port_number(s: str) -> int:
    """argparse ``type=`` for a TCP port (``serve --port``): an int in 0-65535.

    The ceiling is the point: an out-of-range number travelled all the way to
    ``socket.bind``, which raises ``OverflowError`` — not an ``OSError`` boost
    frames — so a typo exited 70 and wrote a crash report inviting the reader
    to file a GitHub issue.

    **Zero is valid and deliberately allowed**, which is why this is not
    :func:`positive_int` with a maximum bolted on. ``bind(("127.0.0.1", 0))``
    is the standard "give me any free port", and boost's own functional tests
    start the server that way; rejecting it would turn a working idiom into a
    parse error to make the bound look tidier.
    """
    import argparse

    try:
        v = int(s)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("invalid int value: %r" % s) from None
    if not 0 <= v <= 65535:
        raise argparse.ArgumentTypeError("must be 0-65535")
    return v


def score_int(s: str) -> int:
    """argparse ``type=`` for ``lint --min``: an int in [0, 100].

    Scores are capped at 100 (``score_skill``), so a bare ``type=int`` let
    ``--min 500`` through and failed every skill, and a negative ``--min``
    passed every skill silently rather than being rejected as meaningless.
    Unlike :func:`positive_int`, 0 is a legitimate value here — "fail nobody".
    """
    import argparse

    try:
        v = int(s)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("invalid int value: %r" % s) from None
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return v


def nonempty_str(s: str) -> str:
    """argparse ``type=`` for a NAME, path or value that was given explicitly.

    An empty string is not the same as an omitted argument, but every handler
    that branches on ``if args.name:`` treats it as one: ``attest --verify ""``
    verified every skill, ``cohort apply ""`` applied every cohort, ``tap ""``
    and ``import ""`` read ``Path("")`` as the current directory, and
    ``export -o ""`` wrote the default filename. ``boost attest "$UNSET"`` in a
    script is the usual way to get here, and it went green having done the
    wrong thing. Rejecting it at parse time makes it a usage error (exit 2)
    naming the argument; an *omitted* optional NAME keeps meaning "all",
    because argparse never runs ``type=`` on a missing positional.

    The value is returned unchanged -- whitespace inside a real value is the
    caller's business; only a value that is nothing *but* whitespace is
    refused. A string ``default=`` is passed through ``type=`` too, so an
    argument using this must default to ``None``, never ``""``.
    """
    import argparse

    if not s.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return s


def resolve_exe(argv: list[str]) -> list[str]:
    """``argv`` with ``argv[0]`` swapped for the path ``shutil.which`` finds.

    On Windows npm installs ``npx``, ``gemini`` and an npm-installed
    ``claude`` only as ``.cmd`` shims. ``shutil.which`` honours PATHEXT and
    finds them, but ``CreateProcess`` appends only ``.exe`` to a bare name, so
    launching the bare name raises ``FileNotFoundError`` right after the
    ``which`` check said the tool exists. Launching the resolved path runs the
    shim. Unresolvable names pass through unchanged, so the caller's own
    ``OSError`` handling still reports them. Returns a new list.
    """
    found = shutil.which(argv[0]) if argv else None
    return [found, *argv[1:]] if found else argv.copy()


def now_iso() -> str:
    """Return UTC now as ``'2026-07-16T01:00:00Z'`` (what ``rel_time`` parses)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def user() -> str:
    """Best-effort login name for journal/team attribution; 'unknown' if the
    environment has no resolvable user (getpass raises in some sandboxes)."""
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def iso_from_epoch(when: float) -> str:
    """A Unix time in :func:`now_iso`'s format."""
    return datetime.fromtimestamp(when, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_from_iso(iso) -> float | None:
    """A :func:`now_iso`-format time as a Unix time; None for anything else."""
    if not isinstance(iso, str):
        return None
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC).timestamp()
    except ValueError:
        return None


def rel_time(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(UTC) - then).total_seconds()
    if secs < 0:
        # A stamp from a machine whose clock runs ahead (the feed is shared
        # via `boost onboard`). Floored, it read "1s ago" however far ahead
        # it was; a minute of skew is "just now", more is said plainly.
        return "just now" if secs > -60 else "in the future"
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def iso_date(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '2026-07-16', matching git's `--date=short`.

    Same parse and same fallback (`iso` itself, or "?" when empty) as
    `rel_time` — a caller that mixes a git-log short date with this on
    different rows gets one format either way, not "3h ago" beside
    "2026-07-16".
    """
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return iso or "?"
    return then.strftime("%Y-%m-%d")


def human_duration(seconds: float) -> str:
    """A short, honest duration: ``'45s'``, ``'12m'``, ``'2h 5m'``.

    Coarse on purpose. This labels an estimate that is extrapolated from a
    partial run, so seconds of precision on a two-hour figure would claim an
    accuracy the number does not have.
    """
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "%ds" % seconds
    minutes = seconds // 60
    if minutes < 60:
        return "%dm" % minutes
    hours, minutes = divmod(minutes, 60)
    return "%dh %dm" % (hours, minutes) if minutes else "%dh" % hours


def human_size(n: int) -> str:
    """Format a byte count for humans: ``1536`` -> ``'1.5KB'``.

    Whole bytes (``'512B'``), one decimal above; never goes past GB.
    """
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (size, unit)
        size /= 1024.0
    return str(size)


def head_lines(text: str, cap: int) -> tuple[list[str], int]:
    """The first `cap` lines of `text`, and how many were left out.

    A preview that silently stops is worse than a short one: `onboard
    --dry-run` cut every file at 24 lines with no marker, so its lock preview
    ended mid-object and read as a truncated *file* rather than a truncated
    *view* of one. Callers print the remainder; returning the count rather than
    a formatted ellipsis keeps the wording with the emitter that owns the pane.
    """
    lines = text.splitlines()
    return lines[:cap], max(len(lines) - cap, 0)


def _slug_or_none(name: str) -> str | None:
    """``name`` as ``[a-z0-9-]``, accents folded to their base letter, or None.

    Folded under NFKD before the character class applies, so one typed name is
    one slug however its bytes arrived: a precomposed ``é`` (NFC) used to be
    dropped outright while ``e`` + U+0301 (NFD, what a macOS paste often
    produces) kept its ``e`` — ``profile save café`` wrote a file one letter
    short of the ``cafe.json`` that ``profile show café`` looked for. The same fold the
    catalog applies to a frontmatter name (``catalog._entry_slug``).
    """
    folded = "".join(c for c in unicodedata.normalize("NFKD", name)
                     if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9-]+", "-", folded.strip().lower()).strip("-") or None


def slugify(name: str) -> str:
    """Lowercase ``name`` into a ``[a-z0-9-]`` slug; empty result -> ``'skill'``."""
    return _slug_or_none(name) or "skill"


#: The longest single path component APFS and ext4 will take, in bytes.
#: (NTFS counts 255 UTF-16 units instead, so it takes some names this refuses;
#: refusing them everywhere keeps the answer the same on every OS.)
#: Past it the OS refuses even to *stat* the path, and `Path.exists()` is not
#: total: pathlib swallows ENOENT, ENOTDIR, EBADF and ELOOP, but ENAMETOOLONG
#: raises straight out as a bare OSError that the CLI frames as a crash.
MAX_COMPONENT_BYTES = 255


def _check_component(part: str, what: str) -> None:
    size = len(part.encode("utf-8", "surrogateescape"))
    if size > MAX_COMPONENT_BYTES:
        # Over 255 bytes is at least 64 characters (UTF-8 is at most four
        # bytes a character), so the echo is always a truncation.
        raise BoostError(
            "%s is too long (%d bytes, limit %d): %r"
            % (what, size, MAX_COMPONENT_BYTES, part[:40] + "…"),
            hint="APFS and ext4 refuse a file or directory name over %d "
                 "bytes" % MAX_COMPONENT_BYTES)


#: What boost names its own temp files and staging dirs with. Short and
#: fixed, so a temp beside a long final name is no longer than the name, and
#: dot-led, so a leftover reads as nobody's skill (``store._may_hold_skill``).
TEMP_PREFIX = ".boost-"

#: The longest suffix an install appends to an item's name for a final path:
#: a skill is a bare dir (and a bare link), a rule a Cursor ``<name>.mdc``, a
#: workflow a Gemini ``<name>.toml``.
_ITEM_SUFFIX = {"skill": "", "rule": ".mdc", "workflow": ".toml"}


def check_item_name(name: str, kind: str = "skill") -> str:
    """Return ``name``, or raise a BoostError if an install of it cannot fit.

    The catalog indexes any name a frontmatter gives, and search and doctor
    show it as installable; the OS refusing it came from deep inside the
    install — a staging ``mkdtemp`` (hinted as "free space") or a workflow's
    temp file (a crash). Asked up front, against the longest file name the
    install would write for that kind.

    It is also the one answer to "is this a name boost installs under?":
    a name that is not a safe path component is refused here with a hint,
    rather than later as a bare "invalid skill name" from the store, and
    `boost lint` asks the same question through :func:`item_name_error`.
    """
    # A namespaced slash command (`frontend/test`, `workflows.NAMESPACE_SEP`)
    # is a dir per namespace plus a file, each one a component of its own.
    *namespace, leaf = name.split("/") if kind == "workflow" else [name]
    if not all(is_safe_component(part) for part in (*namespace, leaf)):
        raise BoostError("invalid %s name %r" % (kind, name), hint=NAME_RULE_HINT)
    for part in namespace:
        _check_component(part, "%s name" % kind)
    _check_component(leaf + _ITEM_SUFFIX.get(kind, ".toml"), "%s name" % kind)
    return name


#: What a valid item name may contain, said once for every refusal of one.
NAME_RULE_HINT = ("a name may use only letters, digits, '.', '_' and '-' "
                  "(e.g. my-skill)")


def item_name_error(name: str, kind: str = "skill") -> str | None:
    """Why ``name`` cannot be installed as a ``kind``, or None when it can.

    :func:`check_item_name` as a predicate, for a caller that reports rather
    than raises — `boost lint`, whose pass has to mean `boost import` takes
    the skill as written.
    """
    try:
        check_item_name(name, kind)
    except BoostError as exc:
        return str(exc)
    return None


def frontmatter_text(meta: dict, key: str) -> str:
    """A scalar frontmatter field as stripped text; a nested map reads as "".

    `frontmatter.parse_block` keeps `author:`/`metadata:`-style maps as dicts,
    and `str()` of one would put a Python repr into a name or description.
    This is the reading the catalog indexes (`catalog._text`), so lint scores
    the same text search will show.
    """
    val = meta.get(key)
    if isinstance(val, dict):
        return ""
    return str(val or "").strip()


def _yaml_kind(val: object) -> str:
    if isinstance(val, dict):
        return "a map"
    if isinstance(val, list):
        return "a list"
    if isinstance(val, bool):
        return "a boolean"
    return "a number" if isinstance(val, int | float) else type(val).__name__


def string_field_error(meta: dict, key: str) -> str | None:
    """Why frontmatter ``key`` is not a usable string, or None when it is.

    Missing (absent, empty, blank) and present-but-not-a-string are different
    faults: `description:` written as a map, or `name: true`, is truthy, so a
    presence check passed it, while the catalog reads a map as "" (and falls
    back to the body's first line) and a bool as ``"True"``.
    """
    val = meta.get(key)
    if val is None or (isinstance(val, str) and not val.strip()):
        return "missing required field: %s" % key
    if not isinstance(val, str):
        return "`%s` must be a string, not %s" % (key, _yaml_kind(val))
    return None


def frontmatter_name(meta: dict, default: str) -> str:
    """The name a local install reads from ``meta``, else ``default``.

    Raises BoostError for a name that is present but not a string: `name:
    [a, b]` used to install as ``"['a', 'b']"`` (refused as a path) and
    `name: true` as ``True``, a name the SKILL.md never says.
    """
    val = meta.get("name")
    if val is None or val == "":
        return default
    if not isinstance(val, str):
        raise BoostError("frontmatter `name` must be a string, not %s"
                         % _yaml_kind(val),
                         hint="write it as plain text, e.g. `name: my-skill`")
    return val.strip() or default


def check_path_length(path: Path, *, what: str = "path") -> Path:
    """Return ``path``, or raise a BoostError if any component is too long.

    Call it on a user-supplied path *before* the first ``exists()`` — a pure
    string check, so it answers the same on every OS rather than depending on
    which errno a given filesystem raises.
    """
    for part in Path(path).parts:
        _check_component(part, what)
    return path


def write_unclaimed(directory: Path, stem: str, suffix: str, text: str) -> Path:
    """Write ``text`` to ``directory/<stem><suffix>`` without replacing anything.

    When that name is taken, ``<stem>.1<suffix>``, ``<stem>.2<suffix>``, ... are
    tried in turn. Each attempt opens with ``"x"``, so a file that appears
    between the check and the write is skipped rather than clobbered. For a
    file written on the user's behalf that they never named: the name is
    boost's guess, so a file already sitting there is theirs, not ours.
    """
    n = 0
    while True:
        dest = directory / ("%s%s%s" % (stem, ".%d" % n if n else "", suffix))
        try:
            with dest.open("x", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            return dest
        except FileExistsError:
            n += 1
        except OSError as exc:
            raise BoostError("cannot write %s: %s" % (dest, exc)) from exc


def resolve_slug(raw: str, *, what: str = "name") -> str:
    """Slugify a user-typed ``raw``, refusing one with nothing to slug.

    The one shared helper for a user-typed name that must become a slug:
    unlike :func:`slugify` (used where indexing must never fail on a hostile
    entry), this never falls back to a placeholder — an empty or
    punctuation-only name is the user's mistake to report, not boost's name
    to invent. It also prints a note whenever the slug differs from what was
    typed, so a name is never silently swapped for another without the user
    seeing it — the same silent swap that let ``boost distill -o`` write a
    path its own install hint then refused, and let two differently-typed
    profile names collide on one file.

    The note goes to stderr: it is a notice about the input, not output, and
    every caller may be speaking ``--json`` on stdout — ``boost profile save
    "My Team" --json`` printed it ahead of the JSON object, which then failed
    to parse.
    """
    slug = _slug_or_none(raw)
    if slug is None:
        # `名前` has letters — just none a slug can hold, and saying it had
        # none told the user their input was empty.
        if any(c.isalnum() for c in raw):
            raise BoostError("%s needs ASCII letters or digits: %r" % (what, raw),
                             hint="a name becomes a file name made of a-z, "
                                  "0-9 and '-'")
        raise BoostError("%s has no letters or digits: %r" % (what, raw))
    _check_component(slug, what)
    if slug != raw:
        out.info("using %s %r (from %r)" % (what, slug, raw), stream=sys.stderr)
    return slug


# A catalog name becomes a path component (a rule file, a workflow file, a store
# dir), so it has to be one segment with no traversal. Anchored, and "." / ".."
# excluded separately because both match the character class.
_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9._-]+")


def is_safe_component(name: str) -> bool:
    """True if ``name`` is usable as a single path component.

    The one place to ask "can this name be joined onto a directory?". A tap
    controls its own frontmatter, so a name like ``../../../../.ssh/authorized_keys``
    is attacker-supplied input on the way to an install path.
    """
    return bool(_SAFE_COMPONENT.fullmatch(name)) and name not in {".", ".."}


def safe_component(name: str) -> str:
    """``name`` if it is a safe path component, else a slug of it.

    Used where a usable name is required and rejecting is not an option (catalog
    indexing must not fail on one hostile entry). ``slugify`` alone is wrong here
    because it also mangles names that were already fine — ``ok_name-1.2`` would
    become ``ok-name-1-2`` — so only unsafe names are rewritten.
    """
    return name if is_safe_component(name) else slugify(name)


def _hashed_files(root: Path) -> list[Path]:
    """The files :func:`sha256_dir` and :func:`exec_bits` read, sorted."""
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )


def exec_bits(path: Path) -> list[str] | None:
    """The files under ``path`` whose owner exec bit is set, as sorted
    relative POSIX paths — the same files :func:`sha256_dir` hashes.

    A mode is not content, so :func:`sha256_dir` does not see one: a script
    made executable upstream read as up to date, and a ``chmod -x`` on the
    store copy passed `verify`. Kept apart from the hash rather than folded
    into it, so every lock row written before this still verifies; a row
    records this list as ``exec`` (see :func:`integrity.exec_drifted`).

    None on Windows, which has no exec bit: ``os.stat`` reports one by
    extension, so a project lock written on a Mac would read every script
    as modified there, and the reverse. None is recorded and compared as
    "unknown", never as an empty list.
    """
    if os.name == "nt":
        return None
    root = Path(path)
    return [f.relative_to(root).as_posix() for f in _hashed_files(root)
            if f.stat().st_mode & stat.S_IXUSR]


#: How far into a file a NUL byte makes it binary. ``updatediff.read_file``
#: sniffs the same window, so the two agree about which files are text.
BINARY_SNIFF = 8000


def hashed_bytes(data: bytes) -> bytes:
    """``data`` as :func:`sha256_dir` hashes it: CRLF folded to LF in text.

    A file with a NUL in its first :data:`BINARY_SNIFF` bytes is binary and
    hashed as it is. Text is folded because git's ``core.autocrlf`` (Git for
    Windows' default) checks committed copies out CRLF, and a hash over raw
    bytes read that conversion as a hand edit: every Windows clone of a
    project failed `verify`. Rules and workflows were already immune, being
    read as text. Bytes, not a decode: a file that is not UTF-8 hashes the
    same before and after.
    """
    if b"\0" in data[:BINARY_SNIFF]:
        return data
    return data.replace(b"\r\n", b"\n")


def sha256_dir(path: Path, *, raw: bool = False) -> str:
    """Deterministic content hash of a directory tree (paths + contents).

    Contents as :func:`hashed_bytes` sees them, so a tree that differs only
    in CRLF vs LF hashes alike. A tree with no CRLF in a text file hashes
    exactly as it did over raw bytes, which is most lock rows; ``raw=True``
    is that old hash, for the rows whose copy held CRLF when it was recorded
    (:func:`sha256_matches`).
    """
    h = hashlib.sha256()
    root = Path(path)
    for f in _hashed_files(root):
        data = f.read_bytes()
        h.update(f.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(data if raw else hashed_bytes(data))
        h.update(b"\0")
    return h.hexdigest()


def sha256_matches(path: Path, recorded: str | None) -> bool:
    """Whether the tree at ``path`` holds what a lock row's ``recorded`` names.

    The question every "is this copy intact?" check asks. A row written now
    records :func:`sha256_dir`; one written before it was line-ending blind
    records the raw-byte hash, so either one matching is a match: no lock
    migration, and no copy that verified before fails now. The raw walk only
    runs on a mismatch. An empty ``recorded`` matches nothing.
    """
    if not recorded:
        return False
    return any(sha256_dir(path, raw=raw) == recorded for raw in (False, True))


def dir_size(path: Path) -> int:
    """Sum the byte size of every regular file under ``path``, recursively.

    A symlink is not a regular file, whatever it points at: this is what the
    tree occupies on disk. Following links counted a target's bytes a second
    time, or bytes outside the tree, or nothing once it dangled, and
    ``compact`` reports freed space as this before minus this after, so a
    link whose target the narrow removed made its live figure overstate the
    run. What a *copy* of the tree will hold is :func:`copied_files`.
    """
    return sum(p.lstat().st_size for p in Path(path).rglob("*")
               if p.is_file() and not p.is_symlink())


def copied_files(path: Path) -> list[Path]:
    """The files ``install`` will copy out of ``path``, in walk order.

    Every link counts as what it points at, a linked *directory* included,
    and an ``IGNORED`` name is skipped at any depth. ``store._copy_tree``
    keeps a link inside the skill as a link and skips one out of the tap, so
    this is what the skill *reaches*, an upper bound on the copy's bytes.
    ``Path.rglob`` does not descend through a directory link, so sizing a
    skill from the tap that way said 61 B and 1 file for a skill that
    installs as 861 B and 2. A dangling link copies nothing (install skips
    it and says so). Two paths to one directory are two copies; only a
    directory that resolves to one of its own ancestors — a link cycle — is
    not descended, so the walk cannot hang.
    """
    top = Path(path)
    files: list[Path] = []
    for root, dirs, names in os.walk(path, followlinks=True):
        here = Path(root)
        real = os.path.realpath(here)
        if here != top and any(os.path.realpath(p) == real
                               for p in here.parents
                               if p == top or top in p.parents):
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in IGNORED]
        for name in names:
            f = Path(root) / name
            if name not in IGNORED and f.is_file():
                files.append(f)
    return files


def semver_tuple(v: str):
    """Coerce ``v`` to a 3-int tuple: ``'1.2'`` -> ``(1, 2, 0)``.

    First three digit runs, zero-padded; ``None`` or junk -> ``(0, 0, 0)``.
    """
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def semver_gt(a: str, b: str) -> bool:
    """Return ``True`` when version ``a`` is strictly newer than ``b``."""
    return semver_tuple(a) > semver_tuple(b)


def read_text_arg(value: str, flag: str, stdin=None) -> str:
    """Resolve a free-text option the way curl does, and refuse it empty.

    ``-`` reads standard input, ``@PATH`` reads that file (``~`` expanded),
    and anything else is the text itself. The result is stripped, and an
    empty one raises: a command that folds this text into a file would
    otherwise write a heading with nothing under it and call that a change.
    ``flag`` names the option in the error (``--feedback``); ``stdin`` is
    for tests, and defaults to ``sys.stdin`` read at call time.
    """
    if value == "-":
        stream = stdin if stdin is not None else sys.stdin
        empty = ("%s - read nothing from stdin" % flag,
                 "pipe the text in, or pass it as the value itself")
        if stream is None:
            # fd 0 closed at launch (`<&-`): Python sets sys.stdin to None.
            raise BoostError(empty[0], hint=empty[1])
        # The bytes underneath, decoded the way the `@FILE` arm decodes: a
        # text stream's strict decode raises UnicodeDecodeError on a stray
        # byte, and that is a traceback, not a BoostError.
        raw = getattr(stream, "buffer", None)
        text = (raw.read().decode("utf-8", errors="replace") if raw is not None
                else stream.read())
    elif value.startswith("@"):
        name = value[1:]
        hint = ("`%s @FILE` reads FILE; pass the text itself, or `-` to read "
                "stdin" % flag)
        # A bare `@` is Path(""), the current directory, which read as the
        # riddle "can't read --feedback @: Is a directory".
        if not name.strip():
            raise BoostError("%s @ needs a file path" % flag, hint=hint)
        try:
            # Replaced, not strict: a stray byte would otherwise escape as a
            # UnicodeDecodeError, which is not an OSError, i.e. a traceback.
            text = paths.expand(name).read_text(encoding="utf-8",
                                                errors="replace")
        except OSError as e:
            raise BoostError("can't read %s %s: %s"
                             % (flag, value, e.strerror or e),
                             hint=hint) from None
        empty = ("%s %s: %s is empty" % (flag, value, name),
                 "write the text into the file, or pass it as the value itself")
    else:
        text = value
        empty = ("%s is empty" % flag,
                 "pass the text itself, `%s -` to read stdin, or `%s @FILE` "
                 "to read a file" % (flag, flag))
    text = text.strip()
    if not text:
        raise BoostError(empty[0], hint=empty[1])
    return text


def score_skill(skill_dir: Path) -> tuple[int, list[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: list[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    if frontmatter.unclosed(text):
        # Every field below would read as absent — the block never parsed —
        # so scoring by field would report three symptoms of one cause. The
        # broken fence is the whole diagnosis.
        return 0, [frontmatter.UNCLOSED_NOTE]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if frontmatter_text(meta, "name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = frontmatter_text(meta, "description")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
        if len(desc) > 1024:
            # The Agent Skills format caps descriptions at 1024 chars and
            # hosts truncate past it — a longer one still lints clean today,
            # so an author never learns their description is being cut.
            score -= 10
            notes.append("description exceeds 1024 chars — agent hosts truncate it")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.MULTILINE):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if ("```" in body or re.search(r"^\d+\. ", body, re.MULTILINE)
            or re.search(r"^- ", body, re.MULTILINE)):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def lint_errors(skill_dir: Path) -> list[str]:
    """Hard-failure reasons for a skill dir, independent of `score_skill`'s score.

    A missing SKILL.md, an unclosed frontmatter fence, or a missing required
    field (`name`/`description`) fails a skill regardless of how high its
    heuristic score lands. Split out so `boost lint` and `boost test` can
    share one predicate instead of drifting — a skill scoring 85 with no
    `description` used to pass `test` and fail `lint`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    if not skill_md.exists():
        return ["missing SKILL.md"]
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if frontmatter.unclosed(text):
        return [frontmatter.UNCLOSED_NOTE]
    meta, _body = frontmatter.parse(text)
    errors = [e for e in (string_field_error(meta, "name"),
                          string_field_error(meta, "description")) if e]
    name = meta.get("name")
    if isinstance(name, str) and name.strip():
        # The name `boost import` would install under — the same check, so a
        # pass here means import takes the skill as written (and a tap
        # install does not silently slug it into a name the file never says).
        bad = item_name_error(name.strip())
        if bad:
            errors.append(bad)
    return errors


def lint_label(skill_dir: Path) -> str:
    """The name to show for a skill dir in `boost lint`: the one boost installs
    it under (its frontmatter `name`), falling back to the directory."""
    from . import frontmatter

    try:
        text = (Path(skill_dir) / "SKILL.md").read_text(encoding="utf-8",
                                                        errors="replace")
    except OSError:
        return Path(skill_dir).name
    if frontmatter.unclosed(text):
        return Path(skill_dir).name
    name = frontmatter.parse(text)[0].get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return Path(skill_dir).name


def name_dir_note(skill_dir: Path) -> str | None:
    """A note when a skill's frontmatter `name` differs from its directory.

    Not an error — boost installs under the frontmatter name either way — but
    the Agent Skills format expects the two to match, and an author linting
    `skills/mismatch` should learn it installs as something else.
    """
    label = lint_label(skill_dir)
    if label == Path(skill_dir).name:
        return None
    return "name %r differs from its directory %r — it installs as %r" % (
        label, Path(skill_dir).name, label)


def lint_failed(skill_dir: Path, score: int, min_score: int = 40) -> bool:
    """True when `boost lint` would fail this skill dir.

    A skill fails lint when its score is under `min_score` *or* it has any
    hard error from `lint_errors` — the second clause is what keeps a
    high-scoring-but-incomplete skill (missing `name`/`description`, an
    unclosed frontmatter fence, no SKILL.md) from passing on score alone.
    """
    return score < min_score or bool(lint_errors(skill_dir))


def shell_arg(arg: str) -> str:
    """`arg` as one argument a user can paste into their shell."""
    if sys.platform == "win32":
        # cmd.exe and PowerShell both take double quotes; neither takes the
        # single quotes `shlex.quote` emits.
        return '"%s"' % arg if any(c.isspace() for c in arg) else arg
    return shlex.quote(arg)


def shell_join(argv: list[str]) -> str:
    """``argv`` as one command line a user can paste into their shell.

    Each word goes through :func:`shell_arg`, so on POSIX this is
    ``shlex.join`` and on Windows it keeps that function's double quotes.
    """
    return " ".join(shell_arg(a) for a in argv)
