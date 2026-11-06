# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""boost — Homebrew for AI coding skills."""
from contextlib import suppress


def _checkout_root():
    """The source checkout this package is imported from, or None.

    `.git` is a directory in a clone and a file in a worktree, so existence is
    the test, not `is_dir()`.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    return root if (root / ".git").exists() else None


def _describe(root) -> str | None:
    """`git describe` of the checkout at `root`, without the leading `v`."""
    with suppress(Exception):
        import subprocess
        # `--match v[0-9]*`, exactly as pyproject's git_describe_command:
        # the repo carries a deliberate non-version tag (`shards-latest`, the
        # rolling release hosting the vector shards), and without the match
        # this fallback served `shards-latest-3-g…` as the version — which
        # parses as no version at all, so `self-update` compared nothing and
        # answered "already up to date" while a newer release existed.
        # `--always` still yields a bare SHA when no version tag is reachable.
        proc = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--always",
             "--dirty", "--match", "v[0-9]*"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=3)
        described = proc.stdout.strip()
        if proc.returncode == 0 and described:
            return described.lstrip("v")
    return None


def _detect_version() -> str:
    """Resolve the package version without a hard-coded constant.

    Order: the file setuptools-scm writes at build time; then, when the
    package is imported from a git checkout, that checkout's `git describe`;
    then installed package metadata; then a sentinel. Stdlib only, so the
    dependency-free runtime stays intact.

    A checkout asks git *before* metadata because `importlib.metadata` answers
    for whatever `boost-skill-cli` distribution is on `sys.path` — an
    unrelated pip install beside a fresh clone made the clone report that
    install's `1.0.9` from `boost --version` and `self-update`.
    """
    with suppress(Exception):
        from ._version import version as scm_version
        return scm_version
    root = _checkout_root()
    if root is not None:
        described = _describe(root)
        if described:
            return described
    with suppress(Exception):
        from importlib.metadata import version as dist_version
        return dist_version("boost-skill-cli")
    return "0.0.0+unknown"


__version__ = _detect_version()
PRODUCT = "boost"
TAGLINE = "AI Skill Package Manager"
