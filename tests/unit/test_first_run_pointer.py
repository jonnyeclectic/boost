# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Nothing boost printed ever named an entry point.

Bare `boost` read no state at all, so its first screen was byte-for-byte
identical on a virgin machine and a working one, and `quickstart` sat at line
80 of 103, in the same dim body type as
the other 80 commands. Meanwhile the command every newcomer-facing hint routes
to, `boost tap`, ended on its last `✓ tapped …` row and said nothing about
what to do next, while `install` — which a user only reaches after finding
their own way here — closes with a framed box.

These tests pin both halves, and the disappearance as well as the appearance:
a permanent banner would be noise for every user past their first minute,
which is the reason there wasn't one.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import boost_cli
from boost_cli import cli
from boost_cli.core import config, registry
from boost_cli.core import output as out


def _plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestFirstRun:
    """`config.first_run()` — whether this machine has anything to search."""

    def test_a_machine_with_no_taps_is_a_first_run(self, sandbox):
        assert config.first_run() is True

    def test_one_tap_ends_it(self, boost, fixture_tap_src):
        boost("tap", fixture_tap_src)
        assert config.first_run() is False

    @pytest.mark.parametrize("text", ["{ not json", "[]", "null",
                                      '{"taps": "x"}', '{"taps": null}',
                                      '{"taps": {}}'])
    def test_a_config_that_cannot_be_parsed_is_not_a_first_run(self, sandbox,
                                                               text):
        # Unknown state is not a first run. The file is there, so boost has
        # been set up at least once, and its clones may still be on disk:
        # telling that user "new here?" is a guess dressed as a fact.
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_text(text, encoding="utf-8")
        assert config.first_run() is False

    def test_a_config_that_is_not_utf8_is_not_a_first_run(self, sandbox):
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_bytes(b"\xff\xfe")
        assert config.first_run() is False

    def test_a_config_that_names_no_taps_is_still_a_first_run(self, sandbox):
        # `boost config set` writes the file before anything is tapped, and
        # that user still has nothing to search.
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_text('{"ai": {"enabled": false}}',
                                       encoding="utf-8")
        assert config.first_run() is True


class TestHint:
    """The sentence names `quickstart`, and it names it once."""

    def test_it_names_quickstart_not_tap_defaults(self):
        # The two setup paths are not equivalent: quickstart pins each
        # registry to the commit its published vectors describe and can import
        # those vectors; `tap --defaults` does neither. README leads with
        # quickstart while ~15 source sites route to `tap --defaults`.
        assert "boost quickstart" in config.FIRST_RUN_HINT
        assert "tap --defaults" not in config.FIRST_RUN_HINT

    @pytest.mark.parametrize("cols", [40, 60, 80])
    def test_the_command_survives_a_narrow_pane(self, cols):
        # A backtick span is one atomic token for `out.wrap`: a `boost
        # quickstart` folded across two lines cannot be copy-pasted.
        from boost_cli.core import output as out
        lines = out.wrap(config.FIRST_RUN_HINT, cols)
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
        # An exported COLUMNS is a pane even without a TTY (out.pane_width),
        # and below ~85 it wraps the hint, which this exact-text check reads
        # as a changed index.
        monkeypatch.delenv("COLUMNS", raising=False)
        cli.print_help()
        virgin = _plain(capsys.readouterr().out)
        monkeypatch.setattr(config, "first_run", lambda: False)
        cli.print_help()
        settled = _plain(capsys.readouterr().out)
        assert "%d commands" % len(cli.COMMANDS) in settled
        assert "new here?" not in settled
        # Exactly the pointer, and nothing else: one blank line and the
        # sentence. COLUMNS is unset above, so the hint is never wrapped here.
        assert virgin.replace("\n" + config.FIRST_RUN_HINT + "\n", "", 1) == settled

    def test_a_config_that_cannot_be_read_still_prints_help(self, sandbox,
                                                            capsys, monkeypatch):
        def boom():
            raise RuntimeError("config is on fire")
        monkeypatch.setattr(config, "first_run", boom)
        cli.print_help()                     # must not raise
        assert "%d commands" % len(cli.COMMANDS) in _plain(capsys.readouterr().out)

    def test_a_config_that_cannot_be_parsed_gets_no_pointer(self, sandbox,
                                                            capsys):
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_text("{ not json", encoding="utf-8")
        cli.print_help()
        text = _plain(capsys.readouterr().out)
        assert "%d commands" % len(cli.COMMANDS) in text
        assert "new here?" not in text

    def test_a_config_that_is_not_utf8_still_prints_help(self, boost):
        # The decode failure escaped `logs.configure`, which runs before the
        # crash handler, so `boost --help` was a traceback and exit 1.
        from boost_cli.core import paths
        paths.ensure_dirs()
        paths.config_path().write_bytes(b"\xff\xfe")
        r = boost("--help")
        text = _plain(r.out)
        assert "%d commands" % len(cli.COMMANDS) in text
        assert "new here?" not in text
        assert "not valid UTF-8" in r.err

    def test_every_wrapped_line_carries_its_own_colour(self, sandbox, capsys,
                                                       monkeypatch):
        # `out.role` brackets its argument with a start code and a reset, so
        # colouring the sentence and then splitting it leaves line one
        # unterminated and every later line plain. The sandbox sets NO_COLOR,
        # which `use_color` checks before CLICOLOR_FORCE.
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("BOOST_COLOR", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setenv("COLUMNS", "40")
        cli.print_help()
        raw = capsys.readouterr().out.splitlines()
        wrapped = out.wrap(config.FIRST_RUN_HINT, 40)
        assert len(wrapped) > 1, wrapped
        for want in wrapped:
            line = next(ln for ln in raw if _plain(ln) == want)
            assert line == out.role(want, "muted"), line

    def test_asking_costs_help_no_extra_imports(self, sandbox):
        # `registry` brought gitutil, lockfile, policy, subprocess and
        # concurrent.futures onto the help path to answer a question `config`,
        # which help already loads for its log level, can answer alone. The
        # pointer is asserted too, so a predicate that failed to import (and
        # was swallowed) cannot pass this vacuously.
        code = ("import sys; from boost_cli.cli import main; main(['--help']); "
                "print('registry' if 'boost_cli.core.registry' in sys.modules "
                "else 'lean')")
        # UTF-8 both ways: help prints box and arrow glyphs, and on Windows a
        # cp1252 decode of them kills subprocess's reader thread, which leaves
        # stdout None rather than raising.
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(Path(boost_cli.__file__).resolve().parents[1]))
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, encoding="utf-8",
                              check=True)
        assert "new here?" in proc.stdout
        assert proc.stdout.splitlines()[-1] == "lean"


