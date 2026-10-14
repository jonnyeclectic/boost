# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost sync` must not report success for a link it could not create.

Observed on a real machine, as a closed loop:

    $ boost sync
      ✓ everything in sync
    $ boost doctor
      ! skill hyperframes not linked for claude-code — run `boost sync`

``~/.claude/skills/hyperframes`` was a real directory (another installer put it
there), so :func:`store.link_agents` correctly refused to clobber it and
recorded a *conflict*. :func:`store.sync_apply` then dropped ``res.conflicts``
on the floor, appended no action, and the command layer read "no actions" as
"nothing to do". Doctor kept prescribing the command that could never work.

store.py's own comment at ``sync_plan`` names this anti-pattern: "sync would
answer 'everything in sync', change nothing, and send the reader back to the
same error."
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from boost_cli.core import agents, catalog, lockfile, paths, registry, store, util

#: chmod cannot take the owner's own write access away on Windows, and root
#: writes through any mode.
posix_modes = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permission bits, as a user other than root")


def _agent_path(agent, name="brainstorming"):
    """Ask the code where the link goes instead of restating the layout.

    This used to build the path from a local ``{agent: dotdir}`` table copied
    out of test_store.py. That is a second source of truth for a mapping
    core/agents.py already owns, and it cost all three Windows jobs: the table
    produced a path that named the same directory as the one ``sync_plan``
    records but did not spell it the same way, so every assertion comparing the
    two as strings failed on Windows and passed everywhere else.
    """
    return agents.linking_agents()[agent] / name


