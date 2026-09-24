# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What the sdist ships, checked against the rule instead of restating it.

MANIFEST.in opens by declaring that everything below it is dev-only and must
never ship. It then wrote `prune .claude` and `exclude package.json`, both of
which are ROOT-ANCHORED — so `docs/.claude/settings.local.json` and
`tests/visual/package.json` were in every release on PyPI, under the very
paragraph that forbids them. Today's contents are harmless; a machine-specific
path or a tool allowlist in a checked-in agent-permission file would not be.

These tests apply the real template to the real tracked tree rather than
grepping MANIFEST.in for patterns: `setuptools._distutils.filelist.FileList` is
the engine setuptools' own `sdist` command runs, and `git ls-files` is what
setuptools-scm's file finder hands it. Simulating is deliberate — building an
sdist here would need the build backend resolved over the network and would
leave `*.egg-info` in the developer's checkout, and a test that skips when
neither is available is not a gate. The built artifact is still checked, once,
where one already exists: the `package-metadata` workflow greps the tarball it
builds before every release.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The shapes that must never reach PyPI, as (label, predicate) over a member
# path. Named rather than one regex so a failure says which rule broke.
FORBIDDEN = (
    ("an agent-permission dir", lambda p: ".claude" in Path(p).parts),
    ("the npm toolchain", lambda p: Path(p).name in (
        "package.json", "package-lock.json")),
    ("a node_modules tree", lambda p: "node_modules" in Path(p).parts),
)


def _tracked() -> list[str]:
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout — no file finder to simulate")
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return [p for p in out.split("\0") if p]


def _manifest_survivors(candidates: list[str]) -> list[str]:
    """The candidates MANIFEST.in leaves in, via setuptools' own matcher."""
    from setuptools._distutils.filelist import FileList

    fl = FileList()
    fl.files = list(candidates)
    fl.allfiles = list(candidates)
    for raw in (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            fl.process_template_line(line)
    return list(fl.files)


@pytest.fixture(scope="module")
def shipped() -> list[str]:
    return _manifest_survivors(_tracked())


@pytest.mark.parametrize("label,matches", FORBIDDEN,
                         ids=[f[0] for f in FORBIDDEN])
def test_no_dev_only_file_survives_the_manifest(shipped, label, matches):
    leaked = sorted(p for p in shipped if matches(p))
    assert not leaked, (
        "%s ships in the sdist: %s — MANIFEST.in's pattern for it is "
        "root-anchored, so add a recursive `global-exclude`"
        % (label, ", ".join(leaked)))


@pytest.mark.parametrize("planted", [
    "docs/.claude/settings.local.json",      # depth 1 — the one that shipped
    "a/b/.claude/settings.local.json",       # deeper, in a dir nobody has yet
    "a/b/c/.claude/commands/x.md",           # and a file below such a dir
    "tests/visual/package.json",             # the other one that shipped
    "a/b/c/d/package-lock.json",
])
def test_the_exclusions_are_recursive_not_incidental(planted):
    """The repo having no offender at depth 3 is not the same as the rule
    covering depth 3. Plant one and watch the real matcher remove it."""
    survivors = _manifest_survivors(_tracked() + [planted])
    assert planted not in survivors, (
        "%s survives MANIFEST.in — the pattern that should exclude it is "
        "anchored, or does not reach that depth" % planted)


@pytest.mark.parametrize("wanted", [
    "boost_cli/cli.py",
    "boost_cli/data/registries.json",        # package data, not just code
    "boost_langchain/py.typed",
    "README.md",
    "pyproject.toml",
])
def test_the_runtime_still_ships(shipped, wanted):
    """The negative tests above pass trivially against a manifest that
    excludes everything, so pin the payload the sdist exists to carry."""
    assert wanted in shipped, "%s no longer ships in the sdist" % wanted
