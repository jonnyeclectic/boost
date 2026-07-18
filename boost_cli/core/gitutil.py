"""Thin git wrapper (stdlib subprocess only)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError


def has_git() -> bool:
    return shutil.which("git") is not None


def run(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def clone_shallow(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


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
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def remote_url(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def log_for_path(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def is_repo(path: Path) -> bool:
    return (Path(path) / ".git").exists()
