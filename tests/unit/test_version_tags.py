# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Only `vX.Y.Z` tags are versions.

This repository now carries a non-version tag on purpose: `shards-latest` is
the rolling GitHub release that hosts the prebuilt vector shards, and a release
must have a tag. With setuptools-scm left at its defaults, `git describe`
found that tag and the project's own version became::

    $ git describe --tags --long
    shards-latest-1-g82c3e6a          # -> "vshards-latest-1-g82c3e6a"

which is not a version at all. The visible damage was `boost self-update`
reporting "already up to date" while a newer release sat on PyPI — it compares
version tuples, and that string parses as none — so the failure was a *silent
wrong answer* in the command whose whole job is to tell you whether you are
behind.

Two settings are needed and neither is redundant: `git_describe_command`
decides which tag is *found*, `tag_regex` decides how it is *parsed*. These
tests read them out of pyproject.toml because that is where a future edit would
undo them, and because the alternative — building a wheel — is far too slow to
sit in the unit suite.
"""
from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _scm() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["setuptools_scm"]


class TestDescribeCommand:
    def test_it_requires_a_digit_after_the_v(self):
        cmd = _scm()["git_describe_command"]
        assert "--match" in cmd
        assert cmd[cmd.index("--match") + 1] == "v[0-9]*"

    def test_the_pattern_excludes_the_shards_tag(self):
        # fnmatch is what git's --match uses.
        from fnmatch import fnmatch
        pattern = "v[0-9]*"
        assert not fnmatch("shards-latest", pattern)
        assert not fnmatch("vshards-latest", pattern)
        assert fnmatch("v1.2.48", pattern)

    @pytest.mark.skipif(not (ROOT / ".git").exists(),
                        reason="not a git checkout")
    def test_git_agrees_with_the_pattern(self):
        """The claim above, asserted against real git rather than fnmatch."""
        cmd = _scm()["git_describe_command"]
        proc = subprocess.run([*cmd], cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            pytest.skip("no matching tag in this checkout (shallow clone)")
        assert proc.stdout.startswith("v")
        assert "shards" not in proc.stdout


class TestRuntimeFallback:
    """The third resolver in `boost_cli.__init__` runs its own `git describe`.

    That fallback is what actually serves `__version__` wherever the package
    is imported straight from a checkout — CI's test jobs included, since
    `_version.py` is gitignored and no dist is installed there. Fixing
    pyproject alone therefore fixed the wheel and left the running code wrong:
    CI still reported `vshards-latest-3-g…`, and `self-update` still compared
    a version that parses as none.
    """

    def test_the_fallback_describe_is_pinned_to_version_tags(self):
        import inspect

        import boost_cli
        src = inspect.getsource(boost_cli._detect_version)
        assert '"--match"' in src and '"v[0-9]*"' in src, (
            "the git-describe fallback must exclude non-version tags exactly "
            "as pyproject's git_describe_command does")

    @pytest.mark.skipif(not (ROOT / ".git").exists(),
                        reason="not a git checkout")
    def test_a_checkout_import_never_serves_the_shards_tag(self):
        import boost_cli
        assert "shards" not in boost_cli.__version__


class TestTagRegex:
    def test_a_version_tag_parses(self):
        rx = re.compile(_scm()["tag_regex"])
        m = rx.match("v1.2.48")
        assert m and m.group("version") == "1.2.48"

    @pytest.mark.parametrize("tag", ["shards-latest", "vshards-latest",
                                     "nightly", "v", "release-2026"])
    def test_a_non_version_tag_does_not(self, tag):
        assert not re.compile(_scm()["tag_regex"]).match(tag)
