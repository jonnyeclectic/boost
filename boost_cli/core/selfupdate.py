# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""How this boost was installed, and the command that upgrades it in place.

`boost self-update` assumed a git checkout and told everyone else to abandon
their install method — but the documented way in is `pipx install
boost-skill-cli` or `pip install boost-skill-cli`, where the package lives in
site-packages and there is nothing to `git pull`. This resolves the install
method from evidence on disk and hands the command layer the exact argv that
upgrades *this* copy.

It also answers the question the command layer used to guess at: **is this copy
actually current?** "The version did not change" and "you are on the latest
release" are different propositions, and conflating them let boost tell a user
who was one release behind that they were up to date. See :func:`latest_version`
and :func:`is_behind`.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ..errors import BoostError
from . import gitutil, nethttp, paths

DIST = "boost-skill-cli"

GIT = "git"
PIPX = "pipx"
UV_TOOL = "uv-tool"
PIP = "pip"
UNKNOWN = "unknown"

PYPI_JSON = "https://pypi.org/pypi/%s/json" % DIST

# `boost --version` prints "boost <version>"; anything else means we did not
# actually observe a version and must not report one.
_VERSION_LINE = re.compile(r"^boost\s+(\S+)$", re.MULTILINE)

# Leading digits of one dotted segment. Enough to read the numeric release
# prefix out of `1.0.423` and out of a setuptools-scm `1.0.424.dev3+g36b74ba`.
_LEADING_DIGITS = re.compile(r"\d+")


def installed_version() -> str | None:
    """Version recorded in installed package metadata, or None.

    None is the useful answer, not a failure: it means no Python package
    manager has a record of this boost, so none of them can upgrade it.
    """
    try:
        from importlib.metadata import version
        return version(DIST)
    except Exception:
        return None


def detect(root: Path | None = None, prefix: Path | None = None,
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


def upgrade_command(method: str) -> list[str]:
    """The argv that upgrades boost for `method`.

    Each manager is told to fetch a fresh package index. PyPI serves the simple
    index with ``Cache-Control: max-age=600`` and pip honours it, so two
    self-updates inside ten minutes are answered from pip's HTTP cache — and a
    release published between them is invisible. That is not hypothetical: three
    consecutive `pipx upgrade` runs spanning the 1.0.423 upload all reported
    "Requirement already satisfied ... (1.0.422)" off a cached index fetched
    eight minutes before the wheel existed.

    The flag differs per manager because the managers differ: pip has no
    index-only refresh, so it gets `--no-cache-dir`, while uv does and gets
    `--refresh` (keeping its wheel cache). Don't collapse them into one shape.
    """
    if method == PIPX:
        # pipx owns the venv and shells out to its pip; `--pip-args` is how the
        # flag reaches that pip. The `=` form is required — the value itself
        # starts with `--`.
        return [_require("pipx"), "upgrade", DIST, "--pip-args=--no-cache-dir"]
    if method == UV_TOOL:
        return [_require("uv"), "tool", "upgrade", "--refresh", DIST]
    if method == PIP:
        # sys.executable, never a bare `pip`: the pip first on PATH can belong
        # to a different interpreter than the one running boost, and upgrading
        # that one leaves this install exactly where it was while printing
        # every sign of success.
        return [sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "--upgrade", DIST]
    raise BoostError(
        "cannot work out how boost was installed, so it cannot update itself",
        hint="upgrade with your package manager, e.g. `pipx upgrade %s`" % DIST)


def force_command(method: str, version: str) -> list[str]:
    """The argv that pins boost to `version`, bypassing the resolver.

    Offered only when the manager exited 0 without moving the version while
    PyPI has a newer one. A plain `upgrade` is no help there — the resolver has
    already declined — so this names the exact version and forces the install.
    """
    spec = "%s==%s" % (DIST, version)
    if method == PIPX:
        return [_require("pipx"), "install", "--force", spec]
    if method == UV_TOOL:
        return [_require("uv"), "tool", "install", "--force", spec]
    if method == PIP:
        return [sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "--force-reinstall", spec]
    raise BoostError(
        "cannot work out how boost was installed, so it cannot update itself",
        hint="install the version by hand, e.g. `pipx install --force %s`" % spec)


def latest_version(timeout: float = 10.0) -> str | None:
    """Newest version PyPI publishes for boost, or None if we could not ask.

    None is the load-bearing third answer, as in ``scripts/release_guard.py``:
    it means "PyPI did not tell us", and the caller must not read it as either
    "up to date" or "behind". Every failure — offline, DNS, 503, a maintenance
    HTML page where JSON was expected — degrades to None rather than raising,
    because a version check is never worth failing a self-update over.

    ``BOOST_NO_NET=1`` skips the request entirely, the same contract as
    ``BOOST_NO_AI`` / ``BOOST_NO_SEED``: an air-gapped user (or a test) can
    guarantee nothing leaves the machine.
    """
    if os.environ.get("BOOST_NO_NET"):
        return None
    # S310 is suppressed below: PYPI_JSON is a module constant with an https
    # scheme and no caller-controlled component.
    req = urllib.request.Request(  # noqa: S310
        PYPI_JSON, headers={"Accept": "application/json",
                            "User-Agent": "boost-self-update"})
    try:
        with nethttp.urlopen(req, timeout=timeout) as resp:
            if not 200 <= getattr(resp, "status", 0) < 300:
                return None
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    # http.client.HTTPException covers the body going wrong after the headers
    # arrived — the response is ~735 KB (every release's file list), so a
    # connection that drops mid-read raises IncompleteRead. Listing it
    # explicitly is load-bearing: on CPython <= 3.13 IncompleteRead was also a
    # ValueError and JSONDecodeError's clause swallowed it, but on 3.14 its
    # only base is HTTPException, and it escaped this function as a traceback.
    except (urllib.error.URLError, OSError, TimeoutError, ValueError,
            http.client.HTTPException):
        return None
    info = payload.get("info") if isinstance(payload, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()


def _release_key(version: str) -> tuple[int, ...]:
    """The leading numeric release segments of `version`, as ints.

    Deliberately not a PEP 440 parser: `packaging` is not a dependency of the
    zero-dependency install, boost ships `1.0.N`, and the only other shape that
    reaches here is a setuptools-scm dev string (`1.0.424.dev3+g36b74ba`).
    Comparing the numeric release prefix answers "is PyPI ahead of me" for
    both. An empty tuple means "not a version we can reason about".
    """
    head = version.strip().lstrip("v").split("+", 1)[0]
    parts: list[int] = []
    for chunk in head.split("."):
        m = _LEADING_DIGITS.match(chunk)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts)


def is_behind(installed: str | None, latest: str | None) -> bool:
    """True only when `latest` is visibly a newer release than `installed`.

    Compares numbers, not text — `"1.0.9" > "1.0.10"` lexicographically, which
    is how a version check ships an upgrade nag that never clears. Every
    uncertain input (either side missing or unparseable) is False: a spurious
    "you are behind" would turn a successful upgrade into an alarm, and no
    version string is worth that.
    """
    if not installed or not latest:
        return False
    here, there = _release_key(installed), _release_key(latest)
    if not here or not there:
        return False
    return there > here


def run_upgrade(cmd: list[str], timeout: float = 300.0):
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


def observed_version(timeout: float = 30.0) -> str | None:
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
