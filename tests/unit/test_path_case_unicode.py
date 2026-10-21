# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Paths a tap's index holds apart and a macOS checkout does not.

Two ways a skill used to install as something other than itself while doctor,
drift and verify called it healthy:

* a dir the index records in NFD (a repo authored on Linux): macOS git
  rewrites boost's sparse pattern to NFC, it matches nothing, and the skill's
  ``scripts/`` stay outside the checkout;
* ``skills/Lint`` and ``skills/lint`` in one tap: a case-insensitive checkout
  holds one dir with one SKILL.md and both skills' scripts.
"""
from __future__ import annotations

import subprocess
import unicodedata
from pathlib import Path

import pytest

from boost_cli.core import catalog, gitutil, registry, store
from boost_cli.errors import BoostError

NFD_DIR = unicodedata.normalize("NFD", "skills/café-dir")


def _git(repo: Path, *args: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", "-c", "core.precomposeunicode=false", "-c",
         "core.ignorecase=false", *args],
        cwd=repo, check=True, capture_output=True, text=True,
        input=stdin, encoding="utf-8").stdout.strip()


def plumbing_repo(dest: Path, files: dict[str, str]) -> Path:
    """A repo committing ``files`` byte for byte, through the index alone.

    No working tree: the paths are ones this filesystem may not be able to
    hold apart (case twins) or would renormalize (NFD), which is the point.
    """
    dest.mkdir(parents=True)
    _git(dest, "init", "-q")
    for path, text in files.items():
        blob = _git(dest, "hash-object", "-w", "--stdin", stdin=text)
        _git(dest, "update-index", "--add", "--cacheinfo",
             "100644,%s,%s" % (blob, path))
    commit = _git(dest, "-c", "user.email=t@boost.test", "-c", "user.name=T",
                  "commit-tree", _git(dest, "write-tree"), "-m", "items")
    _git(dest, "update-ref", "refs/heads/main", commit)
    _git(dest, "symbolic-ref", "HEAD", "refs/heads/main")
    return dest


def _skill(name: str) -> str:
    return "---\nname: %s\ndescription: a skill\n---\n\n%s body\n" % (name, name)


def _ignorecase(clone: Path, on: bool) -> None:
    _git(clone, "config", "core.ignorecase", "true" if on else "false")


class TestSpellings:
    def test_plain_ascii_is_one_pattern(self):
        assert gitutil._spellings("skills/demo") == ["skills/demo"]

    def test_an_accent_is_both_forms_nfc_first(self):
        assert gitutil._spellings(NFD_DIR) == [
            unicodedata.normalize("NFC", NFD_DIR), NFD_DIR]


class TestNfdMaterialize:
    @pytest.fixture()
    def clone(self, tmp_path):
        src = plumbing_repo(tmp_path / "src", {
            NFD_DIR + "/SKILL.md": _skill("cafe-uni"),
            NFD_DIR + "/scripts/run.sh": "echo hi\n",
        })
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        return clone

    def test_an_nfd_dir_is_fetched_whole(self, clone):
        (entry,) = catalog.scan_dir(clone, "c")

        gitutil.materialize(clone, entry["rel_dir"])

        assert (clone / entry["rel_dir"] / "scripts" / "run.sh").is_file()
        cone = (clone / ".git" / "info" / "sparse-checkout").read_text(
            encoding="utf-8").splitlines()
        assert "/%s/*" % NFD_DIR in cone
        assert "/%s/*" % unicodedata.normalize("NFC", NFD_DIR) in cone

    def test_a_pattern_that_matched_nothing_is_refused(self, clone,
                                                       monkeypatch):
        """Whatever the cause, a skill still partly outside the checkout
        must not reach the copy that would install half of it."""
        monkeypatch.setattr(gitutil, "_sparse_add", lambda *a: None)

        with pytest.raises(BoostError) as exc:
            gitutil.materialize(clone, NFD_DIR)

        assert exc.value.message == (
            "could not check out 1 file of %s from the c tap (%s/scripts/"
            "run.sh), so installing it would copy a partial skill"
            % (NFD_DIR, NFD_DIR))
        assert exc.value.hint == (
            "`boost update c` and try again; if it persists, the tap's "
            "sparse checkout cannot match this path")

    def test_files_of_another_dir_are_not_counted(self, tmp_path,
                                                  monkeypatch):
        src = plumbing_repo(tmp_path / "src", {
            "skills/a/SKILL.md": _skill("a"),
            "skills/a/x.sh": "echo\n",
            "skills/ab/SKILL.md": _skill("ab"),
            "skills/ab/y.sh": "echo\n",
            "skills/ab/z.sh": "echo\n",
        })
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        monkeypatch.setattr(gitutil, "_sparse_add", lambda *a: None)

        with pytest.raises(BoostError) as exc:
            gitutil.materialize(clone, "skills/ab")

        assert exc.value.message.startswith(
            "could not check out 2 files of skills/ab from the c tap "
            "(skills/ab/y.sh, skills/ab/z.sh), so")

    def test_an_install_copies_the_scripts(self, sandbox, tmp_path):
        src = plumbing_repo(tmp_path / "unitap", {
            NFD_DIR + "/SKILL.md": _skill("cafe-uni"),
            NFD_DIR + "/scripts/run.sh": "echo hi\n",
        })
        tap = registry.add(str(src))
        (entry,) = catalog.rebuild_tap(tap)

        store.install(entry)

        dest = store.skill_store_dir("cafe-uni")
        assert sorted(p.relative_to(dest).as_posix()
                      for p in dest.rglob("*") if p.is_file()) == [
            "SKILL.md", "scripts/run.sh"]


LINT = {
    "skills/Lint/SKILL.md": _skill("Lint"),
    "skills/Lint/scripts/upper.sh": "echo upper\n",
    "skills/lint/SKILL.md": _skill("lint"),
    "skills/lint/scripts/lower.sh": "echo lower\n",
    "skills/other/SKILL.md": _skill("other"),
}


class TestCaseCollisionsInOneTap:
    @pytest.fixture()
    def clone(self, tmp_path):
        src = plumbing_repo(tmp_path / "src", LINT)
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        return clone

    def test_a_case_insensitive_clone_names_the_twins(self, clone):
        _ignorecase(clone, True)
        assert gitutil.case_collisions(clone) == [
            ["skills/Lint/SKILL.md", "skills/lint/SKILL.md"]]

    def test_a_case_sensitive_clone_has_none(self, clone):
        _ignorecase(clone, False)
        assert gitutil.case_collisions(clone) == []

    def test_a_dir_that_is_not_a_repo_has_none(self, tmp_path):
        assert gitutil.case_collisions(tmp_path) == []

    def test_the_tap_drops_both_and_says_so(self, sandbox, tmp_path,
                                            monkeypatch, capsys):
        monkeypatch.setattr(catalog, "_COLLIDED", set())
        tap = registry.add(str(plumbing_repo(tmp_path / "casetap", LINT)))
        _ignorecase(tap.path, True)
        catalog._COLLIDED.clear()
        capsys.readouterr()

        entries = catalog.rebuild_tap(tap)

        assert [e["name"] for e in entries] == ["other"]
        err = " ".join(capsys.readouterr().err.split())
        assert ("skipped 1 item in tap casetap whose paths differ only by "
                "case, which this filesystem cannot hold apart: "
                "skills/Lint/SKILL.md, skills/lint/SKILL.md") in err
        with pytest.raises(BoostError):
            catalog.resolve_one("lint")

    def test_cache_format_was_bumped(self):
        """A cache scanned before this kept the merged item."""
        assert catalog.CACHE_FORMAT >= 6

    def test_it_warns_once_per_tap(self, monkeypatch, capsys):
        monkeypatch.setattr(catalog, "_COLLIDED", set())
        catalog._report_collided("t", 2, ["a", "A"])
        catalog._report_collided("t", 2, ["a", "A"])
        catalog._report_collided("u", 0, ["a", "A"])
        err = " ".join(capsys.readouterr().err.split())
        assert err.count("skipped") == 1
        assert "skipped 2 items in tap t whose" in err


def _e(rel_dir: str, skill_md: str, kind: str = "skill") -> dict:
    return {"rel_dir": rel_dir, "skill_md": skill_md, "kind": kind}


LINT_GROUPS = [["skills/Lint/SKILL.md", "skills/lint/SKILL.md"]]


class TestDropCaseCollisions:

    def test_no_groups_keeps_every_entry(self):
        entries = [_e("skills/a", "skills/a/SKILL.md")]
        assert catalog.drop_case_collisions(entries, []) == (entries, [])

    def test_a_skill_holding_a_twin_is_dropped(self):
        keep = _e("skills/other", "skills/other/SKILL.md")
        kept, hit = catalog.drop_case_collisions(
            [_e("skills/Lint", "skills/Lint/SKILL.md"), keep], LINT_GROUPS)
        assert kept == [keep]
        assert hit == ["skills/Lint/SKILL.md", "skills/lint/SKILL.md"]

    def test_a_twin_deep_inside_a_skill_drops_it(self):
        groups = [["skills/a/scripts/X.sh", "skills/a/scripts/x.sh"]]
        kept, hit = catalog.drop_case_collisions(
            [_e("skills/a", "skills/a/SKILL.md"),
             _e("skills/ab", "skills/ab/SKILL.md")], groups)
        assert [e["rel_dir"] for e in kept] == ["skills/ab"]
        assert hit == groups[0]

    def test_a_skill_at_the_root_holds_every_path(self):
        kept, _ = catalog.drop_case_collisions(
            [_e(".", "SKILL.md")], LINT_GROUPS)
        assert kept == []

    def test_a_workflow_is_dropped_only_for_its_own_file(self):
        groups = [["a/commands/Ship.md", "a/commands/ship.md"]]
        ship = _e("a/commands", "a/commands/ship.md", "workflow")
        other = _e("a/commands", "a/commands/other.md", "workflow")
        kept, hit = catalog.drop_case_collisions([ship, other], groups)
        assert kept == [other]
        assert hit == groups[0]

    def test_an_entry_with_no_kind_is_a_skill(self):
        kept, _ = catalog.drop_case_collisions(
            [{"rel_dir": "skills/lint", "skill_md": "skills/lint/SKILL.md"}],
            LINT_GROUPS)
        assert kept == []

