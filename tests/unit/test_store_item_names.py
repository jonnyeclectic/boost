# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Item names the filesystem cannot hold the way boost spells them.

A name that differs from an installed skill's only by case shares its store
dir on a case-insensitive filesystem; a name that fits the 255-byte component
limit as a final path did not fit the temp name staged beside it; and a
machine that cannot make symlinks cannot link a skill at all. Each used to
fail late, overwrite, or crash at rc 70.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from boost_cli.core import catalog, lockfile, registry, store, util
from boost_cli.errors import BoostError


def make_tap(root: Path, skills: dict[str, str] | None = None,
             commands: dict[str, str] | None = None):
    """``skills`` maps a dir name to its frontmatter name, ``commands`` a
    file stem to its; each body is ``<name> body``. Taps and indexes it."""
    for d, name in (skills or {}).items():
        (root / "skills" / d).mkdir(parents=True)
        (root / "skills" / d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: a skill\n---\n\n%s body\n"
            % (name, name), encoding="utf-8")
    for stem, name in (commands or {}).items():
        (root / "commands").mkdir(parents=True, exist_ok=True)
        (root / "commands" / (stem + ".md")).write_text(
            "---\nname: %s\ndescription: a command\n---\n\n%s body\n"
            % (name, name), encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=root, check=True,
                                    capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@boost.test")
    run("git", "config", "user.name", "T")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "items")
    tap = registry.add(str(root))
    catalog.rebuild_tap(tap)
    return tap


class TestLongNames:
    def test_a_temp_file_beside_a_long_name_is_no_longer_than_it(self, tmp_path):
        # 250 bytes fits as a file name; `.<name>.XXXXXXXX.tmp` did not.
        p = tmp_path / ("w" * 250)
        util.atomic_write_text(p, "x")
        assert p.read_text(encoding="utf-8") == "x"
        assert [q.name for q in tmp_path.iterdir()] == [p.name]

    def test_the_temp_prefix_is_short_and_hidden(self):
        assert util.TEMP_PREFIX == ".boost-"

    def test_a_skill_staged_under_a_long_name_installs(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        dest = tmp_path / ("s" * 255)
        store._copy_skill(src, dest)
        store._copy_skill(src, dest)    # a reinstall moves the old copy aside
        assert (dest / "SKILL.md").is_file()
        assert {q.name for q in tmp_path.iterdir()} == {dest.name, "src"}

    @pytest.mark.parametrize(("kind", "fits"), [
        ("skill", 255), ("rule", 251), ("workflow", 250)])
    def test_the_longest_name_each_kind_can_write(self, kind, fits):
        assert util.check_item_name("n" * fits, kind) == "n" * fits
        with pytest.raises(BoostError) as exc:
            util.check_item_name("n" * (fits + 1), kind)
        assert exc.value.message == (
            "%s name is too long (256 bytes, limit 255): %r"
            % (kind, "n" * 40 + "…"))
        assert exc.value.hint == ("APFS and ext4 refuse a file or directory "
                                  "name over 255 bytes")

    def test_an_unknown_kind_is_held_to_the_longest_suffix(self):
        util.check_item_name("n" * 250, "other")
        with pytest.raises(BoostError):
            util.check_item_name("n" * 251, "other")

    def test_246_character_skill_and_workflow_install(self, sandbox, tmp_path):
        skill, wf = "s" + "b" * 245, "w" + "b" * 245
        make_tap(tmp_path / "long", skills={"long": skill},
                 commands={"lw": wf})
        store.install(catalog.resolve_one(skill))
        store.install(catalog.resolve_one(wf))
        assert (store.skill_store_dir(skill) / "SKILL.md").is_file()
        assert lockfile.get_skill(skill) is not None
        assert lockfile.get_workflow(wf) is not None

    def test_a_name_that_cannot_fit_is_refused_before_any_write(
            self, sandbox, tmp_path, boost):
        wf = "w" * 251
        make_tap(tmp_path / "long", commands={"lw": wf})
        res = boost("install", wf, expect=1)
        assert "workflow name is too long (256 bytes, limit 255)" in res.err
        assert "unexpected error" not in res.err
        assert lockfile.get_workflow(wf) is None
        assert not list((sandbox / ".claude").rglob("w*"))

    def test_an_import_under_a_name_too_long_is_refused(self, sandbox, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            store.install_from_path(src, name="s" * 256)
        assert exc.value.message.startswith(
            "skill name is too long (256 bytes, limit 255)")
        assert not store.skill_store_dir("x").exists()
