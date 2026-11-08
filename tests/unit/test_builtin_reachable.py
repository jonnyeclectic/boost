# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost's own items resolve on every machine, not only after a yes.

The builtin tap used to be registered in exactly one place: the accept branch
of a `boost mcp register` offer. Three things followed, all measured on a
sandbox HOME before this change:

* both offers' decline line, "`boost install <name>` any time", named a
  command that failed with "no skill named ... in any tap";
* a Cursor- or Windsurf-only machine settles no MCP host, the offers ran only
  after one did, and `boost install boost-find-and-install` could not resolve
  there either -- so that user had no boost surface at all;
* a first `boost mcp register` that accepted the skill without seeding left
  the builtin as the machine's only tap, and every later register read that
  as "configured" and seeded nothing.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.commands import configuration
from boost_cli.core import (
    agents,
    bootstrap,
    builtin,
    catalog,
    config,
    lockfile,
    mcphost,
    registry,
)
from boost_cli.errors import BoostError

RULE = builtin.BUILTIN_RULES[0]
SKILL = builtin.BUILTIN_SKILLS[0]


def _tap_names() -> list[str]:
    return [t.name for t in registry.list_taps()]


class TestAShippedNameResolvesWithoutAnOffer:
    def test_the_rule_resolves_on_a_machine_that_never_registered_the_tap(
            self, sandbox):
        assert _tap_names() == []
        entry = catalog.resolve_one(RULE)
        assert entry["tap"] == builtin.BUILTIN_TAP
        assert entry["kind"] == "rule"
        assert _tap_names() == [builtin.BUILTIN_TAP]

    def test_the_skill_resolves_too(self, sandbox):
        entry = catalog.resolve_one(SKILL)
        assert entry["tap"] == builtin.BUILTIN_TAP
        assert entry["kind"] == "skill"

    def test_the_tap_qualified_spelling_resolves(self, sandbox):
        hits = catalog.find("%s:%s" % (builtin.BUILTIN_TAP, SKILL))
        assert [e["tap"] for e in hits] == [builtin.BUILTIN_TAP]

    def test_a_qualifier_naming_another_tap_registers_nothing(self, sandbox):
        assert catalog.find("someone/else:%s" % RULE) == []
        assert _tap_names() == []

    def test_any_other_miss_registers_nothing(self, sandbox):
        assert catalog.find("not-a-builtin") == []
        assert _tap_names() == []

    def test_a_caller_supplied_corpus_is_searched_as_given(self, sandbox):
        # `entries=` is a corpus the caller already holds -- one pass over
        # every installed item. A miss there is an answer about that corpus.
        assert catalog.find(RULE, entries=[]) == []
        assert _tap_names() == []

    def test_it_is_offline(self, sandbox, monkeypatch):
        from boost_cli.core import gitutil
        real = gitutil.run
        seen = []

        def record(args, *a, **k):
            seen.append(gitutil._subcommand(args))
            return real(args, *a, **k)
        monkeypatch.setattr(gitutil, "run", record)
        assert catalog.resolve_one(RULE)["tap"] == builtin.BUILTIN_TAP
        assert not {"clone", "fetch", "pull"} & set(seen), seen

    def test_the_cli_installs_it_on_a_fresh_machine(self, boost):
        boost("install", SKILL)
        assert lockfile.get_skill(SKILL) is not None


class TestATapRegisteredByAnOlderWheel:
    """The builtin tap predates the skill on every machine that took the rule.

    The rule shipped in August and the skill in November. A machine that
    accepted the rule in between has the tap registered and a cache scanned
    without the skill, and ``load_tap`` serves a cache written at the current
    ``CACHE_FORMAT`` as it is. So copying the skill out of the new wheel was
    not enough: the lookup re-read the old cache and missed.
    """

    @pytest.fixture()
    def old_tap(self, sandbox):
        import shutil
        tap = builtin.ensure_tap()
        shutil.rmtree(tap.path / "skills")
        catalog.rebuild_tap(registry.get(builtin.BUILTIN_TAP))
        assert [e["name"] for e in catalog.all_entries()] == [RULE]
        return tap

    def test_the_new_skill_resolves(self, old_tap):
        hits = catalog.find(SKILL)
        assert [(e["tap"], e["kind"]) for e in hits] == \
            [(builtin.BUILTIN_TAP, "skill")]

    def test_the_cli_installs_it(self, old_tap, boost):
        boost("install", SKILL)
        assert lockfile.get_skill(SKILL) is not None

    def test_after_a_declined_offer_too(self, old_tap, boost, monkeypatch):
        # The offer copies the skill out before it asks, and only its yes
        # branch rescanned: a no left the copy on disk and the cache stale.
        monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
        monkeypatch.setattr(configuration.out, "confirm",
                            lambda *a, **kw: False)
        configuration._offer_boost_skill()
        boost("install", SKILL)
        assert lockfile.get_skill(SKILL) is not None


