# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for core/projectlock.py — the committable per-repo lock."""
from __future__ import annotations

import json

import pytest

from boost_cli.core import projectlock
from boost_cli.errors import BoostError


def _entry(version="1.0.0"):
    return {"kind": "skill", "version": version, "tap": "t",
            "agents": ["claude-code"], "materializations": []}


def test_lock_path_is_dot_boost_in_the_repo(tmp_path):
    assert projectlock.lock_path(tmp_path) == \
        tmp_path / ".boost" / "skill-lock.json"


def test_missing_file_reads_as_an_empty_project(tmp_path):
    lock = projectlock.read(tmp_path)
    # Exact shape: this document is committed and read by other machines, so
    # its key names are a contract, not an implementation detail.
    assert set(lock) == {"version", "updated", "skills"}
    assert lock["skills"] == {}
    assert lock["version"] == projectlock.SCHEMA_VERSION
    assert projectlock.exists(tmp_path) is False


def test_set_then_get_round_trips(tmp_path):
    projectlock.set_skill(tmp_path, "brainstorm", _entry())
    assert projectlock.exists(tmp_path) is True
    got = projectlock.get_skill(tmp_path, "brainstorm")
    assert got["version"] == "1.0.0" and got["tap"] == "t"


def test_write_stamps_version_and_updated(tmp_path):
    projectlock.set_skill(tmp_path, "a", _entry())
    raw = projectlock.lock_path(tmp_path).read_text(encoding="utf-8")
    data = json.loads(raw)
    assert set(data) == {"version", "updated", "skills"}
    assert data["version"] == projectlock.SCHEMA_VERSION
    assert data["updated"]


def test_the_written_file_is_indented_and_ends_in_a_newline(tmp_path):
    # It lands in someone's git diff, so it is formatted for humans to read
    # and for line-based tools to diff — not minified onto one line.
    projectlock.set_skill(tmp_path, "a", _entry())
    raw = projectlock.lock_path(tmp_path).read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "\n  " in raw, "not indented — would diff as a single line"


def test_write_creates_missing_parent_directories(tmp_path):
    # `boost install --local` may be the first thing to write into this tree,
    # so .boost/ and everything above it has to be created.
    deep = tmp_path / "a" / "b" / "c"
    projectlock.set_skill(deep, "a", _entry())
    assert projectlock.lock_path(deep).is_file()


def test_a_lock_without_a_version_key_reads_as_the_current_schema(tmp_path):
    p = projectlock.lock_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"skills": {}}), encoding="utf-8")
    assert projectlock.read(tmp_path)["version"] == projectlock.SCHEMA_VERSION


def test_non_ascii_content_round_trips(tmp_path):
    # Skill names and tap names are user data — the file is UTF-8, explicitly.
    projectlock.set_skill(tmp_path, "a", dict(_entry(), tap="taperío-ünicode"))
    assert projectlock.get_skill(tmp_path, "a")["tap"] == "taperío-ünicode"


def test_installed_returns_every_skill(tmp_path):
    projectlock.set_skill(tmp_path, "a", _entry())
    projectlock.set_skill(tmp_path, "b", _entry("2.0.0"))
    assert sorted(projectlock.installed(tmp_path)) == ["a", "b"]


def test_set_replaces_an_existing_entry(tmp_path):
    projectlock.set_skill(tmp_path, "a", _entry("1.0.0"))
    projectlock.set_skill(tmp_path, "a", _entry("2.0.0"))
    assert projectlock.get_skill(tmp_path, "a")["version"] == "2.0.0"
    assert len(projectlock.installed(tmp_path)) == 1


def test_remove_reports_whether_it_was_present(tmp_path):
    projectlock.set_skill(tmp_path, "a", _entry())
    assert projectlock.remove_skill(tmp_path, "a") is True
    assert projectlock.remove_skill(tmp_path, "a") is False
    assert projectlock.get_skill(tmp_path, "a") is None


def test_removing_the_last_skill_keeps_the_file(tmp_path):
    # It is a tracked file in someone's repo — deleting it would show up as a
    # spurious deletion in their next `git status`.
    projectlock.set_skill(tmp_path, "a", _entry())
    projectlock.remove_skill(tmp_path, "a")
    assert projectlock.lock_path(tmp_path).is_file()
    assert projectlock.installed(tmp_path) == {}


