# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A corrupt project lock fails loudly instead of reading as an empty project.

With ``.boost/skill-lock.json`` truncated, `boost list` showed no project
section, doctor said healthy, and the next `install --scope project` rewrote
the lock as that one skill — the other skills' copies stayed in every agent
dir with no record, so `uninstall --local` called them not installed and a
reinstall refused them as files boost did not write.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import projectlock


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "plc-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_a_corrupt_project_lock_is_reported_and_never_written_over(
        boost, tapped, repo):
    boost("install", "brainstorming", "--scope", "project")
    boost("install", "cowboy-coding", "--scope", "project")
    p = projectlock.lock_path(repo)
    raw = p.read_bytes()[:-20]
    p.write_bytes(raw)
    err = projectlock.check(repo)
    assert err is not None and err.startswith("%s: invalid JSON (" % p)

    r = boost("list")
    assert ("%s — boost sees no project skills here and will not write over "
            "it" % err) in _flat(r.err)

    r = boost("doctor", "--json", expect=1)
    rows = [c for c in json.loads(r.out)["checks"]
            if c["name"] == "project-lock"]
    assert [c["message"] for c in rows] == [
        "%s — boost sees no project skills here and refuses to install or "
        "uninstall any until it is repaired; it is tracked by the repo, so "
        "`git checkout -- .boost/skill-lock.json` restores the committed "
        "copy; or repair the JSON by hand" % err]

    r = boost("install", "tdd-workflow", "--scope", "project", expect=1)
    assert ("project lock is corrupt — boost will not write over it (%s)"
            % err) in _flat(r.err)
    # Refused before anything was copied, and the lock is untouched.
    assert not (repo / ".claude" / "skills" / "tdd-workflow").exists()
    assert p.read_bytes() == raw

    r = boost("uninstall", "brainstorming", "--local", expect=1)
    assert "project lock is corrupt" in r.err
    assert "not installed in this project" not in r.err
    assert (repo / ".claude" / "skills" / "brainstorming").is_dir()
    assert p.read_bytes() == raw
    # No sidecar copy: the file stays where it is, for git to restore.
    assert sorted(q.name for q in p.parent.iterdir()) == ["skill-lock.json"]
