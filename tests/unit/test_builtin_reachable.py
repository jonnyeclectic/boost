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

import json
import operator
import subprocess

import pytest

from boost_cli.commands import configuration
from boost_cli.core import (
    agents,
    bootstrap,
    builtin,
    catalog,
    config,
    frontmatter,
    lockfile,
    mcphost,
    paths,
    rag,
    registry,
    store,
)
from boost_cli.errors import BoostError

RULE = builtin.BUILTIN_RULES[0]
SKILL = builtin.BUILTIN_SKILLS[0]


def _tap_names() -> list[str]:
    return [t.name for t in registry.list_taps()]


def _written() -> dict:
    """Everything registering boost's own tap writes, as it stands now.

    ``config.json``, every path under ``~/.boost/repos/`` and the builtin
    tap's cache file. Logs are left out: every command may append to them.
    """
    cfg = paths.config_path()
    repos = paths.repos_dir()
    cache = registry.Tap(name=builtin.BUILTIN_TAP,
                         url=builtin.BUILTIN_URL).cache_file
    return {"config": cfg.read_bytes() if cfg.exists() else None,
            "repos": (sorted(str(f.relative_to(repos))
                             for f in repos.rglob("*"))
                      if repos.exists() else None),
            "cache": cache.read_bytes() if cache.exists() else None}


def _first_body_line(name: str) -> str:
    """The first line of ``name``'s body as the wheel ships it."""
    entry = next(e for e in builtin.shipped_entries() if e["name"] == name)
    path = builtin.shipped_path(entry["skill_md"])
    assert path is not None
    return frontmatter.parse(path.read_text(encoding="utf-8"))[1] \
        .strip().splitlines()[0]


def _shipped_version() -> str:
    """The ``version:`` the wheel's copy of the skill declares."""
    path = builtin.skills_source_dir() / SKILL / "SKILL.md"
    return str(frontmatter.parse(path.read_text(encoding="utf-8"))[0]
               ["version"])


class TestAShippedNameResolvesWithoutAnOffer:
    def test_the_rule_resolves_on_a_machine_that_never_registered_the_tap(
            self, sandbox):
        assert _tap_names() == []
        entry = catalog.resolve_one(RULE)
        assert entry["tap"] == builtin.BUILTIN_TAP
        assert entry["kind"] == "rule"
        # Answered from the wheel: a lookup registers nothing. The install
        # that needs the tap on disk is what registers it.
        assert _tap_names() == []

    def test_the_skill_resolves_too(self, sandbox):
        entry = catalog.resolve_one(SKILL)
        assert entry["tap"] == builtin.BUILTIN_TAP
        assert entry["kind"] == "skill"

    def test_the_tap_qualified_spelling_resolves(self, sandbox):
        hits = catalog.find("%s:%s" % (builtin.BUILTIN_TAP, SKILL))
        assert [e["tap"] for e in hits] == [builtin.BUILTIN_TAP]

    def test_the_qualified_spelling_with_a_namesake_in_another_tap(
            self, boost, tmp_path):
        # Another tap ships a `boost-first` of its own. Its row matched the
        # name, so the fallback was skipped, and the qualifier then filtered
        # that row out: `boost/builtin:boost-first` resolved to nothing.
        other = tmp_path / "namesake"
        (other / "skills" / RULE).mkdir(parents=True)
        (other / "skills" / RULE / "SKILL.md").write_text(
            "---\nname: %s\ndescription: a namesake\n---\n\nbody\n" % RULE,
            encoding="utf-8")
        for argv in (("init", "-q"), ("add", "-A"),
                     ("-c", "user.name=t", "-c", "user.email=t@t",
                      "commit", "-qm", "tap")):
            subprocess.run(["git", "-C", str(other), *argv], check=True,
                           capture_output=True)
        boost("tap", other)
        # The bare name means the tap the user configured, and registers
        # nothing: it had a hit.
        assert {e["tap"] for e in catalog.find(RULE)} == {"namesake"}
        assert builtin.BUILTIN_TAP not in _tap_names()
        hits = catalog.find("%s:%s" % (builtin.BUILTIN_TAP, RULE))
        assert [(e["tap"], e["kind"]) for e in hits] == \
            [(builtin.BUILTIN_TAP, "rule")]

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

    def test_a_tap_that_cannot_be_written_is_an_error_not_a_crash(
            self, boost, monkeypatch):
        def refuse():
            raise PermissionError("read-only home")
        monkeypatch.setattr(builtin, "ensure_tap", refuse)
        # Exit 1 with the reason, where it was 70 and a crash report. The
        # install is the write, so it is where the write fails.
        r = boost("install", RULE, expect=1)
        assert ("could not set up boost's own tap to install %r: "
                "read-only home" % RULE) in r.err
        assert lockfile.get_rule(RULE) is None
        # A lookup needs no write, so an unwritable home does not stop it.
        assert [e["tap"] for e in catalog.find(RULE)] == [builtin.BUILTIN_TAP]
        boost("info", RULE)


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

    def test_reading_it_rewrites_nothing(self, old_tap, boost):
        # Read from the wheel: the stale tap is neither re-copied nor
        # rescanned by a lookup. The install below is what refreshes it.
        before = _written()
        text, is_error = configuration._mcp_tool("boost_read",
                                                 {"name": SKILL})
        assert not is_error, text
        assert _first_body_line(SKILL) in text
        assert _first_body_line(SKILL) in boost("cat", SKILL).out
        assert _written() == before
        assert not (old_tap.path / "skills").exists()

    def test_the_search_body_is_the_wheels_too(self, old_tap):
        # `rag.entry_path` redirected only a tap that is not configured at
        # all, so here it named the missing tap copy and `read_body` came
        # back without the body, where every other read used the wheel.
        before = _written()
        entry = catalog.resolve_one(SKILL)
        assert rag.entry_path(entry) == \
            builtin.shipped_path(entry["skill_md"])
        assert _first_body_line(SKILL) in rag.read_body(entry)
        assert _written() == before

    def test_after_a_declined_offer_too(self, old_tap, boost, monkeypatch):
        # The offer copies the skill out before it asks, and only its yes
        # branch rescanned: a no left the copy on disk and the cache stale.
        monkeypatch.delenv(configuration.NO_SKILL_ENV, raising=False)
        monkeypatch.setattr(configuration.out, "confirm",
                            lambda *a, **kw: False)
        configuration._offer_boost_skill()
        boost("install", SKILL)
        assert lockfile.get_skill(SKILL) is not None


