"""Small shared utilities: time, hashing, versions, skill quality scoring."""
from __future__ import annotations

import contextlib
import getpass
import hashlib
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

IGNORED = {".git", "__pycache__", ".DS_Store"}


def _clear_readonly_and_retry(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path) -> None:
    """``shutil.rmtree`` that survives read-only files.

    Git writes objects under ``.git/objects/`` read-only; POSIX still lets the
    owner unlink a read-only file (permission lives on the directory), but
    Windows refuses outright. Clear the read-only bit and retry once per
    failure — ``onexc`` on 3.12+, ``onerror`` below that (both get the same
    handler; it ignores the exception argument either way).
    """
    if sys.version_info >= (3, 12):
        shutil.rmtree(str(path), onexc=_clear_readonly_and_retry)
    else:
        shutil.rmtree(str(path), onerror=_clear_readonly_and_retry)


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
        with contextlib.suppress(OSError), os.fdopen(fd, "w") as f:
            fd = None                      # fdopen owns it now
            f.write(str(os.getpid()))
        yield True
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(OSError):
            path.unlink()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` so a reader never sees a partial file.

    The bytes go to a temp file in the *same* directory (so the rename stays on
    one filesystem and is atomic), get flushed and fsynced to disk, then swap
    into place with ``os.replace``. An interrupted or concurrent write can no
    longer truncate the target: the previous file survives intact until the
    complete new one atomically replaces it. This is the corruption-safe
    substitute for a bare ``Path.write_text`` on any file boost must not lose —
    the lock file, the config, the pulse journal.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        # Never leave a temp turd behind, and never mask the original error.
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


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


def now_iso() -> str:
    """Return UTC now as ``'2026-07-16T01:00:00Z'`` (what ``rel_time`` parses)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def user() -> str:
    """Best-effort login name for journal/team attribution; 'unknown' if the
    environment has no resolvable user (getpass raises in some sandboxes)."""
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def rel_time(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


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


def slugify(name: str) -> str:
    """Lowercase ``name`` into a ``[a-z0-9-]`` slug; empty result -> ``'skill'``."""
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "skill"


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


def sha256_dir(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(f.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def dir_size(path: Path) -> int:
    """Sum the byte size of every regular file under ``path``, recursively."""
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def semver_tuple(v: str):
    """Coerce ``v`` to a 3-int tuple: ``'1.2'`` -> ``(1, 2, 0)``.

    First three digit runs, zero-padded; ``None`` or junk -> ``(0, 0, 0)``.
    """
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def semver_gt(a: str, b: str) -> bool:
    """Return ``True`` when version ``a`` is strictly newer than ``b``."""
    return semver_tuple(a) > semver_tuple(b)


def score_skill(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
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