@pytest.fixture()
def brainstorming(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    entry = catalog.resolve_one("brainstorming")
    store.install(entry)
    return entry


class TestBlockedLinks:
    def test_a_foreign_directory_is_reported_as_blocked_not_missing(self, brainstorming):
        link = _agent_path("claude-code")
        link.unlink()
        link.mkdir()                      # a foreign real dir, as HyperFrames leaves
        plan = store.sync_plan()
        assert ("brainstorming", "claude-code") not in plan["missing_links"], (
            "sync cannot create this link, so calling it merely 'missing' is what "
            "made `boost sync` promise a repair it never performs")
        assert any(n == "brainstorming" and a == "claude-code"
                   for n, a, *_ in plan["blocked_links"])

    def test_blocked_link_names_the_path_in_the_way(self, brainstorming):
        link = _agent_path("claude-code")
        link.unlink()
        link.mkdir()
        blocked = store.sync_plan()["blocked_links"]
        # Compare the paths as paths, not as strings. Two spellings of one
        # location are equal here and unequal to `in`, which is what made this
        # the only assertion in the file that Windows failed.
        assert any(Path(p).resolve() == link.resolve() for _, _, p in blocked), (
            "the warning has to name the path that is in the way, or the reader "
            "has nothing to move")

    def test_a_genuinely_absent_link_is_still_missing(self, brainstorming):
        # The ordinary case must keep working: nothing in the way, sync fixes it.
        _agent_path("windsurf").unlink()
        plan = store.sync_plan()
        assert ("brainstorming", "windsurf") in plan["missing_links"]
        assert plan["blocked_links"] == []

    def test_a_dangling_boost_symlink_is_missing_not_blocked(self, brainstorming):
        # boost owns this link, so it may replace it — that is a repair, not a
        # conflict.
        link = _agent_path("windsurf")
        target = link.resolve()
        link.unlink()
        link.symlink_to(target.parent / "gone")
        plan = store.sync_plan()
        assert ("brainstorming", "windsurf") in plan["missing_links"]
        assert plan["blocked_links"] == []

    def test_sync_apply_does_not_claim_to_have_linked_a_blocked_path(self, brainstorming):
        link = _agent_path("claude-code")
        link.unlink()
        link.mkdir()
        actions = store.sync_apply(store.sync_plan())
        assert not any("linked brainstorming" in a for a in actions)


class TestBlockedLinkWithMissingStore:
    """The residual case of the fix above: the store copy is ALSO gone.

    Observed for real, as a closed loop across three commands: with the store
    dir deleted and a foreign directory sitting at
    ``~/.windsurf/skills/brainstorming``, ``sync --diff`` named only the
    missing store and said nothing about windsurf; the live ``sync`` then
    "repaired" it — reinstalling the store, relinking every agent it could —
    with no mention of windsurf either; only a *second* ``sync`` finally
    reported the blocked link. ``sync_plan`` used to ``continue`` the moment it
    classified an entry as ``missing_store``, skipping the agent-link
    classification below entirely — even though that classification reads only
    the agent directory, never the store, so it never needed the store dir to
    exist in the first place.
    """

    def test_missing_store_and_blocked_link_appear_in_the_same_plan(
            self, brainstorming):
        link = _agent_path("windsurf")
        link.unlink()
        link.mkdir()                      # a foreign real dir, as before
        util.rmtree(store.skill_store_dir("brainstorming"))

        plan = store.sync_plan()

        assert "brainstorming" in plan["missing_store"]
        assert any(n == "brainstorming" and a == "windsurf"
                   for n, a, *_ in plan["blocked_links"]), (
            "a foreign file blocking a link must be reported the same run "
            "the store copy is found missing, not held back for a second "
            "`sync` to discover")
        assert ("brainstorming", "windsurf") not in plan["missing_links"]

    def test_the_other_agents_still_repair_in_one_pass(self, brainstorming):
        # Only windsurf is blocked; claude-code, cursor and antigravity's
        # links are merely dangling (their target just vanished) and must
        # still come back once the store is restored — the fix must not cost
        # the ordinary repair to catch the blocked one.
        link = _agent_path("windsurf")
        link.unlink()
        link.mkdir()
        util.rmtree(store.skill_store_dir("brainstorming"))

        actions = store.sync_apply(store.sync_plan())

        assert any("reinstalled missing brainstorming" in a for a in actions)
        assert _agent_path("claude-code").is_symlink()
        assert _agent_path("claude-code").exists()
        # windsurf stays blocked — sync never deletes a file it does not own.
        assert _agent_path("windsurf").is_dir()
        assert not _agent_path("windsurf").is_symlink()

    def test_a_healthy_missing_store_repair_is_unaffected(self, brainstorming):
        # No blocked link at all: the classic case from PR #515 must keep
        # working exactly as before — a missing-store entry's own agents
        # never enter `missing_links` (the reinstall in `sync_apply` relinks
        # them as one step), and none of them are blocked either.
        util.rmtree(store.skill_store_dir("brainstorming"))
        plan = store.sync_plan()
        assert "brainstorming" in plan["missing_store"]
        assert plan["blocked_links"] == []
        for agent in ("claude-code", "cursor", "windsurf"):
            assert ("brainstorming", agent) not in plan["missing_links"]


class TestDoctorNamesAReachableRemedy:
    def test_doctor_does_not_prescribe_sync_for_a_blocked_link(self, brainstorming, capsys):
        from boost_cli.commands import quality
        link = _agent_path("claude-code")
        link.unlink()
        link.mkdir()
        quality.cmd_doctor([])
        out = capsys.readouterr().out
        assert "brainstorming" in out
        line = next(x for x in out.splitlines() if "brainstorming" in x and "claude-code" in x)
        # `boost sync` may still appear — but only as the *second* step, after
        # the one that unblocks it. Naming sync alone is the dead end, because
        # the reader has just run it and nothing changed.
        assert "not a boost link" in line, (
            "the remedy has to say why sync did nothing, or it reads as the "
            "same advice that already failed")
        assert "move or delete" in line
        assert link.name in line

    def test_doctor_still_prescribes_sync_for_an_ordinary_missing_link(
            self, brainstorming, capsys):
        from boost_cli.commands import quality
        _agent_path("windsurf").unlink()
        quality.cmd_doctor([])
        out = capsys.readouterr().out
        line = next(x for x in out.splitlines()
                    if "brainstorming" in x and "windsurf" in x)
        assert "boost sync" in line


def _users_link(agent: str, target: Path) -> Path:
    """Put the user's own link where boost's ``agent`` link to brainstorming goes."""
    link = _agent_path(agent)
    link.unlink()
    link.symlink_to(target, target_is_directory=True)
    return link


def _leads_to(link: Path, target: Path) -> bool:
    return (store.normalize_link_target(link.readlink())
            == store.normalize_link_target(target))


@pytest.fixture()
def checkout(tmp_path):
    """The user's own copy of the skill, kept outside the store."""
    d = tmp_path / "code" / "brainstorming"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: brainstorming\n---\nmine\n",
                                encoding="utf-8")
    return d


