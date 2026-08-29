# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
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


class TestResolveAsFarAsItExists:
    def test_a_real_ancestor_resolves_normally(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        missing = real / "gone" / "deeper"
        got = quality._resolve_as_far_as_it_exists(missing)
        assert got == (real.resolve() / "gone" / "deeper")

    def test_a_runtime_error_from_a_symlink_loop_is_swallowed_not_raised(
            self, tmp_path, monkeypatch):
        # Path.resolve() raises RuntimeError (not OSError) for a symlink
        # loop reached while resolving strict=False on Python 3.12 — the
        # exact split boost_cli/core/store.py's resolves_into_store already
        # documents and guards against with `except (OSError, RuntimeError)`.
        # This helper's `suppress(OSError)` alone fails open on that
        # interpreter: it lets the RuntimeError escape instead of falling
        # back to the deepest real ancestor the way a real symlink loop
        # (which IS reachable in a broken-link sweep) needs it to.
        real = tmp_path / "real"
        real.mkdir()
        missing = real / "gone"

        from pathlib import Path as _Path
        real_resolve = _Path.resolve

        def loop_then_real(self, *a, **k):
            if self == real:
                raise RuntimeError("Symlink loop from %r" % str(self))
            return real_resolve(self, *a, **k)

        monkeypatch.setattr(_Path, "resolve", loop_then_real)
        got = quality._resolve_as_far_as_it_exists(missing)
        assert got == real / "gone"   # fell back to the unresolved ancestor
