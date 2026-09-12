# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A typo must not be reported as a bug in boost.

Three commands turned ordinary bad input into ``exit 70`` plus a crash report
whose hint invites the reader to *file a GitHub issue*:

* ``boost infer -o <an existing directory>`` — ``IsADirectoryError``, and the
  generated skill is lost with it.
* ``boost create --dir <a file>`` — ``NotADirectoryError``; an unwritable
  directory gives ``PermissionError``.
* ``boost tap <a path that does not exist>`` took a fourth route: rather than
  crashing it rewrote the path into ``https://github.com/<path>``, producing a
  doomed clone whose error names a URL the user never typed.

boost already owns the right shape for all of these — ``boost import ./nope``
answers ``Error: no such directory: ./nope`` with a hint, exit 1 — so these are
commands that miss a house style rather than an absent one.
"""
from __future__ import annotations

import os
import sys

import pytest

CRASH_MARKERS = ("boost hit an unexpected error", "crash report", "file it at")


def assert_clean_error(result) -> str:
    """Fail unless this is a framed error rather than a crash report."""
    text = result.out + result.err
    for marker in CRASH_MARKERS:
        assert marker not in text, "crash report for bad input:\n%s" % text
    assert "Error:" in text
    return text


class TestInferOutput:
    def test_an_existing_directory_is_refused_cleanly(self, boost, sandbox):
        (sandbox / "proj").mkdir()
        (sandbox / "out").mkdir()
        r = boost("infer", "--path", str(sandbox / "proj"),
                  "-o", str(sandbox / "out"), expect=1)
        assert_clean_error(r)

    def test_a_writable_path_still_works(self, boost, sandbox):
        (sandbox / "proj").mkdir()
        dest = sandbox / "good.md"
        boost("infer", "--path", str(sandbox / "proj"), "-o", str(dest))
        assert dest.is_file()


class TestCreateDir:
    def test_a_file_as_the_parent_is_refused_cleanly(self, boost, sandbox):
        (sandbox / "afile").write_text("x", encoding="utf-8")
        r = boost("create", "x", "--dir", str(sandbox / "afile"), expect=1)
        assert_clean_error(r)

    # The condition is evaluated at COLLECTION time, so `os.geteuid` must not
    # be touched on a platform that does not have it: Windows has no such
    # attribute and the whole module failed to import, taking every test in it
    # down with a collection error rather than a skip. `or` short-circuits.
    @pytest.mark.skipif(
        sys.platform == "win32" or os.geteuid() == 0,
        reason="Windows has no POSIX mode bits to honour; root ignores them")
    def test_an_unwritable_parent_is_refused_cleanly(self, boost, sandbox):
        ro = sandbox / "ro"
        ro.mkdir(mode=0o500)
        try:
            assert_clean_error(boost("create", "x", "--dir", str(ro), expect=1))
        finally:
            ro.chmod(0o700)          # let the tmpdir be cleaned up

    def test_a_missing_parent_is_created(self, boost, sandbox):
        """Deliberate: `--dir` builds the tree, so this is not the bad-input case."""
        boost("create", "x", "--dir", str(sandbox / "new" / "deeper"))
        assert (sandbox / "new" / "deeper" / "x" / "SKILL.md").is_file()

    def test_a_valid_dir_still_works(self, boost, sandbox):
        dest = sandbox / "made"
        boost("create", "x", "--dir", str(dest))
        assert (dest / "x" / "SKILL.md").is_file()


class TestTapPathSpec:
    @pytest.mark.parametrize("spec", ["./no-such-dir", "../no-such-dir", "/no/such/dir"])
    def test_a_path_that_does_not_exist_is_named_as_a_path(self, boost, spec):
        """Not rewritten into a github.com URL the user never typed."""
        r = boost("tap", spec, expect=1)
        text = r.out + r.err
        assert "github.com" not in text, text
        assert "no such directory" in text

    def test_a_home_relative_path_too(self, boost, sandbox):
        r = boost("tap", "~/no-such-dir", expect=1)
        assert "github.com" not in (r.out + r.err)

    def test_owner_repo_is_still_a_github_spec(self):
        from boost_cli.core import registry

        _name, url = registry.parse_spec("someowner/somerepo")
        assert url == "https://github.com/someowner/somerepo"

    def test_a_real_directory_still_taps(self, boost, fixture_tap_src):
        boost("tap", str(fixture_tap_src))
        assert "fixture-tap" in boost("taps").out
