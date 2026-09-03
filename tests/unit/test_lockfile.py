# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/lockfile.py — v3 lock file + history snapshots."""
from __future__ import annotations

import json
import re

import pytest

from boost_cli.core import lockfile, paths
from boost_cli.errors import BoostError

ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"


def _make_snaps(n):
    paths.ensure_dirs()
    d = paths.lock_history_dir()
    names = ["lock-%04dfake.json" % i for i in range(n)]
    for nm in names:
        (d / nm).write_text("{}", encoding="utf-8")
    return names


class TestRead:
    def test_missing_file_returns_skeleton(self, sandbox):
        lock = lockfile.read()
        assert lock["version"] == 3
        assert lock["skills"] == {}
        assert re.fullmatch(ISO, lock["updated"])

    def test_corrupt_file_returns_skeleton(self, sandbox):
        paths.ensure_dirs()
        paths.lockfile_path().write_text("{definitely not json", encoding="utf-8")
        lock = lockfile.read()
        assert lock["version"] == 3
        assert lock["skills"] == {}

    def test_corrupt_file_preserved_as_sidecar(self, sandbox):
        paths.ensure_dirs()
        p = paths.lockfile_path()
        p.write_text("{definitely not json", encoding="utf-8")
        lockfile.read()
        backup = p.with_name(p.name + ".corrupt")
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "{definitely not json"

    def test_missing_file_leaves_no_sidecar(self, sandbox):
        lockfile.read()
        p = paths.lockfile_path()
        assert not p.with_name(p.name + ".corrupt").exists()

    def test_corrupt_read_does_not_lose_prior_records(self, sandbox):
        # A corrupt lock followed by a new install must not silently erase the
        # only surviving copy of the earlier records — they live on in .corrupt.
        paths.ensure_dirs()
        p = paths.lockfile_path()
        p.write_text('{"skills": {"old": {"version": "1.0"}}, TRAILING GARBAGE', encoding="utf-8")
        lockfile.set_skill("new", {"version": "2.0"})
        assert set(lockfile.installed()) == {"new"}      # skeleton took over
        backup = p.with_name(p.name + ".corrupt")
        assert '"old"' in backup.read_text(encoding="utf-8")             # but old bytes survive

    def test_missing_keys_defaulted(self, sandbox):
        paths.ensure_dirs()
        paths.lockfile_path().write_text('{"skills": {"a": {}}}', encoding="utf-8")
        lock = lockfile.read()
        assert lock["version"] == 3
        assert lock["skills"] == {"a": {}}
        paths.lockfile_path().write_text('{"version": 2}', encoding="utf-8")
        lock = lockfile.read()
        assert lock["version"] == 2      # preserved, only defaulted when absent
        assert lock["skills"] == {}


class TestCheck:
    """lockfile.check() — the lock file's own health, not its content.

    Unlike read(), which collapses missing/corrupt/wrong-schema into an empty
    skeleton for callers that only want the data, check() must report each
    state distinctly so `boost verify`/`drift`/`doctor` can tell "nothing
    installed yet" apart from "the record broke".
    """

    def test_missing_file(self, sandbox):
        integ = lockfile.check()
        assert integ == (False, "missing", None)
        assert not integ.ok

    def test_valid_file(self, sandbox):
        lockfile.set_skill("a", {"version": "1.0"})
        integ = lockfile.check()
        assert integ.ok
        assert integ.problem is None
        assert integ.version == 3

    def test_corrupt_file(self, sandbox):
        paths.ensure_dirs()
        paths.lockfile_path().write_text("{definitely not json", encoding="utf-8")
        integ = lockfile.check()
        assert not integ.ok
        assert integ.problem == "corrupt"

    def test_wrong_schema_version(self, sandbox):
        paths.ensure_dirs()
        paths.lockfile_path().write_text(
            json.dumps({"version": 2, "skills": {}}), encoding="utf-8")
        integ = lockfile.check()
        assert not integ.ok
        assert integ.problem == "schema"
        assert integ.version == 2

    def test_check_does_not_mutate_or_preserve_corrupt(self, sandbox):
        # check() only reports; it must not trigger the .corrupt sidecar that
        # read() writes as a side effect (that stays read()'s job on the
        # first real access).
        paths.ensure_dirs()
        p = paths.lockfile_path()
        p.write_text("{definitely not json", encoding="utf-8")
        lockfile.check()
        assert not p.with_name(p.name + ".corrupt").exists()


