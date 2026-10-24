# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A project skill whose tap moved: doctor's advice has to be one that works.

doctor said "run `boost heal`" (or `boost sync`) for a missing copy, heal
and sync declined because the tap had moved past the locked commit, and
doctor said the same thing again. An intact sibling copy holds the locked
bytes, so heal restores from it; with no copy left doctor names the choices
that do work, and sync fails over the decline instead of exiting 0.
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from boost_cli.core import gitutil, projectlock, util

pytestmark = pytest.mark.skipif(not gitutil.has_git(), reason="needs git")

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t",
       "-c", "commit.gpgsign=false"]


def _git(cwd, *args):
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def _md(version):
    return ("---\nname: movey\ndescription: %s\nversion: 1.0.0\n---\n%s\n"
            % (version, version))


@pytest.fixture()
def moved(boost, tmp_path, monkeypatch):
    """`movey` installed --local at v1, then its tap moved to v2."""
    src = tmp_path / "mvtap"
    (src / "skills" / "movey").mkdir(parents=True)
    md = src / "skills" / "movey" / "SKILL.md"
    md.write_text(_md("v1"), encoding="utf-8")
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "v1")
    boost("tap", src)
    repo = tmp_path / "mvproj"
    repo.mkdir()
    _git(repo, "init", "-q")
    # Pinned off so each test controls line endings itself; the
    # core.autocrlf=true checkout has its own case below.
    _git(repo, "config", "core.autocrlf", "false")
    monkeypatch.chdir(repo)
    boost("install", "--local", "movey")
    md.write_text(_md("v2"), encoding="utf-8")
    _git(src, "commit", "-qam", "v2")
    # From outside the project, so the update moves the tap and not the copies.
    monkeypatch.chdir(tmp_path)
    boost("update", "mvtap")
    monkeypatch.chdir(repo)
    # In lock row order, which is the order doctor names them in.
    rows = projectlock.get_skill(repo, "movey")["materializations"]
    copies = [repo / m["path"] for m in rows]
    assert len(copies) >= 2 and all(c.is_dir() for c in copies)
    assert all("v1" in (c / "SKILL.md").read_text(encoding="utf-8")
               for c in copies)
    return repo.resolve(), copies


def _project_issues(boost):
    r = boost("doctor", "--json", expect=None)
    return [c["message"] for c in json.loads(r.out)["checks"]
            if c["name"] == "project-skill" and c["status"] == "issue"]


def test_one_copy_gone_is_restored_from_an_intact_sibling(boost, moved):
    repo, copies = moved
    locked = util.sha256_dir(copies[1])
    util.rmtree(copies[0])
    rel = copies[0].relative_to(repo).as_posix()
    assert _project_issues(boost) == [
        "project skill movey is missing %s — run `boost heal`" % rel]
    r = boost("heal", "--dry-run")
    assert "would re-materialize project skill movey" in r.out
    assert not copies[0].exists()
    r = boost("heal")
    assert "re-materialized movey from its" in r.out
    assert util.sha256_dir(copies[0]) == locked
    assert "v2" not in (copies[0] / "SKILL.md").read_text(encoding="utf-8")
    assert _project_issues(boost) == []


def test_every_copy_gone_names_what_works_and_sync_fails(boost, moved):
    repo, copies = moved
    for c in copies:
        util.rmtree(c)
    rels = [c.relative_to(repo).as_posix() for c in copies]
    [msg] = _project_issues(boost)
    assert msg == (
        "project skill movey is missing %s, and its tap has moved since the "
        "project lock was written, so `boost heal` restores it only if this "
        "skill's files did not change — `boost heal --dry-run` says which; "
        "otherwise `boost install --local movey --force` moves every copy "
        "and the lock to the tap's new version" % ", ".join(rels))
    assert "run `boost sync`" not in msg
    r = boost("heal", "--dry-run", expect=1)
    assert "repair declined" in r.out
    assert not any(c.exists() for c in copies)
    boost("sync", expect=1)
    boost("heal", expect=1)
    assert not any(c.exists() for c in copies)
    # The remedy it names works.
    boost("install", "--local", "movey", "--force")
    assert _project_issues(boost) == []


def test_committed_copies_get_a_git_checkout_that_restores_them(
        boost, moved):
    repo, copies = moved
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "proj")
    locked = util.sha256_dir(copies[0])
    for c in copies:
        util.rmtree(c)
    [msg] = _project_issues(boost)
    cmd = re.search(r"`(git -C [^`]*)`", msg)
    assert cmd is not None, msg
    rels = [c.relative_to(repo).as_posix() for c in copies]
    assert cmd.group(1) == "git -C %s checkout -- %s" % (
        util.shell_arg(str(repo)), " ".join(map(util.shell_arg, rels)))
    assert "restores the committed copies, or `boost install" in msg
    subprocess.run(["git", "-C", str(repo), "checkout", "--", *rels],
                   cwd=repo / ".boost", check=True)
    assert all(util.sha256_dir(c) == locked for c in copies)
    assert _project_issues(boost) == []


def test_an_autocrlf_checkout_of_the_copies_is_not_drift(boost, moved):
    # Git for Windows' default: a teammate's checkout restores every copy
    # CRLF. That is not an edit, so verify, doctor and drift stay clean.
    repo, copies = moved
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "proj")
    locked = projectlock.get_skill(repo, "movey")["sha256"]
    for c in copies:
        util.rmtree(c)
    rels = [c.relative_to(repo).as_posix() for c in copies]
    _git(repo, "-c", "core.autocrlf=true", "checkout", "--", *rels)
    assert all(b"\r\n" in (c / "SKILL.md").read_bytes() for c in copies)
    assert all(util.sha256_dir(c, raw=True) != locked for c in copies)
    assert _project_issues(boost) == []
    r = boost("verify")
    assert "modified" not in r.out
    r = boost("drift")
    assert "local-edits" not in r.out
    assert projectlock.get_skill(repo, "movey")["sha256"] == locked
