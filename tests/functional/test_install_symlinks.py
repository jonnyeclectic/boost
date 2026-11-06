# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a skill whose source holds symlinks.

A tap clone is sparse — Markdown plus each installed skill's own dir — so a
skill's link to a file elsewhere in the tap (``../../shared/helper.py``)
dangles in the clone though the file is in the repo. Install followed every
link and crashed on that one with a raw ``shutil.Error``, exit 2, nothing
installed. Now the target is fetched and copied, a link inside the skill stays
a link, and a link to nothing or out of the tap is skipped and named.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

from boost_cli.core import gitutil, paths, registry, store
from boost_cli.errors import BoostError

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="symlinks need a privilege on Windows")

SKILL = "---\nname: linky\ndescription: A skill with links\n---\n\n# Linky\n"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


@pytest.fixture
def link_tap(boost, fixture_tap_src, tmp_path):
    tap_dir = tmp_path / "link-tap"
    shutil.copytree(fixture_tap_src, tap_dir)
    skill = tap_dir / "skills" / "linky"
    (skill / "notes").mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL, encoding="utf-8")
    (skill / "notes" / "real.txt").write_text("inside\n", encoding="utf-8")
    (tap_dir / "shared" / "lib").mkdir(parents=True)
    (tap_dir / "shared" / "helper.py").write_text("print('hi')\n",
                                                  encoding="utf-8")
    (tap_dir / "shared" / "lib" / "util.py").write_text("X = 1\n",
                                                        encoding="utf-8")
    (skill / "helper.py").symlink_to("../../shared/helper.py")
    (skill / "lib").symlink_to("../../shared/lib")
    (skill / "alias.txt").symlink_to("notes/real.txt")
    (skill / "gone.txt").symlink_to("nowhere.txt")
    (skill / "out.txt").symlink_to(tmp_path / "secret.txt")
    (tmp_path / "secret.txt").write_text("not the tap's\n", encoding="utf-8")
    _git(tap_dir, "add", "-A")
    _git(tap_dir, "commit", "-qm", "add linky")
    boost("tap", tap_dir)
    return registry.get("link-tap").path


def _store():
    return paths.store_dir() / "linky"


class TestInstallWithLinks:
    def test_the_clone_is_sparse_so_the_target_starts_missing(self, link_tap):
        """The precondition the crash needed: the link is there, its target
        is not, because the cone holds only Markdown and the skill's dir."""
        gitutil.materialize(link_tap, "skills/linky")
        assert os.path.islink(link_tap / "skills" / "linky" / "helper.py")
        assert not (link_tap / "shared" / "helper.py").exists()

    def test_install_copies_in_tap_targets_and_skips_the_rest(self, boost,
                                                              link_tap):
        r = boost("install", "linky")
        dest = _store()
        helper = dest / "helper.py"
        assert helper.is_file() and not helper.is_symlink()
        assert helper.read_text(encoding="utf-8") == "print('hi')\n"
        lib = dest / "lib"
        assert lib.is_dir() and not lib.is_symlink()
        assert (lib / "util.py").read_text(encoding="utf-8") == "X = 1\n"
        # A link inside the skill is kept as a link, and still leads home.
        alias = dest / "alias.txt"
        assert alias.is_symlink()
        assert os.readlink(alias) == "notes/real.txt"
        assert alias.read_text(encoding="utf-8") == "inside\n"
        # Nothing from outside the tap, and nothing for a dangling link.
        assert not os.path.lexists(dest / "out.txt")
        assert not os.path.lexists(dest / "gone.txt")
        flat = " ".join((r.out + r.err).split())
        assert "linky: not copied — the link gone.txt → nowhere.txt leads " \
               "to nothing" in flat
        assert "linky: not copied — the link out.txt → " in flat
        assert "leads outside the tap" in flat
        assert "alias.txt" not in flat and "helper.py" not in flat

    def test_the_copy_holds_exactly_the_tap_content(self, boost, link_tap):
        boost("install", "linky")
        # The targets were fetched into the clone, not read from elsewhere.
        assert (link_tap / "shared" / "helper.py").is_file()
        assert (link_tap / "shared" / "lib" / "util.py").is_file()
        assert {p.name for p in _store().iterdir()} == {
            "SKILL.md", "notes", "helper.py", "lib", "alias.txt"}


