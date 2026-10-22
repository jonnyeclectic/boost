# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: tap / untap / taps / outdated (registry commands)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from boost_cli.core import config, paths, staleness, util


def _copy_tap(src, dest):
    """Copy the session fixture tap (with its .git) to a private location."""
    shutil.copytree(src, dest)
    return dest


def _bump(tap_dir, skill, old, new):
    """Bump a skill's version in a tap repo copy and commit it."""
    md = tap_dir / "skills" / skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace("version: %s" % old,
                                         "version: %s" % new), encoding="utf-8")
    subprocess.run(["git", "-C", str(tap_dir), "commit", "-aqm",
                    "bump %s to %s" % (skill, new)],
                   check=True, capture_output=True)


def _commit_clone(repo, msg):
    """Commit tracked changes inside a boost-made clone (which has no git
    identity of its own) and return the new HEAD commit."""
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *list(a)],
                                    check=True, capture_output=True, text=True)
    run("config", "user.email", "t@boost.test")
    run("config", "user.name", "Boost Test")
    run("commit", "-aqm", msg)
    return run("rev-parse", "HEAD").stdout.strip()


# ── tap ──────────────────────────────────────────────────────────────────

class TestTap:
    def test_local_dir_happy(self, boost, fixture_tap_src):
        r = boost("tap", fixture_tap_src)
        assert "tapped fixture-tap (5 items)" in r.out
        # real effects: clone, cache, config entry
        assert (paths.repos_dir() / "fixture-tap" / "SKILL.md").exists() is False
        assert (paths.repos_dir() / "fixture-tap" / "skills" /
                "brainstorming" / "SKILL.md").is_file()
        assert (paths.cache_dir() / "fixture-tap.json").is_file()
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert cfg["taps"][0]["name"] == "fixture-tap"
        assert cfg["taps"][0]["curated"] is False

    def test_several_specs_tap_in_one_invocation(self, boost,
                                                  fixture_tap_src, tmp_path):
        # Not only a convenience. `xargs boost_cli tap < list` hands every
        # line to ONE invocation, and rejecting the extras is how the shards
        # workflow tapped nothing: argparse errored, `|| true` swallowed it,
        # and the job died three steps later on "no taps configured" — 17 of
        # 60 matrix jobs, every multi-registry chunk.
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        r = boost("tap", fixture_tap_src, str(second))
        assert "tapped fixture-tap (5 items)" in r.out
        assert "tapped second-tap (5 items)" in r.out
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert [t["name"] for t in cfg["taps"]] == ["fixture-tap",
                                                    "second-tap"]
        # Plain multi-spec taps are not curated — that stays opt-in.
        assert all(t["curated"] is False for t in cfg["taps"])

    def test_one_bad_spec_does_not_cost_the_others(self, boost,
                                                   fixture_tap_src):
        r = boost("tap", fixture_tap_src, "@@@garbage@@@", expect=1)
        assert "tapped fixture-tap (5 items)" in r.out
        assert "could not tap" in r.out + r.err
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert [t["name"] for t in cfg["taps"]] == ["fixture-tap"]

    def test_at_with_several_specs_is_a_usage_error(self, boost,
                                                    fixture_tap_src, tmp_path):
        # A pin names one commit, which cannot describe two repositories.
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        r = boost("tap", fixture_tap_src, str(second), "--at", "a" * 40,
                  expect=2)
        assert "exactly one SPEC" in r.err

    def test_duplicate_single_spec_skips_like_multi_spec(self, boost, tapped):
        # A single already-tapped SPEC used to error (rc=1) while the same
        # name inside a multi-SPEC call quietly skipped (rc=0) — the two
        # surfaces answered "already tapped?" two different ways. Both now
        # route through the same skip logic.
        r = boost("tap", tapped)  # rc=0 — boost() asserts the default
        assert "fixture-tap already tapped" in r.out

    def test_duplicate_with_at_still_errors(self, boost, tapped):
        # --at pins one commit; silently skipping an already-tapped repo would
        # leave it on whatever commit it already had, which is the exact
        # staleness a pin exists to prevent.
        r = boost("tap", tapped, "--at", "a" * 40, expect=1)
        assert "tap fixture-tap is already configured" in r.err
        # `boost update` skips a pinned tap and `--force` goes to HEAD, so
        # the hint names the one sequence that lands on the commit asked for.
        err = " ".join(r.err.split())
        assert "boost untap fixture-tap" in err
        assert "--at %s" % ("a" * 40) in err
        assert "boost update" not in err

    def test_untap_survives_a_nameless_config_row(self, boost, tapped):
        cfg = config.load()
        cfg["taps"].append({"url": "https://github.com/x/y"})
        config.save(cfg)
        boost("untap", "fixture-tap", "-f")
        assert config.load()["taps"] == [{"url": "https://github.com/x/y"}]

    def test_garbage_spec_rc1(self, boost, sandbox):
        r = boost("tap", "@@@garbage@@@", expect=1)
        assert "cannot parse tap spec" in r.err
        assert "owner/repo, a git URL, or a local directory" in r.err

    def test_no_args_rc2(self, boost, sandbox):
        r = boost("tap", expect=2)
        assert "provide a SPEC, --defaults, or --catalog" in r.err

    @pytest.mark.parametrize("extra, named", [
        (("--limit", "2"), "--limit only filters --catalog; pass --catalog "
                           "or drop it"),
        (("--include-lists",), "--include-lists only filters --catalog; "
                               "pass --catalog or drop it"),
        (("--type", "rule", "--category", "ui"),
         "--type/--category only filter --catalog; pass --catalog or drop "
         "them"),
    ])
    @pytest.mark.parametrize("target", [("--defaults",), ("someone/repo",)])
    def test_catalog_filters_without_catalog_rc2(self, boost, sandbox, extra,
                                                 named, target):
        # They used to be ignored: `tap --limit 2 --defaults` cloned all seven.
        r = boost("tap", "--dry-run", *extra, *target, expect=2)
        assert named in r.err
        assert r.out == ""

    def test_catalog_filters_with_catalog_are_accepted(self, boost, sandbox):
        r = boost("tap", "--catalog", "--dry-run", "--limit", "1")
        assert "dry run" in r.out

    def test_missing_local_path_names_the_directory_not_github(
            self, boost, sandbox, tmp_path):
        # A path-shaped SPEC that doesn't exist used to fall through to the
        # owner/repo branch, which cloned "https://github.com//tmp/.../nope"
        # instead of naming the local path that was actually wrong.
        missing = tmp_path / "nonexistent-dir"
        r = boost("tap", str(missing), expect=1)
        assert "no such directory: %s" % missing in r.err
        assert "github.com" not in r.err

    def test_existing_dir_without_git_names_the_real_problem(
            self, boost, sandbox, tmp_path):
        plain = tmp_path / "plain-skill-dir"
        plain.mkdir()
        (plain / "SKILL.md").write_text("---\nname: x\n---\nbody\n",
                                        encoding="utf-8")
        r = boost("tap", str(plain), expect=1)
        assert "is not a git repository" in r.err
        assert "git init" in r.err
        assert "boost import %s" % plain in r.err

    def test_defaults_offline_warns_rc1(self, boost, sandbox, monkeypatch):
        from boost_cli.core import registry
        from boost_cli.errors import BoostError

        def boom(url, dest):
            raise BoostError("network down")

        monkeypatch.setattr("boost_cli.core.gitutil.clone_shallow", boom)
        r = boost("tap", "--defaults", expect=1)
        assert "  ! could not tap anthropics/skills: network down\n" in r.err
        assert "  ! could not tap obra/superpowers: network down\n" in r.err
        assert "could not tap" not in r.out
        assert registry.list_taps() == []   # nothing half-added

    def test_defaults_success_then_already_tapped(self, boost, sandbox,
                                                  fixture_tap_src, monkeypatch):
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        r = boost("tap", "--defaults")
        assert ("tapped anthropics/skills (5 items) — "
                "Official Anthropic skills") in r.out
        assert ("tapped obra/superpowers (5 items) — "
                "Community powerhouse") in r.out
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert [t["name"] for t in cfg["taps"]] == [
            t["name"] for t in config.DEFAULT_TAPS]
        assert all(t["curated"] for t in cfg["taps"])
        r = boost("tap", "--defaults")           # idempotent second run
        assert "anthropics/skills already tapped" in r.out
        assert "obra/superpowers already tapped" in r.out

    def test_dry_run_single_spec_clones_nothing(self, boost, sandbox,
                                                monkeypatch):
        from boost_cli.core import registry

        def boom(url, dest):
            raise AssertionError("dry run must not clone")

        monkeypatch.setattr("boost_cli.core.gitutil.clone_shallow", boom)
        r = boost("tap", "--dry-run", "expo/skills")
        assert "expo/skills" in r.out
        assert "https://github.com/expo/skills" in r.out
        assert "dry run — nothing tapped" in r.out
        assert registry.list_taps() == []
        assert not paths.config_path().exists()

    def test_dry_run_multi_spec_clones_nothing(self, boost, sandbox,
                                               monkeypatch):
        from boost_cli.core import registry

        def boom(url, dest):
            raise AssertionError("dry run must not clone")

        monkeypatch.setattr("boost_cli.core.gitutil.clone_shallow", boom)
        r = boost("tap", "--dry-run", "expo/skills", "anthropics/skills")
        assert "expo/skills" in r.out
        assert "anthropics/skills" in r.out
        assert "2 registries" in r.out
        assert registry.list_taps() == []

    def test_dry_run_defaults_clones_nothing(self, boost, sandbox,
                                             monkeypatch):
        from boost_cli.core import registry

        def boom(url, dest):
            raise AssertionError("dry run must not clone")

        monkeypatch.setattr("boost_cli.core.gitutil.clone_shallow", boom)
        r = boost("tap", "--defaults", "--dry-run")
        assert "anthropics/skills" in r.out
        assert "%d registries" % len(config.DEFAULT_TAPS) in r.out
        assert "dry run — nothing tapped" in r.out
        assert registry.list_taps() == []


