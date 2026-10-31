# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ..errors import BoostError

# `embed` and `localembed` are imported here, not lazily: the relocation path
# below rebuilds the venv this process runs from, and a module first imported
# after that would load from a different install than the one already running.
from . import embed, gitutil, localembed, nethttp, paths, typedvalue

DIST = "boost-skill-cli"

GIT = "git"
PIPX = "pipx"
UV_TOOL = "uv-tool"
UV_PIP = "uv-pip"
PIP = "pip"
UNKNOWN = "unknown"

PYPI_JSON = "https://pypi.org/pypi/%s/json" % DIST

# `boost --version` prints "boost <version>"; anything else means we did not
# actually observe a version and must not report one.
_VERSION_LINE = re.compile(r"^boost\s+(\S+)$", re.MULTILINE)

# The public part of a PEP 440 version (the `+local` label is cut off first):
# release, then optional pre (a/b/rc), post and dev segments, each with the
# separators and spellings PEP 440 normalises.
_PEP440 = re.compile(
    r"^(?P<release>\d+(?:\.\d+)*)"
    r"(?:[-_.]?(?P<pre>a|b|c|rc|alpha|beta|pre|preview)[-_.]?(?P<pre_n>\d*))?"
    r"(?:-(?P<post_implicit>\d+)|[-_.]?(?:post|rev|r)[-_.]?(?P<post_n>\d*))?"
    r"(?:[-_.]?dev[-_.]?(?P<dev_n>\d*))?$", re.IGNORECASE)

# A `git describe` string: N commits past the tag `release` — what a source
# checkout reports when no build-time version file exists.
_DESCRIBE = re.compile(
    r"^(?P<release>\d+(?:\.\d+)*)-(?P<ahead>\d+)-g[0-9a-f]+(?:-dirty)?$",
    re.IGNORECASE)

_PRE_RANK = {"a": 0, "alpha": 0, "b": 1, "beta": 1,
             "c": 2, "rc": 2, "pre": 2, "preview": 2}
# Phase ranks around the pre-releases (0..2): a bare `X.devN` sorts below every
# pre-release of X, and a final (or post) release above them.
_DEV_ONLY = -1
_FINAL = 3


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


def installer() -> str | None:
    """The tool that wrote this distribution's metadata (its ``INSTALLER``
    record, e.g. ``pip`` or ``uv``), lower-cased, or None when unrecorded."""
    try:
        from importlib.metadata import distribution
        # `Distribution.read_text` takes no `encoding=`: it is not a file open
        # but a metadata accessor that decodes UTF-8 itself. Bound to a name
        # first so the repo's unencoded-IO sweep does not read it as one.
        read_record = distribution(DIST).read_text
        text = read_record("INSTALLER")
    except Exception:
        return None
    return (text or "").strip().lower() or None


def has_pip() -> bool:
    """Whether this interpreter can run ``-m pip`` at all.

    A venv made by uv (``uv venv``) has no pip unless asked for one, so
    ``sys.executable -m pip`` there is "No module named pip".
    """
    return importlib.util.find_spec("pip") is not None


def detect(root: Path | None = None, prefix: Path | None = None,
           metadata_version=None, installed_by=None, pip_present=None) -> str:
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
    if not lookup():
        return UNKNOWN
    # `uv pip install` records itself as the INSTALLER and needs no pip in the
    # venv; handing that install `python -m pip` names a module that is not
    # there. A venv without pip can only have been filled by something else,
    # and uv's `--python` is the one installer that targets it from outside.
    by = installer if installed_by is None else installed_by
    pip_ok = has_pip if pip_present is None else pip_present
    if by() == "uv" or not pip_ok():
        return UV_PIP
    return PIP


