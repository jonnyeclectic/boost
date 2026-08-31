# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `garrytan/gstack` in the catalogue, and beside boost on disk.

gstack is the largest thing in boost's domain — 130k stars — and it ships
roughly three dozen `<name>/SKILL.md` directories at its repo root, which is
exactly the layout `catalog.scan_dir` already indexes. So the catalogue fit is
free. The *install* fit is not, and the coexistence fit is the part that is
actually about boost: at that size gstack is now the likeliest other tenant in
the dotdirs boost writes to, and every hazard below is a place where boost
sweeping "its own" leftovers could take someone else's working install with it.

Three things are pinned here, in the order they bite:

1. **The row is measured.** gstack's repo description advertises "23
   opinionated tools" and its README lists ~35 slash commands;
   `scripts/measure_registry.py` counts **61** distinct items. That spread is
   precisely why `est_items` is defined as measured rather than quoted.

2. **boost refuses to half-install it.** A gstack skill is a thin Markdown
   entry point over a build step — `./setup` renders per-host variants and
   `/browse`/`/qa` drive a real Chromium behind Bun. Copying the Markdown
   yields a skill that looks installed and cannot run, so `store.install`
   refuses and names the upstream command instead.

3. **Neither installer may sweep the other's files.** gstack installs a *real
   directory* at `~/.claude/skills/gstack` (verified in its README, not
   assumed) and registers its own Stop hooks in the same
   `~/.claude/settings.json` boost writes. boost's ownership tests are
   `is_symlink()` for files and the `# boost:` command marker for hooks; both
   already exclude gstack, and these tests are what keep it that way. The cost
   of being wrong is a user's install or hooks silently disappearing, which is
   not a failure any later test would attribute to this change.