class TestTapCatalog:
    def test_dry_run_lists_without_tapping(self, boost, sandbox):
        from boost_cli.core import registry
        r = boost("tap", "--catalog", "--type", "skill", "--limit", "3", "--dry-run")
        assert "dry run — nothing tapped" in r.out
        assert "3 registries" in r.out
        assert registry.list_taps() == []

    def test_type_filter_restricts_selection(self, boost, sandbox):
        r = boost("tap", "--catalog", "--type", "rule", "--dry-run")
        # rule rows present, no skill/workflow rows in the type column
        assert "rule" in r.out
        assert "microsoft/skills" not in r.out

    def test_category_filter(self, boost, sandbox):
        r = boost("tap", "--catalog", "--type", "skill",
                  "--category", "security", "--dry-run")
        assert "jthack/ffuf_claude_skill" in r.out
        assert "microsoft/skills" not in r.out

    def test_empty_selection_rc1(self, boost, sandbox):
        r = boost("tap", "--catalog", "--category", "no-such-cat", "--dry-run",
                  expect=1)
        assert "no catalog registries match" in r.out

    def test_limit_must_be_positive_int(self, boost, sandbox):
        # --limit -1 used to silently drop the last registry (entries[:-1])
        # rather than being rejected as meaningless.
        r = boost("tap", "--catalog", "--limit", "-1", "--dry-run", expect=2)
        assert "must be >= 1" in r.err
        r = boost("tap", "--catalog", "--limit", "0", "--dry-run", expect=2)
        assert "must be >= 1" in r.err

    def test_real_tap_from_catalog(self, boost, sandbox, fixture_tap_src,
                                   monkeypatch):
        from boost_cli.core import registry
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        r = boost("tap", "--catalog", "--type", "skill", "--limit", "2")
        assert "tapped " in r.out and "items)" in r.out
        assert len(registry.list_taps()) == 2

    def test_catalog_tap_stars_only_curated_rows(self, boost, sandbox,
                                                 fixture_tap_src, monkeypatch):
        # One batch flag starred all 463 registries; the ★ must follow the
        # catalogue's own column, row by row.
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        boost("tap", "--catalog", "--type", "skill", "--limit", "12")
        want = {e["name"]: bool(e.get("curated"))
                for e in config.load_registry_catalog()}
        got = {t["name"]: t["curated"]
               for t in json.loads(paths.config_path().read_text(
                   encoding="utf-8"))["taps"]}
        assert got == {n: want[n] for n in got}
        assert set(got.values()) == {True, False}

    def test_catalog_tap_curated_flag_stars_everything(self, boost, sandbox,
                                                       fixture_tap_src,
                                                       monkeypatch):
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        boost("tap", "--catalog", "--type", "skill", "--limit", "12",
              "--curated")
        taps = json.loads(paths.config_path().read_text(
            encoding="utf-8"))["taps"]
        assert len(taps) == 12 and all(t["curated"] for t in taps)


