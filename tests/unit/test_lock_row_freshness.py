# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A command writes only the lock fields it owns, onto the row as it is now.

`boost edit`, `tag`, `pin` and `install` each read a lock row, did their
work, and wrote the whole row back. `lockfile.mutate` serialised the write
but not the read, so whatever landed in between was reverted: a pin made
while `boost edit` sat in the editor was gone when it exited, an uninstall in
that window came back as a ghost row, and a tag made during a reinstall's
copy was dropped. Each now applies its own change inside
`lockfile.update_entry`, to the row read under the lock.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from boost_cli.core import lockfile, paths, store

# Every child runs here: under the mutation gate the child's import is
# mutmut's trampoline, which reads `setup.cfg` from the current directory
# (see test_first_run_pointer.py).
ROOT = Path(lockfile.__file__).resolve().parents[2]

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX shebang script isn't directly executable on Windows")


def _row(name="brainstorming"):
    return lockfile.read()["skills"].get(name)


def _edit_events():
    p = paths.pulse_path()
    if not p.exists():
        return []
    return [e for e in map(json.loads, p.read_text(encoding="utf-8").splitlines())
            if e.get("action") == "edit"]


def _editor(tmp_path, monkeypatch, *commands, edit=True, rm_store=False):
    """An $EDITOR that runs boost ``commands`` in a child while it is open."""
    lines = ['#!/bin/sh', 'target="$1"', 'cd "%s" || exit 9' % ROOT]
    lines.extend(
        'PYTHONPATH="%s" "%s" -c "import sys; from boost_cli.cli import '
        'main; sys.exit(main(sys.argv[1:]))" %s || exit 7'
        % (ROOT, sys.executable, " ".join(argv)) for argv in commands)
    if edit:
        lines.append('echo "- extra line" >> "$target"')
    if rm_store:
        lines.append('/bin/rm -rf "$(dirname "$target")"')
    script = tmp_path / "editor.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("EDITOR", str(script))
    monkeypatch.delenv("VISUAL", raising=False)


# ── lockfile.update_entry ───────────────────────────────────────────────

class TestUpdateEntry:
    def test_applies_to_the_row_as_the_lock_holds_it(self, sandbox):
        lockfile.set_skill("a", {"version": "1.0.0", "tags": []})
        stale = lockfile.get_skill("a")
        lockfile.set_skill("a", {"version": "1.0.0", "tags": ["other"]})
        assert stale == {"version": "1.0.0", "tags": []}
        wrote = lockfile.update_skill("a", lambda row: row.update(pinned=True))
        assert wrote is True
        assert lockfile.get_skill("a") == {"version": "1.0.0", "tags": ["other"],
                                           "pinned": True}

    def test_a_vanished_row_is_not_recreated_and_fn_not_called(self, sandbox):
        lockfile.set_skill("b", {"version": "1.0.0"})
        calls = []
        assert lockfile.update_skill("a", calls.append) is False
        assert calls == []
        assert set(lockfile.installed()) == {"b"}

    def test_fn_returning_false_writes_nothing(self, sandbox):
        lockfile.set_skill("a", {"version": "1.0.0"})
        before = paths.lockfile_path().read_bytes()

        def change_then_decline(row):
            row["pinned"] = True
            return False
        assert lockfile.update_skill("a", change_then_decline) is False
        assert paths.lockfile_path().read_bytes() == before

    def test_routes_by_kind(self, sandbox):
        lockfile.set_skill("x", {"v": "s"})
        lockfile.set_rule("x", {"v": "r"})
        lockfile.set_workflow("x", {"v": "w"})
        assert lockfile.update_entry("rule", "x", lambda r: r.update(t=1)) is True
        assert lockfile.update_entry("workflow", "x", lambda r: r.update(t=2)) is True
        assert lockfile.get_skill("x") == {"v": "s"}
        assert lockfile.get_rule("x") == {"v": "r", "t": 1}
        assert lockfile.get_workflow("x") == {"v": "w", "t": 2}

    def test_unknown_kind_raises(self, sandbox):
        with pytest.raises(ValueError, match="unknown lock kind 'tap'"):
            lockfile.update_entry("tap", "x", lambda r: None)
        with pytest.raises(ValueError, match="unknown lock kind 'tap'"):
            lockfile.set_entry("tap", "x", {})


