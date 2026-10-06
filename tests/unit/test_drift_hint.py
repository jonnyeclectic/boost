# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `_drift_hint`'s branches, and the drift vocabulary itself.

`boost update` only refreshes configured taps, so hinting it for a skill
whose tap was untapped is a guaranteed no-op — the CLI audit's repro. Pinned
directly against `registry.is_tapped` (monkeypatched) rather than through a
full `boost drift` run, because reaching "source-missing while still tapped"
end-to-end would require a tap whose clone cannot be silently re-fetched,
which `store.source_dir_for` does for anything with a reachable URL.
"""
from __future__ import annotations

from typing import ClassVar

from boost_cli.commands import quality
from boost_cli.core import integrity
from boost_cli.core import output as out


class TestDriftHintSourceMissing:
    def test_untapped_hints_retap(self, monkeypatch):
        monkeypatch.setattr(quality.registry, "is_tapped", lambda name: False)
        assert (quality._drift_hint("brainstorming", "source-missing",
                                    "owner/repo")
                == "boost tap owner/repo")

    def test_still_tapped_hints_update(self, monkeypatch):
        monkeypatch.setattr(quality.registry, "is_tapped", lambda name: True)
        assert (quality._drift_hint("brainstorming", "source-missing",
                                    "owner/repo")
                == "boost update")


class TestDriftHintOtherStatuses:
    """Untouched by this fix — pinned so the source-missing branch can't
    leak into a neighboring status."""

    def test_quarantined(self):
        assert (quality._drift_hint("x", "quarantined")
                == "boost quarantine --release x to restore")

    def test_upstream_moved(self):
        assert quality._drift_hint("x", "upstream-moved") == "boost update"

    def test_local_edits(self):
        assert (quality._drift_hint("x", "local-edits")
                == "boost reinstall x to discard local edits")

    def test_store_missing(self):
        assert quality._drift_hint("x", "store-missing") == "boost heal"

    def test_in_sync_has_no_hint(self):
        assert quality._drift_hint("x", "in-sync") == ""

    def test_defaults_to_empty_tap(self):
        # `_drift_hint` is called with no explicit tap outside source-missing,
        # so the default must not raise even though it is never dereferenced.
        assert quality._drift_hint("x", "n/a") == ""

    def test_unreachable_hints_doctor_and_never_sync(self):
        """`boost sync` filters an unwritten row out by design, so hinting it
        here would be a guaranteed no-op -- the same fault the whole
        source-missing branch above exists to avoid. And "re-enable the
        agent" is wrong advice for `agents.WITHDRAWN_REASONS`, so the hint
        points at the one command that words the split correctly."""
        hint = quality._drift_hint("x", "unreachable")
        assert hint == "boost doctor"
        assert "sync" not in hint


class TestDriftVocabularyIsCovered:
    """`_DRIFT_ROLE` is subscripted directly at the render site.

    `cmd_drift` builds its table with `_DRIFT_ROLE[r["status"]]`, so a word
    the status functions can return and this table does not carry is a
    `KeyError` -- not a `BoostError`, so it escapes the CLI's handler and
    `boost drift` exits 70 with a crash report rather than mis-painting one
    cell. Unlike the historical `_PROVENANCE_STYLE` bug it is not masked by
    `NO_COLOR`: the lookup happens before `out.role` can short-circuit. The
    suite only catches that on a test that reaches the state, so the two
    tables are linted against each other here instead.
    """

    #: Every word `_drift_status_materialized` and `_drift_status` can return.
    #: `staleness.drift_state` owns the skill half.
    WORDS: ClassVar[set[str]] = {
        "in-sync", "local-edits", "upstream-moved", "source-missing",
        "store-missing", "n/a", "quarantined", "unreachable"}

    def test_every_drift_word_has_a_role(self):
        assert set(quality._DRIFT_ROLE) >= self.WORDS

    def test_every_role_is_a_real_palette_entry(self):
        """`out.role` looks the name up in `output.ROLES`; a name that is not
        there raised KeyError on any colour terminal, which is exactly how
        the `_PROVENANCE_STYLE` "err" bug shipped."""
        assert set(quality._DRIFT_ROLE.values()) <= set(out.ROLES)

    def test_the_materialized_statuses_each_map_to_a_word(self):
        """The three integrity statuses `_drift_status_materialized`
        translates must each land on a word this table carries, so a new
        status cannot reach the render site unmapped."""
        for st in (integrity.STATUS_MISSING, integrity.STATUS_MODIFIED,
                   integrity.STATUS_UNREACHABLE):
            assert quality._DRIFT_ROLE[_STATUS_WORD[st]]


#: How `_drift_status_materialized` spells each integrity status.
_STATUS_WORD = {
    integrity.STATUS_MISSING: "store-missing",
    integrity.STATUS_MODIFIED: "local-edits",
    integrity.STATUS_UNREACHABLE: "unreachable",
}