# ── untap ────────────────────────────────────────────────────────────────

class TestUntap:
    def test_unknown_rc1(self, boost, sandbox):
        r = boost("untap", "nope", expect=1)
        # The reason for rc 1 is on stderr, where a script looks for it.
        assert r.err == "  ! could not untap nope: no such tap: nope\n"
        assert "could not untap" not in r.out

    def test_dependents_declined_keeps_tap(self, boost, installed, monkeypatch):
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("untap", "fixture-tap", expect=1)
        assert "1 installed item(s) from fixture-tap: brainstorming" in r.out
        assert "installed items keep working but lose their update source" in r.out
        assert "cancelled" in r.out
        # the tap survives: clone, cache, config all intact
        assert (paths.repos_dir() / "fixture-tap").is_dir()
        assert (paths.cache_dir() / "fixture-tap.json").is_file()
        assert "fixture-tap" in boost("taps").out

    def test_force_removes_clone_cache_config(self, boost, installed):
        clone = paths.repos_dir() / "fixture-tap"
        cache = paths.cache_dir() / "fixture-tap.json"
        assert clone.is_dir() and cache.is_file()
        r = boost("untap", "fixture-tap", "--force")
        assert "untapped fixture-tap" in r.out
        assert not clone.exists()
        assert not cache.exists()
        assert json.loads(paths.config_path().read_text(encoding="utf-8"))["taps"] == []

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="chmod can't make a directory unwritable on Windows")
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                        reason="root ignores mode bits")
    def test_a_cache_dir_it_cannot_write_is_a_warning(self, boost, tapped):
        # In a cache dir boost cannot write, untap exited 70 unlinking the
        # tap's cache file, after the tap was already deregistered.
        cache = paths.cache_dir() / "fixture-tap.json"
        paths.cache_dir().chmod(0o500)
        try:
            r = boost("untap", "fixture-tap")
        finally:
            paths.cache_dir().chmod(0o700)
        assert "untapped fixture-tap" in r.out
        assert "could not remove the catalog cache for fixture-tap " \
            "(Permission denied)" in " ".join(r.err.split())
        assert not list(paths.logs_dir().glob("crash-*.log"))
        assert "no taps configured" in boost("taps").out
        assert cache.is_file()
        boost("clean")                    # the leftover is a stale tap cache
        assert not cache.exists()

    def test_clean_untap_no_dependents(self, boost, tapped):
        r = boost("untap", "fixture-tap")
        assert "untapped fixture-tap" in r.out
        assert "item(s) from" not in r.out    # no dependents warning
        assert "no taps configured" in boost("taps").out

    def test_untap_warns_it_would_orphan_a_rule(self, boost, tapped,
                                                monkeypatch):
        # A rule materialized into CLAUDE.md from this tap is a dependent too:
        # before, untap counted only the skills section and dropped the rule's
        # update source without a word.
        from boost_cli.core import lockfile
        cm = paths.home() / ".claude" / "CLAUDE.md"
        cm.parent.mkdir(parents=True, exist_ok=True)
        cm.write_text("rule body", encoding="utf-8")
        lockfile.set_rule("house-style", {
            "kind": "rule", "version": "1.0.0", "tap": "fixture-tap",
            "materializations": [
                {"agent": "claude-code", "mode": "claude", "path": str(cm)}]})
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("untap", "fixture-tap", expect=1)
        assert "1 installed item(s) from fixture-tap: house-style (rule)" in r.out
        assert "cancelled" in r.out
        assert "fixture-tap" in boost("taps").out

    def test_several_names_untap_in_one_invocation(self, boost, fixture_tap_src,
                                                    tmp_path):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", fixture_tap_src)
        boost("tap", second)
        r = boost("untap", "fixture-tap", "second-tap")
        assert "untapped fixture-tap" in r.out
        assert "untapped second-tap" in r.out
        assert json.loads(paths.config_path().read_text(encoding="utf-8"))["taps"] == []
        assert "no taps configured" in boost("taps").out

    def test_one_unknown_name_does_not_cost_the_others(self, boost, tapped):
        r = boost("untap", "fixture-tap", "nope", expect=1)
        assert "untapped fixture-tap" in r.out
        assert "could not untap nope" in r.out + r.err
        assert "no such tap: nope" in r.out + r.err
        assert json.loads(paths.config_path().read_text(encoding="utf-8"))["taps"] == []

    def test_declined_dependent_does_not_cost_a_clean_tap(
            self, boost, installed, fixture_tap_src, tmp_path, monkeypatch):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", second)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("untap", "fixture-tap", "second-tap", expect=1)
        assert "1 installed item(s) from fixture-tap: brainstorming" in r.out
        assert "cancelled" in r.out
        assert "untapped second-tap" in r.out
        names = [t["name"] for t in
                 json.loads(paths.config_path().read_text(encoding="utf-8"))["taps"]]
        assert names == ["fixture-tap"]   # declined tap survives, clean one gone