"""
from __future__ import annotations

import json
from typing import ClassVar

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import config, paths, store
from boost_cli.errors import BoostError

GSTACK = "garrytan/gstack"

# Measured with `python3 scripts/measure_registry.py <clone>` over a sparse
# clone of 07b59e39 (2026-08-30). The two numbers it is not:
ADVERTISED_IN_DESCRIPTION = 23
ADVERTISED_IN_README = 35
MEASURED = 61


@pytest.fixture(scope="module")
def row():
    hit = [e for e in config.load_registry_catalog() if e["name"] == GSTACK]
    assert hit, "%s dropped out of the shipped catalog" % GSTACK
    return hit[0]


class TestTheRowIsMeasured:
    def test_it_is_carried_as_a_scannable_skill_registry(self, row):
        # scan_dir classifies all 61 as `skill` (they are <name>/SKILL.md), and
        # the repo ships them rather than linking out, so it is not list_only.
        assert row["type"] == "skill"
        assert not row["list_only"]

    def test_category_comes_from_the_item_names(self, row):
        # `ship`, `qa`, `review`, `plan-*`, `retro`, `office-hours`, `freeze`:
        # sprint-workflow roles. Filing it `meta` would read the README (which
        # looks like an index) instead of the items, the trap TestDesignDomain
        # pins in the other direction.
        assert row["category"] == "workflow"

    def test_est_items_is_the_measurement_not_either_advertised_number(self, row):
        assert row["est_items"] == MEASURED, (
            "est_items %d is not the measured %d — re-run "
            "scripts/measure_registry.py" % (row["est_items"], MEASURED))
        assert row["est_items"] not in (ADVERTISED_IN_DESCRIPTION,
                                        ADVERTISED_IN_README)

    def test_focus_does_not_quote_an_advertised_count(self, row):
        # Same rule as TestEfficiencyDomain: the catalogue must not repeat a
        # headline number that its own measurement contradicts.
        for n in (ADVERTISED_IN_DESCRIPTION, ADVERTISED_IN_README):
            assert str(n) not in row["focus"], row["focus"]


class TestBoostRefusesToHalfInstallIt:
    def test_the_row_carries_the_upstream_installer(self, row):
        assert "./setup" in row["self_installing"]
        assert "garrytan/gstack" in row["self_installing"]

    def test_only_marked_repos_carry_the_field(self):
        # The marker is opt-in per repo; emitting a null on all ~487 rows would
        # rewrite the generated file to say nothing about any of them.
        marked = [e["name"] for e in config.load_registry_catalog()
                  if e.get("self_installing")]
        assert marked == [GSTACK], marked

    @pytest.mark.parametrize("tap", [GSTACK, "gstack"])
    def test_the_tap_resolves_by_full_name_or_bare_clone_dir(self, tap):
        assert config.self_installing_command(tap)

    @pytest.mark.parametrize("tap", ["", "obra/superpowers", "gstack-other"])
    def test_an_ordinary_tap_is_not_refused(self, tap):
        assert config.self_installing_command(tap) is None

    @pytest.mark.parametrize("kind", ["skill", "rule", "workflow"])
    def test_install_refuses_every_kind_it_ships(self, sandbox, kind):
        # The property belongs to the repo, not the item, so the guard runs
        # before the kind dispatch — a rule from a self-installing repo is no
        # more installable than a skill from it.
        entry = {"name": "review", "kind": kind, "tap": GSTACK}
        with pytest.raises(BoostError) as exc:
            store.install(entry)
        assert "installs itself" in str(exc.value)

    def test_the_refusal_names_the_command_to_run_instead(self, sandbox):
        entry = {"name": "review", "kind": "skill", "tap": GSTACK}
        with pytest.raises(BoostError) as exc:
            store.install(entry)
        # A refusal that only says "no" leaves the user where pretending would.
        assert "./setup" in str(getattr(exc.value, "hint", "") or exc.value)

    def test_it_refuses_before_writing_anything(self, sandbox):
        entry = {"name": "review", "kind": "skill", "tap": GSTACK}
        with pytest.raises(BoostError):
            store.install(entry)
        assert not (paths.store_dir() / "review").exists()


class TestNeitherInstallerSweepsTheOther:
    """gstack's files are real; boost's are symlinks. That is the whole test."""

    def test_a_real_gstack_dir_in_an_agent_skills_dir_is_not_a_stale_link(
            self, sandbox):
        # The verified shape: `git clone … ~/.claude/skills/gstack && ./setup`.
        # boost's stale-link sweep asks `is_symlink()` first, so a real
        # directory is never a candidate — but nothing said so out loud, and
        # this is an 8 MB working install of someone else's program.
        d = paths.home() / ".claude" / "skills" / "gstack"
        (d / "review").mkdir(parents=True)
        (d / "review" / "SKILL.md").write_text(
            "---\nname: review\n---\n", encoding="utf-8")
        plan = store.sync_plan()
        flat = json.dumps(plan, default=str)
        assert "gstack" not in flat, plan
        assert d.is_dir() and (d / "review" / "SKILL.md").exists()

    def test_a_real_gstack_dir_is_never_a_duplicate_discovery(self, sandbox):
        # Same claim for the native-store agent's dir, which `heal
        # --prune-duplicates` acts on. Topology, not ownership — and a real
        # directory has no topology into the store to begin with.
        d = paths.home() / ".gemini" / "skills" / "gstack"
        d.mkdir(parents=True)
        assert store.duplicate_discovery() == []

    def test_remove_duplicate_discovery_refuses_a_real_directory(self, sandbox):
        # Re-gated at the point of deletion, so even a stale report cannot
        # turn into an rmtree of a real directory.
        d = paths.home() / ".gemini" / "skills" / "gstack"
        d.mkdir(parents=True)
        dup = store.DuplicateDiscovery(
            agent="gemini", name="gstack", path=d, target=paths.store_dir())
        assert store.remove_duplicate_discovery(dup) is False
        assert d.is_dir()


class TestOneSettingsFileTwoWriters:
    """`./setup` registers gstack's own Stop hooks in `~/.claude/settings.json`.

    Each installer prunes "its own" entries — gstack by a `--source` name it
    stamps, boost by the `# boost:` command marker. The namespaces *look*
    disjoint and the claim was never tested. It is tested now, in both
    directions and in the arrangement that is easiest to get wrong: both
    writers' hooks inside a single event block, where boost's `_strip` rebuilds
    the inner list.
    """

    # The shape gstack's ./setup writes (README: gstack-verify-gate is opt-in
    # on Stop; the timeline hook is default-on).
    THEIRS: ClassVar[dict] = {
        "type": "command",
        "command": "~/.claude/skills/gstack/bin/gstack-timeline-stop",
        "timeout": 10}

    def test_boosts_remove_leaves_a_foreign_hook_in_the_same_block(self, sandbox):
        cs.save("global", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}})
        cs.add_hook("global", "Stop", "bmad", "boost bmad orient")
        assert cs.remove_hook("global", "Stop", "bmad") == 1
        survivors = [h for b in cs.load("global")["hooks"]["Stop"]
                     for h in b["hooks"]]
        assert survivors == [self.THEIRS]

    def test_boost_never_claims_a_gstack_hook_as_its_own(self, sandbox):
        # Ownership is the trailing `# boost:<name>` marker. gstack's command
        # carries none, so it can never be matched by name — including by the
        # empty name a naive split would produce.
        cs.save("global", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}})
        assert cs.list_hooks("global") == []
        for name in ("gstack-timeline-stop", "", "gstack"):
            assert cs.remove_hook("global", "Stop", name) == 0
        assert cs.load("global")["hooks"]["Stop"][0]["hooks"] == [self.THEIRS]

    def test_a_foreign_block_survives_boost_adding_and_removing_its_own(
            self, sandbox):
        # The round trip ./setup and `boost hooks` would really interleave.
        theirs = {"matcher": "*", "hooks": [dict(self.THEIRS)]}
        cs.save("global", {"hooks": {"Stop": [theirs]}, "model": "opus"})
        cs.add_hook("global", "Stop", "guard", "boost guard")
        cs.remove_hook("global", "Stop", "guard")
        data = cs.load("global")
        assert data["model"] == "opus"
        assert data["hooks"]["Stop"] == [theirs]


class TestDoctorCanSeeTheOtherTenantWithoutTouchingIt:
    """`list_hooks` skips everything unmarked, so boost could write this file
    for years and never be able to say who else writes it. `foreign_hooks` is
    the complement — read-only, and reported by `boost doctor` as information
    rather than as an issue, because boost will never fix it and a health check
    that stays permanently red on something no command can clear stops being
    read."""

    THEIRS: ClassVar[dict] = {
        "type": "command",
        "command": "~/.claude/skills/gstack/bin/gstack-timeline-stop"}

    def test_a_foreign_hook_is_visible(self, sandbox):
        cs.save("global", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}})
        # The whole row, not a field or two: doctor groups by `event` and a
        # reader chasing the hook needs `scope` and `matcher` to find it, so a
        # row that silently loses one is a row that cannot be acted on.
        assert cs.foreign_hooks("global") == [{
            "scope": "global",
            "event": "Stop",
            "command": self.THEIRS["command"],
            "matcher": "*",
        }]

    def test_a_block_with_no_matcher_still_reports_one(self, sandbox):
        # `matcher` is optional in the file; the key must still be present in
        # the row, or a caller formatting it raises KeyError on real settings.
        cs.save("global", {"hooks": {"Stop": [
            {"hooks": [dict(self.THEIRS)]}]}})
        assert cs.foreign_hooks("global")[0]["matcher"] == ""

    def test_both_scopes_are_searched_when_none_is_named(self, sandbox, tmp_path):
        # An unscoped call must cover every scope, or a project-scoped foreign
        # hook is invisible to the doctor line that exists to surface it.
        cs.save("project", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}},
            project_dir=tmp_path)
        rows = cs.foreign_hooks(project_dir=tmp_path)
        assert [r["scope"] for r in rows] == ["project"]

    def test_boosts_own_hooks_are_not_reported_as_foreign(self, sandbox):
        cs.add_hook("global", "Stop", "bmad", "boost bmad orient")
        assert cs.foreign_hooks("global") == []

    def test_the_two_views_partition_the_file(self, sandbox):
        # Every hook is exactly one of ours or theirs — no entry may be
        # invisible to both, which is how a second writer goes unnoticed.
        cs.save("global", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}})
        cs.add_hook("global", "Stop", "bmad", "boost bmad orient")
        total = sum(len(b["hooks"])
                    for b in cs.load("global")["hooks"]["Stop"])
        assert len(cs.list_hooks("global")) + len(cs.foreign_hooks("global")) \
            == total

    def test_reading_never_writes(self, sandbox):
        cs.save("global", {"hooks": {"Stop": [
            {"matcher": "*", "hooks": [dict(self.THEIRS)]}]}})
        before = cs.settings_path("global").read_text(encoding="utf-8")
        cs.foreign_hooks("global")
        assert cs.settings_path("global").read_text(encoding="utf-8") == before

    def test_a_missing_settings_file_reports_nothing(self, sandbox):
        assert cs.foreign_hooks("global") == []