def _err(capsys) -> str:
    """Captured stderr with the pane wrapping folded back to single spaces."""
    return " ".join(capsys.readouterr().err.split())


def _corrupt(tmp_path, raw: bytes):
    p = projectlock.lock_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return p


def test_a_corrupt_lock_is_left_in_place_not_silently_emptied(tmp_path, capsys):
    p = _corrupt(tmp_path, b"{not json")
    assert projectlock.read(tmp_path)["skills"] == {}
    # Left exactly where it is — no sidecar copy (it is committed; git has
    # it), and above all nothing written over it.
    assert sorted(q.name for q in p.parent.iterdir()) == ["skill-lock.json"]
    assert p.read_bytes() == b"{not json"
    err = _err(capsys)
    assert "%s: invalid JSON" % p in err
    assert "boost sees no project skills here and will not write over it" in err
    assert "`git checkout -- .boost/skill-lock.json`" in err


def test_a_corrupt_lock_warns_once_per_lock(tmp_path, capsys):
    _corrupt(tmp_path / "a", b"{")
    _corrupt(tmp_path / "b", b"{")
    for _ in range(3):
        projectlock.read(tmp_path / "a")
    projectlock.installed(tmp_path / "b")
    assert _err(capsys).count("will not write over it") == 2


def test_a_non_dict_document_is_treated_as_corrupt(tmp_path, capsys):
    p = _corrupt(tmp_path, b"[1, 2, 3]")
    assert projectlock.read(tmp_path)["skills"] == {}
    assert projectlock.check(tmp_path) == \
        "%s: expected a JSON object, found list" % p


def test_check_is_none_for_a_missing_or_valid_lock(tmp_path, capsys):
    assert projectlock.check(tmp_path) is None
    projectlock.set_skill(tmp_path, "a", _entry())
    assert projectlock.check(tmp_path) is None
    assert capsys.readouterr().err == ""


def test_write_refuses_over_a_corrupt_lock(tmp_path):
    # The bug: the next project install recorded only itself and dropped
    # every other skill's record, leaving their copies orphaned.
    p = _corrupt(tmp_path, b'{"skills": {"a": {}, "b": {}')
    with pytest.raises(BoostError) as exc:
        projectlock.set_skill(tmp_path, "c", _entry())
    assert exc.value.message == (
        "project lock is corrupt — boost will not write over it (%s)"
        % projectlock.check(tmp_path))
    assert exc.value.hint == (
        "it is tracked by the repo, so `git checkout -- "
        ".boost/skill-lock.json` restores the committed copy; or repair the "
        "JSON by hand")
    assert p.read_bytes() == b'{"skills": {"a": {}, "b": {}'
    with pytest.raises(BoostError):
        projectlock.remove_skill(tmp_path, "a")
    assert p.read_bytes() == b'{"skills": {"a": {}, "b": {}'


def test_refuse_corrupt_passes_a_missing_or_valid_lock(tmp_path):
    projectlock.refuse_corrupt(tmp_path)
    projectlock.set_skill(tmp_path, "a", _entry())
    projectlock.refuse_corrupt(tmp_path)
    assert list(projectlock.installed(tmp_path)) == ["a"]


def test_a_non_dict_skills_key_degrades_to_empty(tmp_path):
    p = projectlock.lock_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"version": 1, "skills": ["a"]}), encoding="utf-8")
    assert projectlock.read(tmp_path)["skills"] == {}


def test_there_is_no_history_directory(tmp_path):
    # git is this file's history — a .boost/lock-history would be litter.
    projectlock.set_skill(tmp_path, "a", _entry())
    projectlock.set_skill(tmp_path, "a", _entry("2.0.0"))
    assert sorted(p.name for p in (tmp_path / ".boost").iterdir()) == \
        ["skill-lock.json"]


def test_a_lock_that_is_not_utf8_is_preserved_not_a_crash(tmp_path, capsys):
    p = _corrupt(tmp_path, b"\xff\xfe")
    assert projectlock.read(tmp_path)["skills"] == {}
    assert p.read_bytes() == b"\xff\xfe"
    assert "%s: not valid UTF-8" % p in _err(capsys)
