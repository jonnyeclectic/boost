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


    @pytest.mark.parametrize("flag", ["--output", "--out"])
    def test_both_long_spellings_of_o_write(self, boost, sandbox, flag):
        (sandbox / "proj").mkdir()
        dest = sandbox / "good.md"
        boost("infer", "--path", str(sandbox / "proj"), flag, str(dest))
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


class TestOverLongNames:
    """A name longer than one path component allows — 255 bytes on APFS and
    ext4 — reached ``Path.exists()``, which is not total: pathlib swallows
    ENOENT and friends but not ENAMETOOLONG, so four commands answered a
    300-character name with ``OSError: [Errno 63] File name too long`` and a
    crash report. Tap's parse boundary already refuses one by length; these
    are the same rule, applied where each command turns input into a path."""

    LONG = "a" * 300

    def test_create(self, boost, sandbox):
        text = assert_clean_error(
            boost("create", self.LONG, "--dir", str(sandbox), expect=1))
        assert "skill name is too long (300 bytes, limit 255)" in text

    def test_profile_save(self, boost, sandbox):
        text = assert_clean_error(boost("profile", "save", self.LONG, expect=1))
        assert "too long" in text

    def test_profile_save_counts_the_suffix(self, boost, sandbox):
        # 252 bytes is a legal slug, but the file is `<slug>.json` — 257
        # bytes — so a check on the slug alone still let this one crash.
        text = assert_clean_error(boost("profile", "save", "b" * 252, expect=1))
        assert "too long" in text

    # The one test here that writes a real 255-byte name: under a Windows
    # runner's temp dir the *total* path passes MAX_PATH, which is a
    # long-path setting this test cannot see rather than boost's limit.
    @pytest.mark.skipif(sys.platform == "win32",
                        reason="total path exceeds MAX_PATH under the runner's temp dir")
    def test_profile_save_at_the_limit_still_works(self, boost, sandbox):
        boost("profile", "save", "c" * 250)          # 250 + ".json" == 255

    def test_export_output(self, boost, sandbox, installed):
        text = assert_clean_error(
            boost("export", installed, "-o", str(sandbox / self.LONG), expect=1))
        assert "too long" in text

    def test_infer_output(self, boost, sandbox):
        (sandbox / "proj").mkdir()
        text = assert_clean_error(
            boost("infer", "--path", str(sandbox / "proj"),
                  "-o", str(sandbox / self.LONG), expect=1))
        assert "too long" in text

    def test_infer_output_under_an_over_long_directory(self, boost, sandbox):
        # The long component need not be the last one: `exists()` stats the
        # whole path, so a long parent crashes it just the same.
        (sandbox / "proj").mkdir()
        text = assert_clean_error(
            boost("infer", "--path", str(sandbox / "proj"),
                  "-o", str(sandbox / self.LONG / "x.md"), expect=1))
        assert "too long" in text