# ── taps ─────────────────────────────────────────────────────────────────

class TestTaps:
    def test_table_footer_and_curated_star(self, boost, tapped,
                                           fixture_tap_src, tmp_path):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", second, "--curated")
        r = boost("taps")
        # "items", not "skills": a tap can carry rules and workflows too —
        # `cmd_tap` already prints "items" for the same count.
        assert "NAME" in r.out and "ITEMS" in r.out and "URL" in r.out
        assert "SKILLS" not in r.out
        assert "fixture-tap" in r.out
        assert "second-tap" in r.out
        assert "★" in r.out                       # curated marker
        assert "2 taps · 10 items" in r.out       # footer counts

    def test_json_pure(self, boost, tapped, fixture_tap_src, tmp_path):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", second, "--curated")
        r = boost("taps", "--json")
        data = json.loads(r.out)                  # pure JSON
        assert [t["name"] for t in data] == ["fixture-tap", "second-tap"]
        assert data[0]["url"] == str(fixture_tap_src.resolve())
        assert data[0]["curated"] is False
        assert data[1]["curated"] is True
        assert data[0]["items"] == 5
        assert data[1]["items"] == 5
        # "skills" stays as a deprecated alias so an existing JSON consumer
        # of `boost taps --json` does not break.
        assert data[0]["skills"] == 5
        assert data[1]["skills"] == 5
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", data[0]["updated"])
        # An unpinned tap reports null, not the empty-string sentinel a
        # machine consumer would have to know to treat as "unset".
        assert data[0]["pin"] is None

    def test_empty_state_hint(self, boost, sandbox):
        r = boost("taps")
        assert "no taps configured" in r.out
        assert "boost tap --defaults" in r.out

    def test_url_under_home_contracts_to_tilde(self, boost, sandbox,
                                               fixture_tap_src):
        shutil.copytree(fixture_tap_src, sandbox / "my-tap")
        boost("tap", sandbox / "my-tap")
        assert "~/my-tap" in boost("taps").out

    def test_a_missing_clone_is_marked_not_dated(self, boost, tapped):
        util.rmtree(paths.repos_dir() / "fixture-tap")   # clone gone
        r = boost("taps")
        # The row is served from the cached catalogue, so a date there would
        # vouch for a clone `boost doctor` reports missing on the same machine.
        row = next(ln for ln in r.out.splitlines() if "fixture-tap" in ln)
        assert "not cloned" in row
        assert not re.search(r"\d{4}-\d{2}-\d{2}", row)
        # Items still count — they are searchable from the cache — but the
        # footer says how many of the taps behind them have no clone.
        assert "1 tap · 5 items · 1 not cloned" in r.out
        assert "`boost update` clones it" in r.out
        # JSON keeps the machine facts: the raw ISO timestamp the cache
        # recorded, plus the clone state the table rendered.
        data = json.loads(boost("taps", "--json").out)
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", data[0]["updated"])
        assert data[0]["cloned"] is False
        (paths.cache_dir() / "fixture-tap.json").unlink()
        r = boost("taps")
        assert "1 tap · 0 items · 1 not cloned" in r.out
        assert json.loads(boost("taps", "--json").out)[0]["updated"] is None

    def test_a_cloned_tap_says_nothing_about_clones(self, boost, tapped):
        r = boost("taps")
        assert "not cloned" not in r.out
        assert "1 tap · 5 items\n" in r.out
        assert json.loads(boost("taps", "--json").out)[0]["cloned"] is True

    def test_a_pinned_tap_with_no_clone_is_not_said_to_be_skipped(
            self, boost, fixture_tap_src):
        # `registry.update` clones a missing pinned tap at its pin rather
        # than skipping it, so "@sha … skips it" would be false here.
        from boost_cli.core import gitutil
        head = gitutil.head_commit(fixture_tap_src)
        boost("tap", str(fixture_tap_src), "--at", head)
        util.rmtree(paths.repos_dir() / fixture_tap_src.name)
        r = boost("taps")
        assert "not cloned" in r.out
        assert "@%s" % head[:7] not in r.out
        assert "@sha = pinned" not in r.out

    def test_pinned_footer_hints_boost_update_skips_it(
            self, boost, fixture_tap_src):
        from boost_cli.core import gitutil
        head = gitutil.head_commit(fixture_tap_src)
        boost("tap", str(fixture_tap_src), "--at", head)
        r = boost("taps")
        assert "@%s" % head[:7] in r.out
        assert "@sha = pinned" in r.out
        assert "boost update` skips it" in r.out

    def test_no_pinned_footer_when_nothing_pinned(self, boost, tapped):
        r = boost("taps")
        assert "@sha = pinned" not in r.out