class TestSkippedLinksAreNotDrift:
    """The lock hashes the copy, so the tap side must hash the same view:
    a link install skips by policy is not a change upstream."""

    def _move_tap(self, tmp_path, n=0):
        src = tmp_path / "link-tap"
        (src / "README.md").write_text("moved %d\n" % n, encoding="utf-8")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "unrelated")

    def test_an_unrelated_tap_move_does_not_refresh_it(self, boost, link_tap,
                                                       tmp_path):
        boost("install", "linky")
        for n in range(2):
            self._move_tap(tmp_path, n)
            r = boost("update")
            flat = " ".join((r.out + r.err).split())
            assert "refreshed linky" not in flat
            assert "leads outside the tap" not in flat

    def test_drift_calls_it_in_sync_after_a_tap_move(self, boost, link_tap,
                                                     tmp_path):
        boost("install", "linky")
        self._move_tap(tmp_path)
        boost("update")
        r = boost("drift", "--json")
        rows = {row["name"]: row["status"] for row in json.loads(r.out)["skills"]}
        assert rows["linky"] == "in-sync"

    def test_a_real_change_inside_the_skill_still_counts(self, boost, link_tap,
                                                         tmp_path):
        boost("install", "linky")
        src = tmp_path / "link-tap"
        (src / "skills" / "linky" / "notes" / "real.txt").write_text(
            "changed\n", encoding="utf-8")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "edit")
        r = boost("update")
        assert "refreshed linky v0.0.0 (source changed)" in " ".join(
            (r.out + r.err).split())
        assert (_store() / "notes" / "real.txt").read_text(
            encoding="utf-8") == "changed\n"

    def test_copy_view_sha_is_the_installed_copys_hash(self, boost, link_tap):
        from boost_cli.core import lockfile, util
        boost("install", "linky")
        src = link_tap / "skills" / "linky"
        want = lockfile.get_skill("linky")["sha256"]
        assert util.sha256_dir(src) != want, "the raw tree must differ here"
        assert store.copy_view_sha(src, link_tap) == want

    def test_a_lone_dir_link_takes_the_staged_path(self, tmp_path):
        """``rglob`` does not descend a dir link the copy holds as a real
        dir, so a tree whose only link is a dir must not hash in place."""
        from boost_cli.core import util
        root = tmp_path / "repo"
        skill = root / "skills" / "s"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        (root / "shared").mkdir()
        (root / "shared" / "u.py").write_text("u", encoding="utf-8")
        (skill / "lib").symlink_to("../../shared")
        store._copy_tree(skill, tmp_path / "copy", root)
        want = util.sha256_dir(tmp_path / "copy")
        assert util.sha256_dir(skill) != want
        assert store.copy_view_sha(skill, root) == want

    def test_a_tree_without_links_hashes_in_place(self, tmp_path, monkeypatch):
        from boost_cli.core import util
        (tmp_path / "s").mkdir()
        (tmp_path / "s" / "SKILL.md").write_text("x", encoding="utf-8")
        monkeypatch.setattr(store, "_copy_tree", None)
        assert store.copy_view_sha(tmp_path / "s", tmp_path) == \
            util.sha256_dir(tmp_path / "s")


