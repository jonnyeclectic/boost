# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Nothing boost printed ever named an entry point.

Bare `boost` read no state at all, so its first screen was byte-for-byte
identical on a virgin machine and a working one — measured md5 a8da6daf on
both — and `quickstart` sat at line 80 of 103, in the same dim body type as
the other 80 commands. Meanwhile the command every newcomer-facing hint routes
to, `boost tap`, ended on its last `✓ tapped …` row and said nothing about
what to do next, while `install` — which a user only reaches after finding
their own way here — closes with a framed box.

These tests pin both halves, and the disappearance as well as the appearance:
a permanent banner would be noise for every user past their first minute,
which is the reason there wasn't one.
"""
import re

import pytest

from boost_cli import cli
from boost_cli.core import registry


def _plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestFirstRun:
    """`registry.first_run()` — the predicate both surfaces share."""

    def test_a_machine_with_no_taps_is_a_first_run(self, sandbox):
        assert registry.first_run() is True

    def test_one_tap_ends_it(self, boost, fixture_tap_src):
        boost("tap", fixture_tap_src)
        assert registry.first_run() is False

    def test_a_broken_config_is_not_a_crash(self, sandbox):
        # `list_taps` answers a malformed config as "no taps" rather than
        # raising, and a help screen must render on a machine whose
        # config.json someone hand-edited badly.
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_text("{ not json", encoding="utf-8")
        assert registry.first_run() is True


class TestHint:
    """The sentence names `quickstart`, and it names it once."""

    def test_it_names_quickstart_not_tap_defaults(self):
        # The two setup paths are not equivalent: quickstart pins each
        # registry to the commit its published vectors describe and can import
        # those vectors; `tap --defaults` does neither. README leads with
        # quickstart while ~15 source sites route to `tap --defaults`.
        assert "boost quickstart" in registry.FIRST_RUN_HINT
        assert "tap --defaults" not in registry.FIRST_RUN_HINT

    @pytest.mark.parametrize("cols", [40, 60, 80])
    def test_the_command_survives_a_narrow_pane(self, cols):
        # A backtick span is one atomic token for `out.wrap`: a `boost
        # quickstart` folded across two lines cannot be copy-pasted.
        from boost_cli.core import output as out
        lines = out.wrap(registry.FIRST_RUN_HINT, cols)
        assert any("`boost quickstart`" in line for line in lines), lines


class TestHelpScreen:
    """Bare `boost` adapts to the machine it is run on."""

    def test_a_virgin_machine_is_pointed_at_setup(self, sandbox, capsys):
        cli.print_help()
        assert "boost quickstart" in _plain(capsys.readouterr().out)

    def test_the_pointer_goes_away_once_there_is_a_tap(self, boost,
                                                       fixture_tap_src, capsys):
        boost("tap", fixture_tap_src)
        capsys.readouterr()
        cli.print_help()
        out_text = _plain(capsys.readouterr().out)
        assert "new here?" not in out_text

    def test_the_command_index_itself_is_unchanged(self, sandbox, capsys,
                                                   monkeypatch):
        """Only the pointer is added — every command row still prints."""
        cli.print_help()
        virgin = _plain(capsys.readouterr().out)
        monkeypatch.setattr(registry, "first_run", lambda: False)
        cli.print_help()
        settled = _plain(capsys.readouterr().out)
        assert "%d commands" % len(cli.COMMANDS) in settled
        assert "new here?" not in settled
        # Exactly the pointer, and nothing else: one blank line and the
        # sentence. A test has no pane, so the hint is never wrapped here.
        assert virgin.replace("\n" + registry.FIRST_RUN_HINT + "\n", "", 1) == settled

    def test_a_config_that_cannot_be_read_still_prints_help(self, sandbox,
                                                            capsys, monkeypatch):
        def boom():
            raise RuntimeError("config is on fire")
        monkeypatch.setattr(registry, "first_run", boom)
        cli.print_help()                     # must not raise
        assert "%d commands" % len(cli.COMMANDS) in _plain(capsys.readouterr().out)


class TestTapSummary:
    """`tap` closes like `install` does: a summary and one next step."""

    def test_it_counts_registries_and_items(self):
        assert registry.tap_summary([("a", 5), ("b", 7)]) == "2 registries · 12 items"

    def test_one_of_each_is_singular(self):
        assert registry.tap_summary([("a", 1)]) == "1 registry · 1 item"

    def test_nothing_tapped_summarises_nothing(self):
        # A run where every clone failed must not frame a zero; the per-tap
        # warnings above are the report of what went wrong.
        from boost_cli.commands import taps
        assert taps._print_tap_next_step([]) is None

    def test_a_real_tap_prints_the_panel(self, boost, fixture_tap_src):
        res = boost("tap", fixture_tap_src)
        assert "1 registry · 5 items" in res.out
        assert "next: boost search" in res.out

    def test_a_dry_run_taps_nothing_and_promises_nothing(self, boost,
                                                         fixture_tap_src):
        res = boost("tap", fixture_tap_src, "--dry-run")
        assert "next: boost search" not in res.out