# ── outdated ─────────────────────────────────────────────────────────────

class TestOutdated:
    def test_clean_everything_up_to_date(self, boost, installed):
        r = boost("outdated")
        assert "everything up to date" in r.out
        assert json.loads(boost("outdated", "--json").out) == []

    def test_upstream_bump_pin_and_json(self, boost, fixture_tap_src, tmp_path):
        tap_dir = _copy_tap(fixture_tap_src, tmp_path / "bumped-tap")
        boost("tap", tap_dir)
        boost("install", "brainstorming")

        _bump(tap_dir, "brainstorming", "1.4.0", "1.5.0")
        r = boost("update", "--taps-only")
        assert "bumped-tap:" in r.out and "→" in r.out

        r = boost("outdated")                      # rc always 0
        assert "brainstorming" in r.out
        assert "1.4.0" in r.out and "1.5.0" in r.out
        assert "INSTALLED" in r.out and "LATEST" in r.out
        assert "1 outdated" in r.out
        assert "pinned and quarantined items stay put" in r.out

        boost("pin", "brainstorming")
        r = boost("outdated")
        assert "1.4.0 (pinned)" in r.out

        r = boost("outdated", "--json")
        assert json.loads(r.out) == [{"name": "brainstorming",
                                      "kind": "skill",
                                      "installed": "1.4.0",
                                      "latest": "1.5.0",
                                      "reason": "version",
                                      "latest_commit": None,
                                      "tap": "bumped-tap",
                                      "pinned": True,
                                      "scope": "user"}]

    def test_local_import_always_current(self, boost, sandbox, tmp_path):
        d = tmp_path / "loc"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: loc\ndescription: local skill\nversion: 0.1.0\n---\n\n"
            "# Loc\n", encoding="utf-8")
        boost("import", d)
        assert "everything up to date" in boost("outdated").out

    def test_untapped_source_reported(self, boost, installed):
        # Untapping the skill's own registry used to make it vanish from
        # `outdated` silently — a rule in the same state is reported as
        # "source missing" (see test_source_vanished_marker below), and a
        # skill should be too rather than being dropped from the table.
        boost("untap", "fixture-tap", "--force")
        r = boost("outdated")
        assert "source missing" in r.out
        assert "1 outdated" in r.out
        assert "can't restore a deleted tap" in r.out
        # The table still says "source missing"; the JSON says it in machine
        # fields. This row (an untapped registry) was added to `cmd_outdated`
        # after #769 branched, so the PR never converted it — leaving it on
        # the old shape would put a display string back in `latest` for the
        # one case, and hand `_outdated_display` a row with no `reason`.
        data = json.loads(boost("outdated", "--json").out)
        assert data == [{"name": "brainstorming", "kind": "skill",
                         "installed": "1.4.0", "latest": None,
                         "reason": staleness.SOURCE_MISSING,
                         "latest_commit": None,
                         "tap": "fixture-tap", "pinned": False, "scope": "user"}]

    def test_mixed_footer_splits_upstream_from_source_missing(
            self, boost, fixture_tap_src, tmp_path):
        # One row is a real upstream bump (boost update can fix it), the
        # other's tap is gone (boost update can't) — the footer must not
        # lump them into one "boost update upgrades" promise.
        bumped = _copy_tap(fixture_tap_src, tmp_path / "bumped-tap")
        gone = _copy_tap(fixture_tap_src, tmp_path / "gone-tap")
        boost("tap", bumped, gone)
        boost("install", "bumped-tap:brainstorming")
        boost("install", "gone-tap:jira-integration")

        _bump(bumped, "brainstorming", "1.4.0", "1.5.0")
        boost("update", "--taps-only")
        boost("untap", "gone-tap", "--force")

        r = boost("outdated")
        assert "2 outdated" in r.out
        assert "1 upstream" in r.out
        assert "1 source missing" in r.out

    def test_entry_dropped_after_update_is_removed_upstream(
            self, boost, fixture_tap_src, tmp_path):
        # The reported path: `boost update` rescans, the catalog no longer
        # lists the skill, and the footer used to say to re-tap a tap that
        # `boost taps` shows present and current.
        src = _copy_tap(fixture_tap_src, tmp_path / "drop-tap")
        boost("tap", src)
        boost("install", "brainstorming")
        subprocess.run(["git", "-C", str(src), "rm", "-rq",
                        "skills/brainstorming"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "commit", "-qm", "drop"],
                       check=True, capture_output=True)
        assert "no longer in tap" in boost("update").out
        r = boost("outdated")
        assert "1 outdated · removed upstream" in r.out
        assert "re-tap or" not in r.out
        # The LATEST cell names the same state the footer does; the JSON
        # keeps its machine reason unchanged.
        row = next(l for l in r.out.splitlines() if "brainstorming" in l)
        assert "removed upstream" in row
        assert "source missing" not in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert [(d["name"], d["reason"], d["latest"]) for d in data] == [
            ("brainstorming", staleness.SOURCE_MISSING, None)]

    def test_two_entries_dropped_upstream_read_in_the_plural(
            self, boost, fixture_tap_src, tmp_path):
        src = _copy_tap(fixture_tap_src, tmp_path / "drop2-tap")
        boost("tap", src)
        boost("install", "brainstorming")
        boost("install", "jira-integration")
        for d in ("skills/brainstorming", "skills/jira-integration"):
            subprocess.run(["git", "-C", str(src), "rm", "-rq", d],
                           check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "commit", "-qm", "drop"],
                       check=True, capture_output=True)
        boost("update")
        r = boost("outdated")
        assert ("2 outdated · removed upstream — `boost update` can't bring "
                "them back; `boost uninstall` them") in r.out

    def test_content_change_shows_head_commit(self, boost, installed):
        clone = paths.repos_dir() / "fixture-tap"
        md = clone / "skills" / "brainstorming" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nUpstream tweak, same version.\n", encoding="utf-8")
        head = _commit_clone(clone, "content tweak")
        r = boost("outdated")
        assert "1.4.0 (%s)" % head[:7] in r.out
        assert "1 outdated" in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert data == [{"name": "brainstorming", "kind": "skill",
                         "installed": "1.4.0", "latest": "1.4.0",
                         "reason": "content", "latest_commit": head[:7],
                         "tap": "fixture-tap", "pinned": False, "scope": "user"}]

    def test_source_vanished_marker(self, boost, installed):
        clone = paths.repos_dir() / "fixture-tap"
        shutil.rmtree(clone / "skills" / "brainstorming")
        _commit_clone(clone, "drop skill")       # cache still lists it
        r = boost("outdated")
        assert "1 outdated" in r.out
        # The tap is still configured, so re-tapping restores nothing: the
        # row and the footer both name the item as removed upstream, not the
        # tap as deleted (the JSON reason below stays source-missing).
        row = next(l for l in r.out.splitlines() if "brainstorming" in l)
        assert "removed upstream" in row
        assert "source missing" not in r.out
        assert "re-tap or" not in r.out
        assert "deleted tap" not in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert data == [{"name": "brainstorming", "kind": "skill",
                         "installed": "1.4.0", "latest": None,
                         "reason": "source-missing", "latest_commit": None,
                         "tap": "fixture-tap", "pinned": False, "scope": "user"}]

    def test_changed_rule_source_is_listed_with_kind(self, boost,
                                                     fixture_tap_src, tmp_path):
        # A rule whose tap source moved is outdated the same way a skill is —
        # it used to be invisible here because only the skills section was read.
        tap_dir = _copy_tap(fixture_tap_src, tmp_path / "rule-tap")
        rp = tap_dir / "rules" / "house.mdc"
        rp.parent.mkdir(parents=True)
        rp.write_text("---\nname: house-style\nversion: 1.0.0\n---\n\n"
                      "Two-space indents.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(tap_dir), "add", "-A"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tap_dir), "commit", "-qm", "add rule"],
                       check=True, capture_output=True)
        boost("tap", tap_dir)
        boost("install", "house-style")
        assert "everything up to date" in boost("outdated").out

        clone_rule = paths.repos_dir() / "rule-tap" / "rules" / "house.mdc"
        clone_rule.write_text("---\nname: house-style\nversion: 1.0.0\n---\n\n"
                              "Tabs, actually.\n", encoding="utf-8")
        r = boost("outdated")
        assert "house-style (rule)" in r.out
        assert "content changed" in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert data == [{"name": "house-style", "kind": "rule",
                         "installed": "1.0.0", "latest": "1.0.0",
                         "reason": "content", "latest_commit": None,
                         "tap": "rule-tap", "pinned": False, "scope": "user"}]