class TestATapHoldingAnOlderCopy:
    """The tap is registered and holds the item, at an older version.

    What every machine has after a boost release revises the skill. The
    lookup finds the cached row and never reaches the wheel, and the install
    then rewrites the tap from this wheel before copying from it.
    """

    @pytest.fixture()
    def stale_tap(self, sandbox):
        tap = builtin.ensure_tap()
        skill_md = tap.path / "skills" / SKILL / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        assert _shipped_version() in text
        skill_md.write_text(text.replace("version: " + _shipped_version(),
                                         "version: 0.0.1"), encoding="utf-8")
        catalog.rebuild_tap(registry.get(builtin.BUILTIN_TAP))
        assert [e["version"] for e in catalog.find(SKILL)] == ["0.0.1"]
        return tap

    def test_the_install_records_the_version_it_copied(self, stale_tap,
                                                        boost):
        # It recorded the stale row's 0.0.1 beside the new files, and
        # `boost outdated` then offered to upgrade what had just upgraded.
        boost("install", SKILL)
        copied = (paths.store_dir() / SKILL / "SKILL.md").read_text(
            encoding="utf-8")
        assert "version: " + _shipped_version() in copied
        assert lockfile.get_skill(SKILL)["version"] == _shipped_version()
        assert SKILL not in boost("outdated").out


    def test_boost_install_names_the_version_it_installed(self, stale_tap):
        text, is_error = configuration._mcp_tool("boost_install",
                                                 {"name": SKILL})
        assert not is_error, text
        assert "installed %s v%s from" % (SKILL, _shipped_version()) in text
        assert lockfile.get_skill(SKILL)["version"] == _shipped_version()


class TestALostLockIsRecoveredFromTheWheel:
    def test_sync_records_it_from_boosts_tap_again(self, boost):
        # The lock and everything under ~/.boost are gone; the store copy is
        # the wheel's bytes. Matching it hashed the wheel's copy bounded by
        # `registry.get("boost/builtin")`, which raised, so the skill was
        # re-recorded as a local one that no update would ever reach.
        import shutil
        boost("install", SKILL)
        shutil.rmtree(paths.boost_home())
        paths.lockfile_path().unlink()
        assert _tap_names() == []
        assert "re-recorded %s from %s" % (SKILL, builtin.BUILTIN_TAP) in \
            boost("sync").out
        assert lockfile.get_skill(SKILL)["tap"] == builtin.BUILTIN_TAP
        # The record names a tap, so the tap is registered: a write path.
        assert _tap_names() == [builtin.BUILTIN_TAP]

    def test_the_source_hash_reads_the_wheel_and_writes_nothing(self, sandbox):
        from boost_cli.core import util
        before = _written()
        assert store.skill_source_sha(catalog.resolve_one(SKILL)) == \
            util.sha256_dir(builtin.skills_source_dir() / SKILL)
        assert _written() == before


