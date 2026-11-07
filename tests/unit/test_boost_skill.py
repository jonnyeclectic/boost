# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost's own skill, `boost-find-and-install`, and its offer.

boost shipped one built-in item, the boost-first rule, offered only to hosts
boost registered a server with and defaulting to No. Skills are the item kind
every agent reads — Gemini CLI and Codex from the canonical store, the others
through links — and a skill's name and description sit wherever the host
lists its skills, with the body loaded only when the agent reaches for it. So
boost now ships a skill carrying the rule's search -> read -> install ->
use-now guidance and its consent line, offered from `boost mcp register`
beside the rule and defaulting to yes.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

from boost_cli import cli
from boost_cli.commands import configuration
from boost_cli.core import (
    builtin,
    catalog,
    frontmatter,
    lockfile,
    paths,
    registry,
    store,
)

SKILL = builtin.BUILTIN_SKILLS[0]


def _text() -> str:
    return (builtin.skills_source_dir() / SKILL / "SKILL.md").read_text(
        encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split()).lower()


def _rule_flat() -> str:
    return _flat((builtin.source_dir() / (builtin.BUILTIN_RULES[0] + ".mdc"))
                 .read_text(encoding="utf-8"))


@pytest.fixture
def offering(sandbox, monkeypatch):
    """A sandbox with the skill offer's guard lifted."""
    monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
    return sandbox


