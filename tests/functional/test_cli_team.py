# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: Team & Collaboration commands, in-process.

cohort / profile / protocol / pulse / replay / who — deterministic rollout
hashing, profile switching, boost:// URLs, the journal feed, and lock-history
rollback (with a ticking fake clock so every write gets its own snapshot).
"""
from __future__ import annotations

import getpass
import hashlib
import json
import shutil
import stat
import sys

import pytest

from boost_cli.core import journal, lockfile, paths

USER = getpass.getuser()


def _member(cohort: str, percent: int) -> bool:
    """Reference implementation of the deterministic membership hash."""
    digest = hashlib.sha256(("%s:%s" % (USER, cohort)).encode()).hexdigest()
    return int(digest, 16) % 100 < percent


def _seed_rule(name="house-style", tap="rule-tap"):
    """A materialized rule in the lock, without a real tap behind it."""
    from boost_cli.core import rules
    cm = paths.home() / ".claude" / "CLAUDE.md"
    cm.parent.mkdir(parents=True, exist_ok=True)
    cm.write_text(rules.merge_block("", name, "Do the thing."), encoding="utf-8")
    lockfile.set_rule(name, {
        "kind": "rule", "version": "1.0.0", "tap": tap,
        "installed_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "materializations": [
            {"agent": "claude-code", "mode": "claude", "path": str(cm)}]})
    return cm


@pytest.fixture()
def tick_clock(monkeypatch):
    """Monotonic fake now_iso() so each lock write snapshots separately."""
    counter = {"n": 0}

    def fake_now():
        counter["n"] += 1
        return "2026-07-16T%02d:%02d:%02dZ" % (
            counter["n"] // 3600, counter["n"] // 60 % 60, counter["n"] % 60)

    monkeypatch.setattr("boost_cli.core.util.now_iso", fake_now)
    return fake_now


# ---------------------------------------------------------------- cohort

class TestCohort:
    def test_create_full_rollout_warns_on_unknown_skill(self, boost, tapped):
        r = boost("cohort", "create", "pilot",
                 "--skills", "brainstorming,ghost-skill", "--percent", "100")
        assert "skill 'ghost-skill' not found in any tap (kept anyway)" in r.out
        assert ("created cohort pilot (100% rollout, 2 skills) — "
                "you are IN") in r.out

    def test_create_singular_skill_agrees(self, boost, tapped):
        r = boost("cohort", "create", "solo",
                 "--skills", "brainstorming", "--percent", "100")
        assert ("created cohort solo (100% rollout, 1 skill) — "
                "you are IN") in r.out

    def test_list_membership_column_and_json_determinism(self, boost, tapped):
        boost("cohort", "create", "pilot", "--skills", "brainstorming",
             "--percent", "100")
        boost("cohort", "create", "zero", "--skills", "brainstorming",
             "--percent", "0")
        r = boost("cohort", "list")
        pilot = next(l for l in r.out.splitlines() if l.startswith("pilot"))
        zero = next(l for l in r.out.splitlines() if l.startswith("zero"))
        assert "100%" in pilot and "IN" in pilot
        assert "0%" in zero and "out" in zero
        assert "membership = sha256(user:cohort)" in r.out

        one = boost("cohort", "list", "--json")
        two = boost("cohort", "list", "--json")
        assert one.out == two.out  # deterministic across calls
        data = json.loads(one.out)
        assert data == [
            {"name": "pilot", "skills": ["brainstorming"], "percent": 100,
             "member": True, "created": data[0]["created"]},
            {"name": "zero", "skills": ["brainstorming"], "percent": 0,
             "member": False, "created": data[1]["created"]}]
        assert data[0]["member"] == _member("pilot", 100)
        assert data[1]["member"] == _member("zero", 0)

    def test_no_literal_double_percent_reaches_the_terminal(self, boost, tapped):
        """`%%` is printf escaping, and neither of these two strings is ever
        %-formatted — so both reached the terminal verbatim as `%%`. The
        membership assertion above stops one character short of the listing's
        occurrence, which is how it survived.
        """
        boost("cohort", "create", "pilot", "--skills", "brainstorming",
             "--percent", "50")
        listing = boost("cohort", "list")
        assert "%%" not in listing.out
        assert "sha256(user:cohort) % 100 < rollout" in listing.out

        helptext = boost("cohort", "--help")
        assert "%%" not in helptext.out
        assert "a 50% rollout" in helptext.out

    def test_zero_percent_creates_out_and_apply_skips(self, boost, tapped):
        r = boost("cohort", "create", "zero", "--skills", "brainstorming",
                 "--percent", "0")
        assert "you are OUT" in r.out
        r = boost("cohort", "apply", "zero")
        assert "zero: not in the 0% rollout — skipping" in r.out
        assert "applied: 0 installed, 0 already present" in r.out
        assert not (paths.store_dir() / "brainstorming").exists()

    def test_apply_installs_then_reports_already_installed(self, boost, tapped):
        boost("cohort", "create", "pilot",
             "--skills", "brainstorming,ghost-skill", "--percent", "100")
        r = boost("cohort", "apply", "pilot")
        assert "cohort pilot" in r.out
        assert "installed brainstorming → claude-code · windsurf · cursor" in r.out
        assert "ghost-skill not found in any tap — skipped" in r.out
        assert "applied: 1 installed, 0 already present" in r.out
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

        r = boost("cohort", "apply")  # no name -> all cohorts
        assert "brainstorming already installed" in r.out
        assert "applied: 0 installed, 1 already present" in r.out

    def test_apply_does_not_reinstall_an_installed_rule(self, boost, tapped):
        # Membership checks the whole lock: a cohort item installed as a RULE
        # used to fail the skills-section check and get re-installed per apply.
        _seed_rule("house-style")
        boost("cohort", "create", "pilot", "--skills", "house-style",
             "--percent", "100")
        r = boost("cohort", "apply", "pilot")
        assert "house-style (rule) already installed" in r.out
        assert "applied: 0 installed, 1 already present" in r.out
        assert not (paths.store_dir() / "house-style").exists()

    def test_delete_declined_then_confirmed(self, boost, tapped, monkeypatch):
        boost("cohort", "create", "pilot", "--skills", "brainstorming")
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("cohort", "delete", "pilot", expect=1)
        assert "cancelled" in r.out
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        assert "pilot" in boost("cohort", "list").out  # survived the decline
        r = boost("cohort", "delete", "pilot")
        assert "deleted cohort pilot" in r.out
        assert "no cohorts defined" in boost("cohort", "list").out

    def test_errors_and_edge_cases(self, boost, tapped):
        r = boost("cohort", "create", "bad", "--skills", "x",
                 "--percent", "101", expect=2)
        assert "--percent must be 0-100" in r.err
        r = boost("cohort", "create", "bad", expect=2)
        assert "create needs --skills" in r.err
        r = boost("cohort", "delete", "ghost", expect=1)
        assert "no cohort named ghost" in r.err
        r = boost("cohort", "apply", "ghost", expect=1)
        assert "no cohort named ghost" in r.err
        r = boost("cohort", "apply")
        assert "no cohorts defined" in r.out

    def test_empty_listing_hint_wraps_and_keeps_the_command_atomic(
            self, boost, tapped, monkeypatch):
        # The hint's backtick-quoted command is 62 columns by itself — wider
        # than a 60-column pane even alone, so it is the one line allowed to
        # overflow whole (out.wrap's documented law: an atomic token wider
        # than the line is emitted whole rather than split). What must be
        # true is: the message no longer runs 76 columns unwrapped, "no
        # cohorts defined" still wraps onto its own short line, and the
        # command is intact on one physical line rather than split in half.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("cohort", "list")
        lines = r.out.split("\n")
        assert any(ln.strip() == "○ no cohorts defined" for ln in lines)
        cmd = "`boost cohort create pilot --skills tdd-workflow --percent 50`"
        assert any(cmd in ln for ln in lines)
        # every OTHER line — i.e. not the one carrying the unbreakable
        # command — still fits the pane
        assert all(len(ln) <= 60 for ln in lines if cmd not in ln)


# ---------------------------------------------------------------- profile

class TestProfile:
    def test_save_show_diff_use_lifecycle(self, boost, tapped):
        boost("install", "brainstorming")
        boost("install", "tdd-workflow")
        r = boost("profile", "save", "daily")
        assert "saved profile daily (2 skills)" in r.out
        r = boost("profile", "list")
        assert "daily" in r.out and "2" in r.out
        r = boost("profile", "show", "daily")
        assert "profile daily" in r.out
        assert "brainstorming" in r.out and "1.4.0" in r.out
        assert "tdd-workflow" in r.out and "3.0.1" in r.out
        r = boost("profile", "diff", "daily")
        assert "current setup matches profile daily" in r.out

        boost("uninstall", "tdd-workflow")
        r = boost("profile", "diff", "daily")
        assert "+ tdd-workflow" in r.out
        assert "(in profile, not installed)" in r.out
        r = boost("profile", "diff", "daily", "--json")
        assert json.loads(r.out) == {"missing": ["tdd-workflow"],
                                     "extras": [], "changed": [],
                                     "other_kind": {}}

        r = boost("profile", "use", "daily")
        assert "installed tdd-workflow → claude-code · windsurf · cursor" in r.out
        assert "switched to profile daily" in r.out
        assert "tdd-workflow" in json.loads(
            paths.lockfile_path().read_text(encoding="utf-8"))["skills"]

    def test_use_sidelines_then_prune_uninstalls_extras(self, boost, tapped):
        boost("install", "brainstorming")
        boost("profile", "save", "solo")
        boost("install", "cowboy-coding")
        r = boost("profile", "diff", "solo")
        assert "- cowboy-coding" in r.out
        assert "(installed, not in profile)" in r.out

        r = boost("profile", "use", "solo")
        assert ("sidelined 1 skill not in the profile (unlinked, still "
                "installed): cowboy-coding") in r.out
        link = paths.home() / ".claude" / "skills" / "cowboy-coding"
        assert not link.exists()
        assert (paths.store_dir() / "cowboy-coding").is_dir()

        r = boost("profile", "use", "solo", "--prune")
        assert "uninstalled cowboy-coding" in r.out
        assert not (paths.store_dir() / "cowboy-coding").exists()
        assert "cowboy-coding" not in json.loads(
            paths.lockfile_path().read_text(encoding="utf-8"))["skills"]

    def test_version_drift_shows_changed(self, boost, installed):
        boost("profile", "save", "pin")
        p = paths.lockfile_path()
        lock = json.loads(p.read_text(encoding="utf-8"))
        lock["skills"]["brainstorming"]["version"] = "0.9.0"
        p.write_text(json.dumps(lock), encoding="utf-8")
        r = boost("profile", "diff", "pin")
        assert "~ brainstorming" in r.out and "(version differs)" in r.out
        r = boost("profile", "diff", "pin", "--json")
        assert json.loads(r.out) == {"missing": [], "extras": [],
                                     "changed": ["brainstorming"],
                                     "other_kind": {}}

    def test_save_notes_uncaptured_rules_and_workflows(self, boost, installed):
        # Profiles carry skills only — with a rule and workflow installed the
        # save must say so out loud, not silently drop them from the snapshot.
        _seed_rule("house-style")
        lockfile.set_workflow("ship-it", {
            "kind": "workflow", "version": "1.0.0", "tap": "rule-tap",
            "slot": "commands", "materializations": []})
        r = boost("profile", "save", "daily")
        assert "saved profile daily (1 skill)" in r.out
        assert ("1 rule and 1 workflow not captured — profiles carry "
                "skills only") in r.out

    def test_diff_and_use_see_a_name_installed_as_a_rule(self, boost, installed):
        # A profile can hold a name that is installed as a RULE today (saved
        # before the item changed kind upstream). diff must not report it as a
        # missing skill, and use must not install a skill over it.
        boost("profile", "save", "daily")
        boost("uninstall", "brainstorming")
        _seed_rule("brainstorming")
        r = boost("profile", "diff", "daily")
        assert ("(in profile, installed as a rule — profiles carry skills "
                "only)") in r.out
        assert "(in profile, not installed)" not in r.out
        r = boost("profile", "diff", "daily", "--json")
        assert json.loads(r.out) == {"missing": [], "extras": [], "changed": [],
                                     "other_kind": {"brainstorming": "rule"}}
        r = boost("profile", "use", "daily")
        assert ("brainstorming is installed as a rule — profiles carry skills "
                "only, leaving it as-is") in r.out
        assert "installed brainstorming" not in r.out
        assert lockfile.get_skill("brainstorming") is None
        assert lockfile.get_rule("brainstorming")["version"] == "1.0.0"

    def test_delete_and_unknown(self, boost, installed):
        boost("profile", "save", "gone")
        r = boost("profile", "delete", "gone")
        assert "deleted profile gone" in r.out
        r = boost("profile", "show", "gone", expect=1)
        assert "no profile named gone" in r.err
        r = boost("profile", "list")
        assert "no profiles saved" in r.out
        r = boost("profile", "show", expect=2)
        assert "show needs a profile NAME" in r.err

    def test_list_and_show_json(self, boost, installed):
        boost("profile", "save", "daily")
        r = boost("profile", "list", "--json")
        data = json.loads(r.out)
        assert len(data) == 1
        assert data[0]["name"] == "daily" and data[0]["skills"] == 1
        r = boost("profile", "show", "daily", "--json")
        prof = json.loads(r.out)
        assert prof["skills"]["brainstorming"] == {"tap": "fixture-tap",
                                                   "version": "1.4.0"}
        assert prof["user"] == USER


# ---------------------------------------------------------------- protocol

class TestProtocol:
    def test_status_lists_url_forms(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.team.platform.system",
                            lambda: "Darwin")
        r = boost("protocol", "status")
        assert "Darwin" in r.out
        assert "not registered" in r.out
        # One form per row now, not a `·`-joined run: the run was 100 columns
        # and wrapping it stranded a bare `·` at the start of a line.
        for form in ("boost://install/<skill>", "boost://install/<tap>:<skill>",
                     "boost://tap/<owner>/<repo>"):
            assert form in r.out
        assert "·" not in r.out
        assert "try it: boost protocol open boost://install/brainstorming" in r.out

    def test_open_installs(self, boost, tapped):
        r = boost("protocol", "open", "boost://install/brainstorming")
        assert "copied to" in r.out
        assert "linked → claude-code · windsurf · cursor · antigravity" in r.out
        assert "lock updated (.skill-lock.json)" in r.out
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_open_qualified_tap_skill(self, boost, tapped):
        boost("protocol", "open", "boost://install/fixture-tap:brainstorming")
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").is_file()

    def test_bad_urls(self, boost, tapped):
        r = boost("protocol", "open", "http://x/y", expect=1)
        assert "not a boost:// URL" in r.err
        r = boost("protocol", "open", "boost://frobnicate/x", expect=1)
        assert "cannot parse boost://frobnicate/x" in r.err
        assert "boost://install/<tap>:<skill>" in r.err
        r = boost("protocol", "open", "boost://install/", expect=1)
        assert "cannot parse boost://install/" in r.err
        r = boost("protocol", "open", expect=2)
        assert "open needs a boost:// URL" in r.err

    def test_declined_install_and_tap(self, boost, tapped, monkeypatch):
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("protocol", "open", "boost://install/brainstorming", expect=1)
        assert "cancelled" in r.out
        assert not (paths.store_dir() / "brainstorming").exists()
        r = boost("protocol", "open", "boost://tap/owner/repo", expect=1)
        assert "cancelled" in r.out

    def test_open_tap_refreshes_the_completion_cache(self, boost, sandbox,
                                                      fixture_tap_src,
                                                      monkeypatch):
        from boost_cli.core import complete
        monkeypatch.setattr(
            "boost_cli.core.gitutil.clone_shallow",
            lambda url, dest: shutil.copytree(fixture_tap_src, dest))
        complete.refresh_names()
        assert "brainstorming" not in complete._cached_names()
        r = boost("protocol", "open", "boost://tap/owner/repo")
        assert "tapped owner/repo" in r.out
        assert "brainstorming" in complete._cached_names()

    def test_register_unregister_darwin(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.team.platform.system",
                            lambda: "Darwin")
        monkeypatch.setattr("boost_cli.core.paths.shutil.which",
                            lambda c: None)
        r = boost("protocol", "register")
        script = paths.state_dir() / "boost-protocol-handler.sh"
        assert "wrote handler script ~/.boost/state/boost-protocol-handler.sh" in r.out
        if sys.platform != "win32":
            # Windows filesystems have no POSIX exec bit for chmod to set.
            assert script.stat().st_mode & stat.S_IEXEC
        body = script.read_text(encoding="utf-8")
        assert 'protocol open "$1"' in body
        assert str(paths.repo_root() / "boost") in body
        assert "Automator" in r.out  # macOS guidance
        r = boost("protocol", "status")
        assert "~/.boost/state/boost-protocol-handler.sh" in r.out

        r = boost("protocol", "unregister")
        assert "removed ~/.boost/state/boost-protocol-handler.sh" in r.out
        assert not script.exists()
        r = boost("protocol", "unregister")
        assert "nothing registered" in r.out
        assert "not registered" in boost("protocol", "status").out

    def test_register_linux_and_other(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.team.platform.system",
                            lambda: "Linux")
        monkeypatch.setattr("boost_cli.commands.team.shutil.which",
                            lambda c: None)
        r = boost("protocol", "register")
        desktop = (paths.home() / ".local" / "share" / "applications" /
                   "boost-protocol.desktop")
        assert desktop.exists()
        assert "x-scheme-handler/boost" in desktop.read_text(encoding="utf-8")
        assert "xdg-mime not found — handler written but not registered" in r.out
        r = boost("protocol", "status")
        assert "boost-protocol.desktop" in r.out
        boost("protocol", "unregister")
        assert not desktop.exists()

        monkeypatch.setattr("boost_cli.commands.team.platform.system",
                            lambda: "Windows")
        r = boost("protocol", "register")
        assert "no automatic registration on Windows" in r.out


# ---------------------------------------------------------------- pulse

class TestPulse:
    def test_empty_journal(self, boost, sandbox):
        r = boost("pulse")
        assert ("no activity yet — events appear as you install and manage "
                "skills") in r.out

    def test_empty_journal_fits_a_narrow_pane(self, boost, sandbox,
                                              monkeypatch):
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("pulse")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln

    def test_feed_newest_first_with_user(self, boost, installed):
        r = boost("pulse")
        rows = [l for l in r.out.splitlines() if USER in l]
        assert len(rows) == 2
        assert "install" in rows[0] and "brainstorming" in rows[0]
        assert "tap" in rows[1] and "fixture-tap" in rows[1]
        assert "tap=fixture-tap version=1.4.0" in rows[0]  # extras rendered
        assert "local journal · share it with your team via `boost onboard`" in r.out

    def test_limit_and_action_filter(self, boost, installed):
        r = boost("pulse", "-n", "1")
        rows = [l for l in r.out.splitlines() if USER in l]
        assert len(rows) == 1 and "install" in rows[0]
        r = boost("pulse", "--action", "tap")
        rows = [l for l in r.out.splitlines() if USER in l]
        assert len(rows) == 1 and "fixture-tap" in rows[0]

    def test_negative_or_zero_limit_rejected(self, boost, installed):
        r = boost("pulse", "-n", "-1", expect=2)
        assert "argument -n: must be >= 1" in r.err
        r = boost("pulse", "-n", "0", expect=2)
        assert "argument -n: must be >= 1" in r.err

    def test_json_purity(self, boost, installed):
        r = boost("pulse", "--json")
        events = json.loads(r.out)
        assert len(events) == 2
        assert events[0]["action"] == "install"
        assert events[0]["subject"] == "brainstorming"
        assert events[0]["user"] == USER
        assert events[0]["tap"] == "fixture-tap"
        assert events[0]["version"] == "1.4.0"
        assert events[1]["action"] == "tap"
        assert events[1]["subject"] == "fixture-tap"


# ---------------------------------------------------------------- replay

def _history_ops(boost):
    """tap + 4 lock writes -> 3 snapshots (first write has no predecessor)."""
    boost("install", "brainstorming")
    boost("install", "tdd-workflow")      # snapshot: {brainstorming}
    boost("uninstall", "brainstorming")   # snapshot: {brainstorming, tdd}
    boost("install", "cowboy-coding")     # snapshot: {tdd}


class TestReplay:
    def test_list_shows_deltas(self, boost, tapped, tick_clock):
        _history_ops(boost)
        history = lockfile.history_list()
        assert [h["count"] for h in history] == [1, 2, 1]
        r = boost("replay", "list")
        rows = [l for l in r.out.splitlines()
                if any(l.startswith(h["id"]) for h in history)]
        assert len(rows) == 3
        # newest first: {tdd} (-1), {b,tdd} (+1), {b} (no predecessor)
        assert rows[0].startswith(history[2]["id"]) and "-1" in rows[0]
        assert rows[1].startswith(history[1]["id"]) and "+1" in rows[1]
        assert rows[2].startswith(history[0]["id"])
        assert "+1" not in rows[2] and "-1" not in rows[2]
        r = boost("replay", "list", "--json")
        assert [h["count"] for h in json.loads(r.out)] == [1, 2, 1]

    def test_show_diff_vs_current(self, boost, tapped, tick_clock):
        _history_ops(boost)
        snap_id = lockfile.history_list()[1]["id"]  # {brainstorming, tdd}
        r = boost("replay", "show", snap_id)
        assert "+ cowboy-coding" in r.out and "added since" in r.out
        assert "- brainstorming" in r.out and "removed since" in r.out
        r = boost("replay", "show", snap_id, "--json")
        assert json.loads(r.out) == {"id": snap_id, "since_snapshot": {
            "added": ["cowboy-coding"], "removed": ["brainstorming"],
            "changed": [],
            "rules": {"added": [], "removed": [], "changed": []},
            "workflows": {"added": [], "removed": [], "changed": []}}}

    def test_rollback_restores_and_removes(self, boost, tapped, tick_clock):
        _history_ops(boost)
        snap_id = lockfile.history_list()[1]["id"]
        r = boost("replay", "rollback", snap_id)
        assert "uninstall 1, install 1" in r.out
        assert "uninstalled cowboy-coding" in r.out
        assert "restored brainstorming → claude-code · windsurf · cursor" in r.out
        assert "rollback to %s complete" % snap_id in r.out
        skills = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))["skills"]
        assert sorted(skills) == ["brainstorming", "tdd-workflow"]
        assert (paths.store_dir() / "brainstorming").is_dir()
        assert not (paths.store_dir() / "cowboy-coding").exists()
        ev = journal.events(action="replay")[0]
        assert ev["subject"] == snap_id and ev["op"] == "rollback"

        r = boost("replay", "rollback", snap_id)
        assert "already at this snapshot — nothing to do" in r.out

    def test_rollback_declined(self, boost, tapped, tick_clock, monkeypatch):
        _history_ops(boost)
        snap_id = lockfile.history_list()[1]["id"]
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("replay", "rollback", snap_id, expect=1)
        assert "cancelled" in r.out
        assert "cowboy-coding" in json.loads(
            paths.lockfile_path().read_text(encoding="utf-8"))["skills"]

    def test_rollback_skill_gone_from_taps(self, boost, tapped, tick_clock):
        boost("install", "brainstorming")
        boost("install", "tdd-workflow")
        boost("uninstall", "brainstorming")  # snapshot holds both
        snap_id = lockfile.history_list()[-1]["id"]
        boost("untap", "fixture-tap", "--force")
        r = boost("replay", "rollback", snap_id)
        assert "brainstorming is gone from every tap — cannot restore" in r.out

    def test_unknown_and_missing_id(self, boost, sandbox):
        r = boost("replay", "show", "99999999", expect=1)
        assert "no lock history entry 99999999" in r.err
        r = boost("replay", "show", expect=2)
        assert "show needs a history ID" in r.err
        r = boost("replay", "list")
        assert "no lock history yet" in r.out

    def test_empty_history_fits_a_narrow_pane(self, boost, sandbox,
                                              monkeypatch):
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("replay", "list")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln

    def test_diffs_cover_rules_with_kind_labels(self, boost, tapped,
                                                tick_clock):
        # Snapshots hold all three lock sections; a rule that appeared since
        # the snapshot is a labeled difference, and rollback names it as out
        # of its reach instead of claiming "already at this snapshot".
        boost("install", "brainstorming")     # first write: no snapshot yet
        _seed_rule("house-style")             # snapshots the skills-only lock
        snap_id = lockfile.history_list()[0]["id"]

        r = boost("replay", "show", snap_id)
        assert "+ house-style (rule)" in r.out
        r = boost("replay", "show", snap_id, "--json")
        data = json.loads(r.out)["since_snapshot"]
        assert data["rules"]["added"] == ["house-style"]
        assert data["added"] == []            # no skill drift

        r = boost("replay", "rollback", snap_id)
        assert ("not rolled back (rollback restores skills only): "
                "rule house-style") in r.out
        assert "skills already match this snapshot — nothing to do" in r.out
        assert lockfile.get_rule("house-style") is not None   # untouched

        boost("uninstall", "brainstorming")   # snapshots the skill+rule lock
        history = lockfile.history_list()
        assert [h["count"] for h in history] == [1, 2]  # rule counted
        r = boost("replay", "list")
        newest = next(l for l in r.out.splitlines()
                      if l.startswith(history[1]["id"]))
        assert "+1" in newest                 # the rule the old delta missed


# ---------------------------------------------------------------- who

class TestWho:
    def test_user_aggregate_row(self, boost, installed):
        r = boost("who")
        row = next(l for l in r.out.splitlines() if l.startswith(USER))
        cols = row.split()
        assert cols[0] == USER
        assert cols[1] == "2"   # events: tap + install
        assert cols[2] == "2"   # distinct subjects
        assert cols[3] == "1"   # installs
        assert "USER" in r.out and "LAST ACTIVE" in r.out
        assert "based on the local journal" in r.out

    def test_aggregate_json(self, boost, installed):
        r = boost("who", "--json")
        data = json.loads(r.out)
        assert set(data) == {USER}
        assert data[USER]["events"] == 2
        assert data[USER]["installs"] == 1
        assert data[USER]["skills"] == ["brainstorming", "fixture-tap"]
        assert data[USER]["last_active"]

    def test_per_skill_view(self, boost, installed):
        r = boost("who", "brainstorming")
        assert "brainstorming" in r.out
        assert "v1.4.0 from fixture-tap" in r.out
        assert "install" in r.out
        r = boost("who", "brainstorming", "--json")
        data = json.loads(r.out)
        assert data["skill"] == "brainstorming"
        assert data["installed"] is True
        assert data["events"][0]["action"] == "install"

    def test_reports_an_installed_rule_with_kind(self, boost, tapped):
        # `boost list` shows the rule; who answering "installed: false" for
        # the same name would read as data loss.
        _seed_rule("house-style")
        journal.log("install", "house-style", tap="rule-tap", version="1.0.0")
        r = boost("who", "house-style")
        assert "v1.0.0 from rule-tap (rule)" in r.out
        r = boost("who", "house-style", "--json")
        data = json.loads(r.out)
        assert data["installed"] is True
        assert data["kind"] == "rule"

    def test_per_skill_falls_back_to_all_events(self, boost, tapped):
        # only a "tap" event exists for this subject — not an expertise action
        r = boost("who", "fixture-tap")
        assert "tap" in r.out
        assert USER in r.out

    def test_empty_journal(self, boost, sandbox):
        r = boost("who")
        assert "no journal activity yet" in r.out

    def test_empty_journal_fits_a_narrow_pane(self, boost, sandbox,
                                              monkeypatch):
        # 89 columns unwrapped — the widest of this audit's empty-state finds.
        monkeypatch.setenv("COLUMNS", "60")
        r = boost("who")
        for ln in r.out.split("\n"):
            assert len(ln) <= 60, ln
