# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`sync` and `heal` keep the lock row of a skill they decline to restore.

A skill blocklisted after it was installed, then deleted from the store:
`heal --dry-run` promised "would reinstall", and the run swallowed the
policy refusal, dropped the row and reported "store dir missing, source
gone" with exit 0 -- over a source still in the tap. The version, commit,
agent scope and tags went with it. Now the preview asks the policy too, both
name it, the row stays, and the line is an unrepaired one (heal exits 1).
Only a source that is really gone still drops the row.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.core import catalog, lockfile, paths, policy, registry, store
from boost_cli.errors import BoostError

BLOCKED = ("brainstorming not restored: policy blocks installing "
           "brainstorming: skill 'brainstorming' is on the blocklist — "
           "inspect with `boost policy list` (its lock row is kept)")


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


@pytest.fixture()
def missing(tap):
    """brainstorming installed, then its store dir deleted by hand."""
    store.install(catalog.resolve_one("brainstorming"))
    shutil.rmtree(paths.store_dir() / "brainstorming")
    return lockfile.get_skill("brainstorming")


def _local(tmp_path, name="local-skill"):
    src = tmp_path / name
    src.mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: %s\ndescription: d\nversion: 1.0.0\n---\n\nBody\n" % name,
        encoding="utf-8")
    return src


class TestPolicyBlockedRestore:
    def test_preview_and_run_name_the_policy_and_keep_the_row(self, missing):
        policy.save({"blocked_skills": ["brainstorming"]})
        plan = store.sync_plan()

        assert store.sync_preview(plan) == [BLOCKED]
        applied = store.sync_apply(plan)

        assert BLOCKED in applied
        assert not any(a.startswith("dropped") for a in applied)
        assert lockfile.get_skill("brainstorming") == missing
        assert not (paths.store_dir() / "brainstorming").exists()
        assert store.is_unrepaired(BLOCKED)

    def test_a_blocked_tap_is_declined_the_same_way(self, missing, tap):
        policy.save({"blocked_taps": [tap.name]})
        line = ("brainstorming not restored: policy blocks installing "
                "brainstorming: tap %r is blocked — inspect with `boost "
                "policy list` (its lock row is kept)" % tap.name)
        plan = store.sync_plan()
        assert store.sync_preview(plan) == [line]
        assert line in store.sync_apply(plan)
        assert lockfile.get_skill("brainstorming") is not None

    def test_a_moved_source_warns_before_the_decline(self, missing, tap):
        mirror = tap.path / "mirrors" / "brainstorming"
        mirror.mkdir(parents=True)
        (mirror / "SKILL.md").write_text(
            "---\nname: brainstorming\ndescription: mirror copy\n"
            "version: 9.9.9\n---\nmirror body\n", encoding="utf-8")
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        catalog.rebuild_tap(tap)
        policy.save({"blocked_skills": ["brainstorming"]})
        plan = store.sync_plan()
        preview = store.sync_preview(plan)
        assert len(preview) == 2
        assert "no longer at its installed source" in preview[0]
        assert preview[1] == BLOCKED
        applied = store.sync_apply(plan)
        assert preview[0] in applied
        assert BLOCKED in applied
        assert lockfile.get_skill("brainstorming") == missing

    def test_at_exactly_max_skills_the_restore_still_happens(self, missing):
        # The row is still in the lock, so it is weighed against the others.
        policy.save({"max_skills": len(lockfile.installed())})
        plan = store.sync_plan()
        assert store.sync_preview(plan) == [
            "would reinstall brainstorming from fixture-tap"]
        assert ("reinstalled missing brainstorming from fixture-tap"
                in store.sync_apply(plan))
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_a_blocked_local_skill_keeps_its_row(self, sandbox, tmp_path):
        src = _local(tmp_path)
        store.install_from_path(src)
        shutil.rmtree(paths.store_dir() / "local-skill")
        policy.save({"blocked_skills": ["local-skill"]})
        line = ("local-skill not restored: policy blocks installing "
                "local-skill: skill 'local-skill' is on the blocklist — "
                "inspect with `boost policy list` (its lock row is kept)")
        plan = store.sync_plan()
        assert store.sync_preview(plan) == [line]
        assert line in store.sync_apply(plan)
        assert lockfile.get_skill("local-skill") is not None

    def test_a_local_skill_is_weighed_by_its_own_frontmatter(
            self, sandbox, tmp_path):
        src = _local(tmp_path)
        store.install_from_path(src)
        shutil.rmtree(paths.store_dir() / "local-skill")
        (src / "SKILL.md").write_text(
            "---\nname: local-skill\nversion: 1.0.0\n---\n\nBody\n",
            encoding="utf-8")
        policy.save({"require_description": True})
        plan = store.sync_plan()
        assert store.sync_preview(plan) == [
            "local-skill not restored: policy blocks installing local-skill: "
            "skill has no description (required by policy) — inspect with "
            "`boost policy list` (its lock row is kept)"]


