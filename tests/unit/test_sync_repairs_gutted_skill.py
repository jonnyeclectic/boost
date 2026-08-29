# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: `boost sync` repairs a skill whose SKILL.md is gone, not just a missing dir.

Two commands tell the user that `boost sync` is the repair for a missing
``SKILL.md``::

    $ boost edit brainstorming
    Error: SKILL.md missing from ~/.agents/skills/brainstorming
      hint: repair the store with `boost sync`

    $ boost evolve brainstorming --feedback ...
    Error: brainstorming has no SKILL.md in the store
      hint: repair with `boost sync`

It was not. ``sync_plan`` classified a skill as ``missing_store`` only when its
**directory** was absent (``if not sdir.is_dir()``), so a directory that still
existed but had been emptied read as healthy. ``boost sync`` printed
``✓ everything in sync``, changed nothing, and the next ``boost edit`` produced
the identical error — advice that sends the reader round a loop they have
already completed. ``boost heal`` said ``nothing to heal`` too, and the only
command that actually repaired it, ``boost reinstall``, was named by neither
hint.

This is not a hypothetical state. An interrupted copy, a partial rsync, a
half-finished disk cleanup, or a user deleting the file to "start fresh" all
leave the directory in place.

The existing suite could not see it: the one test pinning that hint
(``tests/functional/test_cli_pkg.py``) removes the whole directory with
``shutil.rmtree``, which is the case ``sync`` already handled. Nothing deleted
only the file, so the file-level check in the two commands and the
directory-level check in ``sync`` were never compared.

Same shape as the `export_shard` bug fixed earlier this session: a remedy that
names the step the user has already taken.
"""
from __future__ import annotations

from boost_cli.core import store


def _gut(name: str) -> None:
    """Delete a skill's SKILL.md, leaving its store directory in place."""
    path = store.skill_store_dir(name) / "SKILL.md"
    assert path.exists(), "fixture did not install %s" % name
    path.unlink()


class TestSyncPlanSeesAGuttedSkill:
    def test_a_skill_with_no_skill_md_is_reported_as_missing(
            self, installed):
        _gut(installed)
        assert installed in store.sync_plan()["missing_store"]

    def test_the_directory_still_exists(self, installed):
        # The whole point: this is NOT the rmtree case the old check caught.
        _gut(installed)
        assert store.skill_store_dir(installed).is_dir()

    def test_a_healthy_skill_is_still_not_reported(self, installed):
        # The rejection must not widen — a working install stays absent from
        # the plan, or `sync` would reinstall everything on every run.
        assert installed not in store.sync_plan()["missing_store"]

    def test_a_wholly_missing_directory_is_still_reported(self, installed):
        # The case that already worked, kept so the fix cannot regress it.
        import shutil
        shutil.rmtree(store.skill_store_dir(installed))
        assert installed in store.sync_plan()["missing_store"]


class TestSyncActuallyRepairsIt:
    """A plan that names the problem but does not fix it is the same bug."""

    def test_sync_restores_the_file(self, installed):
        _gut(installed)

        store.sync_apply(store.sync_plan())

        assert (store.skill_store_dir(installed) / "SKILL.md").exists()

    def test_the_repaired_skill_leaves_the_plan_clean(self, installed):
        # The loop the user was stuck in: run the remedy, re-check, still broken.
        _gut(installed)
        store.sync_apply(store.sync_plan())
        assert installed not in store.sync_plan()["missing_store"]

    def test_the_restored_content_is_the_real_skill(self, installed):
        # Restoring an empty file would satisfy every assertion above and help
        # nobody — `boost edit` would open a blank document.
        before = (store.skill_store_dir(installed)
                  / "SKILL.md").read_text(encoding="utf-8")
        _gut(installed)
        store.sync_apply(store.sync_plan())
        after = (store.skill_store_dir(installed)
                 / "SKILL.md").read_text(encoding="utf-8")
        assert after.strip() and after == before
