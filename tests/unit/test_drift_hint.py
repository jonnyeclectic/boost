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



class TestRetapHint:
    """`registry.retap_hint` — the command that restores an untapped source.

    The tap's *name* is not a spec: a local tap is named after its directory's
    basename (`boost tap fix` cannot parse), and a GitLab tap is named
    `owner/repo`, which `parse_spec` resolves to GitHub. Only the recorded URL
    re-taps what was actually installed from.
    """

    def test_recorded_https_url_is_used_verbatim(self):
        assert (quality.registry.retap_hint(
            "acme/fix", "https://gitlab.example.com/acme/fix")
                == "boost tap https://gitlab.example.com/acme/fix")

    def test_recorded_local_path_is_used(self, tmp_path):
        src = tmp_path / "fix"
        hint = quality.registry.retap_hint("fix", str(src))
        assert hint == "boost tap %s" % str(src)

    def test_a_path_with_a_space_is_quoted_so_it_stays_one_argument(self):
        hint = quality.registry.retap_hint("fix", "/srv/my taps/fix")
        assert hint.startswith("boost tap ")
        arg = hint[len("boost tap "):]
        assert arg != "/srv/my taps/fix"
        assert arg[0] in "'\"" and arg[-1] == arg[0]
        assert "/srv/my taps/fix" in arg

    def test_windows_double_quotes_only_a_path_with_whitespace(self, monkeypatch):
        """cmd.exe and PowerShell do not take `shlex.quote`'s single quotes."""
        monkeypatch.setattr(quality.registry.sys, "platform", "win32")
        assert (quality.registry.retap_hint("fix", r"C:\my taps\fix")
                == 'boost tap "C:\\my taps\\fix"')
        assert (quality.registry.retap_hint("fix", r"C:\taps\fix")
                == r"boost tap C:\taps\fix")
        assert (quality.registry.retap_hint("fix", "C:\\my\ttab")
                == 'boost tap "C:\\my\ttab"')

    def test_legacy_entry_with_an_owner_repo_name_falls_back_to_it(self):
        assert quality.registry.retap_hint("owner/repo") == "boost tap owner/repo"
        assert quality.registry.retap_hint("owner/repo", "") == "boost tap owner/repo"

    def test_legacy_local_name_prints_no_command(self):
        hint = quality.registry.retap_hint("fix")
        assert "boost tap" not in hint
        assert "fix" in hint
        assert "not recorded" in hint

    def test_a_name_with_a_space_is_not_offered_as_a_spec(self):
        assert "boost tap" not in quality.registry.retap_hint("a b/c")

    def test_the_wheel_tap_is_never_offered_as_a_spec(self):
        hint = quality.registry.retap_hint("boost/builtin", "builtin:boost")
        assert "builtin:boost" not in hint
        assert "boost tap" not in hint


class TestDriftHintUsesRecordedSource:
    def test_untapped_local_tap_hints_its_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(quality.registry, "is_tapped", lambda name: False)
        src = str(tmp_path / "fix")
        assert (quality._drift_hint("brainstorming", "source-missing", "fix",
                                    tap_url=src)
                == "boost tap %s" % src)

    def test_untapped_gitlab_tap_hints_its_host(self, monkeypatch):
        monkeypatch.setattr(quality.registry, "is_tapped", lambda name: False)
        hint = quality._drift_hint("brainstorming", "source-missing", "acme/fix",
                                   tap_url="https://gitlab.example.com/acme/fix")
        assert hint == "boost tap https://gitlab.example.com/acme/fix"

    def test_still_tapped_ignores_the_url(self, monkeypatch):
        monkeypatch.setattr(quality.registry, "is_tapped", lambda name: True)
        assert (quality._drift_hint("x", "source-missing", "fix",
                                    tap_url="/somewhere/fix") == "boost update")


class TestDriftEndToEnd:
    def test_drift_after_untap_names_the_path_that_retaps(
            self, boost, fixture_tap_src, tmp_path):
        import json
        import shutil
        src = tmp_path / "drift-retap-src"
        shutil.copytree(fixture_tap_src, src)
        boost("tap", src)
        boost("install", "brainstorming")
        boost("untap", "drift-retap-src", "--force", expect=None)
        rows = json.loads(boost("drift", "--json").out)["skills"]
        row = next(r for r in rows if r["name"] == "brainstorming")
        assert row["status"] == "source-missing"
        assert row["hint"] == "boost tap %s" % str(src.resolve())
        # …and the hint actually runs.
        boost(*row["hint"].split(" ", 2)[1:])

    def test_a_narrow_pane_never_clips_the_hint_command(
            self, boost, fixture_tap_src, tmp_path, monkeypatch):
        """The hint is a command with an absolute path in it now; clipped to
        `boost tap /priv…` it is a command that does not run."""
        import shutil
        src = tmp_path / "drift-narrow-src"
        shutil.copytree(fixture_tap_src, src)
        boost("tap", src)
        boost("install", "brainstorming")
        boost("untap", "drift-narrow-src", "--force", expect=None)
        monkeypatch.setenv("COLUMNS", "60")
        text = boost("drift").out
        assert "source-missing" in text
        assert "…" not in text
        assert ("boost tap %s" % str(src.resolve())) in text
