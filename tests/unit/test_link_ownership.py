"""Unit tests: the link-ownership helpers behind `boost heal`.

`heal` deletes what it decides it owns, so the decision is worth pinning
directly rather than only through the command. These run on every platform
because they are string logic — the Windows shapes below are exactly what
made a genuine boost link read as foreign on `windows-latest` while passing
on Linux and macOS.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from boost_cli.commands import quality


class TestNorm:
    def test_it_folds_case_the_way_the_platform_does(self):
        # A no-op on POSIX, case-folding on Windows. Asserting against
        # os.path.normcase rather than a literal keeps this true on both.
        assert quality._norm(Path("/A/B")) == os.path.normcase(
            os.path.abspath("/A/B"))

    def test_it_makes_a_relative_path_absolute(self):
        assert os.path.isabs(quality._norm(Path("rel/ative")))

    @pytest.mark.parametrize("prefixed,plain", [
        ("\\\\?\\C:\\x\\y", "C:\\x\\y"),
        ("\\\\?\\UNC\\srv\\share\\x", "srv\\share\\x"),
    ])
    def test_it_strips_windows_extended_length_prefixes(self, prefixed, plain):
        """`os.readlink` returns this form; `store_dir()` never does.

        One location, two strings — which is how `heal` concluded it did not
        own a link it had created itself, and repaired nothing on Windows.
        """
        got = quality._norm(Path(prefixed))
        assert "?" not in got            # the prefix is gone, on any host
        assert got.endswith(os.path.normcase(plain))


class TestWithin:
    def test_a_path_is_within_itself(self):
        assert quality._within("/a/b", "/a/b")

    def test_a_child_is_within(self):
        assert quality._within(os.sep.join(["", "a", "b", "c"]),
                               os.sep.join(["", "a", "b"]))

    def test_a_sibling_with_a_shared_prefix_is_not(self):
        # The bug a bare `startswith` would introduce: `/a/bc` is not under
        # `/a/b`, and treating it as owned would delete a stranger's link.
        assert not quality._within(os.sep.join(["", "a", "bc"]),
                                   os.sep.join(["", "a", "b"]))

    def test_a_parent_is_not_within_its_child(self):
        assert not quality._within(os.sep.join(["", "a"]),
                                   os.sep.join(["", "a", "b"]))

    def test_a_trailing_separator_on_the_parent_does_not_break_it(self):
        assert quality._within(os.sep.join(["", "a", "b", "c"]),
                               os.sep.join(["", "a", "b"]) + os.sep)


class TestOwnedLink:
    def test_a_link_into_the_store_is_ours(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        monkeypatch.setattr(quality.paths, "store_dir", lambda: store)
        link = tmp_path / "link"
        link.symlink_to(store / "gone")           # dangling, but ours
        assert quality._owned_link(link)

    def test_a_link_somewhere_else_is_not(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        monkeypatch.setattr(quality.paths, "store_dir", lambda: store)
        link = tmp_path / "link"
        link.symlink_to(tmp_path / "elsewhere" / "thing")
        assert not quality._owned_link(link)

    def test_a_relative_link_resolves_against_its_own_directory(
            self, tmp_path, monkeypatch):
        # Ownership is about where a link points, not how it is spelled.
        store = tmp_path / "store"
        store.mkdir()
        monkeypatch.setattr(quality.paths, "store_dir", lambda: store)
        link = tmp_path / "link"
        link.symlink_to(os.path.join("store", "gone"))
        assert quality._owned_link(link)

    def test_a_sibling_directory_sharing_a_prefix_is_not_ours(
            self, tmp_path, monkeypatch):
        store = tmp_path / "skills"
        store.mkdir()
        monkeypatch.setattr(quality.paths, "store_dir", lambda: store)
        link = tmp_path / "link"
        link.symlink_to(tmp_path / "skills-backup" / "thing")
        assert not quality._owned_link(link)

    def test_something_that_is_not_a_link_is_not_ours(self, tmp_path,
                                                      monkeypatch):
        monkeypatch.setattr(quality.paths, "store_dir", lambda: tmp_path)
        plain = tmp_path / "file"
        plain.write_text("x", encoding="utf-8")
        assert not quality._owned_link(plain)     # readlink raises; no crash