class TestALookupOfBoostsOwnItemsWritesNothing:
    """Reading one of boost's own items registers nothing.

    ``catalog.find`` used to register the builtin tap on a miss, writing
    ``config.json`` and ``~/.boost/repos/boost__builtin``. ``boost info``,
    ``boost cat``, ``boost_read`` and ``boost_info`` all look up through it,
    and the last two are described to agents as changing nothing. They now
    describe and read the item from the wheel; an install still registers.
    """

    def test_the_rows_are_the_ones_the_registered_tap_scans_to(self, sandbox):
        # Same row identity both ways, so a lock written from a wheel row
        # matches the tap's row once an install has registered it.
        shipped = builtin.shipped_entries()
        tap = builtin.ensure_tap()
        scanned = catalog.scan_dir(tap.path, builtin.BUILTIN_TAP,
                                   curated=True)
        by_file = operator.itemgetter("skill_md")
        assert sorted(shipped, key=by_file) == sorted(scanned, key=by_file)
        assert sorted(e["name"] for e in shipped) == sorted([RULE, SKILL])

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_find(self, sandbox, name):
        before = _written()
        assert [e["tap"] for e in catalog.find(name)] == [builtin.BUILTIN_TAP]
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL,
                                      "%s:%s" % (builtin.BUILTIN_TAP, RULE)])
    def test_boost_read(self, sandbox, name):
        before = _written()
        text, is_error = configuration._mcp_tool("boost_read", {"name": name})
        assert not is_error, text
        assert _first_body_line(catalog.split_name(name)[1]) in text
        assert "installed: no" in text
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_boost_info(self, sandbox, name):
        before = _written()
        text, is_error = configuration._mcp_tool("boost_info", {"name": name})
        assert not is_error, text
        assert "tap: %s" % builtin.BUILTIN_TAP in text
        assert "installed: no" in text
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_info(self, boost, name):
        before = _written()
        assert builtin.BUILTIN_TAP in boost("info", name).out
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_cat(self, boost, name):
        before = _written()
        assert _first_body_line(name) in boost("cat", name).out
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_log_says_why_there_is_no_history(self, boost, name):
        # Not "comes from tap boost/builtin, which is no longer tapped": it
        # was never tapped, and it has no git history to show if it were.
        before = _written()
        assert "ships with boost" in boost("log", name).out
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_an_install_dry_run(self, boost, name):
        before = _written()
        assert "dry run" in boost("install", name, "--dry-run").out
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_the_body_is_read_from_the_wheel(self, sandbox, name):
        before = _written()
        entry = catalog.resolve_one(name)
        shipped = builtin.shipped_path(entry["skill_md"])
        assert rag.entry_path(entry) == shipped
        assert _first_body_line(name) in rag.read_body(entry)
        assert store.source_file_for(entry) == shipped
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_deps(self, boost, name):
        before = _written()
        assert "requires: (none)" in boost("deps", name).out
        assert _written() == before

    def test_boost_serve_reads_it_too(self, sandbox):
        from boost_cli.core import serve
        before = _written()
        text = serve.skill_text(SKILL)
        assert text is not None and _first_body_line(SKILL) in text
        assert _written() == before

    def test_a_wheel_missing_the_file_says_so(self, sandbox):
        # Package data a build left out is not something `boost update`
        # can fetch, so the error does not send the user there.
        ghost = {"name": "ghost", "tap": builtin.BUILTIN_TAP, "kind": "rule",
                 "skill_md": "ghost.mdc", "rel_dir": "."}
        with pytest.raises(BoostError, match="missing from this boost "
                           "install") as err:
            store.source_file_for(ghost)
        assert "self-update" in (err.value.hint or "")

    def test_the_skill_dir_is_the_wheels(self, sandbox):
        entry = catalog.resolve_one(SKILL)
        assert store.source_dir_for(entry) == \
            builtin.skills_source_dir() / SKILL

    def test_a_path_outside_the_shipped_layout_reads_nothing(self):
        for rel in ("../registries.json", "/etc/passwd", "rules/x.mdc",
                    "skills", ".", "skills/../../x"):
            assert builtin.shipped_path(rel) is None, rel

    @pytest.mark.parametrize("rel", [
        "skills\\..\\..\\x", "..\\registries.json", "skills/a\\..\\..\\..\\x",
        "C:x.mdc", "C:\\Windows\\x.mdc", "\\\\server\\share\\x.mdc",
        "\\x.mdc", "\\", "C:", "skills/a:b", "skills/x/C:SKILL.md"])
    def test_a_windows_spelling_reads_nothing(self, rel):
        # One component to PurePosixPath, so the `..` and absolute checks
        # passed it. Joined onto a WindowsPath, a backslashed `..` climbs out
        # of the package and a drive letter resets to that drive.
        assert builtin.shipped_path(rel) is None

    def test_the_shipped_layout_maps_either_separator(self):
        skill_md = builtin.skills_source_dir() / SKILL / "SKILL.md"
        assert builtin.shipped_path(RULE + ".mdc") == \
            builtin.source_dir() / (RULE + ".mdc")
        assert builtin.shipped_path("skills/%s/SKILL.md" % SKILL) == skill_md
        assert builtin.shipped_path("skills\\%s\\SKILL.md" % SKILL) == skill_md

    def test_only_shipped_names_come_back(self, monkeypatch, tmp_path):
        # The scan roots hold whatever the package does; only the names
        # `ensure_tap` copies are rows the registered tap would have.
        rules, skills = tmp_path / "rules", tmp_path / "skills"
        for path in (rules / (RULE + ".mdc"), rules / "stray.mdc",
                     skills / SKILL / "SKILL.md",
                     skills / "stray" / "SKILL.md"):
            name = path.stem if path.suffix == ".mdc" else path.parent.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("---\nname: %s\ndescription: d\n---\n\nbody\n"
                            % name, encoding="utf-8")
        monkeypatch.setattr(builtin, "source_dir", lambda: rules)
        monkeypatch.setattr(builtin, "skills_source_dir", lambda: skills)
        assert sorted((e["name"], e["kind"])
                      for e in builtin.shipped_entries()) == \
            sorted([(RULE, "rule"), (SKILL, "skill")])

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_its_frontmatter_is_the_wheels(self, sandbox, name):
        # What `deps` reads for a requirement that is not installed.
        from boost_cli.commands import info
        before = _written()
        meta = info._skill_meta(name)
        assert meta is not None and meta["name"] == name
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_changelog_says_why_there_is_no_history(self, boost, name):
        # It asked the registry for the tap, and an unregistered one is
        # "no such tap": exit 1 for a command that only reads.
        before = _written()
        assert builtin.no_history_note(name) in boost("changelog", name).out
        data = json.loads(boost("changelog", name, "--json").out)
        assert data == {"name": name, "tap": builtin.BUILTIN_TAP,
                        "commits": []}
        assert _written() == before

    @pytest.mark.parametrize("name", [RULE, SKILL])
    def test_cli_home_names_the_shipped_file(self, boost, name):
        # It printed the bare `boost-first.mdc`, which reads as a local
        # import's path, and once registered `builtin:boost/boost-first.mdc`.
        before = _written()
        entry = catalog.resolve_one(name)
        shipped = builtin.shipped_path(catalog.upstream_path(entry))
        assert shipped is not None and shipped.exists()
        assert boost("home", name, "--print").out.strip() == \
            paths.tilde(shipped)
        assert _written() == before
        boost("install", name)
        assert boost("home", name, "--print").out.strip() == \
            paths.tilde(shipped)

    def test_another_taps_rows_are_not_redirected(self, sandbox):
        assert builtin.wheel_source("someone/else", RULE + ".mdc") is None

    def test_the_cli_install_registers_it(self, boost):
        boost("install", SKILL)
        assert _tap_names() == [builtin.BUILTIN_TAP]
        assert lockfile.get_skill(SKILL)["tap"] == builtin.BUILTIN_TAP
        # Registered, the tap's own copy is what reads open from now on.
        assert store.source_file_for(catalog.resolve_one(SKILL)) == \
            registry.get(builtin.BUILTIN_TAP).path / "skills" / SKILL \
            / "SKILL.md"

    def test_boost_install_registers_it(self, sandbox):
        text, is_error = configuration._mcp_tool("boost_install",
                                                 {"name": SKILL})
        assert not is_error, text
        assert _tap_names() == [builtin.BUILTIN_TAP]
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

