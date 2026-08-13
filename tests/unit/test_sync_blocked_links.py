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

import pytest

from boost_cli.core import catalog, paths, registry, store

# Same layout table as tests/unit/test_store.py. Duplicated rather than
# imported: importing a test module for its fixtures makes pytest collect it
# twice under some rootdir layouts.
AGENT_DIRS = {"claude-code": ".claude", "windsurf": ".windsurf",
              "cursor": ".cursor", "gemini": ".gemini"}


def _agent_path(agent, name="brainstorming"):
    return paths.home() / AGENT_DIRS[agent] / "skills" / name


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
        assert any(str(link) in str(row) for row in blocked)

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