class TestCopyTree:
    """``store._copy_tree`` on its own: the rules, case by case."""

    def _skill(self, tmp_path):
        root = tmp_path / "repo"
        skill = root / "skills" / "s"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        return root, skill

    def test_a_link_to_an_ancestor_is_not_copied_into_itself(self, tmp_path):
        root, skill = self._skill(tmp_path)
        (skill / "up").symlink_to("..")
        skipped = store._copy_tree(skill, tmp_path / "dst", root)
        assert skipped == ["up → .. loops back over the skill"]
        assert not os.path.lexists(tmp_path / "dst" / "up")

    def test_a_link_spelled_through_the_skill_dir_is_copied_as_a_file(
            self, tmp_path):
        """``../s/f`` resolves inside the skill, but the store may name the
        dir differently, so the copy holds the bytes rather than the link."""
        root, skill = self._skill(tmp_path)
        (skill / "f").write_text("f", encoding="utf-8")
        (skill / "g").symlink_to("../s/f")
        assert store._copy_tree(skill, tmp_path / "dst", root) == []
        g = tmp_path / "dst" / "g"
        assert g.is_file() and not g.is_symlink()
        assert g.read_text(encoding="utf-8") == "f"

    def test_an_absolute_link_into_the_skill_is_copied_as_a_file(self, tmp_path):
        root, skill = self._skill(tmp_path)
        (skill / "f").write_text("f", encoding="utf-8")
        (skill / "g").symlink_to(skill / "f")
        assert store._copy_tree(skill, tmp_path / "dst", root) == []
        assert not (tmp_path / "dst" / "g").is_symlink()

    def test_with_no_bound_a_link_out_is_followed(self, tmp_path):
        """A path import (``within`` None) copies what the user's links lead
        to; dangling ones are still skipped."""
        root, skill = self._skill(tmp_path)
        (root / "shared.txt").write_text("s", encoding="utf-8")
        (skill / "s.txt").symlink_to("../../shared.txt")
        (skill / "d.txt").symlink_to("../../none.txt")
        skipped = store._copy_tree(skill, tmp_path / "dst", None)
        assert skipped == ["d.txt → ../../none.txt leads to nothing"]
        assert (tmp_path / "dst" / "s.txt").read_text(encoding="utf-8") == "s"

    def test_a_url_import_is_bounded_by_its_clone(self, sandbox, tmp_path):
        clone = tmp_path / "clone"
        skill = clone / "skills" / "alpha"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: alpha\n---\n\nBody\n",
                                        encoding="utf-8")
        (clone / "shared.py").write_text("in\n", encoding="utf-8")
        (tmp_path / "outside.py").write_text("out\n", encoding="utf-8")
        (skill / "in.py").symlink_to("../../shared.py")
        (skill / "out.py").symlink_to("../../../outside.py")
        remote = store.RemoteSource(url="https://git.example.test/x.git",
                                    root=clone, commit="0" * 40)
        res = store.install_from_path(skill, remote=remote)
        dest = paths.store_dir() / "alpha"
        assert (dest / "in.py").read_text(encoding="utf-8") == "in\n"
        assert not os.path.lexists(dest / "out.py")
        assert res.skipped_links == [
            "out.py → ../../../outside.py leads outside the tap"]

    def test_a_linked_dirs_own_links_obey_the_same_rules(self, tmp_path):
        root, skill = self._skill(tmp_path)
        lib = root / "lib"
        lib.mkdir()
        (lib / "a.txt").write_text("a", encoding="utf-8")
        (lib / "dead").symlink_to("missing")
        (skill / "lib").symlink_to("../../lib")
        skipped = store._copy_tree(skill, tmp_path / "dst", root)
        assert skipped == ["lib/dead → missing leads to nothing"]
        assert (tmp_path / "dst" / "lib" / "a.txt").read_text(
            encoding="utf-8") == "a"

    def test_a_copy_error_is_a_boost_error_not_a_crash(self, tmp_path,
                                                       monkeypatch):
        _root, skill = self._skill(tmp_path)

        def boom(*_a, **_k):
            raise shutil.Error([(str(skill / "x"), "dst", "No such file")])
        monkeypatch.setattr(store, "_copy_tree", boom)
        dest = tmp_path / "store" / "s"
        with pytest.raises(BoostError) as exc:
            store._copy_skill(skill, dest)
        assert str(exc.value) == ("could not copy s into the skill store: "
                                  "1 file failed")
        assert exc.value.hint == "first: %s" % (skill / "x")
        # The staging dir is cleaned up and nothing lands at dest.
        assert not dest.exists()
        assert os.listdir(dest.parent) == []


class TestLinkTargetsToFetch:
    def test_names_only_missing_targets_inside_the_repo(self, tmp_path):
        repo = tmp_path / "repo"
        skill = repo / "skills" / "s"
        skill.mkdir(parents=True)
        (repo / "here.txt").write_text("h", encoding="utf-8")
        (skill / "a").symlink_to("../../missing.py")
        (skill / "b").symlink_to("../../here.txt")
        (skill / "c").symlink_to(tmp_path / "elsewhere")
        (skill / "d").symlink_to("../../pkg")
        assert sorted(store.link_targets_to_fetch(repo, skill)) == [
            "missing.py", "pkg"]
