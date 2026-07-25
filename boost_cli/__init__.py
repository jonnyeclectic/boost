"""boost — Homebrew for AI coding skills."""
from contextlib import suppress


def _detect_version() -> str:
    """Resolve the package version without a hard-coded constant.

    Order: the file setuptools-scm writes at build time, then installed
    package metadata, then a git-checkout fallback (stdlib only, so the
    dependency-free runtime stays intact), then a sentinel.
    """
    with suppress(Exception):
        from ._version import version as scm_version
        return scm_version
    with suppress(Exception):
        from importlib.metadata import version as dist_version
        return dist_version("boost-skill-cli")
    with suppress(Exception):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=3)
        described = proc.stdout.strip()
        if proc.returncode == 0 and described:
            return described.lstrip("v")
    return "0.0.0+unknown"


__version__ = _detect_version()
PRODUCT = "boost"
TAGLINE = "AI Skill Package Manager"