class TestTapSummary:
    """`tap` closes like `install` does: a summary and one next step."""

    def test_it_counts_registries_and_items(self):
        assert registry.tap_summary([("a", 5), ("b", 7)]) == "2 registries · 12 items"

    def test_one_of_each_is_singular(self):
        assert registry.tap_summary([("a", 1)]) == "1 registry · 1 item"

    def test_zero_is_plural(self):
        assert registry.tap_summary([("a", 0)]) == "1 registry · 0 items"
        assert registry.tap_summary([]) == "0 registries · 0 items"

    def test_nothing_tapped_summarises_nothing(self, capsys):
        # A run where every clone failed must not frame a zero; the per-tap
        # warnings above are the report of what went wrong.
        from boost_cli.commands import taps
        taps._print_tap_next_step([])
        assert capsys.readouterr().out == ""

    def test_nothing_to_search_is_not_sent_to_search(self, capsys):
        from boost_cli.commands import taps
        taps._print_tap_next_step([("a", 0), ("b", 0)])
        assert capsys.readouterr().out == ""

    def test_a_real_tap_prints_the_panel(self, boost, fixture_tap_src):
        res = boost("tap", fixture_tap_src)
        assert "1 registry · 5 items" in res.out
        assert "next: boost search" in res.out

    def test_a_dry_run_taps_nothing_and_promises_nothing(self, boost,
                                                         fixture_tap_src):
        res = boost("tap", fixture_tap_src, "--dry-run")
        assert "next: boost search" not in res.out

    def test_an_empty_registry_is_not_sent_to_search(self, boost, tmp_path):
        # A repo that holds nothing boost indexes taps cleanly with 0 items,
        # and "next: boost search <topic>" would point at an empty catalog.
        repo = tmp_path / "empty-registry"
        repo.mkdir()
        (repo / "README.md").write_text("# nothing to index\n",
                                        encoding="utf-8")
        git = ["git", "-C", str(repo), "-c", "user.email=t@boost.test",
               "-c", "user.name=Boost Test"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "readme"], check=True)
        res = boost("tap", str(repo))
        assert "tapped empty-registry (0 items)" in res.out
        assert "next: boost search" not in res.out
        assert "registry ·" not in res.out


class TestTapPanelRoutes:
    """Every route through `tap` reaches the panel, not only the single SPEC.

    `--defaults`, `--catalog` and several SPECs all land through `_tap_all`,
    and `--at` through a branch of its own. The card's own complaint is that
    `tap --defaults` ended with no next step, so each route is pinned.
    """

    @staticmethod
    def _second(src, tmp_path):
        return shutil.copytree(src, tmp_path / "second-tap")

    def test_several_specs(self, boost, fixture_tap_src, tmp_path):
        second = self._second(fixture_tap_src, tmp_path)
        res = boost("tap", fixture_tap_src, second)
        assert "2 registries · 10 items" in res.out
        assert "next: boost search" in res.out

    def test_defaults(self, boost, fixture_tap_src, tmp_path, monkeypatch):
        from boost_cli.core import config
        second = self._second(fixture_tap_src, tmp_path)
        monkeypatch.setattr(config, "DEFAULT_TAPS", [
            {"name": "fixture-tap", "url": str(fixture_tap_src),
             "curated": True, "focus": "first"},
            {"name": "second-tap", "url": str(second),
             "curated": True, "focus": "second"}])
        res = boost("tap", "--defaults")
        assert "2 registries · 10 items" in res.out
        assert "next: boost search" in res.out

    def test_catalog(self, boost, fixture_tap_src, monkeypatch):
        from boost_cli.core import config
        monkeypatch.setattr(config, "load_registry_catalog", lambda: [
            {"name": "fixture-tap", "url": str(fixture_tap_src),
             "type": "skill", "est_items": 5}])
        res = boost("tap", "--catalog")
        assert "1 registry · 5 items" in res.out
        assert "next: boost search" in res.out

    def test_a_pinned_tap(self, boost, fixture_tap_src):
        from boost_cli.core import gitutil
        head = gitutil.head_commit(fixture_tap_src)
        res = boost("tap", fixture_tap_src, "--at", head)
        assert "1 registry · 5 items" in res.out
        assert "next: boost search" in res.out