def _commit_all(repo, msg):
    """Stage and commit everything in a test-owned repo copy."""
    subprocess.run(["git", "-C", str(repo), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@boost.test",
                    "-c", "user.name=Boost Test", "commit", "-qm", msg],
                   check=True, capture_output=True)


_RULE = "---\nname: house-style\nversion: %s\n---\n\n%s\n"


@pytest.fixture()
def two_sources(fixture_tap_src, tmp_path):
    """Two different repos that both name themselves `reg`: the second ships
    an unrelated `brainstorming` (at a higher version) and `house-style`."""
    a = _copy_tap(fixture_tap_src, tmp_path / "a" / "reg")
    b = _copy_tap(fixture_tap_src, tmp_path / "b" / "reg")
    for repo, version, body in ((a, "1.0.0", "Two-space indents."),
                                (b, "2.0.0", "Something unrelated.")):
        rule = repo / "rules" / "house.mdc"
        rule.parent.mkdir(parents=True)
        rule.write_text(_RULE % (version, body), encoding="utf-8")
        _commit_all(repo, "add rule")
    (b / "skills" / "brainstorming" / "SKILL.md").write_text(
        "---\nname: brainstorming\ndescription: Totally different skill from "
        "another repo\nversion: 9.0.0\n---\n\nSomething unrelated.\n",
        encoding="utf-8")
    _commit_all(b, "unrelated skill")
    return a, b


