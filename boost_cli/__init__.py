"""boost — Homebrew for AI coding skills."""


def _detect_version() -> str:
    """Resolve the package version without a hard-coded constant.

    Order: the file setuptools-scm writes at build time, then installed
    package metadata, then a git-checkout fallback (stdlib only, so the
    dependency-free runtime stays intact), then a sentinel.
    """
    try:
        from ._version import version as scm_version
        return scm_version
    except Exception:
        pass
    try:
        from importlib.metadata import version as dist_version
        return dist_version("boost-skill-cli")
    except Exception:
        pass
    try:
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=3)
        described = proc.stdout.strip()
        if proc.returncode == 0 and described:
            return described.lstrip("v")
    except Exception:
        pass
    return "0.0.0+unknown"


__version__ = _detect_version()
PRODUCT = "boost"
TAGLINE = "AI Skill Package Manager"
