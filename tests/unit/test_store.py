"""Unit tests: boost_cli/core/store.py — install/uninstall/link/sync (no CLI)."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import ClassVar

import pytest

from boost_cli.core import (
    catalog,
    config,
    gitutil,
    journal,
    lockfile,
    paths,
    policy,
    registry,
    store,
    util,
)
from boost_cli.errors import BoostError

ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
# Keep insertion order in step with config.DEFAULTS["agents"] — several tests
# assert the linked list exactly, and that list follows enabled_agents() order.
AGENT_DIRS = {"claude-code": ".claude", "windsurf": ".windsurf",
              "cursor": ".cursor", "gemini": ".gemini"}
# The agents a *user-scope skill* is symlinked into. gemini is deliberately
# absent: it reads ~/.agents/skills (the canonical store) natively, so
# links_skills is False and link_agents never touches ~/.gemini/skills. It is
# still a full agent everywhere else — rules, workflows and project-scope
# copies all materialize into ~/.gemini, so those assertions DO include it.
LINKED_AGENTS = ["claude-code", "windsurf", "cursor"]


def _link(agent):
    return paths.home() / AGENT_DIRS[agent] / "skills" / "brainstorming"


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


@pytest.fixture()
def entry(tap):
    return catalog.resolve_one("brainstorming")


@pytest.fixture()
def brainstorming(entry):
    store.install(entry)
    return entry


class TestInstall:
    def test_unknown_kind_refused(self, tap, entry):
        # skill/rule/workflow all install (see TestRuleInstall/TestWorkflowInstall);
        # anything else is refused with the kinds it does know.
        weird = dict(entry, kind="gizmo", name="some-gizmo")
        with pytest.raises(BoostError) as ei:
            store.install(weird)
        assert ei.value.message == (
            "some-gizmo is a gizmo, which boost does not know how to install")
        assert ei.value.hint == "known kinds: skill, rule, workflow"
        assert lockfile.get_skill("some-gizmo") is None

    def test_happy_path(self, tap, entry):
        src = tap.path / "skills" / "brainstorming"
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("junk", encoding="utf-8")
        (src / "__pycache__").mkdir()
        (src / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
        (src / ".DS_Store").write_text("junk", encoding="utf-8")

        res = store.install(entry)

        dest = paths.store_dir() / "brainstorming"
        assert res.name == "brainstorming"
        assert res.dest == dest
        assert res.linked == LINKED_AGENTS
        assert res.native == ["gemini"]
        assert res.conflicts == []
        assert res.upgraded is False
        assert res.score == 95
        assert (dest / "SKILL.md").is_file()
        assert not (dest / ".git").exists()
        assert not (dest / "__pycache__").exists()
        assert not (dest / ".DS_Store").exists()
        for agent in LINKED_AGENTS:
            link = _link(agent)
            assert link.is_symlink()
            assert link.resolve() == dest.resolve()

        e = lockfile.get_skill("brainstorming")
        assert e["version"] == "1.4.0"
        assert e["tap"] == "fixture-tap"
        assert e["source_dir"] == "skills/brainstorming"
        assert re.fullmatch(r"[0-9a-f]{40}", e["commit"])
        assert e["commit"] == gitutil.head_commit(tap.path)   # tap HEAD, not cwd
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"])
        assert e["sha256"] == util.sha256_dir(dest)
        assert re.fullmatch(ISO, e["installed_at"])
        assert e["updated_at"] == e["installed_at"]
        assert e["pinned"] is False
        assert e["quarantined"] is False
        assert e["agents"] == LINKED_AGENTS
        assert e["tags"] == []

        ev = journal.events(action="install")[0]
        assert ev["subject"] == "brainstorming"
        assert ev["tap"] == "fixture-tap"
        assert ev["version"] == "1.4.0"

    def test_installed_passthrough(self, brainstorming):
        assert set(store.installed()) == {"brainstorming"}

    def test_duplicate_raises_with_reinstall_hint(self, brainstorming, entry):
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == "brainstorming is already installed (v1.4.0)"
        assert ei.value.hint == (
            "`boost reinstall brainstorming` to force, `boost update` to upgrade")

    def test_force_upgrades_preserving_installed_at_and_tags(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        # a fixed *past* timestamp — the second-granularity `now` of the force
        # reinstall must not collide with it, or a dropped-preservation
        # regression would masquerade as passing.
        e["installed_at"] = "2020-01-01T00:00:00Z"
        e["tags"] = ["keeper"]
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)

        res = store.install(entry, force=True)
        assert res.upgraded is True
        e2 = lockfile.get_skill("brainstorming")
        assert e2["installed_at"] == "2020-01-01T00:00:00Z"   # preserved
        assert e2["updated_at"] != "2020-01-01T00:00:00Z"     # refreshed to now
        assert re.fullmatch(ISO, e2["updated_at"])
        assert e2["tags"] == ["keeper"]
        assert e2["pinned"] is True

    def test_missing_version_defaults_to_zero(self, tap, entry):
        no_ver = {k: v for k, v in entry.items() if k != "version"}
        store.install(no_ver)
        assert lockfile.get_skill("brainstorming")["version"] == "0.0.0"

    def test_policy_block_joins_multiple_violations(self, tap, entry):
        policy.save({"blocked_skills": ["brainstorming"],
                     "blocked_taps": ["fixture-tap"]})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == (
            "policy blocks installing brainstorming: "
            "skill 'brainstorming' is on the blocklist; "
            "tap 'fixture-tap' is blocked")

    def test_pinned_reinstall_raises(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)
        with pytest.raises(BoostError):
            store.install(entry)

    def test_pinned_error_mentions_pin(self, brainstorming, entry):
        e = lockfile.get_skill("brainstorming")
        e["pinned"] = True
        lockfile.set_skill("brainstorming", e)
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == "brainstorming is pinned"
        assert ei.value.hint == "`boost unpin brainstorming` first"

    def test_policy_block_then_restore(self, tap, entry):
        policy.save({"blocked_skills": ["brainstorming"]})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == ("policy blocks installing brainstorming: "
                                    "skill 'brainstorming' is on the blocklist")
        assert ei.value.hint == "inspect with `boost policy list`"
        assert lockfile.get_skill("brainstorming") is None

        policy.save({})
        store.install(entry)
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_max_skills_uses_live_installed_count(self, tap, entry):
        # exercises the `installed_count` argument wiring into check_install:
        # with the cap at 0 even the first install is over budget.
        policy.save({"max_skills": 0})
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert "max_skills limit (0) reached" in ei.value.message
        assert lockfile.get_skill("brainstorming") is None

    def test_only_agents_links_subset(self, tap, entry):
        res = store.install(entry, only_agents=["claude-code"])
        assert res.linked == ["claude-code"]
        assert _link("claude-code").is_symlink()
        assert not _link("windsurf").exists()
        assert not _link("cursor").exists()
        assert not _link("gemini").exists()
        assert lockfile.get_skill("brainstorming")["agents"] == ["claude-code"]

    def test_preexisting_real_dir_is_conflict_not_clobbered(self, tap, entry):
        blocker = _link("claude-code")
        blocker.mkdir(parents=True)
        (blocker / "precious.txt").write_text("mine", encoding="utf-8")

        res = store.install(entry)
        assert res.conflicts == [str(blocker)]
        assert res.linked == ["windsurf", "cursor"]
        assert not blocker.is_symlink()
        assert (blocker / "precious.txt").read_text(encoding="utf-8") == "mine"
        assert lockfile.get_skill("brainstorming")["agents"] == ["windsurf", "cursor"]

    def test_source_vanished_raises(self, tap, entry):
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        with pytest.raises(BoostError) as ei:
            store.install(entry)
        assert ei.value.message == (
            "source for brainstorming vanished from tap fixture-tap")
        assert ei.value.hint == "run `boost update fixture-tap`"


class TestUnlinkAgents:
    def test_removes_only_symlinks(self, brainstorming):
        cursor_link = _link("cursor")
        cursor_link.unlink()
        cursor_link.mkdir()
        removed = store.unlink_agents("brainstorming")
        assert removed == ["claude-code", "windsurf"]
        assert cursor_link.is_dir()
        assert not _link("claude-code").exists()
        assert not _link("windsurf").exists()
        assert not _link("gemini").exists()


class TestNativeStoreAgents:
    """A skill install must reach Gemini CLI without ever linking into it.

    Gemini reads ``~/.agents/skills`` — the canonical store — directly, so the
    contract is precisely: the store dir is written, ``~/.gemini/skills`` is
    NOT, and the result still reports gemini as reached. Each half is pinned
    separately because getting either wrong fails silently: no link and no
    report reads as "boost does not support Gemini", while a link makes Gemini
    log a skill conflict on every session.
    """

    def test_install_writes_the_store_but_no_gemini_link(self, brainstorming):
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()
        assert not (paths.home() / ".gemini" / "skills").exists()

    def test_result_reports_gemini_as_native_not_linked(self, tap, entry):
        res = store.install(entry)
        assert res.linked == LINKED_AGENTS
        assert res.native == ["gemini"]
        assert "gemini" not in res.linked

    def test_the_lock_records_only_real_links(self, brainstorming):
        # `agents` drives `boost sync`; a native agent recorded there would make
        # sync create the very link this design avoids.
        assert lockfile.get_skill("brainstorming")["agents"] == LINKED_AGENTS

    def test_native_is_reported_even_when_the_scope_is_narrowed(self, tap, entry):
        # `--agent cursor` narrows which agents get a *link*, but the store is
        # written regardless, so Gemini really can see the skill. Reporting
        # otherwise would be untrue.
        res = store.install(entry, only_agents=["cursor"])
        assert res.linked == ["cursor"]
        assert res.native == ["gemini"]

    def test_native_survives_a_reinstall(self, tap, entry):
        # Regression: reinstall replays the lock's recorded links as the scope,
        # and those never contain a native agent — filtering `native` by that
        # scope silently emptied it on every reinstall.
        store.install(entry)
        res = store.install(entry, force=True)
        assert res.native == ["gemini"]

    def test_sync_never_wants_a_gemini_link(self, brainstorming):
        plan = store.sync_plan()
        assert not any(a == "gemini" for _n, a in plan["missing_links"])

    def test_unlink_reports_only_agents_it_actually_unlinked(self, brainstorming):
        assert "gemini" not in store.unlink_agents("brainstorming")

    def test_uninstall_removes_the_store_dir_gemini_reads(self, brainstorming):
        store.uninstall("brainstorming")
        assert not (paths.store_dir() / "brainstorming").exists()

    def test_flipping_links_skills_on_restores_the_link(self, tap, entry):
        cfg = config.load()
        cfg["agents"]["gemini"]["links_skills"] = True
        config.save(cfg)
        res = store.install(entry)
        assert "gemini" in res.linked
        assert res.native == []
        assert _link("gemini").is_symlink()


class TestInstallFromPath:
    def _src(self, tmp_path, fm, extras=True):
        src = tmp_path / "dir-name-skill"
        src.mkdir()
        (src / "SKILL.md").write_text(fm + "\n\n# Title\n\nBody line\n", encoding="utf-8")
        if extras:
            (src / "notes.txt").write_text("extra", encoding="utf-8")
            (src / ".git").mkdir()
            (src / ".git" / "HEAD").write_text("ref", encoding="utf-8")
            (src / "__pycache__").mkdir()
            (src / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
        return src

    # ── gates: install_from_path used to enforce NONE of these, so every local
    # path in (import, create --install, migrate, distill/infer/absorb --install)
    # was a way around the blocklist, pin_only, max_skills and denied_capabilities.

    def test_refuses_a_pinned_skill(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: pinned-skill\nversion: 1.0.0\n---")
        store.install_from_path(src)
        lk = lockfile.get_skill("pinned-skill")
        lk["pinned"] = True
        lockfile.set_skill("pinned-skill", lk)
        with pytest.raises(BoostError, match="pinned-skill is pinned"):
            store.install_from_path(src)

    def test_force_overrides_the_pin(self, sandbox, tmp_path):
        # `boost reinstall` on a local skill must still work when pinned.
        src = self._src(tmp_path, "---\nname: pinned-skill\nversion: 1.0.0\n---")
        store.install_from_path(src)
        lk = lockfile.get_skill("pinned-skill")
        lk["pinned"] = True
        lockfile.set_skill("pinned-skill", lk)
        store.install_from_path(src, force=True)
        assert lockfile.get_skill("pinned-skill")["pinned"] is True

    def test_reimport_preserves_an_existing_pin(self, sandbox, tmp_path):
        # The lock write hardcoded "pinned": False, so a re-import did not just
        # skip the check — it silently CLEARED the pin.
        src = self._src(tmp_path, "---\nname: keeps-pin\nversion: 1.0.0\n---")
        store.install_from_path(src)
        lk = lockfile.get_skill("keeps-pin")
        lk["pinned"] = True
        lockfile.set_skill("keeps-pin", lk)
        store.install_from_path(src, force=True)
        assert lockfile.get_skill("keeps-pin")["pinned"] is True

    def test_unpinned_stays_unpinned(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: no-pin\nversion: 1.0.0\n---")
        store.install_from_path(src)
        store.install_from_path(src)
        assert lockfile.get_skill("no-pin")["pinned"] is False

    def test_blocklist_policy_refuses(self, sandbox, tmp_path):
        policy.save({"blocked_skills": ["blocked-one"]})
        src = self._src(tmp_path, "---\nname: blocked-one\nversion: 1.0.0\n---")
        with pytest.raises(BoostError, match="policy blocks installing blocked-one"):
            store.install_from_path(src)
        assert lockfile.get_skill("blocked-one") is None

    def test_pin_only_policy_refuses(self, sandbox, tmp_path):
        policy.save({"pin_only": True})
        src = self._src(tmp_path, "---\nname: frozen-env\nversion: 1.0.0\n---")
        with pytest.raises(BoostError, match="pin-only"):
            store.install_from_path(src)

    def test_denied_capability_refuses(self, sandbox, tmp_path):
        policy.save({"denied_capabilities": ["shell"]})
        src = self._src(tmp_path,
                        "---\nname: shelly\nversion: 1.0.0\ncapabilities: [shell]\n---")
        with pytest.raises(BoostError, match="shell"):
            store.install_from_path(src)

    def test_force_does_not_bypass_policy(self, sandbox, tmp_path):
        # force is about the pin, not about policy — matching install().
        policy.save({"blocked_skills": ["still-blocked"]})
        src = self._src(tmp_path, "---\nname: still-blocked\nversion: 1.0.0\n---")
        with pytest.raises(BoostError, match="policy blocks"):
            store.install_from_path(src, force=True)

    def test_reimport_does_not_trip_max_skills(self, sandbox, tmp_path):
        # The skill is already counted in the lock, so re-importing it must not
        # be measured as if it were a new one.
        src = self._src(tmp_path, "---\nname: only-one\nversion: 1.0.0\n---")
        store.install_from_path(src)
        policy.save({"max_skills": 1})
        store.install_from_path(src)
        assert lockfile.get_skill("only-one") is not None

    def test_max_skills_still_refuses_a_genuinely_new_skill(self, sandbox, tmp_path):
        first = self._src(tmp_path, "---\nname: first-one\nversion: 1.0.0\n---")
        store.install_from_path(first)
        policy.save({"max_skills": 1})
        second = tmp_path / "second"
        second.mkdir()
        (second / "SKILL.md").write_text(
            "---\nname: second-one\nversion: 1.0.0\n---\n\n# t\n", encoding="utf-8")
        with pytest.raises(BoostError, match="policy blocks"):
            store.install_from_path(second)

    def test_refusal_leaves_no_half_copied_store_dir(self, sandbox, tmp_path):
        policy.save({"blocked_skills": ["never-lands"]})
        src = self._src(tmp_path, "---\nname: never-lands\nversion: 1.0.0\n---")
        with pytest.raises(BoostError):
            store.install_from_path(src)
        assert not (paths.store_dir() / "never-lands").exists()

    def test_name_from_frontmatter(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: imported-skill\nversion: 9.9.9\n---")
        res = store.install_from_path(src)
        assert res.name == "imported-skill"
        dest = paths.store_dir() / "imported-skill"
        assert (dest / "SKILL.md").is_file()
        assert (dest / "notes.txt").is_file()
        assert not (dest / ".git").exists()
        assert not (dest / "__pycache__").exists()
        e = lockfile.get_skill("imported-skill")
        assert e["version"] == "9.9.9"
        assert e["tap"] == "local"
        assert e["source_dir"] == str(src)
        assert e["commit"] == ""
        assert e["pinned"] is False
        assert e["quarantined"] is False
        assert e["tags"] == []
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"])
        assert re.fullmatch(ISO, e["installed_at"])
        assert e["updated_at"] == e["installed_at"]   # both set to `now`
        assert e["agents"] == LINKED_AGENTS

    def test_reinstall_preserves_installed_at_and_tags(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: keep\nversion: 1.0\n---", extras=False)
        store.install_from_path(src)
        e = lockfile.get_skill("keep")
        e["installed_at"] = "2019-06-06T06:06:06Z"   # fixed past — no `now` collision
        e["tags"] = ["fav", "team"]
        lockfile.set_skill("keep", e)

        store.install_from_path(src)
        e2 = lockfile.get_skill("keep")
        assert e2["installed_at"] == "2019-06-06T06:06:06Z"   # preserved
        assert e2["updated_at"] != "2019-06-06T06:06:06Z"     # refreshed
        assert re.fullmatch(ISO, e2["updated_at"])
        assert e2["tags"] == ["fav", "team"]                  # preserved

    def test_name_falls_back_to_dirname(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nversion: 1.0\n---", extras=False)
        res = store.install_from_path(src)
        assert res.name == "dir-name-skill"
        assert lockfile.get_skill("dir-name-skill")["version"] == "1.0"

    def test_explicit_name_wins(self, sandbox, tmp_path):
        src = self._src(tmp_path, "---\nname: meta-name\n---", extras=False)
        res = store.install_from_path(src, name="override", tap_label="team")
        assert res.name == "override"
        e = lockfile.get_skill("override")
        assert e["tap"] == "team"
        assert e["version"] == "0.0.0"

    def test_missing_skill_md_raises(self, sandbox, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(BoostError) as ei:
            store.install_from_path(empty)
        assert ei.value.message == "%s has no SKILL.md" % empty


class TestUninstall:
    def test_uninstall_removes_everything(self, brainstorming):
        result = store.uninstall("brainstorming")
        assert result["name"] == "brainstorming"
        assert result["unlinked"] == LINKED_AGENTS
        assert result["entry"]["version"] == "1.4.0"
        assert not (paths.store_dir() / "brainstorming").exists()
        for agent in LINKED_AGENTS:
            assert not _link(agent).exists()
        assert lockfile.get_skill("brainstorming") is None

    def test_uninstall_missing_raises(self, sandbox):
        with pytest.raises(BoostError) as ei:
            store.uninstall("ghost")
        assert ei.value.message == "ghost is not installed"
        assert ei.value.hint == "see what is with `boost list`"


class TestSyncPlan:
    EMPTY: ClassVar[dict] = {"missing_store": [], "missing_links": [],
             "stale_links": [], "orphaned_store": [],
             "missing_materializations": []}

    def test_clean_state_empty_plan(self, brainstorming):
        assert store.sync_plan() == self.EMPTY

    def test_missing_links(self, brainstorming):
        _link("windsurf").unlink()
        plan = store.sync_plan()
        assert plan == {**self.EMPTY,
                        "missing_links": [("brainstorming", "windsurf")]}

    def test_quarantined_excluded_from_missing_links(self, brainstorming):
        e = lockfile.get_skill("brainstorming")
        e["quarantined"] = True
        lockfile.set_skill("brainstorming", e)
        for agent in LINKED_AGENTS:
            _link(agent).unlink()
        assert store.sync_plan() == self.EMPTY

    def test_stale_dangling_symlink(self, brainstorming):
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.store_dir() / "ghost")   # target missing
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "stale_links": [str(ghost)]}

    def test_unmanaged_link_into_store_is_stale(self, brainstorming):
        orphan_store = paths.store_dir() / "orphan"
        orphan_store.mkdir()
        (orphan_store / "f.txt").write_text("x", encoding="utf-8")
        link = paths.home() / ".cursor" / "skills" / "orphan"
        link.symlink_to(orphan_store)
        plan = store.sync_plan()
        assert plan["stale_links"] == [str(link)]
        assert plan["orphaned_store"] == ["orphan"]

    def test_valid_symlink_outside_store_not_stale(self, brainstorming):
        target = paths.home() / "elsewhere"
        target.mkdir()
        link = paths.home() / ".claude" / "skills" / "external"
        link.symlink_to(target)
        assert store.sync_plan() == self.EMPTY

    def test_broken_symlink_boost_does_not_own_is_left_alone(self,
                                                             brainstorming):
        # The ownership test used to be short-circuited by `not link.exists()`,
        # so a user's own dangling link — an unmounted volume, a moved notes
        # repo — was swept up by plain `boost sync`.
        mine = paths.home() / ".claude" / "skills" / "my-notes"
        mine.symlink_to(paths.home() / "unmounted-volume" / "notes")
        assert store.sync_plan() == self.EMPTY
        store.sync_apply(store.sync_plan())
        assert mine.is_symlink()

    def test_broken_link_into_a_lookalike_sibling_is_left_alone(self,
                                                                brainstorming):
        # `~/.agents/skills-backup` starts with the store path as a *string*
        # but is a different directory; the check compares path components.
        sibling = Path(str(paths.store_dir()) + "-backup")
        link = paths.home() / ".claude" / "skills" / "backup-thing"
        link.symlink_to(sibling / "brainstorming")
        assert store.sync_plan() == self.EMPTY

    def test_broken_link_with_a_relative_target_into_the_store_is_stale(
            self, brainstorming):
        # readlink() hands back the raw target; a relative one has to be
        # resolved against the link's own directory before it can be judged.
        adir = paths.home() / ".claude" / "skills"
        rel = os.path.relpath(str(paths.store_dir() / "gone"), str(adir))
        link = adir / "gone"
        link.symlink_to(rel)
        assert store.sync_plan()["stale_links"] == [str(link)]

    def test_points_into_store_ignores_an_unreadable_link(self, brainstorming):
        # A plain file is not a symlink, so readlink() raises rather than
        # returning something that might accidentally look owned.
        plain = paths.home() / ".claude" / "skills" / "notalink"
        plain.write_text("x", encoding="utf-8")
        assert store.points_into_store(plain) is False

    def test_orphaned_store_dir(self, brainstorming):
        rogue = paths.store_dir() / "rogue"
        rogue.mkdir()
        (paths.store_dir() / "stray.txt").write_text("not a dir", encoding="utf-8")
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "orphaned_store": ["rogue"]}

    def test_missing_agent_dir_reports_missing_links_not_stale(self, tap, entry):
        # only claude-code was linked, so the other agent dirs were never
        # created — sync still wants links there, and the stale-link scan
        # skips the nonexistent dirs.
        #
        # `--agent` is used here purely to leave those dirs uncreated, so the
        # declaration it records is cleared again: a *narrowed* skill is now
        # deliberately left alone (TestSyncRespectsDeclaredScope), and what
        # this test is about is the unnarrowed fan-out reporting a missing
        # directory as missing_links rather than stale_links.
        store.install(entry, only_agents=["claude-code"])
        e = lockfile.get_skill("brainstorming")
        e["only_agents"] = None
        lockfile.set_skill("brainstorming", e)
        assert not (paths.home() / ".windsurf" / "skills").exists()
        # gemini never gets a link, so its dir is absent for a different reason
        # and sync must NOT report one as missing — doing so would make `boost
        # sync` recreate the duplicate links_skills exists to prevent.
        assert not (paths.home() / ".gemini" / "skills").exists()
        plan = store.sync_plan()
        assert plan == {**self.EMPTY, "missing_links": [
            ("brainstorming", "windsurf"), ("brainstorming", "cursor")]}

    def test_missing_store(self, brainstorming):
        shutil.rmtree(paths.store_dir() / "brainstorming")
        plan = store.sync_plan()
        assert plan["missing_store"] == ["brainstorming"]
        assert plan["missing_links"] == []          # skipped via continue
        assert plan["orphaned_store"] == []
        assert sorted(plan["stale_links"]) == sorted(
            str(_link(a)) for a in LINKED_AGENTS)    # links now dangle



class TestNormalizeLinkTarget:
    """Windows readlink() hands back the reparse point's substitution path.

    Since 3.8 that typically carries the `\\\\?\\` extended-length prefix, so
    boost's own link into the store stopped matching the store root once the
    comparison became component-wise instead of a substring test. Every
    Windows leg of the matrix went red on exactly this.
    """

    def test_extended_length_prefix_is_stripped(self):
        got = store.normalize_link_target(Path(r"\\?\C:\Users\me\.agents\skills"))
        assert got == os.path.normcase(os.path.normpath(r"C:\Users\me\.agents\skills"))

    def test_unc_prefix_becomes_a_plain_unc_path(self):
        got = store.normalize_link_target(Path(r"\\?\UNC\server\share\x"))
        assert got == os.path.normcase(os.path.normpath(r"\\server\share\x"))

    def test_an_ordinary_path_is_left_alone_apart_from_normalizing(self,
                                                                   tmp_path):
        got = store.normalize_link_target(tmp_path / "a" / ".." / "b")
        assert got == os.path.normcase(os.path.normpath(str(tmp_path / "b")))

    def test_windows_containment_holds_under_ntpath_rules(self):
        """Pin the actual Windows failure on every platform.

        `ntpath` imports fine on POSIX, so the semantics that broke all three
        Windows legs can be asserted here rather than only on a Windows runner
        — where nobody can read the log from this sandbox anyway.
        """
        import ntpath
        target = r"\\?\C:\Users\runneradmin\.agents\skills\gone"
        root = r"C:\Users\runneradmin\.agents\skills"

        # Why it went unnoticed: the check this replaced was a substring test,
        # which the extended-length prefix sails straight through.
        assert root in target

        # Component-wise, the prefix reads as a different drive entirely.
        with pytest.raises(ValueError):
            ntpath.commonpath([ntpath.normpath(target), ntpath.normpath(root)])

        # Stripped, containment holds — and the lookalike sibling still fails.
        def win(text):
            return ntpath.normcase(
                ntpath.normpath(store.strip_extended_prefix(text)))

        assert ntpath.commonpath([win(target), win(root)]) == win(root)
        sibling = win(r"\\?\C:\Users\runneradmin\.agents\skills-backup\x")
        assert ntpath.commonpath([sibling, win(root)]) != win(root)



class TestSyncApply:
    def test_repairs_missing_link(self, brainstorming):
        _link("windsurf").unlink()
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["linked brainstorming → windsurf"]
        assert _link("windsurf").is_symlink()

    def test_removes_stale_link(self, brainstorming):
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.store_dir() / "ghost")
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["removed stale link %s" % ghost]
        assert not ghost.is_symlink()

    def test_missing_store_reinstalled_from_tap(self, brainstorming):
        shutil.rmtree(paths.store_dir() / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert len(actions) == 4                     # 3 stale links + reinstall
        assert actions[-1] == "reinstalled missing brainstorming from fixture-tap"
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()
        assert lockfile.get_skill("brainstorming") is not None
        for agent in LINKED_AGENTS:
            assert _link(agent).is_symlink()

    def test_missing_store_reinstall_fails_falls_back_to_drop(self, tap, brainstorming):
        # catalog cache still lists the skill, but its source dir vanished
        # from the tap clone: the reinstall attempt raises and is swallowed,
        # then the entry is dropped from the lock.
        shutil.rmtree(paths.store_dir() / "brainstorming")
        shutil.rmtree(tap.path / "skills" / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert ("dropped brainstorming from lock (store dir missing, source gone)"
                in actions)
        assert not any(a.startswith("reinstalled") for a in actions)
        assert lockfile.get_skill("brainstorming") is None

    def test_missing_store_tap_gone_dropped_from_lock(self, brainstorming):
        registry.remove("fixture-tap")
        shutil.rmtree(paths.store_dir() / "brainstorming")
        actions = store.sync_apply(store.sync_plan())
        assert ("dropped brainstorming from lock (store dir missing, source gone)"
                in actions)
        assert lockfile.get_skill("brainstorming") is None

    def test_nothing_to_do_no_actions(self, brainstorming):
        assert store.sync_apply(store.sync_plan()) == []


class TestCopySkillAtomic:
    def _mkskill(self, root, name, body="v1"):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(body, encoding="utf-8")
        return d

    def _leftovers(self, parent, keep):
        return sorted(p.name for p in parent.iterdir() if p.name != keep)

    def test_fresh_copy(self, tmp_path):
        src = self._mkskill(tmp_path / "src", "sk")
        (src / ".git").mkdir()
        (src / ".git" / "cfg").write_text("junk", encoding="utf-8")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src, dest)
        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "v1"
        assert not (dest / ".git").exists()           # ignore patterns honoured
        assert self._leftovers(dest.parent, "sk") == []   # no temp/backup dirs

    def test_reinstall_replaces_and_cleans_up(self, tmp_path):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="old")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)
        src2 = self._mkskill(tmp_path / "s2", "sk", body="new")
        store._copy_skill(src2, dest)
        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "new"
        assert self._leftovers(dest.parent, "sk") == []

    def test_swap_in_failure_rolls_back_to_original(self, tmp_path, monkeypatch):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="original")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)          # dest now holds the good copy
        src2 = self._mkskill(tmp_path / "s2", "sk", body="broken")

        real = store.os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if calls["n"] == 2:                # the swap-IN of the new copy
                raise OSError("swap failed")
            return real(a, b)

        monkeypatch.setattr(store.os, "replace", flaky)
        with pytest.raises(OSError, match="swap failed"):
            store._copy_skill(src2, dest)
        # original survives intact, nothing half-swapped, no debris
        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "original"
        assert self._leftovers(dest.parent, "sk") == []

    def test_copytree_failure_preserves_existing(self, tmp_path, monkeypatch):
        src1 = self._mkskill(tmp_path / "s1", "sk", body="original")
        dest = tmp_path / "store" / "sk"
        store._copy_skill(src1, dest)

        def boom(*a, **k):
            raise OSError("copy failed")

        monkeypatch.setattr(store.shutil, "copytree", boom)
        with pytest.raises(OSError, match="copy failed"):
            store._copy_skill(tmp_path / "s1" / "sk", dest)
        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "original"
        assert self._leftovers(dest.parent, "sk") == []


def _rule_entry(tap, name="team-conventions", rel="rules/team.mdc"):
    """Write a rule file into the tap clone and return its catalog entry."""
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: Team Conventions\n---\n\nAlways write tests first.\n", encoding="utf-8")
    return {
        "name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
        "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
        "description": "team rules", "curated": False,
        "meta": {"name": "Team Conventions"},
    }


class TestRuleInstall:
    def _claude_md(self):
        return paths.home() / ".claude" / "CLAUDE.md"

    def _gemini_md(self):
        return paths.home() / ".gemini" / "GEMINI.md"

    def test_materializes_into_each_agent_native_format(self, tap):
        res = store.install(_rule_entry(tap))
        assert set(res.linked) == {"claude-code", "windsurf", "cursor", "gemini"}

        # Claude Code has no rules folder -> managed block in CLAUDE.md.
        text = self._claude_md().read_text(encoding="utf-8")
        assert "boost:rule:team-conventions start" in text
        assert "# Team Conventions" in text
        assert "Always write tests first." in text
        assert "name: Team Conventions" not in text  # frontmatter stripped for CLAUDE.md

        # Gemini CLI has no rules folder either -> the same managed block, in
        # its own context file. A ~/.gemini/rules/ drop would never be read.
        gem = self._gemini_md()
        assert gem.is_file()
        gtext = gem.read_text(encoding="utf-8")
        assert "boost:rule:team-conventions start" in gtext
        assert "boost:rule:team-conventions end" in gtext
        assert "# Team Conventions" in gtext
        assert "Always write tests first." in gtext
        assert "name: Team Conventions" not in gtext   # frontmatter stripped
        assert not (paths.home() / ".gemini" / "rules").exists()

        # Cursor: verbatim .mdc drop, frontmatter preserved (native metadata).
        cur = paths.home() / ".cursor" / "rules" / "team-conventions.mdc"
        assert cur.is_file()
        assert "name: Team Conventions" in cur.read_text(encoding="utf-8")

        # Windsurf: .md drop.
        assert (paths.home() / ".windsurf" / "rules" / "team-conventions.md").is_file()

        rec = lockfile.get_rule("team-conventions")
        assert rec["kind"] == "rule"
        assert rec["tap"] == tap.name
        assert {m["agent"] for m in rec["materializations"]} == {
            "claude-code", "windsurf", "cursor", "gemini"}
        # The mode is what uninstall dispatches on, so pin it per agent: the two
        # context-file agents share MODE_CLAUDE, the rules-dir agents don't.
        assert {m["agent"]: m["mode"] for m in rec["materializations"]} == {
            "claude-code": "claude", "gemini": "claude",
            "windsurf": "file", "cursor": "file"}
        assert {m["agent"]: m["path"] for m in rec["materializations"]}["gemini"] \
            == str(gem)
        assert lockfile.get_skill("team-conventions") is None  # not a skill

    def test_uninstall_reverses_every_materialization(self, tap):
        store.install(_rule_entry(tap))
        claude_md = self._claude_md()
        # A hand-authored note above our block must survive uninstall.
        claude_md.write_text("# My own standing notes\n\n" + claude_md.read_text(encoding="utf-8"), encoding="utf-8")

        info = store.uninstall("team-conventions")
        assert set(info["unlinked"]) == {"claude-code", "windsurf", "cursor",
                                         "gemini"}
        assert lockfile.get_rule("team-conventions") is None
        text = claude_md.read_text(encoding="utf-8")
        assert "boost:rule" not in text
        assert "# My own standing notes" in text
        assert not (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").exists()
        assert not (paths.home() / ".windsurf" / "rules" / "team-conventions.md").exists()
        # GEMINI.md held only our block, so it goes with it.
        assert not self._gemini_md().exists()

    def test_uninstall_strips_only_our_block_from_gemini_md(self, tap):
        """The GEMINI.md equivalent of the CLAUDE.md guarantee above.

        Gemini's context file is the user's own standing-instructions file, so
        uninstall has to splice our block out and leave the rest — not delete a
        file the user writes in.
        """
        store.install(_rule_entry(tap))
        gem = self._gemini_md()
        gem.write_text("# My Gemini notes\n\n" + gem.read_text(encoding="utf-8"),
                       encoding="utf-8")

        store.uninstall("team-conventions")

        assert gem.is_file()                       # survived: not only our block
        text = gem.read_text(encoding="utf-8")
        assert "boost:rule" not in text
        assert "Always write tests first." not in text
        assert "# My Gemini notes" in text

    def test_uninstall_removes_claude_md_when_only_our_block(self, tap):
        store.install(_rule_entry(tap, name="solo"))
        store.uninstall("solo")
        # CLAUDE.md held only our block -> boost created it -> removed on uninstall.
        assert not self._claude_md().exists()

    def test_reinstall_requires_force_and_stays_idempotent(self, tap):
        entry = _rule_entry(tap)
        store.install(entry)
        with pytest.raises(BoostError):
            store.install(entry)
        res = store.install(entry, force=True)
        assert res.upgraded is True
        assert self._claude_md().read_text(encoding="utf-8").count("boost:rule:team-conventions start") == 1

    def test_only_agents_limits_materialization(self, tap):
        res = store.install(_rule_entry(tap), only_agents=["cursor"])
        assert res.linked == ["cursor"]
        assert (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").is_file()
        assert not self._claude_md().exists()
        assert not self._gemini_md().exists()

    def test_missing_source_raises(self, tap):
        entry = _rule_entry(tap)
        (tap.path / entry["skill_md"]).unlink()
        with pytest.raises(BoostError, match="vanished from tap"):
            store.install(entry)


def _workflow_entry(tap, name="ship-it", rel="commands/ship.md",
                    body="---\nname: ship-it\ndescription: release helper\n"
                         "allowed-tools: Bash\n---\n\nRun the release.\n"):
    """Write a workflow file into the tap clone and return its catalog entry."""
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(body, encoding="utf-8")
    return {
        "name": name, "kind": "workflow", "tap": tap.name, "version": "1.0.0",
        "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
        "description": "release helper", "curated": False, "meta": {},
    }


class TestWorkflowInstall:
    def test_command_drops_into_each_agents_commands_dir(self, tap):
        res = store.install(_workflow_entry(tap))
        assert res.kind == "workflow"
        assert set(res.linked) == {"claude-code", "windsurf", "cursor", "gemini"}
        for adir in (".claude", ".windsurf", ".cursor"):
            f = paths.home() / adir / "commands" / "ship-it.md"
            assert f.is_file()
            assert "Run the release." in f.read_text(encoding="utf-8")  # verbatim drop

        # Gemini CLI reads slash commands as TOML: a .md drop there is simply
        # never discovered, so the extension AND the content have to change.
        gem = paths.home() / ".gemini" / "commands" / "ship-it.toml"
        assert gem.is_file()
        assert not (paths.home() / ".gemini" / "commands" / "ship-it.md").exists()
        gtext = gem.read_text(encoding="utf-8")
        assert gtext == ('description = "release helper"\n'
                         'prompt = "Run the release."\n')
        assert "---" not in gtext                  # frontmatter dropped, not carried
        assert "allowed-tools" not in gtext

        rec = lockfile.get_workflow("ship-it")
        assert rec["kind"] == "workflow"
        assert rec["slot"] == "commands"
        assert {m["agent"]: m["path"] for m in rec["materializations"]}["gemini"] \
            == str(gem)
        assert lockfile.get_skill("ship-it") is None

    def test_subagent_drops_into_agents_dir(self, tap):
        entry = _workflow_entry(tap, name="reviewer", rel="agents/reviewer.md",
                                body="---\nname: reviewer\ndescription: reviews\n"
                                     "tools: Read\n---\n\nReview it.\n")
        store.install(entry)
        assert (paths.home() / ".claude" / "agents" / "reviewer.md").is_file()
        assert not (paths.home() / ".claude" / "commands" / "reviewer.md").exists()
        assert lockfile.get_workflow("reviewer")["slot"] == "agents"

    def test_gemini_subagent_stays_verbatim_markdown(self, tap):
        """Only Gemini's *commands* slot is TOML — its subagents are Markdown.

        The easy way to get this wrong is to key the conversion on the agent
        alone, which would hand Gemini a .toml subagent it cannot load.
        """
        body = ("---\nname: reviewer\ndescription: reviews\ntools: Read\n---\n\n"
                "Review it.\n")
        entry = _workflow_entry(tap, name="reviewer", rel="agents/reviewer.md",
                                body=body)
        store.install(entry)

        gem = paths.home() / ".gemini" / "agents" / "reviewer.md"
        assert gem.is_file()
        assert gem.read_text(encoding="utf-8") == body      # byte-for-byte verbatim
        assert not (paths.home() / ".gemini" / "agents" / "reviewer.toml").exists()
        assert not (paths.home() / ".gemini" / "commands" / "reviewer.md").exists()
        assert not (paths.home() / ".gemini" / "commands" / "reviewer.toml").exists()

        rec = lockfile.get_workflow("reviewer")
        assert rec["slot"] == "agents"
        assert {m["agent"]: m["path"] for m in rec["materializations"]}["gemini"] \
            == str(gem)

    def test_uninstall_removes_every_dropped_file(self, tap):
        store.install(_workflow_entry(tap))
        info = store.uninstall("ship-it")
        assert set(info["unlinked"]) == {"claude-code", "windsurf", "cursor",
                                         "gemini"}
        assert lockfile.get_workflow("ship-it") is None
        for adir in (".claude", ".windsurf", ".cursor"):
            assert not (paths.home() / adir / "commands" / "ship-it.md").exists()
        # The recorded path is the .toml one, so that is what must be removed.
        assert not (paths.home() / ".gemini" / "commands" / "ship-it.toml").exists()

    def test_uninstall_removes_a_gemini_subagent_markdown_file(self, tap):
        entry = _workflow_entry(tap, name="reviewer", rel="agents/reviewer.md",
                                body="---\nname: reviewer\n---\n\nReview it.\n")
        store.install(entry)
        gem = paths.home() / ".gemini" / "agents" / "reviewer.md"
        assert gem.is_file()
        info = store.uninstall("reviewer")
        assert "gemini" in info["unlinked"]
        assert not gem.exists()
        assert lockfile.get_workflow("reviewer") is None

    def test_reinstall_requires_force(self, tap):
        entry = _workflow_entry(tap)
        store.install(entry)
        with pytest.raises(BoostError):
            store.install(entry)
        res = store.install(entry, force=True)
        assert res.upgraded is True

    def test_only_agents_limits_drop(self, tap):
        res = store.install(_workflow_entry(tap), only_agents=["claude-code"])
        assert res.linked == ["claude-code"]
        assert (paths.home() / ".claude" / "commands" / "ship-it.md").is_file()
        assert not (paths.home() / ".cursor" / "commands" / "ship-it.md").exists()
        assert not (paths.home() / ".gemini" / "commands" / "ship-it.toml").exists()

    def test_missing_source_raises(self, tap):
        entry = _workflow_entry(tap)
        (tap.path / entry["skill_md"]).unlink()
        with pytest.raises(BoostError, match="vanished from tap"):
            store.install(entry)


class TestSyncMaterializations:
    def _install_rule(self, tap, name="team-conventions"):
        entry = _rule_entry(tap, name=name)
        catalog.rebuild_tap(tap)          # so catalog.find(name) sees the rule
        store.install(entry)
        return entry

    def _install_workflow(self, tap, name="ship-it"):
        entry = _workflow_entry(tap, name=name)
        catalog.rebuild_tap(tap)
        store.install(entry)
        return entry

    def test_intact_materializations_not_flagged(self, tap):
        self._install_rule(tap)
        assert store.sync_plan()["missing_materializations"] == []

    def test_flags_missing_rule_file(self, tap):
        self._install_rule(tap)
        (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").unlink()
        assert store.sync_plan()["missing_materializations"] == [
            ("rule", "team-conventions")]

    def test_flags_stripped_claude_block(self, tap):
        self._install_rule(tap)
        (paths.home() / ".claude" / "CLAUDE.md").write_text("# only my notes\n", encoding="utf-8")
        assert ("rule", "team-conventions") in \
            store.sync_plan()["missing_materializations"]

    def test_apply_rematerializes_missing_rule(self, tap):
        self._install_rule(tap)
        cur = paths.home() / ".cursor" / "rules" / "team-conventions.mdc"
        cur.unlink()
        actions = store.sync_apply(store.sync_plan())
        assert any("re-materialized rule team-conventions" in a for a in actions)
        assert cur.is_file()

    def test_flags_and_repairs_missing_workflow_file(self, tap):
        self._install_workflow(tap)
        f = paths.home() / ".claude" / "commands" / "ship-it.md"
        f.unlink()
        assert store.sync_plan()["missing_materializations"] == [
            ("workflow", "ship-it")]
        store.sync_apply(store.sync_plan())
        assert f.is_file()

    def test_rule_install_carries_scan_text(self, tap):
        res = store.install(_rule_entry(tap))
        assert res.scan_text is not None
        assert "Always write tests first." in res.scan_text  # raw source, for scan

    def test_workflow_install_carries_scan_text(self, tap):
        res = store.install(_workflow_entry(tap))
        assert res.scan_text is not None
        assert "Run the release." in res.scan_text


class TestInstallScope:
    def test_resolve_base(self):
        from pathlib import Path as P
        assert store._resolve_base("user", None) is None
        assert store._resolve_base("project", "/x") == P("/x")

    def test_resolve_base_delegates_the_walk_up_to_scopes(self, monkeypatch):
        """Project scope must resolve the REPO, not the cwd.

        This used to be a bare ``Path.cwd()``, so ``boost install --local`` from
        ``src/deep/nested`` scattered a ``.claude/`` three levels below the repo
        root. The walk-up itself is ``scopes``' job and is tested there against
        real directory trees; what ``store`` owns is *delegating* to it, which
        is what this pins. (Asserting the walk-up here would need a chdir, and a
        unit test that chdirs breaks mutmut's instrumentation — it resolves
        ``boost_cli`` relative to the working directory.)
        """
        from pathlib import Path as P

        from boost_cli.core import scopes
        seen = {}

        def fake(scope, base=None, start=None):
            seen["args"] = (scope, base)
            return P("/sentinel-root")

        monkeypatch.setattr(scopes, "resolve_base", fake)
        assert store._resolve_base("project", None) == P("/sentinel-root")
        assert seen["args"] == ("project", None)

    def test_rule_project_scope_materializes_under_base(self, tap, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        res = store.install(_rule_entry(tap), scope="project", base=str(repo))
        assert res.scope == "project"
        # Claude -> personal repo file, not ~/.claude/CLAUDE.md
        cm = repo / "CLAUDE.local.md"
        assert cm.is_file()
        assert "boost:rule:team-conventions start" in cm.read_text(encoding="utf-8")
        assert (repo / ".cursor" / "rules" / "team-conventions.mdc").is_file()
        assert (repo / ".windsurf" / "rules" / "team-conventions.md").is_file()
        assert not (paths.home() / ".claude" / "CLAUDE.md").exists()  # not global
        rec = lockfile.get_rule("team-conventions")
        assert rec["scope"] == "project"
        assert rec["base"] == str(repo)

    def test_rule_project_scope_uses_geminis_repo_context_file(self, tap, tmp_path):
        """Gemini documents no ``.local`` variant, so its project context file
        is the repo's own ``GEMINI.md`` — not a ``GEMINI.local.md`` that nothing
        reads, and not a ``.gemini/rules/`` drop that nothing reads either."""
        repo = tmp_path / "repo-gem"
        repo.mkdir()
        store.install(_rule_entry(tap), scope="project", base=str(repo))

        gem = repo / "GEMINI.md"
        assert gem.is_file()
        text = gem.read_text(encoding="utf-8")
        assert "boost:rule:team-conventions start" in text
        assert "boost:rule:team-conventions end" in text
        assert "Always write tests first." in text
        assert not (repo / "GEMINI.local.md").exists()
        assert not (repo / ".gemini").exists()
        assert not (paths.home() / ".gemini" / "GEMINI.md").exists()  # not global

        rec = lockfile.get_rule("team-conventions")
        by_agent = {m["agent"]: m for m in rec["materializations"]}
        assert by_agent["gemini"]["mode"] == "claude"
        assert by_agent["gemini"]["path"] == str(gem)

    def test_workflow_project_scope_under_base(self, tap, tmp_path):
        repo = tmp_path / "repo2"
        repo.mkdir()
        store.install(_workflow_entry(tap), scope="project", base=str(repo))
        assert (repo / ".claude" / "commands" / "ship-it.md").is_file()
        assert (repo / ".gemini" / "commands" / "ship-it.toml").is_file()
        assert not (repo / ".gemini" / "commands" / "ship-it.md").exists()
        assert not (paths.home() / ".claude" / "commands" / "ship-it.md").exists()
        assert not (paths.home() / ".gemini" / "commands" / "ship-it.toml").exists()
        assert lockfile.get_workflow("ship-it")["base"] == str(repo)

    def test_user_scope_is_default_and_global(self, tap):
        res = store.install(_rule_entry(tap))
        assert res.scope == "user"
        assert (paths.home() / ".claude" / "CLAUDE.md").is_file()
        rec = lockfile.get_rule("team-conventions")
        assert rec["scope"] == "user" and rec["base"] is None

    def test_project_uninstall_reverses_repo_files(self, tap, tmp_path):
        repo = tmp_path / "repo3"
        repo.mkdir()
        store.install(_rule_entry(tap), scope="project", base=str(repo))
        store.uninstall("team-conventions")
        assert not (repo / ".cursor" / "rules" / "team-conventions.mdc").exists()
        assert not (repo / "CLAUDE.local.md").exists()  # held only our block
        assert not (repo / "GEMINI.md").exists()        # ditto for Gemini's
        assert lockfile.get_rule("team-conventions") is None


class TestProjectSkills:
    """Skills installed into the repo itself (`boost install --local`).

    These drive ``store`` directly rather than through the CLI, so the mutation
    gate — which runs only ``tests/unit`` — actually exercises them. The
    end-to-end behavior has its own coverage in
    ``tests/functional/test_workspace_scope.py``.
    """

    @staticmethod
    def _repo(tmp_path, name="proj"):
        repo = tmp_path / name
        (repo / ".git").mkdir(parents=True)
        return repo

    def _install(self, entry, tmp_path, name="proj", **kw):
        repo = self._repo(tmp_path, name)
        res = store.install(entry, scope="project", base=str(repo), **kw)
        return repo, res

    # ── install ──────────────────────────────────────────────────────────

    def test_materializes_real_dirs_under_the_repo(self, entry, tmp_path):
        repo, res = self._install(entry, tmp_path)
        assert res.scope == "project" and res.kind == "skill"
        for agent, dotdir in AGENT_DIRS.items():
            d = repo / dotdir / "skills" / "brainstorming"
            assert (d / "SKILL.md").is_file()
            # A symlink into ~/.agents/skills dangles on a teammate's machine.
            assert not d.is_symlink()
            assert agent in res.linked

    def test_leaves_the_canonical_store_and_user_lock_alone(self, entry, tmp_path):
        self._install(entry, tmp_path)
        assert not (paths.store_dir() / "brainstorming").exists()
        assert lockfile.get_skill("brainstorming") is None

    def test_records_the_project_lock_not_the_user_one(self, entry, tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        assert rec["scope"] == "project"
        assert rec["kind"] == "skill"
        assert rec["version"] == "1.4.0"
        assert rec["tap"] == "fixture-tap"
        assert rec["agents"] == ["claude-code", "windsurf", "cursor", "gemini"]
        assert len(rec["materializations"]) == 4
        assert re.match(ISO, rec["installed_at"])
        assert re.match(ISO, rec["updated_at"])
        assert rec["sha256"] and rec["commit"]

    def test_result_carries_a_quality_score(self, entry, tmp_path):
        _repo, res = self._install(entry, tmp_path)
        assert res.score > 0
        assert not res.upgraded

    def test_only_agents_narrows_the_materialization(self, entry, tmp_path):
        repo, res = self._install(entry, tmp_path, only_agents=["cursor"])
        assert res.linked == ["cursor"]
        assert (repo / ".cursor" / "skills" / "brainstorming").is_dir()
        assert not (repo / ".claude" / "skills" / "brainstorming").exists()

    def test_a_second_install_is_refused_without_force(self, entry, tmp_path):
        repo = self._repo(tmp_path)
        store.install(entry, scope="project", base=str(repo))
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project", base=str(repo))
        assert "already installed in this project" in err.value.message
        assert "--local" in err.value.hint

    def test_force_reinstalls_and_marks_upgraded(self, entry, tmp_path):
        repo = self._repo(tmp_path)
        store.install(entry, scope="project", base=str(repo))
        res = store.install(entry, scope="project", base=str(repo), force=True)
        assert res.upgraded is True
        assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()

    def test_reinstall_preserves_the_original_installed_at(self, entry, tmp_path):
        from boost_cli.core import projectlock
        repo = self._repo(tmp_path)
        store.install(entry, scope="project", base=str(repo))
        first = projectlock.get_skill(repo, "brainstorming")["installed_at"]
        store.install(entry, scope="project", base=str(repo), force=True)
        assert projectlock.get_skill(repo, "brainstorming")["installed_at"] == first

    def test_symlinked_agent_dir_cannot_escape_the_repo(self, entry, tmp_path):
        """A committed ``.claude/skills`` symlink pointing outside the repo must
        not let the install write on the far side.

        The attack: a hostile clone ships an agent dir as a symlink to, say,
        ``~/.ssh``; ``_copy_skill`` would then ``mkdir``/``os.replace`` through
        it and land outside the project. Guarded by ``scopes.ensure_in_base``
        before any write. Uses a fresh skill name so the squatter check (which
        only fires on an existing path) is not what does the blocking.
        """
        repo = self._repo(tmp_path)
        outside = tmp_path / "outside"          # stands in for ~/.ssh
        outside.mkdir()
        (repo / ".claude").mkdir()
        (repo / ".claude" / "skills").symlink_to(outside, target_is_directory=True)

        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project", base=str(repo))
        assert "outside this project" in err.value.message
        # Nothing written through the symlink, and the all-or-nothing pre-check
        # means the other agents' in-repo dirs stay untouched too.
        assert list(outside.iterdir()) == []
        assert not (repo / ".windsurf" / "skills" / "brainstorming").exists()
        assert not (repo / ".cursor" / "skills" / "brainstorming").exists()
        assert not (repo / ".gemini" / "skills" / "brainstorming").exists()

    def test_policy_blocks_a_project_install_too(self, entry, tmp_path):
        # Vendoring into a repo is not an escape hatch around policy.
        policy.save({"blocked_skills": ["brainstorming"]})
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project", base=str(tmp_path / "p"))
        assert err.value.message == ("policy blocks installing brainstorming: "
                                     "skill 'brainstorming' is on the blocklist")
        assert not (tmp_path / "p" / ".claude").exists()

    def test_an_unknown_scope_is_rejected(self, entry):
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="galaxy")
        assert "unknown scope" in err.value.message

    def test_no_enabled_agents_is_an_error_not_a_silent_noop(self, entry, tmp_path,
                                                             monkeypatch):
        from boost_cli.core import agents as agents_mod
        monkeypatch.setattr(agents_mod, "enabled_agents", dict)
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project", base=str(tmp_path / "p"))
        assert "no enabled agents" in err.value.message

    # ── uninstall ────────────────────────────────────────────────────────

    def test_uninstall_project_removes_dirs_and_record(self, entry, tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        info = store.uninstall_project("brainstorming", base=str(repo))
        assert info["scope"] == "project"
        assert sorted(info["unlinked"]) == ["claude-code", "cursor", "gemini",
                                            "windsurf"]
        assert info["base"] == str(repo)
        for dotdir in AGENT_DIRS.values():
            assert not (repo / dotdir / "skills" / "brainstorming").exists()
        assert projectlock.get_skill(repo, "brainstorming") is None

    def test_uninstall_project_errors_when_not_installed(self, tap, tmp_path):
        with pytest.raises(BoostError) as err:
            store.uninstall_project("brainstorming", base=str(self._repo(tmp_path)))
        assert "not installed in this project" in err.value.message
        assert "--local" in err.value.hint

    def test_uninstall_refuses_a_path_outside_the_project(self, entry, tmp_path):
        """The lock is committed, so its paths are input — never trusted."""
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        victim = tmp_path / "not-the-repo"
        victim.mkdir()
        (victim / "keep.txt").write_text("precious", encoding="utf-8")
        rec = projectlock.get_skill(repo, "brainstorming")
        rec["materializations"] = [{"agent": "claude-code", "path": str(victim)}]
        projectlock.set_skill(repo, "brainstorming", rec)
        store.uninstall_project("brainstorming", base=str(repo))
        assert (victim / "keep.txt").is_file()
        assert victim.is_dir()

    def test_uninstall_refuses_the_project_root_itself(self, entry, tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        rec["materializations"] = [{"agent": "claude-code", "path": str(repo)}]
        projectlock.set_skill(repo, "brainstorming", rec)
        store.uninstall_project("brainstorming", base=str(repo))
        assert repo.is_dir(), "deleted the whole repo"

    # ── sync ─────────────────────────────────────────────────────────────

    def test_sync_plan_is_empty_when_everything_is_present(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        assert store.project_sync_plan(base=str(repo)) == \
            {"missing": [], "orphaned": []}

    def test_sync_plan_reports_a_missing_dir(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        shutil.rmtree(repo / ".claude" / "skills" / "brainstorming")
        plan = store.project_sync_plan(base=str(repo))
        assert plan["missing"] == [("brainstorming", "claude-code")]

    def test_sync_plan_reports_an_unclaimed_dir(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        mine = repo / ".claude" / "skills" / "hand-written"
        mine.mkdir(parents=True)
        assert [p for p in store.project_sync_plan(base=str(repo))["orphaned"]
                if p.endswith("hand-written")]

    def test_sync_apply_rematerializes_what_is_missing(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        shutil.rmtree(repo / ".claude" / "skills" / "brainstorming")
        plan = store.project_sync_plan(base=str(repo))
        actions = store.project_sync_apply(plan, base=str(repo))
        assert any("re-materialized brainstorming" in a for a in actions)
        assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()

    def test_sync_apply_never_deletes_an_unclaimed_dir(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        mine = repo / ".claude" / "skills" / "hand-written"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("mine\n", encoding="utf-8")
        plan = store.project_sync_plan(base=str(repo))
        store.project_sync_apply(plan, base=str(repo))
        assert (mine / "SKILL.md").is_file()

    def test_sync_apply_is_a_noop_with_nothing_to_do(self, entry, tmp_path):
        repo, _ = self._install(entry, tmp_path)
        assert store.project_sync_apply(
            store.project_sync_plan(base=str(repo)), base=str(repo)) == []

    def test_sync_apply_reports_when_the_source_is_gone(self, entry, tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        shutil.rmtree(repo / ".claude" / "skills" / "brainstorming")
        rec = projectlock.get_skill(repo, "brainstorming")
        rec["tap"] = "local"          # nothing to re-fetch from
        projectlock.set_skill(repo, "brainstorming", rec)
        actions = store.project_sync_apply(
            store.project_sync_plan(base=str(repo)), base=str(repo))
        assert any("source is gone" in a for a in actions)

    # ── the committed-lock contract ──────────────────────────────────────

    def test_lock_paths_are_relative_so_another_clone_can_read_them(self, entry,
                                                                    tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        paths_rec = sorted(m["path"] for m in rec["materializations"])
        assert paths_rec == [".claude/skills/brainstorming",
                             ".cursor/skills/brainstorming",
                             ".gemini/skills/brainstorming",
                             ".windsurf/skills/brainstorming"]
        # Nothing machine-specific: this file is committed and read elsewhere.
        for p in paths_rec:
            assert not p.startswith("/") and str(tmp_path) not in p

    def test_sync_reads_the_lock_from_a_different_clone_path(self, entry, tmp_path):
        """Simulates the teammate: same lock, different absolute directory."""
        repo, _ = self._install(entry, tmp_path)
        clone = tmp_path / "their-clone"
        shutil.copytree(repo, clone)
        shutil.rmtree(clone / ".claude" / "skills" / "brainstorming")
        plan = store.project_sync_plan(base=str(clone))
        assert plan["missing"] == [("brainstorming", "claude-code")]
        store.project_sync_apply(plan, base=str(clone))
        assert (clone / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()

    def test_an_empty_recorded_path_is_refused_not_resolved_to_the_repo(
            self, entry, tmp_path):
        """``Path(base) / "" == base`` — so a missing key must not reach rmtree."""
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        rec["materializations"] = [{"agent": "claude-code", "path": ""}]
        projectlock.set_skill(repo, "brainstorming", rec)
        info = store.uninstall_project("brainstorming", base=str(repo))
        assert repo.is_dir(), "deleted the project root"
        assert info["unlinked"] == []

    def test_uninstall_only_reports_agents_it_actually_removed(self, entry,
                                                              tmp_path):
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        shutil.rmtree(repo / ".cursor" / "skills" / "brainstorming")
        info = store.uninstall_project("brainstorming", base=str(repo))
        # cursor's dir was already gone — claiming to have removed it would be
        # a lie in the CLI's own summary line.
        assert sorted(info["unlinked"]) == ["claude-code", "gemini", "windsurf"]
        assert projectlock.get_skill(repo, "brainstorming") is None

    # ── conflicts and partial reinstalls ─────────────────────────────────

    def test_refuses_to_clobber_a_hand_written_skill_dir(self, entry, tmp_path):
        repo = self._repo(tmp_path)
        mine = repo / ".claude" / "skills" / "brainstorming"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("my own work\n", encoding="utf-8")
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project", base=str(repo))
        assert "boost did not install it" in err.value.message
        assert "--force" in err.value.hint
        assert (mine / "SKILL.md").read_text(encoding="utf-8") == "my own work\n"

    def test_force_overwrites_a_hand_written_dir_when_asked(self, entry, tmp_path):
        repo = self._repo(tmp_path)
        mine = repo / ".claude" / "skills" / "brainstorming"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("my own work\n", encoding="utf-8")
        store.install(entry, scope="project", base=str(repo), force=True)
        assert "my own work" not in (mine / "SKILL.md").read_text(encoding="utf-8")

    def test_filtered_reinstall_keeps_the_other_agents_in_the_lock(self, entry,
                                                                  tmp_path):
        """Otherwise the untouched copies become records nobody claims."""
        from boost_cli.core import projectlock
        repo = self._repo(tmp_path)
        store.install(entry, scope="project", base=str(repo))
        store.install(entry, scope="project", base=str(repo), force=True,
                      only_agents=["cursor"])
        rec = projectlock.get_skill(repo, "brainstorming")
        assert sorted(rec["agents"]) == ["claude-code", "cursor", "gemini",
                                         "windsurf"]
        assert len(rec["materializations"]) == 4
        # And uninstall still reverses every one of them.
        store.uninstall_project("brainstorming", base=str(repo))
        for dotdir in AGENT_DIRS.values():
            assert not (repo / dotdir / "skills" / "brainstorming").exists()

    # ── sync stays quiet where project scope is not in use ───────────────

    def test_sync_plan_is_empty_without_a_project_lock(self, tap, tmp_path):
        """A repo with hand-written skills but no project lock is not "unclaimed"."""
        repo = self._repo(tmp_path)
        mine = repo / ".claude" / "skills" / "hand-written"
        mine.mkdir(parents=True)
        assert store.project_sync_plan(base=str(repo)) == \
            {"missing": [], "orphaned": []}

    # ── no project here ──────────────────────────────────────────────────

    def test_project_install_in_bare_home_is_refused(self, entry, monkeypatch):
        """$HOME with no repo above it is not a project.

        Materializing there would write to ~/.claude/skills — user scope's own
        directories — so the two scopes would silently be the same place.

        Points HOME at the cwd rather than chdir'ing into a fake home: the
        condition under test is "cwd resolves to no project base", and a unit
        test that chdirs breaks mutmut's instrumentation.
        """
        monkeypatch.setenv("HOME", os.getcwd())
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project")
        assert err.value.message == \
            "there is no project here to install brainstorming into"
        assert "drop --local" in err.value.hint

    def test_project_rule_in_bare_home_is_refused_not_silently_global(
            self, tap, monkeypatch):
        """Rules took this path before too — and reported "this repo" while
        writing to ~/.claude/CLAUDE.md."""
        entry = _rule_entry(tap)
        monkeypatch.setenv("HOME", os.getcwd())
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project")
        assert "no project here" in err.value.message

    def test_project_workflow_in_bare_home_is_refused(self, tap, monkeypatch):
        entry = _workflow_entry(tap)
        monkeypatch.setenv("HOME", os.getcwd())
        with pytest.raises(BoostError) as err:
            store.install(entry, scope="project")
        assert "no project here" in err.value.message

    # ── sync must not revert committed edits ─────────────────────────────

    def test_sync_repairs_only_the_agents_that_are_missing(self, entry, tmp_path):
        """The sharpest failure mode this feature has.

        Project skill dirs are COMMITTED files that a team edits in place. If
        repairing one agent's missing directory re-installed the whole skill,
        `boost sync` would silently revert a teammate's checked-in edit to a
        different agent's copy — data loss in a git working tree, from a
        command whose whole job is "make it match the lock".

        Scenario: the team edits the committed .claude copy; .cursor is
        gitignored, so a fresh clone lacks it; someone runs `boost sync`.
        """
        from boost_cli.core import projectlock
        repo, _ = self._install(entry, tmp_path)
        claude_md = repo / ".claude" / "skills" / "brainstorming" / "SKILL.md"
        claude_md.write_text("---\nname: brainstorming\n---\nTEAM EDIT\n",
                             encoding="utf-8")
        shutil.rmtree(repo / ".cursor" / "skills" / "brainstorming")

        plan = store.project_sync_plan(base=str(repo))
        assert plan["missing"] == [("brainstorming", "cursor")]
        store.project_sync_apply(plan, base=str(repo))

        assert "TEAM EDIT" in claude_md.read_text(encoding="utf-8")
        assert (repo / ".cursor" / "skills" / "brainstorming" / "SKILL.md").is_file()
        # and the lock still describes all four
        assert len(projectlock.get_skill(repo, "brainstorming")
                   ["materializations"]) == 4


class TestCopySkillBackupCleanup:
    """_copy_skill's staging cleanup, when what it displaces is a symlink."""

    def test_a_displaced_symlink_leaves_no_litter(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        real = tmp_path / "real"
        real.mkdir()
        dest = tmp_path / "dest"
        dest.symlink_to(real)

        store._copy_skill(src, dest)

        assert (dest / "SKILL.md").is_file() and not dest.is_symlink()
        # rmtree() raises on a symlink and ignore_errors swallows it, so the
        # .tmpXXXX.old staging link used to survive forever — one dangling
        # pointer per reinstall, accumulating in the user's agent dirs.
        leftovers = [p.name for p in tmp_path.iterdir() if ".old" in p.name]
        assert leftovers == [], "left staging litter: %s" % leftovers

    def test_a_dangling_symlink_is_replaced_too(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        dest = tmp_path / "dest"
        dest.symlink_to(tmp_path / "nowhere")   # exists() is False for this

        store._copy_skill(src, dest)

        assert (dest / "SKILL.md").is_file() and not dest.is_symlink()
        assert [p.name for p in tmp_path.iterdir() if ".old" in p.name] == []

    def test_a_real_directory_is_still_replaced_cleanly(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("new\n", encoding="utf-8")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "SKILL.md").write_text("old\n", encoding="utf-8")
        (dest / "gone.md").write_text("stale\n", encoding="utf-8")

        store._copy_skill(src, dest)

        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "new\n"
        assert not (dest / "gone.md").exists()   # a swap, not a merge
        assert [p.name for p in tmp_path.iterdir() if ".old" in p.name] == []


class TestPreservedAgentScope:
    """The rule: a re-install may not widen what an install narrowed.

    ``update``/``reinstall`` force-reinstall with ``only_agents=None``, which
    used to mean "link into every enabled agent" and rewrote the lock's agent
    list to match — so ``boost install foo --agent claude-code`` quietly became
    a full install the first time anything upstream changed.
    """

    def test_an_explicit_scope_always_wins(self):
        # Re-running install with --agent is how a narrowed skill is widened
        # again; the lock must not veto it.
        assert store.preserved_agent_scope(
            ["cursor"], {"agents": ["claude-code"]}) == ["cursor"]
        assert store.preserved_agent_scope(
            ["a", "b"], {"agents": ["a"]}) == ["a", "b"]

    def test_an_explicit_empty_list_is_not_the_lock_s_scope(self):
        # [] is not None: the caller passed something, so it is theirs to mean.
        assert store.preserved_agent_scope([], {"agents": ["claude-code"]}) == []

    def test_a_fresh_install_has_no_scope_to_preserve(self):
        assert store.preserved_agent_scope(None, None) is None
        assert store.preserved_agent_scope(None, {}) is None

    def test_a_skill_s_scope_comes_from_its_agents_list(self):
        assert store.preserved_agent_scope(
            None, {"agents": ["claude-code"]}) == ["claude-code"]

    def test_a_rule_s_scope_comes_from_its_materializations(self):
        existing = {"materializations": [{"agent": "cursor", "path": "/x"},
                                         {"agent": "windsurf", "path": "/y"}]}
        assert store.preserved_agent_scope(None, existing) == ["cursor", "windsurf"]

    def test_a_materialization_row_with_no_agent_is_dropped(self):
        existing = {"materializations": [{"agent": "cursor"}, {"path": "/y"}]}
        assert store.preserved_agent_scope(None, existing) == ["cursor"]

    def test_an_empty_record_means_every_agent_not_no_agent(self):
        # Nothing was linked last time (no agents enabled, or all conflicted).
        # Reading that as "link nowhere" would strand the skill forever.
        assert store.preserved_agent_scope(None, {"agents": []}) is None
        assert store.preserved_agent_scope(None, {"materializations": []}) is None
        assert store.preserved_agent_scope(
            None, {"materializations": [{"path": "/y"}]}) is None

    def test_agents_is_preferred_over_materializations(self):
        # A project skill records both; `agents` is the complete list (it
        # carries forward agents an earlier filtered install left untouched).
        existing = {"agents": ["claude-code", "cursor"],
                    "materializations": [{"agent": "cursor"}]}
        assert store.preserved_agent_scope(None, existing) == \
            ["claude-code", "cursor"]


class TestReinstallKeepsAgentScope:
    """End-to-end of the same rule, through the real install paths."""

    def test_a_forced_skill_reinstall_does_not_relink_everywhere(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        res = store.install(entry, force=True)          # what `update` does
        assert res.linked == ["claude-code"]
        assert lockfile.get_skill("brainstorming")["agents"] == ["claude-code"]
        assert _link("claude-code").is_symlink()
        assert not _link("windsurf").exists()
        assert not _link("cursor").exists()
        assert not _link("gemini").exists()

    def test_a_forced_reinstall_can_still_widen_on_request(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        res = store.install(entry, force=True,
                            only_agents=["claude-code", "cursor"])
        assert res.linked == ["claude-code", "cursor"]
        assert _link("cursor").is_symlink()
        assert not _link("windsurf").exists()
        assert not _link("gemini").exists()

    def test_an_unnarrowed_skill_still_reinstalls_everywhere(self, tap, entry):
        store.install(entry)
        res = store.install(entry, force=True)
        assert res.linked == LINKED_AGENTS
        assert res.native == ["gemini"]

    def test_install_from_path_keeps_the_scope_too(self, tap, entry, tmp_path):
        # `boost reinstall` on a local skill goes through install_from_path.
        store.install(entry, only_agents=["cursor"])
        src = tmp_path / "brainstorming"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: brainstorming\nversion: 9.9.9\n---\nhi\n", encoding="utf-8")
        res = store.install_from_path(src, name="brainstorming", force=True)
        assert res.linked == ["cursor"]
        assert lockfile.get_skill("brainstorming")["agents"] == ["cursor"]
        assert not _link("claude-code").exists()

    def test_a_forced_rule_reinstall_keeps_its_materializations(self, tap):
        rule = _rule_entry(tap)
        store.install(rule, only_agents=["cursor"])
        res = store.install(rule, force=True)
        assert res.linked == ["cursor"]
        assert [m["agent"] for m in
                lockfile.get_rule("team-conventions")["materializations"]] == ["cursor"]
        assert not (paths.home() / "CLAUDE.md").exists()
        assert not (paths.home() / ".gemini" / "GEMINI.md").exists()
        assert not (paths.home() / ".windsurf" / "rules"
                    / "team-conventions.mdc").exists()

    def test_a_forced_workflow_reinstall_keeps_its_drops(self, tap):
        wf = _workflow_entry(tap)
        store.install(wf, only_agents=["claude-code"])
        res = store.install(wf, force=True)
        assert res.linked == ["claude-code"]
        assert not (paths.home() / ".cursor" / "commands" / "ship-it.md").exists()
        assert not (paths.home() / ".gemini" / "commands" / "ship-it.toml").exists()

    def test_a_forced_project_reinstall_keeps_its_agent_dirs(self, entry, tmp_path):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        store.install(entry, scope="project", base=str(repo),
                      only_agents=["cursor"])
        res = store.install(entry, scope="project", base=str(repo), force=True)
        assert res.linked == ["cursor"]
        assert not (repo / ".claude" / "skills" / "brainstorming").exists()


class TestDeclaredAgentScope:
    """What the lock RECORDS as the requested scope.

    Distinct from `preserved_agent_scope`, which answers "what should this
    install link into". Conflating them is the bug: `agents` records what is
    linked right now, so promoting it to a declared scope would freeze a skill
    out of every agent enabled later.
    """

    def test_an_explicit_narrowing_is_recorded(self):
        assert store.declared_agent_scope(["cursor"], None) == ["cursor"]

    def test_a_never_narrowed_install_declares_nothing(self):
        assert store.declared_agent_scope(None, None) is None
        assert store.declared_agent_scope(None, {}) is None

    def test_the_linked_agents_list_is_not_promoted_to_a_declaration(self):
        # The whole point. This entry was installed unnarrowed and happens to
        # be linked into one agent; that must not become "only ever cursor".
        assert store.declared_agent_scope(None, {"agents": ["cursor"]}) is None

    def test_an_earlier_declaration_survives_update(self):
        # update/reinstall pass only_agents=None; the request must persist.
        assert store.declared_agent_scope(
            None, {"agents": ["cursor"], "only_agents": ["cursor"]}) == ["cursor"]

    def test_a_re_narrowing_replaces_the_old_declaration(self):
        assert store.declared_agent_scope(
            ["windsurf"], {"only_agents": ["cursor"]}) == ["windsurf"]

    def test_the_declaration_is_copied_not_aliased(self):
        # The caller's list must not become the lock's mutable state.
        asked = ["cursor"]
        got = store.declared_agent_scope(asked, None)
        asked.append("windsurf")
        assert got == ["cursor"]


class TestScopedAgents:
    ENABLED: ClassVar[dict] = {"claude-code": Path("/a"), "cursor": Path("/b")}

    def test_no_declaration_means_every_enabled_agent(self):
        assert store.scoped_agents({}, self.ENABLED) == self.ENABLED

    def test_a_declaration_filters_to_it(self):
        assert store.scoped_agents({"only_agents": ["cursor"]}, self.ENABLED) \
            == {"cursor": Path("/b")}

    def test_an_empty_declaration_fails_open(self):
        # Every entry written before this field existed reads as [] or absent.
        # Reading that as "link nowhere" would strand every existing install.
        assert store.scoped_agents({"only_agents": []}, self.ENABLED) == self.ENABLED

    def test_a_declared_agent_that_is_not_enabled_is_not_invented(self):
        assert store.scoped_agents(
            {"only_agents": ["cursor", "zed"]}, self.ENABLED) == {"cursor": Path("/b")}

    def test_the_enabled_mapping_is_not_mutated(self):
        enabled = dict(self.ENABLED)
        store.scoped_agents({"only_agents": ["cursor"]}, enabled)
        assert enabled == self.ENABLED


class TestSyncRespectsDeclaredScope:
    """`boost sync` was a second, independent path to the scope leak.

    `preserved_agent_scope` (PR #288) closed the install side. sync_plan walked
    every enabled agent regardless, reported a missing_link for each one outside
    the narrowing, and sync_apply linked them — so a single `boost sync` undid
    what `install --agent` asked for.
    """

    def test_sync_does_not_report_links_outside_the_declared_scope(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        assert store.sync_plan()["missing_links"] == []

    def test_sync_does_not_relink_a_narrowed_skill(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        store.sync_apply(store.sync_plan())
        assert _link("claude-code").is_symlink()
        for agent in ("windsurf", "cursor", "gemini"):
            assert not _link(agent).exists(), agent

    def test_a_dropped_link_inside_the_scope_is_still_repaired(self, tap, entry):
        # Narrowing must not turn sync off for the agents it does cover.
        store.install(entry, only_agents=["claude-code"])
        _link("claude-code").unlink()
        assert store.sync_plan()["missing_links"] == [("brainstorming", "claude-code")]
        store.sync_apply(store.sync_plan())
        assert _link("claude-code").is_symlink()

    def test_an_unnarrowed_skill_still_reaches_a_newly_enabled_agent(self,
                                                                     brainstorming):
        # sync's other job. An entry with no declaration must keep fanning out,
        # which is why scoped_agents fails open rather than closed.
        _link("cursor").unlink()
        assert store.sync_plan()["missing_links"] == [("brainstorming", "cursor")]

    def test_a_pre_existing_lock_entry_is_unaffected(self, brainstorming):
        # Locks written before `only_agents` existed have no such key at all.
        e = lockfile.get_skill("brainstorming")
        assert "only_agents" in e          # new installs record it (as None)
        del e["only_agents"]
        lockfile.set_skill("brainstorming", e)
        for agent in LINKED_AGENTS:
            _link(agent).unlink()
        assert sorted(store.sync_plan()["missing_links"]) == [
            ("brainstorming", "claude-code"), ("brainstorming", "cursor"),
            ("brainstorming", "windsurf")]

    def test_the_declaration_is_written_to_the_lock(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        assert lockfile.get_skill("brainstorming")["only_agents"] == ["claude-code"]

    def test_an_unnarrowed_install_records_no_declaration(self, brainstorming):
        assert lockfile.get_skill("brainstorming")["only_agents"] is None

    def test_a_forced_reinstall_keeps_the_declaration(self, tap, entry):
        store.install(entry, only_agents=["claude-code"])
        store.install(entry, force=True)
        assert lockfile.get_skill("brainstorming")["only_agents"] == ["claude-code"]
        assert store.sync_plan()["missing_links"] == []

    def test_import_from_path_records_its_narrowing(self, sandbox, tmp_path):
        # `boost import --agent ...` is a second entry point to the same lock
        # entry. Narrow links plus no declaration is the worst combination:
        # sync sees no scope and widens them straight back.
        src = tmp_path / "mine"
        src.mkdir()
        (src / "SKILL.md").write_text(
            "---\nname: mine\ndescription: d\nversion: 1.0.0\n---\nbody\n",
            encoding="utf-8")
        store.install_from_path(src, only_agents=["claude-code"])
        assert lockfile.get_skill("mine")["only_agents"] == ["claude-code"]
        assert store.sync_plan()["missing_links"] == []
