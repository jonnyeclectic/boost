# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: what a sparse tap holds is never what an install copies by luck.

Three shapes of tap content each installed an incomplete skill, exited 0, and
left ``verify`` saying ``ok``:

* a ``SKILL.md`` at the repo root (``rel_dir`` ``"."``), whose ``scripts/``
  materialize skipped as "the root needs no narrowing";
* a link to another skill's directory, which exists (its ``SKILL.md`` is in
  the Markdown cone) and so was never widened: the copy held that Markdown,
  or the whole dir if the other skill had been installed first;
* a ``scripts/`` that is a git submodule, which boost never fetches.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import gitutil, lockfile, paths, store


def _git(cwd, *argv):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "-c", "protocol.file.allow=always", *argv],
                   cwd=cwd, check=True, capture_output=True)


def _skill(d, name):
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: %s skill\n---\n\nBody.\n" % (name, name),
        encoding="utf-8")


def _commit(repo):
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _files(d):
    return sorted(p.relative_to(d).as_posix() for p in d.rglob("*")
                  if p.is_file())


def _flat(text):
    return " ".join(text.split())


class TestARootSkillInstallsWhole:
    @pytest.fixture()
    def root_tap(self, tmp_path):
        src = tmp_path / "rootskill"
        _skill(src, "rootskill")
        (src / "scripts").mkdir()
        (src / "scripts" / "run.sh").write_text("echo hi\n", encoding="utf-8")
        (src / "lib" / "deep").mkdir(parents=True)
        (src / "lib" / "deep" / "a.py").write_text("x = 1\n", encoding="utf-8")
        return _commit(src)

    def test_install_copies_every_file_and_widens_to_the_root(
            self, boost, root_tap):
        boost("tap", root_tap)
        clone = paths.repos_dir() / "rootskill"
        assert not (clone / "scripts" / "run.sh").exists(), (
            "the fixture must start sparse, or it proves nothing")

        boost("install", "rootskill")

        assert _files(paths.store_dir() / "rootskill") == [
            "SKILL.md", "lib/deep/a.py", "scripts/run.sh"]
        cone = (clone / ".git" / "info" / "sparse-checkout").read_text(
            encoding="utf-8").splitlines()
        assert "/*" in cone
        assert _flat(boost("verify", "rootskill").out).startswith(
            "rootskill ok")

    def test_compact_keeps_a_root_skills_tree(self, boost, root_tap):
        """`compact` re-materializes `source_dir` "." as the root and its
        preview counts nothing under it as freight."""
        from boost_cli.core import compact

        boost("tap", root_tap)
        boost("install", "rootskill")
        clone = paths.repos_dir() / "rootskill"

        assert compact._kept_prefixes([".", "/", "skills/x/"]) == (
            "", "", "skills/x/")
        assert compact.freight_bytes(clone, ["."]) == 0
        boost("compact")
        assert (clone / "scripts" / "run.sh").is_file()


@pytest.mark.skipif(sys.platform == "win32",
                    reason="symlinks need Developer Mode on Windows")
class TestALinkToAnotherSkillIsOrderIndependent:
    @pytest.fixture()
    def link_tap(self, tmp_path):
        src = tmp_path / "linktap"
        _skill(src / "skills" / "a", "a")
        _skill(src / "skills" / "b", "b")
        (src / "skills" / "b" / "scripts").mkdir()
        (src / "skills" / "b" / "scripts" / "b.sh").write_text(
            "echo b\n", encoding="utf-8")
        _skill(src / "skills" / "c", "c")
        (src / "skills" / "c" / "tool.py").write_text("t = 1\n",
                                                       encoding="utf-8")
        (src / "skills" / "a" / "peer").symlink_to("../b")
        # A link inside the target leads on again: fetched in turn.
        (src / "skills" / "b" / "next").symlink_to("../c")
        return _commit(src)

    WANT = ("SKILL.md", "peer/SKILL.md", "peer/next/SKILL.md",
            "peer/next/tool.py", "peer/scripts/b.sh")

    def test_the_first_install_copies_the_whole_target(self, boost, link_tap):
        boost("tap", link_tap)
        boost("install", "a")
        assert _files(paths.store_dir() / "a") == list(self.WANT)

    def test_installing_the_target_first_changes_nothing(self, boost,
                                                         link_tap):
        boost("tap", link_tap)
        boost("install", "b")
        boost("install", "a")
        assert _files(paths.store_dir() / "a") == list(self.WANT)

    def test_an_already_widened_target_costs_no_git_call(self, boost,
                                                         link_tap,
                                                         monkeypatch):
        """`drift`, `outdated` and `doctor` resolve every installed skill's
        source: once the cone holds a target, that must be a file read."""
        from boost_cli.core import catalog
        boost("tap", link_tap)
        boost("install", "a")
        entry = next(e for e in catalog.all_entries() if e["name"] == "a")
        calls: list = []
        real = gitutil.run

        def spy(argv, **kw):
            calls.append(argv)
            return real(argv, **kw)
        monkeypatch.setattr(gitutil, "run", spy)

        store.source_dir_for(entry)

        assert [c for c in calls
                if "sparse-checkout" in c or "ls-files" in c] == []

    def test_existing_dirs_are_named_and_files_only_when_missing(
            self, tmp_path):
        repo = tmp_path / "repo"
        skill = repo / "skills" / "s"
        (skill / "own").mkdir(parents=True)
        (repo / "other").mkdir()
        (repo / "here.txt").write_text("h", encoding="utf-8")
        (skill / "dir").symlink_to("../../other")
        (skill / "file").symlink_to("../../here.txt")
        (skill / "inside").symlink_to("own")
        (skill / "loop").symlink_to("..")
        (skill / "root").symlink_to("../..")
        assert store.link_targets_to_fetch(repo, skill) == ["other"]

    def test_a_target_dir_that_leaves_the_tap_is_not_walked(
            self, tmp_path, monkeypatch):
        """``skills/b -> <outside>`` is lexically in the tap, so it is named,
        but walking it would read whatever it leads to (``/`` included)."""
        repo = tmp_path / "repo"
        skill = repo / "skills" / "a"
        skill.mkdir(parents=True)
        (repo / "inside" / "deep").mkdir(parents=True)
        (repo / "inside" / "deep" / "f").write_text("f", encoding="utf-8")
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "hop").symlink_to(repo / "inside")
        (repo / "skills" / "b").symlink_to(outside)
        (repo / "skills" / "c").symlink_to("../inside")
        (skill / "peer").symlink_to("../b")
        (skill / "ok").symlink_to("../c")
        walked: list[str] = []
        real = store.link_targets_to_fetch

        def spy(r, src, own=None):
            walked.append(Path(src).relative_to(repo).as_posix())
            return real(r, src, own)
        monkeypatch.setattr(store, "link_targets_to_fetch", spy)
        monkeypatch.setattr(gitutil, "materialize_paths", lambda r, p: None)

        store._materialize_link_targets(repo, skill)

        assert sorted(walked) == ["skills/a", "skills/c"]