class TestSourceIdentity:
    """A tap name re-pointed at another repository is not an upstream: the
    lock's recorded `tap_url` is compared against the configured tap, and a
    mismatch is reported, never upgraded implicitly (not even with --yes)."""

    def _retap_other(self, boost, two_sources):
        a, b = two_sources
        boost("tap", a)
        boost("install", "brainstorming")
        boost("install", "house-style")
        boost("untap", "reg", "--force")
        boost("tap", b)
        return a, b

    def test_outdated_reports_source_changed(self, boost, two_sources):
        self._retap_other(boost, two_sources)
        r = boost("outdated")
        rows = {l.split()[0]: l for l in r.out.splitlines()
                if l.startswith(("brainstorming", "house-style"))}
        assert "source changed" in rows["brainstorming"]
        assert "9.0.0" not in r.out
        assert "source changed" in rows["house-style"]
        assert ("2 outdated · 2 source changed (the tap now points at another "
                "repo; `boost reinstall` takes its copy)") in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert [(d["name"], d["kind"], d["reason"], d["latest"])
                for d in data] == [
            ("brainstorming", "skill", staleness.SOURCE_CHANGED, None),
            ("house-style", "rule", staleness.SOURCE_CHANGED, None)]

    def test_update_yes_never_replaces_the_installed_copy(self, boost,
                                                          two_sources):
        from boost_cli.core import lockfile, store
        a, _b = self._retap_other(boost, two_sources)
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        before = md.read_bytes()
        rule_sha = lockfile.installed_rules()["house-style"]["sha256"]
        r = boost("update", "--yes")
        assert "upgraded" not in r.out
        assert "tap reg now points at" in r.out
        assert "`boost reinstall brainstorming` takes the new" in r.out
        assert "`boost reinstall house-style` takes the new" in r.out
        assert "2 items held back" in r.out
        assert "everything up to date" not in r.out
        assert md.read_bytes() == before
        assert lockfile.get_skill("brainstorming")["tap_url"] == str(
            a.resolve())
        rule = lockfile.installed_rules()["house-style"]
        assert (rule["sha256"], rule["tap_url"]) == (rule_sha,
                                                      str(a.resolve()))

    def test_drift_names_the_changed_source(self, boost, two_sources):
        self._retap_other(boost, two_sources)
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert {(r["name"], r["status"], r["hint"]) for r in rows} == {
            ("brainstorming", "source-changed",
             "boost reinstall brainstorming to take the new source's copy, "
             "or re-tap the original"),
            ("house-style", "source-changed",
             "boost reinstall house-style to take the new source's copy, "
             "or re-tap the original")}

    def test_explicit_reinstall_takes_the_new_source(self, boost,
                                                     two_sources):
        from boost_cli.core import lockfile, store
        _a, b = self._retap_other(boost, two_sources)
        boost("reinstall", "brainstorming", "house-style")
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        assert "Totally different skill" in md.read_text(encoding="utf-8")
        assert lockfile.get_skill("brainstorming")["tap_url"] == str(
            b.resolve())
        assert "everything up to date" in boost("outdated").out

    def test_legacy_row_without_tap_url_keeps_old_behaviour(self, boost,
                                                            two_sources):
        # Only where nothing dates the tap either: a legacy row under a tap
        # row written before `added_at` cannot be told apart from its source
        # (TestLegacyRowSource covers a tap dated after the row).
        from boost_cli.core import lockfile
        self._retap_other(boost, two_sources)
        def drop_urls(lock):
            for section in ("skills", "rules"):
                for row in lock.get(section, {}).values():
                    row.pop("tap_url", None)
        lockfile.mutate(drop_urls)

        def undate(cfg):
            for row in cfg["taps"]:
                row.pop("added_at", None)
        config.mutate(undate)
        data = json.loads(boost("outdated", "--json").out)
        assert ("brainstorming", staleness.VERSION, "9.0.0") in [
            (d["name"], d["reason"], d["latest"]) for d in data]


def _legacy_rows():
    """Rows as a boost from before `tap_url` wrote them, dated well before
    any tap this test makes, and the tap rows as one from before `added_at`."""
    from boost_cli.core import lockfile

    def age(lock):
        for section in ("skills", "rules"):
            for row in lock[section].values():
                row.pop("tap_url", None)
                row["installed_at"] = row["updated_at"] = "2026-01-01T00:00:00Z"
    lockfile.mutate(age)

    def undate(cfg):
        for row in cfg["taps"]:
            row.pop("added_at", None)
    config.mutate(undate)


def _old_untap(name):
    """`boost untap` as an older boost ran it: the config row and the clone
    go, and nothing is recorded on the lock rows first."""
    def drop(cfg):
        cfg["taps"] = [t for t in cfg["taps"] if t["name"] != name]
    config.mutate(drop)
    util.rmtree(paths.repos_dir() / name)