class TestShips:
    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_each_shipped_item(self, name):
        assert builtin.ships(name)

    def test_another_name(self):
        assert not builtin.ships("brainstorming")

    def test_a_wheel_without_the_files_ships_nothing(self, monkeypatch,
                                                      tmp_path):
        monkeypatch.setattr(builtin, "source_dir", lambda: tmp_path)
        monkeypatch.setattr(builtin, "skills_source_dir", lambda: tmp_path)
        assert not builtin.ships(RULE)
        assert not builtin.ships(SKILL)

    def test_a_rule_name_is_not_looked_up_as_a_skill(self, monkeypatch,
                                                      tmp_path):
        # Each list is checked against its own directory: a rule missing from
        # the wheel is not rescued by a skill directory of the same name.
        (tmp_path / RULE).mkdir()
        (tmp_path / RULE / "SKILL.md").write_text("x", encoding="utf-8")
        monkeypatch.setattr(builtin, "source_dir", lambda: tmp_path / "none")
        monkeypatch.setattr(builtin, "skills_source_dir", lambda: tmp_path)
        assert not builtin.ships(RULE)


class TestDecliningLeavesAWayBackThatWorks:
    """The decline line names a command; that command has to run."""

    def test_the_rule_hint(self, sandbox, monkeypatch, capsys, boost):
        monkeypatch.delenv(configuration.NO_RULE_ENV, raising=False)
        monkeypatch.setattr(configuration.out, "confirm",
                            lambda *a, **kw: False)
        configuration._offer_boost_first(["claude"])
        assert ("`boost install %s` any time" % RULE) in \
            capsys.readouterr().out
        boost("install", RULE, "--dry-run")

    def test_the_skill_hint(self, sandbox, monkeypatch, capsys, boost):
        monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
        monkeypatch.setattr(configuration.out, "confirm",
                            lambda *a, **kw: False)
        configuration._offer_boost_skill()
        assert ("`boost install %s` any time" % SKILL) in \
            capsys.readouterr().out
        boost("install", SKILL)
        assert lockfile.get_skill(SKILL) is not None

    def test_the_offer_registers_the_tap_before_it_asks(
            self, sandbox, monkeypatch):
        monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
        seen = []

        def confirm(*_a, **_kw):
            seen.append(_tap_names())
            return False
        monkeypatch.setattr(configuration.out, "confirm", confirm)
        configuration._offer_boost_skill()
        assert seen == [[builtin.BUILTIN_TAP]]

    def test_a_tap_that_cannot_be_written_ends_the_offer_unasked(
            self, sandbox, monkeypatch, capsys):
        monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)

        def refuse():
            raise PermissionError("read-only home")

        def asked(*_a, **_kw):
            raise AssertionError("asked a question a yes could not honor")
        monkeypatch.setattr(builtin, "ensure_tap", refuse)
        monkeypatch.setattr(configuration.out, "confirm", asked)
        configuration._offer_boost_skill()
        captured = capsys.readouterr()
        assert "could not set up boost's own tap: read-only home" in \
            captured.out + captured.err
        assert lockfile.get_skill(SKILL) is None


class TestSeedingIgnoresBoostsOwnTap:
    def test_the_plan_still_names_every_default(self, sandbox, monkeypatch):
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        builtin.ensure_tap()
        assert bootstrap.seed_plan() == [str(d["name"])
                                         for d in config.DEFAULT_TAPS]

    def test_the_seed_still_runs(self, sandbox, monkeypatch):
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        builtin.ensure_tap()
        tried = []

        def offline(url, curated=False):
            tried.append(url)
            raise BoostError("offline")
        monkeypatch.setattr(registry, "add", offline)
        res = bootstrap.seed_catalog()
        assert not res.skipped
        assert len(tried) == len(config.DEFAULT_TAPS)
        assert res.already == []

    def test_a_user_tap_still_stops_the_implicit_seed(self, sandbox,
                                                      monkeypatch):
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        builtin.ensure_tap()
        config.mutate(lambda cfg: cfg.setdefault("taps", []).append(
            {"name": "me/mine", "url": "https://example.invalid/me/mine"}))
        assert bootstrap.seed_plan() == []
        assert bootstrap.seed_catalog().skipped