def _require(tool: str, manual: str | None = None) -> str:
    """Absolute path to `tool`, or a BoostError naming what is missing.

    Falling back to another manager here would upgrade a different copy of
    boost — or none at all — while reporting success. `manual` is the
    subcommand the hint offers; it defaults to `upgrade <dist>`, which is
    right for pipx and does not exist in uv (`uv upgrade` is no command).
    """
    found = shutil.which(tool)
    if not found:
        raise BoostError(
            "boost was installed with %s, but %s is not on PATH" % (tool, tool),
            hint="install %s, or upgrade manually with `%s %s`"
                 % (tool, tool, manual or "upgrade %s" % DIST))
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
        return [_require("uv", "tool upgrade %s" % DIST), "tool", "upgrade",
                "--refresh", DIST]
    if method == UV_PIP:
        # `--python sys.executable` for the same reason pip gets it below: the
        # uv default is whatever venv is active, not the one running boost.
        return [_require("uv", "pip install --upgrade %s" % DIST), "pip",
                "install", "--python", sys.executable, "--refresh", "--upgrade",
                DIST]
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
    if method == UV_PIP:
        return [_require("uv"), "pip", "install", "--python", sys.executable,
                "--refresh", "--reinstall", spec]
    if method == PIP:
        return [sys.executable, "-m", "pip", "install", "--no-cache-dir",
                "--force-reinstall", spec]
    raise BoostError(
        "cannot work out how boost was installed, so it cannot update itself",
        hint="install the version by hand, e.g. `pipx install --force %s`" % spec)


#: Seconds a `--python` reinstall may take. Not the upgrade's 300: the manager
#: may first download a whole interpreter, then every dependency again — the
#: [rag] extra's onnxruntime alone is ~15 MB — into a venv it has just emptied.
REINSTALL_TIMEOUT = 900.0

# A Python *version* (`3.13`, `3.13.9`), as opposed to an interpreter path or a
# name like `python3.13`. Only a version can be fetched, so only a version gets
# the fetch flags below.
_PY_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


#: pipx's flag for "use a python-build-standalone interpreter even when one
#: is on PATH". The only spelling that keeps a venv off Homebrew's
#: ``python@3.X`` on a machine that has one — and every Mac that hit this has.
FETCH_ALWAYS = "--fetch-python=always"
#: The pre-1.18 alias for ``--fetch-python=missing``. It downloads only when no
#: ``python3.13`` is found, so on a Homebrew machine it binds to Homebrew's.
FETCH_MISSING = "--fetch-missing-python"
#: The first pipx that accepts :data:`FETCH_ALWAYS`.
PIPX_FETCH_ALWAYS = (1, 18)


