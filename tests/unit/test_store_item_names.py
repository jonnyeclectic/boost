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

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import agents, catalog, lockfile, paths, registry, store, util
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


# A 246-255 byte component under the runner's temp dir passes MAX_PATH on
# Windows: a long-path setting the test cannot see, not boost's limit (as in
# test_bad_input_is_not_a_crash.py).
long_path = pytest.mark.skipif(
    sys.platform == "win32",
    reason="total path exceeds MAX_PATH under the runner's temp dir")


class TestLongNames:
    @long_path
    def test_a_temp_file_beside_a_long_name_is_no_longer_than_it(self, tmp_path):
        # 250 bytes fits as a file name; `.<name>.XXXXXXXX.tmp` did not.
        p = tmp_path / ("w" * 250)
        util.atomic_write_text(p, "x")
        assert p.read_text(encoding="utf-8") == "x"
        assert [q.name for q in tmp_path.iterdir()] == [p.name]

    def test_the_temp_prefix_is_short_and_hidden(self):
        assert util.TEMP_PREFIX == ".boost-"

    @long_path
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

    @long_path
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


def _entry(tap, name):
    return next(e for e in catalog.load_tap(tap) if e["name"] == name)


class TestCaseCollisions:
    @pytest.fixture()
    def two(self, sandbox, tmp_path):
        a = make_tap(tmp_path / "tapa", skills={"Foo": "Foo"})
        b = make_tap(tmp_path / "tapb", skills={"foo": "foo"})
        store.install(_entry(a, "Foo"))
        return a, b

    MESSAGE = ("foo differs only by case from Foo, which is already "
               "installed; on a case-insensitive filesystem they would share "
               "one store dir")

    @pytest.mark.parametrize("force", [False, True])
    def test_a_name_differing_only_by_case_is_refused(self, two, force):
        with pytest.raises(BoostError) as exc:
            store.install(_entry(two[1], "foo"), force=force)
        assert exc.value.message == self.MESSAGE
        assert exc.value.hint == ("`boost uninstall Foo` first if foo should "
                                  "replace it")
        assert list(lockfile.installed()) == ["Foo"]
        body = (store.skill_store_dir("Foo") / "SKILL.md").read_text(
            encoding="utf-8")
        assert "Foo body" in body

    def test_the_same_name_still_reinstalls(self, two):
        res = store.install(_entry(two[0], "Foo"), force=True)
        assert res.upgraded is True

    def test_the_cli_refuses_without_offering_force(self, two, boost):
        res = boost("install", "foo", "--force", expect=1)
        assert "differs only by case from Foo" in res.err
        assert "--force" not in res.err
        assert "does not record it" not in res.err

    def test_an_import_differing_only_by_case_is_refused(self, two, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: foo\n---\n", encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            store.install_from_path(src, force=True)
        assert exc.value.message == self.MESSAGE

    def test_no_collision_with_an_unrelated_name(self):
        store.refuse_case_collision("foo", {"foo": {}, "bar": {}})

    def test_the_project_names_where_it_is_installed(self):
        with pytest.raises(BoostError) as exc:
            store.refuse_case_collision("foo", {"FOO": {}}, " in this project")
        assert exc.value.message.startswith(
            "foo differs only by case from FOO, which is already installed "
            "in this project; ")
        assert exc.value.wrap is True


def _no_symlinks(monkeypatch, exc):
    def refuse(self, target, target_is_directory=False):
        raise exc
    monkeypatch.setattr(Path, "symlink_to", refuse)


PRIVILEGE = OSError(errno.EINVAL, "A required privilege is not held by the client")


class TestNoSymlinks:
    @pytest.fixture()
    def entry(self, sandbox, tmp_path):
        tap = make_tap(tmp_path / "t", skills={"lone": "lone"})
        return _entry(tap, "lone")

    def test_an_install_skips_every_linking_agent_and_says_why(
            self, entry, monkeypatch, sandbox):
        _no_symlinks(monkeypatch, PRIVILEGE)
        res = store.install(entry)
        linking = list(agents.linking_agents())
        assert res.linked == []
        assert res.refused == linking
        assert res.unlinkable == [str(d) for d in
                                  agents.linking_agents().values()]
        assert res.unwritable == [] and res.blocked == []
        # The store copy stays: agents that read it directly still get it,
        # and the lock records the refused agents so `boost sync` retries.
        assert (store.skill_store_dir("lone") / "SKILL.md").is_file()
        assert lockfile.get_skill("lone")["refused_agents"] == linking
        assert not os.path.lexists(sandbox / ".claude" / "skills" / "lone")

    def test_the_refusal_names_the_dir_and_the_remedy(self):
        assert store.symlink_refusal(str(paths.home() / ".claude" / "skills")) \
            == ("this system refused to create a symlink in ~/.claude/skills",
                "on Windows turn on Developer Mode (Settings > System > For "
                "developers) or use an administrator shell; on a FAT or exFAT "
                "drive keep your home on a filesystem with symlinks")

    def test_the_cli_exits_0_and_warns_not_70(self, entry, monkeypatch, boost):
        _no_symlinks(monkeypatch, PRIVILEGE)
        res = boost("install", "lone")
        err = " ".join((res.out + res.err).split())
        assert ("not linked: this system refused to create a symlink in "
                "~/.claude/skills") in err
        assert "Developer Mode" in err
        assert "then `boost sync` adds the link" in err
        assert "unexpected error" not in err

    def test_an_import_skips_the_agents_and_keeps_the_copy(
            self, sandbox, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: imp\n---\n", encoding="utf-8")
        _no_symlinks(monkeypatch, PRIVILEGE)
        res = store.install_from_path(src)
        assert res.linked == []
        assert res.refused == list(agents.linking_agents())
        assert (store.skill_store_dir("imp") / "SKILL.md").is_file()
        assert lockfile.get_skill("imp") is not None

    def test_a_failed_import_link_leaves_no_fresh_copy(self, sandbox, tmp_path,
                                                       monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: imp\n---\n", encoding="utf-8")
        _no_symlinks(monkeypatch, OSError(errno.ENOSPC, "No space left"))
        with pytest.raises(OSError):
            store.install_from_path(src)
        assert not os.path.lexists(store.skill_store_dir("imp"))
        assert lockfile.get_skill("imp") is None

    def test_a_failed_import_over_an_existing_dir_keeps_it(
            self, sandbox, tmp_path, monkeypatch):
        # Not fresh: the rollback must not delete a copy that was there.
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: imp\n---\n", encoding="utf-8")
        dest = store.skill_store_dir("imp")
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("---\nname: imp\n---\n", encoding="utf-8")
        _no_symlinks(monkeypatch, OSError(errno.ENOSPC, "No space left"))
        with pytest.raises(OSError):
            store.install_from_path(src, force=True)
        assert (dest / "SKILL.md").is_file()

    def test_any_other_link_failure_stays_loud(self, entry, monkeypatch):
        _no_symlinks(monkeypatch, OSError(errno.ENOSPC, "No space left"))
        with pytest.raises(OSError) as exc:
            store.install(entry)
        assert not isinstance(exc.value, BoostError)
        assert not os.path.lexists(store.skill_store_dir("lone"))

    @pytest.mark.parametrize(("exc", "unsupported"), [
        (OSError(errno.EINVAL, "x"), True),
        (OSError(errno.ENOTSUP, "x"), True),
        (OSError(errno.EOPNOTSUPP, "x"), True),
        (OSError(errno.ENOSYS, "x"), True),
        (OSError(errno.ENOSPC, "x"), False),
        (OSError(errno.EEXIST, "x"), False),
        (PermissionError(errno.EPERM, "x"), False),
        (PermissionError(errno.EINVAL, "x"), False),
    ])
    def test_which_errors_mean_no_symlinks(self, exc, unsupported):
        assert store.symlinks_unsupported(exc) is unsupported

    def test_windows_privilege_not_held_by_winerror(self):
        for exc in (OSError(errno.EIO, "x"), PermissionError(errno.EACCES, "x")):
            exc.winerror = 1314
            assert store.symlinks_unsupported(exc) is True
            exc.winerror = 1313
            assert store.symlinks_unsupported(exc) is False