class TestWrite:
    def test_write_stamps_version_and_updated(self, sandbox):
        lockfile.write({"version": 99, "skills": {"a": {"version": "1.0"}}})
        data = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert data["version"] == 3
        assert re.fullmatch(ISO, data["updated"])
        assert data["skills"] == {"a": {"version": "1.0"}}

    def test_first_write_no_snapshot_second_write_one(self, sandbox):
        lockfile.write({"skills": {"a": {}}})
        assert list(paths.lock_history_dir().glob("lock-*.json")) == []
        first_text = paths.lockfile_path().read_text(encoding="utf-8")
        lockfile.write({"skills": {"a": {}, "b": {}}})
        snaps = list(paths.lock_history_dir().glob("lock-*.json"))
        assert len(snaps) == 1
        assert snaps[0].read_text(encoding="utf-8") == first_text  # snapshot is the PREVIOUS lock
        assert re.fullmatch(r"lock-\d{8}T\d{6}Z\.json", snaps[0].name)

    def test_rapid_writes_each_get_a_snapshot(self, sandbox):
        lockfile.write({"skills": {"a": {}}})
        lockfile.write({"skills": {"b": {}}})
        lockfile.write({"skills": {"c": {}}})
        assert len(list(paths.lock_history_dir().glob("lock-*.json"))) == 2


class TestPrune:
    def test_prune_55_keeps_50_newest(self, sandbox):
        names = _make_snaps(55)
        lockfile._prune_history()
        left = sorted(p.name for p in paths.lock_history_dir().glob("lock-*.json"))
        assert len(left) == 50
        assert left == names[5:]

    def test_prune_at_exactly_50_is_noop(self, sandbox):
        names = _make_snaps(50)
        lockfile._prune_history()
        left = sorted(p.name for p in paths.lock_history_dir().glob("lock-*.json"))
        assert left == names

    def test_write_prunes_history(self, sandbox):
        lockfile.write({"skills": {}})            # create the lock file
        names = _make_snaps(55)
        lockfile.write({"skills": {"x": {}}})     # snapshot (56 files) then prune
        left = sorted(p.name for p in paths.lock_history_dir().glob("lock-*.json"))
        assert len(left) == 50
        assert names[0] not in left
        assert names[5] not in left
        assert names[6] in left
        assert left[-1].startswith("lock-2")      # the fresh real snapshot survives


class TestSkillAccessors:
    def test_set_get_roundtrip(self, sandbox):
        lockfile.set_skill("a", {"version": "1.0", "tags": []})
        assert lockfile.get_skill("a") == {"version": "1.0", "tags": []}
        assert lockfile.installed() == {"a": {"version": "1.0", "tags": []}}

    def test_get_missing_none(self, sandbox):
        assert lockfile.get_skill("ghost") is None

    def test_remove_present_true(self, sandbox):
        lockfile.set_skill("a", {"version": "1.0"})
        assert lockfile.remove_skill("a") is True
        assert lockfile.get_skill("a") is None
        assert lockfile.installed() == {}

    def test_remove_absent_false(self, sandbox):
        assert lockfile.remove_skill("ghost") is False

    def test_installed_empty_by_default(self, sandbox):
        assert lockfile.installed() == {}


class TestHistory:
    def _seed_history(self):
        paths.ensure_dirs()
        d = paths.lock_history_dir()
        (d / "lock-20250101T000000Z.json").write_text(
            json.dumps({"updated": "u1", "skills": {"a": {}, "b": {}}}), encoding="utf-8")
        (d / "lock-20250102T000000Z.json").write_text(
            json.dumps({"skills": {"only": {}}}), encoding="utf-8")
        (d / "lock-19990101T000000Z.json").write_text("corrupt not json", encoding="utf-8")

    def test_history_list_shape_and_order(self, sandbox):
        self._seed_history()
        d = paths.lock_history_dir()
        assert lockfile.history_list() == [
            {"id": "20250101T000000Z",
             "path": str(d / "lock-20250101T000000Z.json"),
             "updated": "u1", "count": 2},
            {"id": "20250102T000000Z",
             "path": str(d / "lock-20250102T000000Z.json"),
             "updated": "?", "count": 1},
        ]

    def test_history_list_empty(self, sandbox):
        paths.ensure_dirs()
        assert lockfile.history_list() == []

    def test_history_read_hit(self, sandbox):
        self._seed_history()
        data = lockfile.history_read("20250101T000000Z")
        assert data == {"updated": "u1", "skills": {"a": {}, "b": {}}}

    def test_history_read_miss_raises(self, sandbox):
        paths.ensure_dirs()
        with pytest.raises(BoostError) as ei:
            lockfile.history_read("20990101T000000Z")
        assert ei.value.message == "no lock history entry 20990101T000000Z"
        assert ei.value.hint == "list entries with `boost replay`"

    def test_history_read_corrupt_entry_raises_boosterror_not_raw_jsonerror(self, sandbox):
        # The entry exists (unlike the miss case above) but fails to parse —
        # this used to escape as a raw JSONDecodeError, exit 70.
        self._seed_history()
        with pytest.raises(BoostError) as ei:
            lockfile.history_read("19990101T000000Z")
        assert "19990101T000000Z" in ei.value.message
        assert "unreadable" in ei.value.message

    def test_history_list_with_skipped_counts_unparseable_entries(self, sandbox):
        self._seed_history()  # one corrupt entry alongside two valid ones
        history, skipped = lockfile.history_list(with_skipped=True)
        assert len(history) == 2
        assert skipped == 1

    def test_history_list_default_return_is_unchanged_by_with_skipped(self, sandbox):
        self._seed_history()
        assert lockfile.history_list() == lockfile.history_list(with_skipped=False)

    def test_history_list_skips_corrupt_without_stopping(self, sandbox):
        # a corrupt snapshot that sorts BEFORE a valid one must be skipped, not
        # halt the scan — pins the `continue` (a `break` would drop the later
        # valid entry). The seed in _seed_history can't catch this because its
        # corrupt file is newest, hence last.
        paths.ensure_dirs()
        d = paths.lock_history_dir()
        (d / "lock-20200101T000000Z.json").write_text("not json", encoding="utf-8")
        (d / "lock-20200102T000000Z.json").write_text(
            json.dumps({"updated": "v", "skills": {"x": {}}}), encoding="utf-8")
        assert [e["id"] for e in lockfile.history_list()] == ["20200102T000000Z"]