# ── boost edit ──────────────────────────────────────────────────────────

@posix_only
class TestEditWritesOnlyUpdatedAt:
    def test_a_pin_and_tag_made_while_open_survive(self, boost, installed,
                                                   tmp_path, monkeypatch):
        _editor(tmp_path, monkeypatch, ("pin", "brainstorming"),
                ("tag", "brainstorming", "+work"))
        before = _row()
        r = boost("edit", "brainstorming")
        assert ("local edits diverge from the tap source — "
                "boost drift will flag this") in r.out
        after = _row()
        assert after["pinned"] is True
        assert after["tags"] == ["work"]
        assert after["sha256"] == before["sha256"]
        assert after["updated_at"] >= before["updated_at"]
        assert {k: v for k, v in after.items()
                if k not in ("pinned", "tags", "updated_at")} == \
            {k: v for k, v in before.items()
             if k not in ("pinned", "tags", "updated_at")}
        assert [e["subject"] for e in _edit_events()] == ["brainstorming"]

    def test_an_uninstall_made_while_open_is_not_undone(self, boost, installed,
                                                        tmp_path, monkeypatch):
        _editor(tmp_path, monkeypatch, ("uninstall", "brainstorming"),
                edit=False)
        r = boost("edit", "brainstorming", expect=1)
        assert ("brainstorming was uninstalled while the editor was open — "
                "nothing recorded") in r.out
        assert "local edits diverge" not in r.out
        assert "no changes" not in r.out
        assert _row() is None
        assert not store.skill_store_dir("brainstorming").exists()
        assert _edit_events() == []
        # Nothing ghosted: the name installs again.
        boost("install", "brainstorming")

    def test_a_store_dir_gone_while_open_writes_nothing(self, boost, installed,
                                                        tmp_path, monkeypatch):
        _editor(tmp_path, monkeypatch, edit=False, rm_store=True)
        before = paths.lockfile_path().read_bytes()
        r = boost("edit", "brainstorming", expect=1)
        assert ("brainstorming was uninstalled while the editor was open — "
                "nothing recorded") in r.out
        assert paths.lockfile_path().read_bytes() == before
        assert _edit_events() == []

    def test_no_change_writes_nothing(self, boost, installed, tmp_path,
                                      monkeypatch):
        _editor(tmp_path, monkeypatch, edit=False)
        before = paths.lockfile_path().read_bytes()
        r = boost("edit", "brainstorming")
        assert "no changes" in r.out
        assert paths.lockfile_path().read_bytes() == before
        assert _edit_events() == []


# ── boost tag / pin ─────────────────────────────────────────────────────

def _interleave(monkeypatch, owner, attr, after):
    """Run ``after()`` once, right after ``owner.attr`` first returns."""
    orig = getattr(owner, attr)
    fired = []

    def wrapper(*a, **kw):
        res = orig(*a, **kw)
        if not fired:
            fired.append(True)
            after()
        return res
    monkeypatch.setattr(owner, attr, wrapper)


def _set(**fields):
    return lambda: lockfile.update_skill("brainstorming",
                                         lambda row: row.update(**fields))


