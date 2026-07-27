"""How this boost was installed, and the command that upgrades it in place.

`boost self-update` assumed a git checkout and told everyone else to abandon
their install method — but the documented way in is `pipx install
boost-skill-cli` or `pip install boost-skill-cli`, where the package lives in
site-packages and there is nothing to `git pull`. This resolves the install
method from evidence on disk and hands the command layer the exact argv that
upgrades *this* copy.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError
from . import gitutil, paths

DIST = "boost-skill-cli"

GIT = "git"
PIPX = "pipx"
UV_TOOL = "uv-tool"
PIP = "pip"
UNKNOWN = "unknown"

# `boost --version` prints "boost <version>"; anything else means we did not
# actually observe a version and must not report one.
_VERSION_LINE = re.compile(r"^boost\s+(\S+)$", re.MULTILINE)


def installed_version() -> Optional[str]:
    """Version recorded in installed package metadata, or None.

    None is the useful answer, not a failure: it means no Python package
    manager has a record of this boost, so none of them can upgrade it.
    """
    try:
        from importlib.metadata import version
        return version(DIST)
    except Exception:
        return None


def detect(root: Optional[Path] = None, prefix: Optional[Path] = None,
           metadata_version=None) -> str:
    """Resolve how this boost was installed.

    Order matters. A source checkout wins first — that includes `pip install
    -e .`, where the package metadata exists too but `git pull` is what the
    user means. Then the two managers that own a private venv and leave a
    receipt inside it. Then plain pip, but only if pip actually has a record
    of the distribution: telling someone to `pip install --upgrade` a boost
    that pip never installed sends them chasing a package that isn't there.
    """
    root = paths.repo_root() if root is None else Path(root)
    if gitutil.is_repo(root):
        return GIT
    prefix = Path(sys.prefix) if prefix is None else Path(prefix)
    if (prefix / "pipx_metadata.json").is_file():
        return PIPX
    if (prefix / "uv-receipt.toml").is_file():
        return UV_TOOL
    # Resolved here, not as a default argument: a default binds the function
    # object once at import, which silently defeats every attempt to swap it —
    # including a test's, which is how a test of the "nothing installed this"
    # branch ended up running a real `pip install` against PyPI.
    lookup = installed_version if metadata_version is None else metadata_version
    return PIP if lookup() else UNKNOWN


def _require(tool: str) -> str:
    """Absolute path to `tool`, or a BoostError naming what is missing.

    Falling back to another manager here would upgrade a different copy of
    boost — or none at all — while reporting success.
    """
    found = shutil.which(tool)
    if not found:
        raise BoostError(
            "boost was installed with %s, but %s is not on PATH" % (tool, tool),
            hint="install %s, or upgrade manually with `%s upgrade %s`"
                 % (tool, tool, DIST))
    return found


def upgrade_command(method: str) -> List[str]:
    """The argv that upgrades boost for `method`."""
    if method == PIPX:
        return [_require("pipx"), "upgrade", DIST]
    if method == UV_TOOL:
        return [_require("uv"), "tool", "upgrade", DIST]
    if method == PIP:
        # sys.executable, never a bare `pip`: the pip first on PATH can belong
        # to a different interpreter than the one running boost, and upgrading
        # that one leaves this install exactly where it was while printing
        # every sign of success.
        return [sys.executable, "-m", "pip", "install", "--upgrade", DIST]
    raise BoostError(
        "cannot work out how boost was installed, so it cannot update itself",
        hint="upgrade with your package manager, e.g. `pipx upgrade %s`" % DIST)


def run_upgrade(cmd: List[str], timeout: float = 300.0):
    """Run the upgrade, raising BoostError with the manager's own last words."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as err:
        raise BoostError("could not run %s" % " ".join(cmd),
                         hint=str(err)) from err
    if proc.returncode != 0:
        detail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()
        raise BoostError(
            "upgrade failed (%s exited %d)" % (Path(cmd[0]).name, proc.returncode),
            hint=detail[-1] if detail else "re-run the command by hand to see why")
    return proc


def observed_version(timeout: float = 30.0) -> Optional[str]:
    """Ask a freshly-spawned boost what version it is now, or None.

    This process imported its own version before the upgrade ran, so it cannot
    answer the question. None means "we did not see one" — better to say
    nothing than to report a version we never observed.
    """
    try:
        proc = subprocess.run([str(paths.launcher()), "--version"],
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    match = _VERSION_LINE.search(proc.stdout or "")
    return match.group(1) if match else None