class TestLegacyRowSource:
    """Lock rows written before `tap_url`: while the tap is configured its URL
    is in config.json, so sync, heal, update and untap record it; once a
    later tap took the name, the row reads as a source change."""

    @pytest.fixture()
    def legacy(self, boost, two_sources):
        from boost_cli.core import lockfile
        a, b = two_sources
        boost("tap", a)
        boost("install", "brainstorming")
        boost("install", "house-style")
        _legacy_rows()
        assert "tap_url" not in lockfile.get_skill("brainstorming")
        return a, b

    def _urls(self):
        from boost_cli.core import lockfile
        return (lockfile.get_skill("brainstorming").get("tap_url"),
                lockfile.installed_rules()["house-style"].get("tap_url"))

    def test_sync_records_the_configured_url(self, boost, legacy):
        a, _b = legacy
        r = boost("sync", "--diff")
        assert "would record the tap URL of 2 lock rows" in r.out
        assert self._urls() == (None, None)
        r = boost("sync")
        assert "recorded the tap URL of 2 lock rows" in r.out
        assert self._urls() == (str(a.resolve()),) * 2
        assert "tap URL" not in boost("sync").out

    def test_then_a_retap_of_another_repo_is_held_back(self, boost, legacy):
        from boost_cli.core import store
        _a, b = legacy
        boost("heal")
        boost("untap", "reg", "--force")
        boost("tap", b)
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        before = md.read_bytes()
        r = boost("update", "--yes")
        assert "upgraded" not in r.out
        assert "2 items held back" in r.out
        assert md.read_bytes() == before

    def test_untap_records_it_before_the_config_row_goes(self, boost,
                                                         legacy):
        a, _b = legacy
        boost("untap", "reg", "--force")
        assert self._urls() == (str(a.resolve()),) * 2

    def test_update_records_it_before_comparing(self, boost, legacy):
        a, _b = legacy
        boost("update")
        assert self._urls() == (str(a.resolve()),) * 2

    def test_a_retap_after_an_old_untap_is_a_source_change(self, boost,
                                                           legacy):
        from boost_cli.core import store
        _a, b = legacy
        _old_untap("reg")
        boost("tap", b)
        r = boost("outdated")
        rows = {l.split()[0]: l for l in r.out.splitlines()
                if l.startswith(("brainstorming", "house-style"))}
        assert "source changed" in rows["brainstorming"]
        assert "9.0.0" not in r.out
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        before = md.read_bytes()
        r = boost("update", "--yes")
        flat = " ".join(r.out.split())
        assert ("brainstorming: not updated — tap reg now points at %s, and "
                "was tapped again since it was installed, from a source it "
                "did not record; `boost reinstall brainstorming` takes the "
                "new source's copy" % paths.tilde(str(b.resolve())) in flat)
        assert "upgraded" not in r.out
        assert md.read_bytes() == before
        # Never stamped with the new tap's URL: that is not where it came from.
        assert "would record the tap URL" not in boost("sync", "--diff").out
        assert self._urls() == (None, None)

    def test_a_retap_of_the_same_unmoved_repo_is_not(self, boost, legacy):
        a, _b = legacy
        _old_untap("reg")
        boost("tap", a)
        r = boost("outdated")
        assert "source changed" not in r.out
        boost("sync")
        assert self._urls() == (str(a.resolve()),) * 2


class TestOutdatedNotCloned:
    """A configured tap whose clone is gone is `boost update`'s to fix, and
    `outdated` says so for every kind — not "removed upstream"."""

    def test_skill_and_workflow_read_not_cloned(self, boost, fixture_tap_src,
                                                tmp_path):
        src = _copy_tap(fixture_tap_src, tmp_path / "two")
        cmd = src / "commands" / "ship.md"
        cmd.parent.mkdir(parents=True)
        cmd.write_text("---\ndescription: Ship it\n---\n\nShip.\n",
                       encoding="utf-8")
        _commit_all(src, "add workflow")
        boost("tap", src)
        boost("install", "ship")
        boost("install", "brainstorming")
        util.rmtree(paths.repos_dir() / "two")
        r = boost("outdated")
        for name in ("brainstorming ", "ship (workflow)"):
            row = next(l for l in r.out.splitlines() if l.startswith(name))
            assert "not cloned" in row
        assert "removed upstream" not in r.out
        assert "2 outdated · 2 not cloned (`boost update` clones the tap)" \
            in r.out
        data = json.loads(boost("outdated", "--json").out)
        assert [(d["name"], d["kind"], d["reason"]) for d in data] == [
            ("brainstorming", "skill", staleness.NOT_CLONED),
            ("ship", "workflow", staleness.NOT_CLONED)]
        boost("update", "two")
        assert "everything up to date" in boost("outdated").out


# ── completion cache invalidation ───────────────────────────────────────

class TestCompletionCacheStaysFresh:
    """core/complete.py's module docstring promises the TAB-completion name
    cache is refreshed "after anything that changes the catalogue (tap,
    untap, update)" — these pin that promise against the commands that make
    it. Without the refresh call, `boost install <TAB>` silently drifts from
    whatever `boost taps` actually reports.
    """

    def test_tap_refreshes_the_completion_cache(self, boost, fixture_tap_src):
        from boost_cli.core import complete
        complete.refresh_names()          # snapshot before any tap: empty
        assert "brainstorming" not in complete._cached_names()
        boost("tap", fixture_tap_src)
        assert "brainstorming" in complete._cached_names()

    def test_untap_refreshes_the_completion_cache(self, boost, tapped):
        from boost_cli.core import complete
        complete.refresh_names()
        assert "brainstorming" in complete._cached_names()
        boost("untap", "fixture-tap", "--force")
        assert "brainstorming" not in complete._cached_names()