def pipx_version(pipx: str, timeout: float = 10.0) -> tuple[int, ...] | None:
    """``pipx --version`` as a tuple, or None when it could not be read."""
    try:
        proc = subprocess.run([pipx, "--version"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.match(r"\s*(\d+)\.(\d+)", proc.stdout or "")
    if proc.returncode != 0 or not m:
        return None
    return int(m.group(1)), int(m.group(2))


def fetch_flag_here() -> str:
    """The fetch flag the pipx on PATH accepts, for a command boost runs.

    No pipx at all gets :data:`FETCH_ALWAYS`: the user installs one first, and
    a fresh pipx is new enough for it. It costs one ``pipx --version``, so only
    :func:`reinstall_command` asks it. The hints (:func:`move_command`,
    ``dense.relocate_extra``) print :data:`FETCH_ALWAYS` without asking: they
    render on every ``boost search`` an interpreter past the ceiling makes,
    each one a fresh process, and the README says the flag needs pipx 1.18.
    """
    found = shutil.which("pipx")
    return pipx_fetch_flag(pipx_version(found)) if found else FETCH_ALWAYS


def pipx_fetch_flag(version: tuple[int, ...] | None) -> str:
    """The strongest fetch flag a pipx of ``version`` accepts.

    An unreadable version gets the alias: every pipx from 1.5 accepts it, and
    a command that runs on Homebrew's 3.13 beats one that does not run —
    :func:`homebrew_python` then says which interpreter it landed on.
    """
    if version is not None and version >= PIPX_FETCH_ALWAYS:
        return FETCH_ALWAYS
    return FETCH_MISSING


#: The receipt fields :func:`uv_requirement` knows how to replay. Anything else
#: — ``with``, constraints, overrides, options — is state a re-derived ``uv
#: tool install`` would drop, so its presence sends the caller to ``upgrade``.
_UV_TOOL_KEYS = frozenset({"requirements", "python", "entrypoints"})
_UV_REQ_KEYS = frozenset({"name", "extras", "specifier"})


def uv_requirement(prefix: Path | None = None) -> str | None:
    """This uv tool's requirement as ``uv tool install`` takes it, or None.

    Read from ``uv-receipt.toml``, and only for the plain shape — a single
    index requirement for boost, with extras and a specifier at most. None for
    anything else (a directory, a git URL, ``--with``), which the caller then
    rebuilds with ``uv tool upgrade``: that replays every receipt field, but
    leaves the receipt's own ``python`` naming the interpreter it left.
    """
    import tomllib
    prefix = Path(sys.prefix) if prefix is None else Path(prefix)
    try:
        with (prefix / "uv-receipt.toml").open("rb") as fh:
            tool = tomllib.load(fh)["tool"]
        reqs = tool["requirements"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if (not isinstance(tool, dict) or set(tool) - _UV_TOOL_KEYS
            or not isinstance(reqs, list) or len(reqs) != 1
            or not isinstance(reqs[0], dict)):
        return None
    req = reqs[0]
    name = str(req.get("name", "")).lower().replace("_", "-")
    if set(req) - _UV_REQ_KEYS or name != DIST:
        return None
    extras = req.get("extras") or []
    spec = DIST
    if extras:
        spec += "[%s]" % ",".join(str(e) for e in extras)
    return spec + str(req.get("specifier") or "")


def reinstall_command(method: str, python: str,
                      prefix: Path | None = None) -> list[str]:
    """The argv that rebuilds this install's venv on ``python``, keeping it.

    It exists because a pipx or uv venv is welded to the interpreter that made
    it. Homebrew removes ``python@X`` when it upgrades past it, and every venv
    built on that formula is left with a ``bin/python`` symlink into a deleted
    directory — measured on 2026-10-28, when ``python@3.14`` went and
    ``boost`` answered "bad interpreter: no such file or directory". It is also
    the way off an interpreter the ``[rag]`` extra's onnxruntime has no wheel
    for (see :data:`localembed.ONNX_WHEEL_CEILING`).

    * **pipx** — ``pipx reinstall --python V --fetch-python=always``. pipx
      1.18.5's own help: reinstall "is uninstalled, then installed with pipx
      install PACKAGE with the same options used in the original install", so
      ``boost-skill-cli[rag]`` keeps its extra. ``always`` and not ``missing``
      (alias ``--fetch-missing-python``): pipx resolves a version against PATH
      first and downloads only when that fails, and a Homebrew Mac has
      ``python3.13`` on PATH — measured: ``missing`` rebuilt the venv on
      ``/opt/homebrew/opt/python@3.13``, the formula the next cleanup removes.
      ``always`` is new in 1.18, so an older pipx (read off ``pipx
      --version``) gets the alias rather than an unknown argument.
    * **uv tool** — ``uv tool install --force --managed-python --python V``
      with the requirement read back from ``uv-receipt.toml``
      (:func:`uv_requirement`). Install rather than ``uv tool upgrade
      --reinstall --python V``: both move the environment, but only install
      rewrites the receipt's ``python`` — measured with uv 0.13.6, upgrade
      left ``python = "3.15"`` behind, so the next rebuild from the receipt
      would land back on the interpreter this moved off. A receipt this cannot
      replay whole falls back to upgrade, which can. ``--managed-python``
      makes uv use (and download) its own cpython rather than Homebrew's.

    The fetch flags ride only on a *version*: given a path, there is nothing
    to fetch, and ``--managed-python`` would refuse the interpreter it was
    pointed at. Every other install method is refused — pip, a uv-pip venv and
    a checkout all live in a venv boost did not create and cannot rebuild
    without knowing what else is in it.

    Shown to a person, the argv goes through ``shlex.join``: a requirement
    like ``boost-skill-cli[rag]>=1.2`` is a glob and a redirect to a shell.
    """
    python = python.strip()
    if not python or python.startswith("-"):
        # `-` first would be read by the manager as a flag of its own.
        raise BoostError(
            "--python needs a Python version or an interpreter path",
            hint="e.g. `boost self-update --python %s`" % _recommended())
    version = bool(_PY_VERSION.match(python))
    if method == PIPX:
        tail = ["reinstall", "--python", python,
                *([fetch_flag_here()] if version else []), DIST]
        return [_require("pipx", shlex.join(tail)), *tail]
    if method == UV_TOOL:
        managed = ["--managed-python"] if version else []
        req = uv_requirement(prefix)
        if req:
            tail = ["tool", "install", "--force", *managed, "--python", python,
                    req]
        else:
            tail = ["tool", "upgrade", "--reinstall", *managed, "--python",
                    python, DIST]
        return [_require("uv", shlex.join(tail)), *tail]
    raise BoostError(
        "--python rebuilds a pipx or uv tool install, and this boost was "
        "installed with %s" % _method_name(method),
        hint=move_hint(method, python))


def _recommended() -> str:
    """The interpreter the hints name — `localembed`'s, so they agree."""
    return localembed.RECOMMENDED_PYTHON


def _method_name(method: str) -> str:
    """`method` as a sentence says it."""
    return {GIT: "a git checkout", UV_PIP: "uv pip", PIP: "pip"}.get(
        method, "a method boost cannot identify")


def move_command(method: str, python: str) -> str:
    """The bare command that puts boost on ``python``, for an install
    `--python` cannot rebuild.

    A checkout rebuilds its own venv; anything else (pip, uv pip, unknown) is
    offered a pipx install that downloads its own interpreter — the one way
    off both a removed Homebrew formula and a Python the extra has no wheel
    for that boost can name without knowing what else lives in that venv.
    """
    py = python if _PY_VERSION.match(python) else _recommended()
    if method == GIT:
        # Not `make venv`: its recipe runs `python3`, which is the very
        # interpreter this user is trying to leave.
        return ("python%s -m venv --clear .venv && .venv/bin/pip install -e "
                "'.[rag]'" % py)
    # FETCH_ALWAYS unprobed: this renders in the search hint (see
    # `fetch_flag_here`).
    return 'pipx install --python %s %s "%s[rag]"' % (py, FETCH_ALWAYS, DIST)


def move_hint(method: str, python: str) -> str:
    """:func:`move_command` as a sentence.

    Also the clause `dense` words its ``no-local-wheel`` remedy with, for the
    same installs: one answer to "how do I get this boost onto 3.13".
    """
    if method == GIT:
        return ("recreate the checkout's venv on that interpreter: `%s`"
                % move_command(method, python))
    return ("pipx can own the interpreter for you: `%s`"
            % move_command(method, python))


def observed_python(timeout: float = 30.0) -> tuple[str, str] | None:
    """``(version, sys.base_prefix)`` of what `sys.executable` runs *now*.

    After a `--python` reinstall the venv sits at the same path on a new
    interpreter, so this process's own ``sys.version_info`` is the old answer —
    the question has to go to a fresh process, as :func:`observed_version`'s
    does. The base prefix comes along because *which* 3.13 matters as much as
    the version: :func:`homebrew_python` reads it. None means it was not seen,
    and the caller must not invent one.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c",
             "import sys; print('%d.%d.%d' % sys.version_info[:3]); "
             "print(sys.base_prefix)"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    lines = (proc.stdout or "").strip().splitlines()
    if len(lines) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", lines[0]):
        return None
    return lines[0], lines[1]


def homebrew_python(base_prefix: str) -> bool:
    """True when ``base_prefix`` is a Homebrew ``python@3.X`` formula.

    Those are the interpreters ``brew upgrade`` deletes: macOS's
    ``/opt/homebrew/opt/python@3.13/...`` (``/usr/local`` on Intel), the
    ``Cellar/python@3.13/...`` it resolves to, and Linuxbrew's ``opt``.
    """
    return "/opt/python@" in base_prefix or "/Cellar/python@" in base_prefix


#: Set in the environment of the `boost quickstart` that a relocation re-execs.
#: The child sees it and does not relocate again, so a move that left boost on
#: the same interpreter cannot loop.
RELOCATED_ENV = "BOOST_RELOCATED"


def relocation_reason(method: str | None = None) -> str | None:
    """Why this install should move to :data:`localembed.RECOMMENDED_PYTHON`,
    or None when it should stay where it is.

    A wheel cannot run code when pipx installs it, so a plain ``pipx install
    'boost-skill-cli[rag]'`` on Homebrew's 3.15 lands without onnxruntime and
    nothing tells the user until a search comes back keyword-only. `boost
    self-update` and `boost quickstart` ask this and offer the move. All four
    must hold:

    * this interpreter has no onnxruntime wheel (:func:`localembed.no_wheel_here`);
    * the ``[rag]`` extra was asked for. sqlite-vec ships only with it, so its
      presence is the record of that request; without it there is no local
      model to rescue and the move would only cost a download;
    * no embedding key is set, since Voyage and OpenAI embed over HTTP and
      need no onnxruntime;
    * pipx or uv tool owns the venv, the two managers boost can rebuild.

    Cheap on purpose: no subprocess, and never ``dense.status()``, which opens
    the store. A Homebrew interpreter that works is not a reason here;
    :func:`homebrew_python` stays a warning.
    """
    if not localembed.no_wheel_here():
        return None
    try:
        if importlib.util.find_spec("sqlite_vec") is None:
            return None
    except (ImportError, ValueError):
        return None
    if embed.any_key():
        return None
    if (detect() if method is None else method) not in (PIPX, UV_TOOL):
        return None
    return ("Python %d.%d has no onnxruntime wheel, so the [rag] extra's "
            "local model cannot run here" % sys.version_info[:2])


def relocation_command(method: str) -> list[str]:
    """The argv that moves this install to the recommended Python.

    :func:`reinstall_command` on :data:`localembed.RECOMMENDED_PYTHON`. pipx
    reinstall and uv tool install both replay the spec unpinned, so the move
    also lands on the latest release: one manager call does both jobs.
    """
    return reinstall_command(method, localembed.RECOMMENDED_PYTHON)


def relocation_offer(method: str, reason: str) -> str:
    """The sentence both commands print before asking to move.

    Names the manager as a user types it (``uv``, not the ``uv-tool`` label
    :func:`detect` returns), because that is the tool that will download the
    interpreter.
    """
    manager = "uv" if method == UV_TOOL else method
    return ("%s. boost can move itself to a Python %s that %s downloads and "
            "manages, and update in the same step"
            % (reason, localembed.RECOMMENDED_PYTHON, manager))


def relocated() -> bool:
    """True in the process a relocation re-exec'd (:data:`RELOCATED_ENV`)."""
    return typedvalue.env_flag(RELOCATED_ENV)


def reexec_argv(argv: list[str]) -> list[str] | None:
    """The argv that runs `boost <argv>` on the rebuilt venv, or None.

    ``sys.executable`` and not the ``boost`` first on PATH, for the reason
    :func:`observed_version` gives: that can be another install. The venv
    keeps its path through a reinstall, so this interpreter's path now leads
    to the new one. None when it does not exist any more, which means the
    manager did not put a venv back and there is nothing to run.
    """
    if not Path(sys.executable).exists():
        return None
    return [sys.executable, "-P", "-m", "boost_cli", *argv]


def python_report(method: str,
                  seen: tuple[str, str] | None) -> tuple[str, str | None]:
    """What to say after a reinstall: an ok line, and a warning or None.

    ``seen`` is :func:`observed_python`'s answer. When it is None, say only
    that the manager finished, never which Python it chose: a manager may
    resolve the version it was asked for to something else.
    """
    if not seen:
        return ("reinstalled via %s; run `boost --version` to confirm"
                % method, None)
    ok = ("boost now runs on Python %s; `boost doctor` checks semantic search"
          % seen[0])
    if not homebrew_python(seen[1]):
        return ok, None
    # An older pipx, or a path, can land the venv back on a formula.
    return ok, ("that Python is Homebrew's (%s), which the next `brew upgrade` "
                "past it deletes — upgrade pipx to 1.18 or later and re-run "
                "with a version, so boost fetches its own" % seen[1])


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
    if typedvalue.env_flag("BOOST_NO_NET", unknown=True):
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


def _release_key(version: str) -> tuple | None:
    """A sort key that orders `version` the way PEP 440 does, or None.

    Deliberately not `packaging`: it is not a dependency of the
    zero-dependency install. boost ships `1.0.N`, but a build from a checkout
    is a setuptools-scm `1.0.424.dev3+g36b74ba`, a candidate is `1.0.424rc1`,
    and a bare checkout reports `git describe`'s `1.2.204-203-g9ef1d107`. Only
    the release numbers used to count, so `1.0.424.dev3` and `1.0.424rc1` read
    as equal to `1.0.424` — when both *precede* it — and self-update called a
    copy behind PyPI "already up to date".

    The order is PEP 440's: `X.devN` < `XaN` < `XbN` < `XrcN` < `X` <
    `X.postN`, with a dev segment below the release it is attached to. The
    `+local` label is ignored rather than ranked (PEP 440 puts `X+local` just
    above `X`), so a local build never reads as behind its own release. A
    describe string ranks as a post-release: it is that many commits past the
    tag. Trailing zeros do not count (`1.0` == `1.0.0`). None means "not a
    version we can reason about".
    """
    head = version.strip().lstrip("vV").split("+", 1)[0]
    described = _DESCRIBE.match(head)
    if described:
        release = described.group("release")
        pre: tuple[int, int] = (_FINAL, 0)
        post = int(described.group("ahead"))
        dev: tuple[int, int] = (1, 0)
    else:
        m = _PEP440.match(head)
        if not m:
            return None
        release = m.group("release")
        post_n = m.group("post_implicit") or m.group("post_n")
        has_post = (m.group("post_implicit") is not None
                    or m.group("post_n") is not None)
        post = int(post_n or 0) if has_post else -1
        dev_n = m.group("dev_n")
        dev = (1, 0) if dev_n is None else (0, int(dev_n or 0))
        if m.group("pre"):
            pre = (_PRE_RANK[m.group("pre").lower()], int(m.group("pre_n") or 0))
        elif dev_n is not None and not has_post:
            pre = (_DEV_ONLY, 0)
        else:
            pre = (_FINAL, 0)
    nums = [int(x) for x in release.split(".")]
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    return (tuple(nums), pre, post, dev)


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
    if here is None or there is None:
        return False
    return there > here


def run_upgrade(cmd: list[str], timeout: float = 300.0):
    """Run the upgrade, raising BoostError with the manager's own last words."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as err:
        raise BoostError("could not run %s" % " ".join(cmd),
                         hint=str(err)) from err
    if proc.returncode != 0:
        detail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()
        raise BoostError(
            "upgrade failed (%s exited %d)" % (Path(cmd[0]).name, proc.returncode),
            hint=last_message(detail) or "re-run the command by hand to see why")
    return proc


def last_message(lines: list[str]) -> str:
    """The manager's final message, re-joined if it wrapped.

    pipx folds a long error into indented continuation lines, so the last line
    alone was `https://github.com/.../releases/latest.` — the tail of a
    sentence whose subject ("No executable for ... '3.13'") was two lines up.
    """
    start = len(lines) - 1
    while start > 0 and lines[start][:1].isspace():
        start -= 1
    return " ".join(line.strip() for line in lines[start:] if line.strip())


def observed_version(timeout: float = 30.0) -> str | None:
    """Ask a freshly-spawned boost what version it is now, or None.

    This process imported its own version before the upgrade ran, so it cannot
    answer the question. None means "we did not see one" — better to say
    nothing than to report a version we never observed.

    The child is *this interpreter*, the one whose environment the manager just
    upgraded — never the `boost` first on PATH, which can be another install
    entirely (a checkout shim ahead of the pipx bin) and would report its own
    version as this one's new version. ``-P`` keeps the working directory off
    ``sys.path``, so a `boost_cli/` folder under the cwd cannot answer instead.
    """
    try:
        proc = subprocess.run([sys.executable, "-P", "-m", "boost_cli",
                               "--version"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    match = _VERSION_LINE.search(proc.stdout or "")
    return match.group(1) if match else None