def _no_agent_cli(monkeypatch, present=()):
    """No agent CLI on PATH except ``present``; git and the rest resolve."""
    import shutil
    real = shutil.which
    clis = {mcphost.cli(h) for h in mcphost.hosts()}
    monkeypatch.setattr(
        "boost_cli.commands.configuration.shutil.which",
        lambda c, *a, **k: ("/usr/local/bin/%s" % c if c in present
                            else None if c in clis else real(c, *a, **k)))
    monkeypatch.setattr(
        "boost_cli.commands.configuration.subprocess.run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="Added stdio MCP server boost\n", stderr=""))


@pytest.fixture
def skill_offered(sandbox, monkeypatch):
    monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
    return sandbox


class TestAMachineWithNoMcpHostIsStillOfferedTheSkill:
    """Cursor and Windsurf read skills dirs and take no boost MCP server."""

    def test_register_installs_it_for_the_linking_agents(
            self, boost, skill_offered, monkeypatch):
        _no_agent_cli(monkeypatch)
        r = boost("mcp", "register", "--no-seed")
        assert ("no agent CLI found (looked for: claude, gemini, agy, codex)"
                in r.out)
        assert lockfile.get_skill(SKILL) is not None
        for agent, skills_dir in agents.linking_agents().items():
            assert (skills_dir / SKILL).is_symlink(), agent
        flat = " ".join(r.out.split())
        assert "it works through the shell" in flat
        assert "installed %s for " % SKILL in flat
        assert "cursor" in flat and "windsurf" in flat

    def test_the_rule_is_not_offered_without_a_host(
            self, boost, skill_offered, monkeypatch):
        monkeypatch.delenv(configuration.NO_RULE_ENV, raising=False)
        _no_agent_cli(monkeypatch)
        boost("mcp", "register", "--no-seed", "-y")
        assert lockfile.get_rule(RULE) is None

    def test_one_named_missing_host_fails_without_an_offer(
            self, boost, skill_offered, monkeypatch):
        _no_agent_cli(monkeypatch)
        boost("mcp", "register", "--host", "claude", "--no-seed", expect=1)
        assert lockfile.get_skill(SKILL) is None

    def test_no_linking_agent_no_offer(self, boost, skill_offered,
                                       monkeypatch):
        _no_agent_cli(monkeypatch)
        monkeypatch.setattr(configuration.agents, "linking_agents", dict)
        r = boost("mcp", "register", "--no-seed")
        assert lockfile.get_skill(SKILL) is None
        assert "works through the shell" not in r.out

    def test_unregister_offers_nothing(self, boost, skill_offered,
                                       monkeypatch):
        _no_agent_cli(monkeypatch)
        boost("mcp", "unregister")
        assert lockfile.get_skill(SKILL) is None

    def test_the_dry_run_names_the_offer_and_installs_nothing(
            self, boost, skill_offered, monkeypatch):
        _no_agent_cli(monkeypatch)
        r = boost("mcp", "register", "--no-seed", "--dry-run")
        assert ("would then offer to install the `%s` skill (default yes)"
                % SKILL) in " ".join(r.out.split())
        assert lockfile.get_skill(SKILL) is None
        assert _tap_names() == []

    def test_the_dry_run_for_one_named_missing_host_does_not(
            self, boost, skill_offered, monkeypatch):
        _no_agent_cli(monkeypatch)
        r = boost("mcp", "register", "--host", "claude", "--no-seed",
                  "--dry-run")
        assert "would then offer" not in r.out

    def test_a_settled_host_names_who_the_skill_reached(
            self, boost, skill_offered, monkeypatch):
        _no_agent_cli(monkeypatch, present=("claude",))
        r = boost("mcp", "register", "--no-seed")
        flat = " ".join(r.out.split())
        assert "installed %s for " % SKILL in flat
        assert "(read the store directly)" in flat
        assert "boost uninstall %s" % SKILL in flat


class TestReachPhrase:
    def test_both_halves(self):
        assert agents.reach_phrase(["a", "b"], ["c"]) == \
            "a, b; c (read the store directly)"

    def test_linked_only(self):
        assert agents.reach_phrase(["a"], []) == "a"

    def test_native_only(self):
        assert agents.reach_phrase([], ["c", "d"]) == \
            "c, d (read the store directly)"

    def test_neither(self):
        assert agents.reach_phrase([], []) == "none"