class TestItShips:
    def test_the_wheel_carries_it(self):
        assert builtin.skill_is_available()

    def test_its_frontmatter_names_it_and_carries_a_version(self):
        meta = frontmatter.parse(_text())[0]
        assert meta["name"] == SKILL
        # `boost update` refreshes an installed skill when this moves.
        assert re.fullmatch(r"\d+\.\d+\.\d+", meta["version"])

    def test_ensure_tap_lands_it_where_the_scanner_looks(self, sandbox):
        tap = builtin.ensure_tap()
        landed = tap.path / "skills" / SKILL / "SKILL.md"
        assert landed.read_text(encoding="utf-8") == _text()

    def test_a_hand_edited_copy_is_restored_from_the_wheel(self, sandbox):
        tap = builtin.ensure_tap()
        landed = tap.path / "skills" / SKILL / "SKILL.md"
        landed.write_text("clobbered", encoding="utf-8")
        builtin.ensure_tap()
        assert landed.read_text(encoding="utf-8") == _text()

    def test_update_refreshes_the_tap_copy_from_the_wheel(
            self, sandbox, monkeypatch, tmp_path):
        tap = builtin.ensure_tap()
        newer = tmp_path / "wheel-skills"
        (newer / SKILL).mkdir(parents=True)
        (newer / SKILL / "SKILL.md").write_text(
            "---\nname: %s\ndescription: d\nversion: 9.0.0\n---\n\nREVISED\n"
            % SKILL, encoding="utf-8")
        monkeypatch.setattr(builtin, "skills_source_dir", lambda: newer)
        registry.update()
        assert "REVISED" in (tap.path / "skills" / SKILL / "SKILL.md") \
            .read_text(encoding="utf-8")

    def test_a_wheel_without_it_copies_nothing_and_offers_nothing(
            self, offering, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(builtin, "skills_source_dir",
                            lambda: tmp_path / "absent")
        tap = builtin.ensure_tap()
        assert not (tap.path / "skills").exists()
        assert not builtin.skill_is_available()
        configuration._offer_boost_skill()
        assert capsys.readouterr().out == ""

    def test_the_wheel_copy_is_only_ever_read(self, sandbox):
        before = sorted(p.name for p in builtin.skills_source_dir().iterdir())
        builtin.ensure_tap()
        assert sorted(p.name for p in
                      builtin.skills_source_dir().iterdir()) == before

    def test_the_catalog_calls_it_a_skill_of_boosts_own_tap(self, sandbox):
        builtin.ensure_tap()
        catalog.rebuild_tap(registry.get(builtin.BUILTIN_TAP))
        entry = catalog.resolve_one("%s:%s" % (builtin.BUILTIN_TAP, SKILL))
        assert entry.get("kind", "skill") == "skill"
        assert entry["tap"] == builtin.BUILTIN_TAP

    def test_it_installs_like_any_skill(self, sandbox):
        builtin.ensure_tap()
        catalog.rebuild_tap(registry.get(builtin.BUILTIN_TAP))
        store.install(catalog.resolve_one(SKILL))
        assert lockfile.get_skill(SKILL)["tap"] == builtin.BUILTIN_TAP
        assert (paths.store_dir() / SKILL / "SKILL.md").read_text(
            encoding="utf-8") == _text()


class TestItSaysWhatTheRuleSays:
    """The skill and the rule are two surfaces for one set of instructions."""

    #: The install half of the rule, which the skill must carry verbatim.
    PARITY = ("usable this turn", "`boost install <name> --local`",
              "say in your reply which you chose and where it landed",
              "ask the user before installing a rule", "`boost mcp register`",
              "has a name", "more than one file", "outlives this session",
              "the task stays yours", "mcp__boost__boost_search",
              "look before you conclude it is absent",
              "applies to every project on this machine")

    @pytest.mark.parametrize("phrase", PARITY)
    def test_a_load_bearing_phrase_sits_in_both(self, phrase):
        assert phrase in _flat(_text())
        assert phrase in _rule_flat()

    def test_it_does_not_order_the_agent(self):
        low = _text().lower()
        for coercive in ("always call", "you must", "never skip",
                         "required before", "do not proceed",
                         "is never enough", "must report", "always report"):
            assert coercive not in low, coercive

    def test_the_skip_list_is_visible(self):
        low = _flat(_text())
        assert "not for:" in low
        for skip in ("a question", "one-line edit", "just handed"):
            assert skip in low, skip

    def test_it_names_only_tools_that_exist(self):
        names = {s["name"] for s in configuration.REGISTRY.specs()}
        mentioned = set(re.findall(r"`(boost_\w+)`", _text()))
        assert {"boost_search", "boost_list", "boost_read",
                "boost_install"} <= mentioned
        assert mentioned <= names, mentioned - names

    def test_every_shell_command_it_names_is_real(self):
        real = {row[0] for row in cli.COMMANDS}
        named = set(re.findall(r"`boost (\w[\w-]*)", _text()))
        assert {"search", "list", "cat", "install", "mcp"} <= named
        assert named <= real, named - real

    def test_the_description_carries_the_triggers(self):
        # The description is what a host shows before the body loads.
        desc = frontmatter.parse(_text())[0]["description"].lower()
        for trigger in ("has a name", "more than one file",
                        "outlives this session"):
            assert trigger in desc, trigger


class TestTheOfferDefaultsToYes:
    def test_the_default_answer_installs_it(self, offering, monkeypatch,
                                            capsys):
        # No BOOST_ASSUME_YES, stdin is not a tty: confirm returns its default.
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
        asked = []
        real = configuration.out.confirm

        def confirm(msg, *a, **kw):
            asked.append(kw.get("default"))
            return real(msg, *a, **kw)
        monkeypatch.setattr(configuration.out, "confirm", confirm)
        configuration._offer_boost_skill()
        assert asked == [True]
        assert lockfile.get_skill(SKILL) is not None
        out = capsys.readouterr().out
        assert ("boost uninstall %s" % SKILL) in out

    def test_declining_installs_nothing_and_says_how_later(
            self, offering, monkeypatch, capsys):
        monkeypatch.setattr(configuration.out, "confirm",
                            lambda *a, **kw: False)
        configuration._offer_boost_skill()
        assert lockfile.get_skill(SKILL) is None
        assert ("boost install %s" % SKILL) in capsys.readouterr().out

    def test_yes_installs_without_asking(self, offering, monkeypatch):
        def boom(*_a, **_k):
            raise AssertionError("asked despite yes")
        monkeypatch.setattr(configuration.out, "confirm", boom)
        configuration._offer_boost_skill(yes=True)
        assert lockfile.get_skill(SKILL) is not None

    def test_the_guard_wins_over_assume_yes(self, sandbox, monkeypatch,
                                            capsys):
        monkeypatch.setenv(configuration.NO_SKILL_ENV, "1")
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        configuration._offer_boost_skill(yes=True)
        assert lockfile.get_skill(SKILL) is None
        assert capsys.readouterr().out == ""

    def test_an_installed_skill_is_not_offered_again(self, offering, capsys):
        configuration._offer_boost_skill(yes=True)
        capsys.readouterr()
        configuration._offer_boost_skill(yes=True)
        assert capsys.readouterr().out == ""

    def test_a_failed_install_is_a_warning_not_a_crash(
            self, offering, monkeypatch, capsys):
        from boost_cli.errors import BoostError

        def refuse(*_a, **_k):
            raise BoostError("disk full")
        monkeypatch.setattr(store, "install", refuse)
        configuration._offer_boost_skill(yes=True)
        captured = capsys.readouterr()
        assert "could not install %s: disk full" % SKILL in \
            captured.out + captured.err


class TestMcpRegisterOffersIt:
    @staticmethod
    def _fake_claude(monkeypatch):
        # Claude Code is the one agent CLI present; everything else (git,
        # which a skill install needs) resolves as it really does.
        import shutil
        real = shutil.which
        from boost_cli.core import mcphost
        others = {mcphost.cli(h) for h in mcphost.hosts()} - {"claude"}
        monkeypatch.setattr(
            "boost_cli.commands.configuration.shutil.which",
            lambda c, *a, **k: "/usr/local/bin/claude" if c == "claude"
            else None if c in others else real(c, *a, **k))
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="Added stdio MCP server boost\n", stderr=""))

    def test_register_installs_it(self, boost, offering, monkeypatch):
        self._fake_claude(monkeypatch)
        r = boost("mcp", "register", "--no-seed")
        assert ("installed %s" % SKILL) in r.out
        assert (paths.store_dir() / SKILL / "SKILL.md").is_file()
        # The rule stays behind its own guard and its own default.
        assert lockfile.get_rule(builtin.BUILTIN_RULES[0]) is None

    def test_unregister_does_not(self, boost, offering, monkeypatch):
        self._fake_claude(monkeypatch)
        boost("mcp", "unregister")
        assert lockfile.get_skill(SKILL) is None

    def test_the_dry_run_names_it_and_installs_nothing(
            self, boost, offering, monkeypatch):
        self._fake_claude(monkeypatch)
        r = boost("mcp", "register", "--no-seed", "--dry-run")
        assert ("would then offer to install the `%s` skill (default yes)"
                % SKILL) in " ".join(r.out.split())
        assert lockfile.get_skill(SKILL) is None
        assert not pathlib.Path(paths.store_dir() / SKILL).exists()
