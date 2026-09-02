# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `_drift_hint`'s source-missing branch.

`boost update` only refreshes configured taps, so hinting it for a skill
whose tap was untapped is a guaranteed no-op — the CLI audit's repro. Pinned
directly against `registry.is_tapped` (monkeypatched) rather than through a
full `boost drift` run, because reaching "source-missing while still tapped"
end-to-end would require a tap whose clone cannot be silently re-fetched,
which `store.source_dir_for` does for anything with a reachable URL.
"""
from __future__ import annotations

from boost_cli.commands import quality


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