class TestRefusedInstallKeepsTheRow:
    def test_a_refusal_over_a_present_source_is_reported_not_dropped(
            self, missing, monkeypatch):
        def refuse(*_a, **_k):
            raise BoostError("store refused", hint="fix the store")
        monkeypatch.setattr(store, "install", refuse)
        applied = store.sync_apply(store.sync_plan())
        line = ("brainstorming not restored: store refused — fix the store "
                "(its lock row is kept)")
        assert line in applied
        assert store.is_unrepaired(line)
        assert not any(a.startswith("dropped") for a in applied)
        assert lockfile.get_skill("brainstorming") == missing

    def test_a_refusal_without_a_hint_has_no_dangling_dash(
            self, missing, monkeypatch):
        def refuse(*_a, **_k):
            raise BoostError("store refused")
        monkeypatch.setattr(store, "install", refuse)
        assert ("brainstorming not restored: store refused (its lock row is "
                "kept)") in store.sync_apply(store.sync_plan())

    def test_a_local_refusal_over_a_present_source_keeps_the_row(
            self, sandbox, tmp_path, monkeypatch):
        src = _local(tmp_path)
        store.install_from_path(src)
        shutil.rmtree(paths.store_dir() / "local-skill")

        def refuse(*_a, **_k):
            raise BoostError("denied capability")
        monkeypatch.setattr(store, "install_from_path", refuse)
        assert ("local-skill not restored: denied capability (its lock row "
                "is kept)") in store.sync_apply(store.sync_plan())
        assert lockfile.get_skill("local-skill") is not None

    def test_a_source_gone_mid_run_still_drops(self, missing, tap):
        # Planned as a reinstall; the clone loses the source before the
        # install reads it, so the drop is still the honest outcome.
        plan = store.sync_plan()
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        assert ("dropped brainstorming from lock (store dir missing, source "
                "gone)") in store.sync_apply(plan)
        assert lockfile.get_skill("brainstorming") is None


class TestRepairSourcePresent:
    def test_each_shape(self, tap, tmp_path):
        cat_entry = catalog.resolve_one("brainstorming")
        assert store._repair_source_present(
            store.StoreRepair("tap", "p", "a", cat_entry=cat_entry))
        assert not store._repair_source_present(
            store.StoreRepair("tap", "p", "a", cat_entry={
                **cat_entry, "skill_md": "nowhere/SKILL.md"}))
        assert not store._repair_source_present(
            store.StoreRepair("tap", "p", "a",
                              cat_entry={**cat_entry, "tap": "no-such-tap"}))
        assert not store._repair_source_present(
            store.StoreRepair("drop", "p", "a"))
        src = _local(tmp_path)
        assert store._repair_source_present(
            store.StoreRepair("local", "p", "a", src=src))
        assert not store._repair_source_present(
            store.StoreRepair("local", "p", "a", src=tmp_path / "gone"))


class TestHealExitsOverAKeptRow:
    def test_dry_run_and_run_warn_and_exit_1(self, boost, missing):
        policy.save({"blocked_skills": ["brainstorming"]})
        r = boost("heal", "--dry-run", expect=1)
        said = " ".join((r.out + r.err).split())
        assert "would reinstall brainstorming" not in said
        assert "brainstorming not restored: policy blocks" in said
        r = boost("heal", expect=1)
        said = " ".join((r.out + r.err).split())
        assert "brainstorming not restored: policy blocks" in said
        assert "source gone" not in said
        assert lockfile.get_skill("brainstorming") is not None


class TestSyncExitsOverAKeptRow:
    """`sync` printed the same decline under a "!" as heal, and exited 0."""

    def test_run_warns_and_exits_1(self, boost, missing):
        policy.save({"blocked_skills": ["brainstorming"]})
        r = boost("sync", expect=1)
        assert BLOCKED in " ".join((r.out + r.err).split())
        assert lockfile.get_skill("brainstorming") is not None

    def test_json_names_the_unrepaired_line_and_exits_1(self, boost, missing):
        import json
        policy.save({"blocked_skills": ["brainstorming"]})
        r = boost("sync", "--json", expect=1)
        data = json.loads(r.out)
        assert data["unrepaired"] == [BLOCKED]
        assert BLOCKED in data["actions"]

    def test_a_restore_it_makes_exits_0(self, boost, missing):
        r = boost("sync", "--json", expect=0)
        assert json_unrepaired(r.out) == []
        assert (paths.store_dir() / "brainstorming").is_dir()


def json_unrepaired(text: str) -> list:
    import json
    return json.loads(text)["unrepaired"]
