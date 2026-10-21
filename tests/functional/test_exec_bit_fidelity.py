# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A script's exec bit is part of what is installed.

`util.sha256_dir` hashes paths and bytes, so a mode was invisible: an
upstream `chmod +x` commit left `update` saying "everything up to date" with
the store copy still 0o644, and a `chmod -x` on the store copy passed
`verify`, `doctor` and `drift`. Rows now record the exec bits as ``exec``;
a row written before that keeps the content-only check.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys

import pytest

from boost_cli.core import lockfile, store

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="no POSIX exec bit")


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _make_tap(boost, tmp_path, mode):
    repo = tmp_path / "exec-tap"
    sk = repo / "skills" / "beta"
    (sk / "scripts").mkdir(parents=True)
    (sk / "SKILL.md").write_text(
        "---\nname: beta\ndescription: has a script\n---\nbody\n",
        encoding="utf-8")
    (sk / "scripts" / "run.sh").write_text("echo hi\n", encoding="utf-8")
    (sk / "scripts" / "run.sh").chmod(mode)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    boost("tap", repo)
    return repo


@pytest.fixture()
def tap(boost, tmp_path):
    """``run.sh`` committed 0o644."""
    return _make_tap(boost, tmp_path, 0o644)


@pytest.fixture()
def exec_tap(boost, tmp_path):
    """``run.sh`` committed 0o755."""
    return _make_tap(boost, tmp_path, 0o755)


def _script():
    return store.skill_store_dir("beta") / "scripts" / "run.sh"


def _exec(p):
    return bool(os.stat(p).st_mode & stat.S_IXUSR)


def _drop_exec_field():
    def put(lock):
        lock["skills"]["beta"].pop("exec")
    lockfile.mutate(put)


def test_install_records_the_exec_bits(boost, exec_tap):
    boost("install", "beta")

    assert lockfile.get_skill("beta")["exec"] == ["scripts/run.sh"]


def test_a_mode_only_upstream_commit_is_refreshed_by_update(boost, tap):
    boost("install", "beta")
    assert lockfile.get_skill("beta")["exec"] == []
    (tap / "skills" / "beta" / "scripts" / "run.sh").chmod(0o755)
    _git(tap, "commit", "-qam", "make executable")

    r = boost("update")

    assert "refreshed beta" in r.out
    assert _exec(_script())
    assert lockfile.get_skill("beta")["exec"] == ["scripts/run.sh"]
    boost("verify", "beta")


def test_chmod_on_the_store_copy_fails_verify_and_drift(boost, exec_tap):
    boost("install", "beta")
    _script().chmod(0o644)

    r = boost("verify", "beta", expect=1)
    assert "beta" in r.out and "modified" in r.out
    data = json.loads(boost("drift", "--json").out)
    assert [(s["name"], s["status"]) for s in data["skills"]] == [
        ("beta", "local-edits")]
    r = boost("doctor", expect=None)
    assert "skill beta modified since install" in " ".join(r.out.split())


def test_a_row_without_exec_keeps_the_content_only_check(boost, exec_tap):
    """The backward-compatible half: no existing install reads as modified."""
    boost("install", "beta")
    _drop_exec_field()
    _script().chmod(0o644)

    boost("verify", "beta")
    # The source and the copy disagree, and with no recorded bits the copy
    # is taken as the install: the tap is what moved.
    data = json.loads(boost("drift", "--json").out)
    assert [(s["name"], s["status"]) for s in data["skills"]] == [
        ("beta", "upstream-moved")]


def test_an_untouched_install_stays_in_sync(boost, exec_tap):
    boost("install", "beta")

    boost("verify", "beta")
    data = json.loads(boost("drift", "--json").out)
    assert [(s["name"], s["status"]) for s in data["skills"]] == [
        ("beta", "in-sync")]


def test_a_project_copy_s_mode_is_verified_too(boost, exec_tap, tmp_path,
                                               monkeypatch):
    from boost_cli.core import integrity, projectlock
    repo = tmp_path / "proj"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    boost("install", "--local", "beta")
    entry = projectlock.get_skill(repo.resolve(), "beta")
    assert entry["exec"] == ["scripts/run.sh"]
    copy = integrity.project_skill_dir(entry, repo.resolve())
    assert integrity.project_status(entry, repo.resolve()) == \
        integrity.STATUS_OK

    (copy / "scripts" / "run.sh").chmod(0o644)

    assert integrity.project_status(entry, repo.resolve()) == \
        integrity.STATUS_MODIFIED
    boost("verify", expect=1)


def test_a_row_without_exec_is_refreshed_by_a_mode_only_commit(boost, tap):
    """An install from before rows recorded ``exec`` is compared through the
    copy on disk, so the upstream ``chmod +x`` still reaches it."""
    boost("install", "beta")
    _drop_exec_field()
    (tap / "skills" / "beta" / "scripts" / "run.sh").chmod(0o755)
    _git(tap, "commit", "-qam", "make executable")

    r = boost("update")

    assert "refreshed beta" in r.out
    assert _exec(_script())
    assert lockfile.get_skill("beta")["exec"] == ["scripts/run.sh"]


def test_a_row_without_exec_is_not_refreshed_by_an_unrelated_commit(
        boost, exec_tap):
    """The tap moved but the skill did not: same bytes, same modes."""
    boost("install", "beta")
    _drop_exec_field()
    (exec_tap / "README.md").write_text("other\n", encoding="utf-8")
    _git(exec_tap, "add", "-A")
    _git(exec_tap, "commit", "-qm", "unrelated")

    r = boost("update")

    assert "refreshed beta" not in r.out
    assert "exec" not in lockfile.get_skill("beta")
