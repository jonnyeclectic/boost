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