class TestTheUsersOwnLink:
    """A symlink that does not lead into the store is the user's, dangling or not.

    Adoption said so ("in the way and is not boost's to replace"), and so did
    heal's broken-link sweep, while sync re-pointed one once it dangled and
    `--prune`, uninstall and sideline removed one that worked.
    """

    def test_a_dangling_one_is_blocked_not_repointed(self, brainstorming, tmp_path):
        # A checkout on a volume that is not mounted right now.
        gone = tmp_path / "vol" / "brainstorming"
        link = _users_link("claude-code", gone)
        plan = store.sync_plan()
        assert ("brainstorming", "claude-code") not in plan["missing_links"]
        assert ("brainstorming", "claude-code", str(link)) in plan["blocked_links"]
        store.sync_apply(plan)
        assert _leads_to(link, gone)

    def test_a_live_one_is_neither_missing_nor_blocked(self, brainstorming, checkout):
        link = _users_link("claude-code", checkout)
        plan = store.sync_plan()
        assert ("brainstorming", "claude-code") not in plan["missing_links"]
        assert not any(n == "brainstorming" and a == "claude-code"
                       for n, a, *_ in plan["blocked_links"])
        store.sync_apply(plan)
        assert _leads_to(link, checkout)

    def test_a_dangling_link_into_the_store_is_still_boosts(self, brainstorming):
        link = _agent_path("windsurf")
        link.unlink()
        link.symlink_to(paths.store_dir() / "gone")
        assert store.is_boost_link(link)
        assert not store.is_boost_link(_agent_path("cursor").with_name("absent"))

    def test_uninstall_leaves_it(self, brainstorming, checkout):
        link = _users_link("claude-code", checkout)
        res = store.uninstall("brainstorming")
        assert "claude-code" not in res["unlinked"]
        assert "windsurf" in res["unlinked"]
        assert _leads_to(link, checkout)
        assert not os.path.lexists(_agent_path("windsurf"))

    @posix_modes
    def test_in_a_dir_that_refuses_writes_it_does_not_stop_uninstall(
            self, brainstorming, checkout):
        # The pre-check refuses an uninstall that would stop halfway, and only
        # a link uninstall removes can stop it.
        link = _users_link("claude-code", checkout)
        link.parent.chmod(0o555)
        try:
            store.uninstall("brainstorming")
        finally:
            link.parent.chmod(0o755)
        assert _leads_to(link, checkout)
        assert lockfile.get_skill("brainstorming") is None

    def test_a_focus_and_its_clear_leave_it(self, brainstorming, checkout):
        link = _users_link("claude-code", checkout)
        assert "claude-code" not in store.sideline("brainstorming", "focus")
        assert _leads_to(link, checkout)
        assert not os.path.lexists(_agent_path("windsurf"))
        res = store.unsideline("brainstorming")
        assert _leads_to(link, checkout), "relinking replaced it with the store copy"
        assert str(link) in res.conflicts
        assert "claude-code" not in res.linked
        assert os.path.samefile(_agent_path("windsurf"),
                                store.skill_store_dir("brainstorming"))
        assert "claude-code" not in lockfile.get_skill("brainstorming")["agents"]

    def test_an_install_records_only_boosts_links(self, brainstorming, checkout):
        # What `agents` records is what uninstall removes.
        _users_link("claude-code", checkout)
        linked = store.linked_agents("brainstorming")
        assert "claude-code" not in linked
        assert "windsurf" in linked

    def test_outside_a_declared_scope_it_is_neither_reported_nor_pruned(
            self, brainstorming, checkout):
        entry = lockfile.get_skill("brainstorming")
        entry["only_agents"] = ["cursor"]
        lockfile.set_skill("brainstorming", entry)
        link = _users_link("claude-code", checkout)
        plan = store.sync_plan()
        assert ("brainstorming", "claude-code") not in plan["out_of_scope_links"]
        assert ("brainstorming", "windsurf") in plan["out_of_scope_links"]
        # Asked again at the unlink, whatever the plan says.
        removed = store.prune_out_of_scope_links({"out_of_scope_links": [
            ("brainstorming", "claude-code"), ("brainstorming", "windsurf")]})
        assert _leads_to(link, checkout)
        assert not os.path.lexists(_agent_path("windsurf"))
        assert not any("claude-code" in r for r in removed)

    def test_doctor_names_a_broken_one_and_what_to_do(self, brainstorming, capsys,
                                                      tmp_path):
        from boost_cli.commands import quality
        link = _users_link("claude-code", tmp_path / "vol" / "brainstorming")
        quality.cmd_doctor([])
        # Flattened, so a line folded to the pane still reads as one.
        text = " ".join(capsys.readouterr().out.split())
        assert ("skill brainstorming not linked for claude-code — %s is a broken "
                "link boost did not make; move or delete it" % paths.tilde(link)) in text

    def test_heal_names_a_broken_one_once_and_exits_1(self, brainstorming, capsys,
                                                      tmp_path):
        from boost_cli.commands import quality
        gone = tmp_path / "vol" / "brainstorming"
        link = _users_link("claude-code", gone)
        assert quality.cmd_heal([]) == 1
        cap = capsys.readouterr()
        text = " ".join((cap.out + cap.err).split())
        assert text.count(paths.tilde(link)) == 1, text
        assert "%s is in the way and is not boost's" % paths.tilde(link) in text
        assert "nothing to heal" not in text
        assert _leads_to(link, gone)
