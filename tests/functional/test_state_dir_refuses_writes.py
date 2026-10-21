# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A ``~/.boost/state`` that refuses writes is a sentence, not a crash.

focus, context map, policy set and trust add each ended in a bare
``write_text`` there and exited 70 with a ``PermissionError`` crash report;
focus had already sidelined every other skill by then, and with no session on
file ``boost focus`` then said there was none.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

from boost_cli.core import jsonstate, lockfile, paths

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32",
                       reason="chmod can't make a directory unwritable on Windows"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores mode bits"),
]

KEY = "RWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3"


def _refused(boost, *argv):
    state = paths.state_dir()
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o500)
    try:
        return boost(*argv, expect=1)
    finally:
        state.chmod(0o700)


def _assert_named(r, fname):
    err = " ".join(r.err.split())
    assert ("could not save ~/.boost/state/%s (Permission denied): "
            "~/.boost/state is not writable" % fname) in err
    assert "run `chmod u+w ~/.boost/state`, then re-run" in err
    assert "unexpected error" not in r.out + r.err
    assert not list(paths.logs_dir().glob("crash-*.log"))


@pytest.mark.parametrize("argv, fname", [
    (("context", "map", "main", "brainstorming"), "context.json"),
    (("policy", "set", "max_skills", "5"), "policy.json"),
    (("trust", "add", "k", KEY), "trusted_keys.json"),
])
def test_each_writer_names_the_file(boost, installed, argv, fname):
    r = _refused(boost, *argv)
    _assert_named(r, fname)
    assert not (paths.state_dir() / fname).exists()


def test_focus_sidelines_nothing_it_cannot_record(boost, tapped):
    boost("install", "brainstorming")
    boost("install", "jira-integration", "--no-deps")
    r = _refused(boost, "focus", "brainstorming")
    _assert_named(r, "focus.json")
    for name, entry in lockfile.installed().items():
        assert entry.get("sidelined_by") is None, name
    assert (paths.home() / ".claude" / "skills" / "jira-integration").is_symlink()
    # Writable again, it works — and records the session it sidelined for.
    r = boost("focus", "brainstorming")
    assert "(other 1 skill sidelined)" in r.out
    state = json.loads((paths.state_dir() / "focus.json").read_text(
        encoding="utf-8"))
    assert state["active"] == ["brainstorming"]


def test_save_writes_text_and_quarantines_a_corrupt_file(sandbox, capsys):
    p = paths.state_dir() / "x.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad", encoding="utf-8")
    jsonstate.save(p, '{"a": 1}\n', corrupt=True, noun="thing",
                   show=lambda q: q.name)
    assert p.read_text(encoding="utf-8") == '{"a": 1}\n'
    assert (p.parent / "x.json.corrupt").read_text(encoding="utf-8") == "{bad"
    err = " ".join(capsys.readouterr().err.split())
    assert ("x.json was corrupt and has been moved to x.json.corrupt before "
            "writing the new thing") in err
    jsonstate.save(p, "2\n", corrupt=False)
    assert p.read_text(encoding="utf-8") == "2\n"
    assert not (p.parent / "x.json.corrupt.2").exists()


def test_save_creates_a_missing_parent(sandbox):
    p = paths.state_dir() / "nested" / "y.json"
    jsonstate.save(p, "{}\n", corrupt=False)
    assert p.read_text(encoding="utf-8") == "{}\n"


def test_a_refused_quarantine_is_the_same_error(sandbox):
    from boost_cli.errors import BoostError
    p = paths.state_dir() / "z.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad", encoding="utf-8")
    p.parent.chmod(0o500)
    try:
        with pytest.raises(BoostError) as e:
            jsonstate.save(p, "{}\n", corrupt=True)
    finally:
        p.parent.chmod(0o700)
    assert e.value.message == ("could not save ~/.boost/state/z.json "
                               "(Permission denied): ~/.boost/state is not "
                               "writable")
    assert e.value.hint == "run `chmod u+w ~/.boost/state`, then re-run"
    assert p.read_text(encoding="utf-8") == "{bad"


def test_a_failure_that_is_not_a_permission_has_no_hint(sandbox, monkeypatch):
    from boost_cli.core import util
    from boost_cli.errors import BoostError

    def full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(util, "atomic_write_text", full)
    with pytest.raises(BoostError) as e:
        jsonstate.save(paths.state_dir() / "w.json", "{}\n", corrupt=False)
    assert e.value.message == ("could not save ~/.boost/state/w.json "
                               "(No space left on device)")
    assert e.value.hint is None
