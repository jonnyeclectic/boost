"""Thin git wrapper (stdlib subprocess only)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError


def has_git() -> bool:
    """Return True when a `git` executable is on PATH."""
    return shutil.which("git") is not None


def run(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    """Run `git *args` with captured text output; return the CompletedProcess.

    Raises BoostError if git is missing, on timeout, or (when `check`)
    on nonzero exit.
    """
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout)) from None
    if check and proc.returncode != 0:
        raise BoostError("git %s failed: %s"
                         % (args[0], _git_error(proc.stderr or proc.stdout or "")))
    return proc


def _git_error(text: str) -> str:
    """Pull the one useful line out of git's multi-line failure output.

    git states the cause first and then advises, so the LAST line is usually the
    tail of a prose hint. A missing remote prints::

        fatal: '/nope' does not appear to be a git repository
        fatal: Could not read from remote repository.
        <blank>
        Please make sure you have the correct access rights
        and the repository exists.

    Taking the last line surfaced "and the repository exists." — a sentence
    fragment, with the one line that names the bad path thrown away. Prefer the
    first ``fatal:``/``error:`` line, which is git's own convention for the
    cause, and fall back to the last non-empty line for output that has neither.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for line in lines:
        low = line.lower()
        if low.startswith(("fatal:", "error:")):
            return line
    return lines[-1] if lines else "unknown error"


# git's remote-helper transports run arbitrary commands straight from the URL
# (notably `ext::sh -c …`), so refuse them outright — boost only ever clones
# real http(s)/ssh/git remotes.
_UNSAFE_TRANSPORTS = ("ext::", "file::", "fd::")


def clone_shallow(url: str, dest: Path) -> None:
    """Shallow-clone (`--depth 1`) `url` into `dest`, creating parent dirs.

    Raises BoostError for unsafe remote-helper transports like `ext::`.
    """
    if url.lstrip().lower().startswith(_UNSAFE_TRANSPORTS):
        raise BoostError(
            "refusing to clone via unsafe git transport: %s" % url,
            hint="use an https://, ssh://, or git@ remote")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # `-c core.autocrlf=false`: check out tap content byte-for-byte. On Windows
    # the default `autocrlf=true` rewrites LF->CRLF on checkout, which would
    # change the bytes of a signed manifest (core.provenance) and any content we
    # digest for integrity — so a tap that verifies on Linux would fail on
    # Windows. Forcing it off makes a clone identical across platforms.
    # `--` ends option parsing so a URL beginning with `-` cannot be read as a
    # git flag — argument-injection defense-in-depth beside registry.parse_spec.
    run(["clone", "--depth", "1", "--quiet", "-c", "core.autocrlf=false",
         "-c", "core.eol=lf", "--", url, str(dest)], timeout=600)


def pull(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def head_commit(repo: Path) -> str:
    """Return the full HEAD commit hash of `repo`, or "" if unresolvable."""
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def remote_url(repo: Path) -> str:
    """Return the URL of `repo`'s `origin` remote, or "" if it has none."""
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def log_for_path(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def is_repo(path: Path) -> bool:
    """Return True when `path` contains a `.git` entry."""
    return (Path(path) / ".git").exists()