class TestTagAppliesToTheFreshRow:
    def test_a_tag_landed_since_the_read_survives(self, boost, installed,
                                                  monkeypatch):
        _interleave(monkeypatch, store, "resolve_lock_entry",
                    _set(tags=["other"], pinned=True))
        r = boost("tag", "brainstorming", "+mine")
        assert "#mine" in r.out and "#other" in r.out
        assert _row()["tags"] == ["mine", "other"]
        assert _row()["pinned"] is True

    def test_a_no_op_against_the_fresh_row_writes_nothing(self, boost,
                                                          installed,
                                                          monkeypatch):
        _interleave(monkeypatch, store, "resolve_lock_entry",
                    _set(tags=["mine"]))
        before = None

        def snap():
            nonlocal before
            before = paths.lockfile_path().read_bytes()
        _interleave(monkeypatch, lockfile, "apply_tag_mods", snap)
        r = boost("tag", "brainstorming", "+mine")
        assert "✓" not in r.out
        assert paths.lockfile_path().read_bytes() == before

    def test_a_row_uninstalled_since_the_read_is_not_recreated(
            self, boost, installed, monkeypatch):
        _interleave(monkeypatch, store, "resolve_lock_entry",
                    lambda: lockfile.remove_skill("brainstorming"))
        r = boost("tag", "brainstorming", "+mine", expect=1)
        assert "brainstorming was uninstalled while tagging it" in r.err
        assert _row() is None

    def test_parallel_taggers_keep_every_tag(self, sandbox, installed):
        n = 8
        go = sandbox / "go"
        code = textwrap.dedent("""
            import os, sys, time
            from boost_cli.cli import main
            while not os.path.exists(%r):
                time.sleep(0.005)
            for i in range(%d):
                assert main(["tag", "brainstorming", "+%%s%%d" %% (sys.argv[1], i)]) == 0
        """ % (str(go), n))
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        procs = [subprocess.Popen([sys.executable, "-c", code, who], env=env,
                                  cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
                 for who in ("a", "b")]
        go.write_text("", encoding="utf-8")
        for p in procs:
            _out, err = p.communicate(timeout=180)
            assert p.returncode == 0, err
        assert _row()["tags"] == sorted("%s%d" % (w, i) for w in "ab"
                                        for i in range(n))


class TestPinAppliesToTheFreshRow:
    def test_a_tag_landed_since_the_read_survives(self, boost, installed,
                                                  monkeypatch):
        _interleave(monkeypatch, lockfile, "find_any", _set(tags=["keep"]))
        r = boost("pin", "brainstorming")
        assert "pinned brainstorming at v" in r.out
        assert _row()["pinned"] is True
        assert _row()["tags"] == ["keep"]

    def test_unpin_keeps_a_tag_landed_since_the_read(self, boost, installed,
                                                     monkeypatch):
        boost("pin", "brainstorming")
        _interleave(monkeypatch, lockfile, "find_any", _set(tags=["keep"]))
        boost("unpin", "brainstorming")
        assert _row()["pinned"] is False
        assert _row()["tags"] == ["keep"]

    def test_a_row_uninstalled_since_the_read_is_not_recreated(
            self, boost, installed, monkeypatch):
        _interleave(monkeypatch, lockfile, "find_any",
                    lambda: lockfile.remove_skill("brainstorming"))
        r = boost("pin", "brainstorming", expect=1)
        assert "brainstorming was uninstalled while pinning it" in r.err
        assert _row() is None

    def test_unpin_of_a_vanished_row_names_unpinning(self, boost, installed,
                                                     monkeypatch):
        boost("pin", "brainstorming")
        # unpin reads once itself, then _set_pin reads again: drop it after
        # the second read.
        calls = []
        orig = lockfile.find_any

        def wrapper(name):
            res = orig(name)
            calls.append(name)
            if len(calls) == 2:
                lockfile.remove_skill(name)
            return res
        monkeypatch.setattr(lockfile, "find_any", wrapper)
        r = boost("unpin", "brainstorming", expect=1)
        assert "brainstorming was uninstalled while unpinning it" in r.err
        assert _row() is None

    def test_commit_pin_writes_only_commit_pin(self, boost, installed,
                                               monkeypatch):
        from boost_cli.core import integrity
        stale = _row()
        _set(tags=["keep"])()
        commit = integrity.set_commit_pin("brainstorming", dict(stale))
        assert commit == stale["commit"]
        assert _row()["commit_pin"] == commit
        assert _row()["tags"] == ["keep"]
        stale = _row()
        _set(tags=["kept"])()
        assert integrity.clear_commit_pin("brainstorming", dict(stale)) is True
        assert "commit_pin" not in _row()
        assert _row()["tags"] == ["kept"]


    def test_commit_pin_on_a_vanished_row_refuses(self, boost, installed):
        from boost_cli.core import integrity
        from boost_cli.errors import BoostError
        stale = _row()
        lockfile.remove_skill("brainstorming")
        with pytest.raises(BoostError,
                           match="brainstorming was uninstalled while "
                                 "commit-pinning it"):
            integrity.set_commit_pin("brainstorming", dict(stale))
        assert _row() is None
        assert integrity.clear_commit_pin(
            "brainstorming", {**stale, "commit_pin": "abc"}) is False
        assert _row() is None

# ── install / sideline ──────────────────────────────────────────────────

class TestReinstallCarriesTheFreshRow:
    def test_a_tag_and_pin_landed_during_the_copy_survive(self, boost,
                                                          installed,
                                                          monkeypatch):
        installed_at = _row()["installed_at"]
        _interleave(monkeypatch, store, "check_existing",
                    _set(tags=["keep"], pinned=True, commit_pin="abc"))
        boost("reinstall", "brainstorming")
        row = _row()
        assert row["tags"] == ["keep"]
        assert row["pinned"] is True
        assert row["commit_pin"] == "abc"
        assert row["installed_at"] == installed_at

    def test_a_commit_pin_released_during_the_copy_stays_released(
            self, boost, installed, monkeypatch):
        # At the installed commit, so the reinstall is not refused for it.
        _set(commit_pin=_row()["commit"])()
        _interleave(monkeypatch, store, "check_existing",
                    lambda: lockfile.update_skill(
                        "brainstorming", lambda row: row.pop("commit_pin")))
        boost("reinstall", "brainstorming")
        assert "commit_pin" not in _row()

    def test_a_fresh_install_starts_clean(self, boost, tapped):
        boost("install", "brainstorming")
        row = _row()
        assert row["tags"] == []
        assert row["pinned"] is False
        assert "commit_pin" not in row
        assert row["installed_at"] == row["updated_at"]

    def test_reimport_carries_a_tag_landed_during_the_copy(self, sandbox,
                                                           tmp_path,
                                                           monkeypatch):
        src = tmp_path / "keep-local"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: keep-local\ndescription: keep\n---\n# keep\n",
            encoding="utf-8")
        store.install_from_path(src)
        installed_at = lockfile.get_skill("keep-local")["installed_at"]
        _interleave(monkeypatch, store, "_copy_skill",
                    lambda: lockfile.update_skill(
                        "keep-local", lambda row: row.update(tags=["keep"])))
        store.install_from_path(src)
        row = lockfile.get_skill("keep-local")
        assert row["tags"] == ["keep"]
        assert row["installed_at"] == installed_at


