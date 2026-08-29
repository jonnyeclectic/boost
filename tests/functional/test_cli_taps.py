# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Functional tests: tap / untap / taps / outdated (registry commands)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from boost_cli.core import config, paths, util


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
        assert "Tapped fixture-tap (5 items)" in r.out
        # real effects: clone, cache, config entry
        assert (paths.repos_dir() / "fixture-tap" / "SKILL.md").exists() is False
        assert (paths.repos_dir() / "fixture-tap" / "skills" /
                "brainstorming" / "SKILL.md").is_file()
        assert (paths.cache_dir() / "fixture-tap.json").is_file()
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert cfg["taps"][0]["name"] == "fixture-tap"
        assert cfg["taps"][0]["curated"] is False

    def test_duplicate_rc1_with_hint(self, boost, tapped):
        r = boost("tap", tapped, expect=1)
        assert "tap fixture-tap is already configured" in r.err
        assert "boost update fixture-tap" in r.err  # the hint

    def test_garbage_spec_rc1(self, boost, sandbox):
        r = boost("tap", "@@@garbage@@@", expect=1)
        assert "cannot parse tap spec" in r.err
        assert "owner/repo, a git URL, or a local directory" in r.err

    def test_no_args_rc2(self, boost, sandbox):
        r = boost("tap", expect=2)
        assert "provide a SPEC, --defaults, or --catalog" in r.err

    def test_defaults_offline_warns_rc1(self, boost, sandbox, monkeypatch):
        from boost_cli.core import registry
        from boost_cli.errors import BoostError

        def boom(url, dest):
            raise BoostError("network down")

        monkeypatch.setattr("boost_cli.core.gitutil.clone_shallow", boom)
        r = boost("tap", "--defaults", expect=1)
        assert "could not tap anthropics/skills: network down" in r.out
        assert "could not tap obra/superpowers: network down" in r.out
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

    def test_real_tap_from_catalog(self, boost, sandbox, fixture_tap_src,
                                   monkeypatch):
        from boost_cli.core import registry
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        r = boost("tap", "--catalog", "--type", "skill", "--limit", "2")
        assert "tapped " in r.out and "items)" in r.out
        assert len(registry.list_taps()) == 2


# ── untap ────────────────────────────────────────────────────────────────

class TestUntap:
    def test_unknown_rc1(self, boost, sandbox):
        r = boost("untap", "nope", expect=1)
        assert "no such tap: nope" in r.err
        assert "boost taps" in r.err

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


# ── taps ─────────────────────────────────────────────────────────────────

class TestTaps:
    def test_table_footer_and_curated_star(self, boost, tapped,
                                           fixture_tap_src, tmp_path):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", second, "--curated")
        r = boost("taps")
        assert "NAME" in r.out and "SKILLS" in r.out and "URL" in r.out
        assert "fixture-tap" in r.out
        assert "second-tap" in r.out
        assert "★" in r.out                       # curated marker
        assert "2 taps · 10 skills" in r.out      # footer counts

    def test_json_pure(self, boost, tapped, fixture_tap_src, tmp_path):
        second = _copy_tap(fixture_tap_src, tmp_path / "second-tap")
        boost("tap", second, "--curated")
        r = boost("taps", "--json")
        data = json.loads(r.out)                  # pure JSON
        assert [t["name"] for t in data] == ["fixture-tap", "second-tap"]
        assert data[0]["url"] == str(fixture_tap_src.resolve())
        assert data[0]["curated"] is False
        assert data[1]["curated"] is True
        assert data[0]["skills"] == 5
        assert data[1]["skills"] == 5
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", data[0]["updated"])

    def test_empty_state_hint(self, boost, sandbox):
        r = boost("taps")
        assert "no taps configured" in r.out
        assert "boost tap --defaults" in r.out

    def test_url_under_home_contracts_to_tilde(self, boost, sandbox,
                                               fixture_tap_src):
        shutil.copytree(fixture_tap_src, sandbox / "my-tap")
        boost("tap", sandbox / "my-tap")
        assert "~/my-tap" in boost("taps").out

    def test_updated_from_cache_then_unknown(self, boost, tapped):
        util.rmtree(paths.repos_dir() / "fixture-tap")   # clone gone
        r = boost("taps")
        assert "ago" in r.out                    # cache 'generated' age
        assert "1 taps · 5 skills" in r.out      # skills still from the cache
        (paths.cache_dir() / "fixture-tap.json").unlink()
        r = boost("taps")
        assert "?" in r.out                      # no clone, no cache
        assert "1 taps · 0 skills" in r.out


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
        assert "pinned items stay put" in r.out

        boost("pin", "brainstorming")
        r = boost("outdated")
        assert "1.4.0 (pinned)" in r.out

        r = boost("outdated", "--json")
        assert json.loads(r.out) == [{"name": "brainstorming",
                                      "kind": "skill",
                                      "installed": "1.4.0",
                                      "latest": "1.5.0",
                                      "tap": "bumped-tap",
                                      "pinned": True}]

    def test_local_import_always_current(self, boost, sandbox, tmp_path):
        d = tmp_path / "loc"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: loc\ndescription: local skill\nversion: 0.1.0\n---\n\n"
            "# Loc\n", encoding="utf-8")
        boost("import", d)
        assert "everything up to date" in boost("outdated").out

    def test_untapped_source_skipped(self, boost, installed):
        boost("untap", "fixture-tap", "--force")
        assert "everything up to date" in boost("outdated").out

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
                         "installed": "1.4.0",
                         "latest": "1.4.0 (%s)" % head[:7],
                         "tap": "fixture-tap", "pinned": False}]

    def test_source_vanished_marker(self, boost, installed):
        clone = paths.repos_dir() / "fixture-tap"
        shutil.rmtree(clone / "skills" / "brainstorming")
        _commit_clone(clone, "drop skill")       # cache still lists it
        r = boost("outdated")
        assert "source missing" in r.out
        assert "1 outdated" in r.out

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
                         "installed": "1.0.0",
                         "latest": "1.0.0 (content changed)",
                         "tap": "rule-tap", "pinned": False}]


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
