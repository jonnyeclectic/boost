# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost export` and `boost bundle dump` cover project-scope installs.

Both read only the user lock: with a skill installed `--local`, `boost list`
showed it while `export NAME` said "not installed — see `boost list`",
`export` said "no skills installed" and `bundle dump` wrote an empty file and
reported success.
"""
from __future__ import annotations

import json
import shutil
import tarfile

import pytest

from boost_cli.core import integrity, lockfile, paths, projectlock


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "pse-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _own_tap(boost, fixture_tap_src, tmp_path, name):
    dest = tmp_path / name
    shutil.copytree(fixture_tap_src, dest)
    boost("tap", dest)
    return dest


class TestExportProjectScope:
    def test_named_project_skill_is_exported(self, boost, fixture_tap_src,
                                             tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-named-tap")
        boost("install", "--local", "commit-messages")
        out = tmp_path / "pse-named.tar.gz"
        r = boost("export", "commit-messages", "-o", out)
        assert "exported 1 skill" in r.out
        with tarfile.open(str(out)) as tf:
            names = tf.getnames()
            manifest = tf.extractfile("Boostfile").read().decode()
        assert "commit-messages/SKILL.md" in names
        assert ("skill pse-named-tap:commit-messages@1.0.2 --local"
                in manifest.splitlines())

    def test_default_export_includes_both_scopes(self, boost, fixture_tap_src,
                                                 tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-all-tap")
        boost("install", "brainstorming")
        boost("install", "--local", "commit-messages")
        out = tmp_path / "pse-all.tar.gz"
        r = boost("export", "-o", out)
        assert "exported 2 skills" in r.out
        with tarfile.open(str(out)) as tf:
            names = tf.getnames()
        assert "brainstorming/SKILL.md" in names
        assert "commit-messages/SKILL.md" in names

    def test_both_scopes_exports_user_copy_and_says_so(
            self, boost, fixture_tap_src, tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-both-tap")
        boost("install", "commit-messages")
        boost("install", "--local", "commit-messages")
        out = tmp_path / "pse-both.tar.gz"
        r = boost("export", "-o", out)
        assert "exported 1 skill" in r.out
        assert "installed at both scopes — exported the user-scope copy" in r.out
        with tarfile.open(str(out)) as tf:
            manifest = tf.extractfile("Boostfile").read().decode()
        assert "skill pse-both-tap:commit-messages@1.0.2" in manifest.splitlines()
        assert "--local" not in manifest

    def test_missing_project_copy_is_named(self, boost, fixture_tap_src,
                                           tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-gone-tap")
        boost("install", "--local", "commit-messages")
        entry = projectlock.get_skill(repo, "commit-messages")
        while (d := integrity.project_skill_dir(entry, repo)) is not None:
            shutil.rmtree(d)
        r = boost("export", "commit-messages", "-o",
                  tmp_path / "pse-gone.tar.gz", expect=1)
        assert "project copy of commit-messages is missing" in r.err
        assert "boost install --local commit-messages --force" in r.err

    def test_unknown_name_still_not_installed(self, boost, tapped, repo):
        r = boost("export", "pse-nope", expect=1)
        assert "pse-nope is not installed" in r.err


class TestBundleProjectScope:
    def test_dump_writes_project_skill_with_local_token(
            self, boost, fixture_tap_src, tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-dump-tap")
        boost("install", "--local", "commit-messages")
        bf = tmp_path / "pse-Boostfile"
        r = boost("bundle", "dump", bf)
        assert "wrote" in r.out and "(1 tap, 1 skill)" in r.out
        lines = bf.read_text(encoding="utf-8").splitlines()
        assert lines[1].startswith("tap pse-dump-tap ")
        assert lines[2:] == ["skill pse-dump-tap:commit-messages@1.0.2 --local"]

    def test_dump_round_trips_at_project_scope(self, boost, fixture_tap_src,
                                               tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-rt-tap")
        boost("install", "--local", "commit-messages")
        bf = tmp_path / "pse-rt-Boostfile"
        boost("bundle", "dump", bf)
        r = boost("bundle", "install", bf, "--dry-run")
        assert "1 already present" in r.out
        boost("uninstall", "--local", "commit-messages")
        assert projectlock.get_skill(repo, "commit-messages") is None

        r = boost("bundle", "install", bf, "--dry-run")
        assert "would install commit-messages v1.0.2 (pse-rt-tap) at project scope" in r.out
        r = boost("bundle", "install", bf)
        assert "installed commit-messages v1.0.2 (pse-rt-tap) at project scope" in r.out
        assert projectlock.get_skill(repo, "commit-messages")["version"] == "1.0.2"
        assert lockfile.get_skill("commit-messages") is None
        assert not (paths.store_dir() / "commit-messages").exists()

    def test_local_line_without_a_project_is_skipped(
            self, boost, fixture_tap_src, tmp_path, monkeypatch):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-noproj-tap")
        bf = tmp_path / "pse-noproj-Boostfile"
        bf.write_text("skill pse-noproj-tap:commit-messages@1.0.2 --local\n",
                      encoding="utf-8")
        monkeypatch.chdir(paths.home())
        r = boost("bundle", "install", bf, expect=1)
        assert ("commit-messages is a project-scope skill and there is no "
                "project directory here — skipped") in r.out + r.err
        assert lockfile.get_skill("commit-messages") is None

    def test_dump_user_and_project_json_lock_unchanged(
            self, boost, fixture_tap_src, tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "pse-mixed-tap")
        boost("install", "brainstorming")
        boost("install", "--local", "commit-messages")
        before = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        r = boost("bundle", "dump")
        lines = r.out.splitlines()
        assert "skill pse-mixed-tap:brainstorming@1.4.0" in lines
        assert "skill pse-mixed-tap:commit-messages@1.0.2 --local" in lines
        assert lines.index("skill pse-mixed-tap:brainstorming@1.4.0") < \
            lines.index("skill pse-mixed-tap:commit-messages@1.0.2 --local")
        assert json.loads(paths.lockfile_path().read_text(
            encoding="utf-8")) == before