class TestSidelineAppliesToTheFreshRow:
    def test_sideline_keeps_a_tag_landed_since(self, boost, installed,
                                               monkeypatch):
        _interleave(monkeypatch, store, "unlink_agents", _set(tags=["keep"]))
        store.sideline("brainstorming", "focus")
        row = _row()
        assert row["sidelined_by"] == "focus"
        assert row["agents"] == []
        assert row["tags"] == ["keep"]

    def test_unsideline_keeps_a_tag_landed_since(self, boost, installed,
                                                 monkeypatch):
        store.sideline("brainstorming", "focus")
        _interleave(monkeypatch, store, "link_agents", _set(tags=["keep"]))
        res = store.unsideline("brainstorming")
        row = _row()
        assert "sidelined_by" not in row
        assert row["agents"] == res.linked != []
        assert row["tags"] == ["keep"]

    def test_neither_recreates_an_uninstalled_row(self, boost, installed):
        boost("uninstall", "brainstorming")
        assert store.sideline("brainstorming", "focus") == []
        store.unsideline("brainstorming")
        assert _row() is None


class TestBackfillSourceDates:
    def test_a_row_removed_meanwhile_is_not_recreated(self, boost, installed,
                                                      monkeypatch):
        tap = _row()["tap"]
        lockfile.update_skill("brainstorming",
                              lambda row: row.pop("source_updated_at", None))
        monkeypatch.setattr(store, "source_updated_at", lambda *a: (
            lockfile.remove_skill("brainstorming"), "2026-01-01")[1])
        assert store.backfill_source_dates([tap]) == []
        assert _row() is None

    def test_dates_a_present_row_and_keeps_its_tags(self, boost, installed,
                                                    monkeypatch):
        tap = _row()["tap"]
        lockfile.update_skill("brainstorming",
                              lambda row: row.pop("source_updated_at", None))

        def dated(*a):
            _set(tags=["keep"])()
            return "2026-01-01T00:00:00Z"
        monkeypatch.setattr(store, "source_updated_at", dated)
        assert store.backfill_source_dates([tap]) == ["brainstorming"]
        assert _row()["source_updated_at"] == "2026-01-01T00:00:00Z"
        assert _row()["tags"] == ["keep"]