class TestASubmoduleIsNamedNotShippedAsComplete:
    @pytest.fixture()
    def sub_tap(self, tmp_path):
        helper = tmp_path / "subhelper"
        helper.mkdir()
        (helper / "h.sh").write_text("echo h\n", encoding="utf-8")
        _commit(helper)
        src = tmp_path / "subtap"
        _skill(src / "skills" / "withsub", "withsub")
        _skill(src / "skills" / "plain", "plain")
        _commit(src)
        _git(src, "submodule", "add", "-q", str(helper),
             "skills/withsub/scripts")
        _git(src, "commit", "-qm", "sub")
        return src

    NOTE = ("scripts is a git submodule, which boost does not fetch, so it "
            "is empty")

    def test_gitlinks_reads_the_index(self, boost, sub_tap):
        boost("tap", sub_tap)
        clone = paths.repos_dir() / "subtap"
        assert gitutil.gitlinks(clone, "skills/withsub") == [
            "skills/withsub/scripts"]
        assert gitutil.gitlinks(clone, ".") == ["skills/withsub/scripts"]
        assert gitutil.gitlinks(clone, "skills/plain") == []
        assert gitutil.gitlinks(sub_tap.parent, ".") == [], (
            "a dir git cannot read has nothing to report")

    def test_install_warns_records_and_verify_says_so(self, boost, sub_tap):
        boost("tap", sub_tap)
        assert json.loads(boost("info", "withsub", "--json").out)[
            "submodules"] == ["scripts"]

        res = boost("install", "withsub")

        assert "withsub: " + self.NOTE in _flat(res.out + res.err)
        assert lockfile.get_skill("withsub")["submodules"] == ["scripts"]
        assert _flat(boost("verify", "withsub").out).startswith(
            "withsub ok " + self.NOTE)
        rows = json.loads(boost("verify", "withsub", "--json").out)["skills"]
        assert rows[0]["submodules"] == ["scripts"]
        assert "submodule " + self.NOTE in _flat(boost("info", "withsub").out)

    def test_a_skill_without_one_says_nothing(self, boost, sub_tap):
        boost("tap", sub_tap)
        res = boost("install", "plain")
        assert "submodule" not in res.out + res.err
        assert "submodules" not in lockfile.get_skill("plain")
        assert json.loads(boost("verify", "plain", "--json").out)[
            "skills"][0].get("submodules") is None
        assert json.loads(boost("info", "plain", "--json").out)[
            "submodules"] == []

    def test_a_project_install_records_it_too(self, boost, sub_tap,
                                              tmp_path, monkeypatch):
        from boost_cli.core import projectlock
        proj = tmp_path / "proj"
        proj.mkdir()
        _git(proj, "init", "-q")
        monkeypatch.chdir(proj)
        boost("tap", sub_tap)

        res = boost("install", "withsub", "--local")

        assert "withsub: " + self.NOTE in _flat(res.out + res.err)
        assert projectlock.installed(proj)["withsub"]["submodules"] == [
            "scripts"]
        assert self.NOTE in _flat(boost("verify", "withsub").out)

    def test_not_a_skill_or_not_cloned_is_empty(self, boost, sub_tap):
        boost("tap", sub_tap)
        assert store.unfetched_submodules(
            {"kind": "rule", "tap": "subtap", "rel_dir": "skills/withsub"}) == []
        assert store.unfetched_submodules(
            {"tap": "nope", "rel_dir": "skills/withsub"}) == []
        assert store.unfetched_submodules(
            {"tap": "subtap", "rel_dir": "skills/withsub"}) == ["scripts"]
        assert store.unfetched_submodules(
            {"tap": "subtap", "rel_dir": "."}) == ["skills/withsub/scripts"]