class TestRulesAndWorkflows:
    def test_rule_roundtrip_and_remove(self, sandbox):
        lockfile.set_rule("r", {"v": "1"})
        assert lockfile.get_rule("r") == {"v": "1"}
        assert lockfile.installed_rules() == {"r": {"v": "1"}}
        assert lockfile.remove_rule("r") is True       # present -> True
        assert lockfile.get_rule("r") is None
        assert lockfile.remove_rule("r") is False       # absent -> False

    def test_workflow_roundtrip_and_remove(self, sandbox):
        lockfile.set_workflow("w", {"v": "2"})
        assert lockfile.get_workflow("w") == {"v": "2"}
        assert lockfile.installed_workflows() == {"w": {"v": "2"}}
        assert lockfile.remove_workflow("w") is True    # present -> True
        assert lockfile.get_workflow("w") is None
        assert lockfile.remove_workflow("w") is False    # absent -> False


class TestKindAgnosticAccessors:
    """find_any / set_entry / all_installed — the accessors the command sweep
    migrates to, so a name resolves no matter which section it lives in."""

    def _seed(self):
        lockfile.set_skill("alpha", {"version": "1.0.0"})
        lockfile.set_rule("bravo", {"kind": "rule", "version": "2.0.0"})
        lockfile.set_workflow("charlie", {"kind": "workflow", "version": "3.0.0"})

    def test_find_any_resolves_each_kind(self, sandbox):
        self._seed()
        assert lockfile.find_any("alpha") == ("skill", {"version": "1.0.0"})
        kind, entry = lockfile.find_any("bravo")
        assert kind == "rule" and entry["version"] == "2.0.0"
        kind, entry = lockfile.find_any("charlie")
        assert kind == "workflow" and entry["version"] == "3.0.0"

    def test_find_any_misses_with_none(self, sandbox):
        self._seed()
        assert lockfile.find_any("delta") is None

    def test_find_any_prefers_a_skill_over_a_homonymous_rule(self, sandbox):
        # Same precedence store.uninstall established: skills shadow rules,
        # rules shadow workflows, so behavior cannot depend on dict order.
        lockfile.set_rule("twin", {"kind": "rule"})
        lockfile.set_skill("twin", {"version": "9"})
        kind, entry = lockfile.find_any("twin")
        assert kind == "skill" and entry == {"version": "9"}

    def test_set_entry_dispatches_by_kind(self, sandbox):
        lockfile.set_entry("rule", "echo", {"kind": "rule", "pinned": True})
        assert lockfile.get_rule("echo")["pinned"] is True
        lockfile.set_entry("workflow", "foxtrot", {"kind": "workflow"})
        assert lockfile.get_workflow("foxtrot") is not None
        lockfile.set_entry("skill", "golf", {"version": "1"})
        assert lockfile.get_skill("golf") == {"version": "1"}

    def test_set_entry_rejects_an_unknown_kind(self, sandbox):
        with pytest.raises(ValueError, match="unknown lock kind"):
            lockfile.set_entry("plugin", "hotel", {})

    def test_all_installed_returns_every_section(self, sandbox):
        self._seed()
        allofit = lockfile.all_installed()
        assert set(allofit) == {"skill", "rule", "workflow"}
        assert list(allofit["skill"]) == ["alpha"]
        assert list(allofit["rule"]) == ["bravo"]
        assert list(allofit["workflow"]) == ["charlie"]

    def test_history_count_includes_rules_and_workflows(self, sandbox):
        # One skill, one rule, one workflow, then one more write to snapshot
        # that state: the snapshot's count must say 3, not 1 — `boost replay`
        # reads it, and under-reporting made rule history invisible.
        self._seed()
        lockfile.set_skill("delta", {"version": "1"})
        hist = lockfile.history_list()
        assert hist, "the fourth write must have snapshotted the third state"
        assert hist[-1]["count"] == 3
