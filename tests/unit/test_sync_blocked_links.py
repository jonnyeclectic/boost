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

from pathlib import Path

import pytest

from boost_cli.core import agents, catalog, registry, store, util


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
