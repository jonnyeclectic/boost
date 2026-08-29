# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Functional tests: Configuration commands, in-process.

config / clean / create / policy / onboard / completions / schedule /
serve / mcp / self-update. External tools (launchctl, crontab, gh, claude,
git-for-self-update) are monkeypatched in the module under test.
"""
from __future__ import annotations

import getpass
import io
import itertools
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from boost_cli.core import frontmatter, journal, paths, policy, util
from boost_cli.errors import BoostError


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t", *list(args)], cwd=str(cwd), check=True, capture_output=True)


def _mk_repo(root):
    """A committed git repo with local identity (for onboard's own commits)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.test")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("hi\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _proc(cmd, rc=0, out="", err=""):
    return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr=err)


# ---------------------------------------------------------------- config

class TestConfig:
    def test_list_json_shows_defaults(self, boost, sandbox):
        r = boost("config", "list", "--json")
        cfg = json.loads(r.out)
        assert cfg["ai"]["model"] == "claude-haiku-4-5-20251001"
        assert cfg["serve"]["port"] == 8787
        assert cfg["telemetry"] is False
        # non-json variant appends the config path
        r = boost("config")
        assert "~/.boost/config.json" in r.out

    def test_get_hit_and_miss(self, boost, sandbox):
        r = boost("config", "get", "ai.model")
        assert r.out.strip() == "claude-haiku-4-5-20251001"
        r = boost("config", "get", "ai.enabled", "--json")
        assert r.out.strip() == "true"
        r = boost("config", "get", "serve")
        assert json.loads(r.out) == {"port": 8787}
        r = boost("config", "get", "no.such.key", expect=1)
        assert "no config key 'no.such.key'" in r.err
        r = boost("config", "get", expect=1)
        assert "config get requires a KEY" in r.err

    def test_set_nested_persists_to_disk(self, boost, sandbox):
        r = boost("config", "set", "serve.port", "9999")
        assert "set serve.port = 9999" in r.out
        on_disk = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert on_disk["serve"]["port"] == 9999
        assert boost("config", "get", "serve.port", "--json").out.strip() == "9999"
        r = boost("config", "set", "serve.port", expect=1)
        assert "config set requires a VALUE" in r.err

    def test_set_through_scalar_fails_cleanly(self, boost, sandbox):
        r = boost("config", "set", "ai.model.extra", "1", expect=1)
        assert "config key 'model' is not a section" in r.err
        assert "the parent key holds a plain value" in r.err

    def test_unset_present_and_absent(self, boost, sandbox):
        boost("config", "set", "custom.flag", "true")
        r = boost("config", "unset", "custom.flag")
        assert "unset custom.flag" in r.out
        r = boost("config", "unset", "custom.flag")
        assert "custom.flag not set" in r.out


# ---------------------------------------------------------------- clean

class TestClean:
    def test_dry_run_then_real_then_nothing(self, boost, installed):
        # Into the store: boost put it there, so boost may remove it.
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.store_dir() / "ghost")
        stale = paths.cache_dir() / "old__tap.json"
        stale.write_text('{"skills": []}', encoding="utf-8")            # 14 bytes
        ds = paths.store_dir() / "brainstorming" / ".DS_Store"
        ds.write_bytes(b"junk12")                     # 6 bytes

        r = boost("clean", "--dry-run")
        assert "would remove ~/.claude/skills/ghost (broken symlink)" in r.out
        assert "would remove ~/.boost/cache/old__tap.json (stale tap cache)" in r.out
        assert ".DS_Store" in r.out
        assert "3 item(s) · 20B would be freed" in r.out
        assert ghost.is_symlink() and stale.exists() and ds.exists()

        r = boost("clean")
        assert "cleaned 3 item(s) · 20B freed" in r.out
        assert not ghost.is_symlink() and not stale.exists() and not ds.exists()
        assert (paths.cache_dir() / "fixture-tap.json").exists()  # kept

        r = boost("clean")
        assert "nothing to clean" in r.out

    def test_fresh_sandbox_has_nothing_to_clean(self, boost, sandbox):
        r = boost("clean")
        assert "nothing to clean" in r.out

    def test_leaves_a_broken_symlink_boost_does_not_own(self, boost, installed):
        # `clean` carried the same overreach as `sync`: it removed every broken
        # symlink under an agent dir, boost's or not. A user's own dangling
        # link is not boost's to delete, and `clean` is the command people run
        # without reading it first.
        mine = paths.home() / ".claude" / "skills" / "my-notes"
        mine.symlink_to(paths.home() / "unmounted" / "notes")
        r = boost("clean")
        assert "nothing to clean" in r.out
        assert mine.is_symlink()

    def test_deep_clean_pycache_history_snapshots(self, boost, installed):
        import os
        pyc = paths.store_dir() / "brainstorming" / "__pycache__"
        pyc.mkdir()
        (pyc / "x.pyc").write_bytes(b"123")
        hist = paths.lock_history_dir()
        for i in range(52):
            (hist / ("lock-0000%02d.json" % i)).write_text("{}", encoding="utf-8")
        old_snap = paths.snapshots_dir() / "ancient"
        old_snap.mkdir(parents=True)
        (old_snap / "f").write_text("x", encoding="utf-8")
        old = time.time() - 91 * 86400
        os.utime(old_snap, (old, old))
        r = boost("clean", "--deep")
        assert "(__pycache__)" in r.out
        assert r.out.count("(old lock history)") == 2  # keeps the newest 50
        assert "(old snapshot)" in r.out
        assert not pyc.exists() and not old_snap.exists()
        assert len(list(hist.glob("lock-*.json"))) == 50


# ---------------------------------------------------------------- create

class TestCreate:
    def test_scaffold_contents(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = boost("create", "my-skill")
        assert "created" in r.out and "my-skill/SKILL.md" in r.out
        text = (tmp_path / "my-skill" / "SKILL.md").read_text(encoding="utf-8")
        meta, body = frontmatter.parse(text)
        assert meta == {"name": "my-skill",
                        "description": "TODO: describe when this skill should trigger",
                        "version": "0.1.0"}
        assert "# My Skill" in body
        for section in ("## When to use", "## Instructions", "## Rules",
                        "## Examples"):
            assert section in body
        assert "next: edit it, then `boost import" in r.out
        assert journal.events(action="create")[0]["subject"] == "my-skill"

    def test_refuses_overwrite(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        boost("create", "twice")
        r = boost("create", "twice", expect=1)
        assert "already exists" in r.err

    def test_description_and_slug(self, boost, sandbox, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        boost("create", "My Fancy Skill", "--description", "Does a thing")
        text = (tmp_path / "my-fancy-skill" / "SKILL.md").read_text(encoding="utf-8")
        assert frontmatter.parse(text)[0]["description"] == "Does a thing"

    def test_install_flag(self, boost, sandbox, tmp_path):
        r = boost("create", "inst-skill", "--dir", tmp_path, "--install")
        assert "installed inst-skill" in r.out
        assert "linked: Claude Code, Windsurf, Cursor" in r.out
        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert lock["skills"]["inst-skill"]["tap"] == "local"
        assert lock["skills"]["inst-skill"]["version"] == "0.1.0"


# ---------------------------------------------------------------- policy

class TestPolicy:
    def test_list_defaults(self, boost, sandbox):
        r = boost("policy", "list", "--json")
        assert json.loads(r.out) == policy.DEFAULTS
        r = boost("policy")
        assert "all values at defaults" in r.out

    def test_pin_only_blocks_install_then_unset_restores(self, boost, tapped):
        r = boost("policy", "set", "pin_only", "true")
        assert "set pin_only = true" in r.out
        r = boost("install", "brainstorming", expect=1)
        assert "policy blocks installing brainstorming" in r.err
        assert "environment is pin-only (frozen)" in r.err
        r = boost("policy")
        assert "modified from defaults: pin_only" in r.out
        r = boost("policy", "unset", "pin_only")
        assert "reset pin_only to default (false)" in r.out
        boost("install", "brainstorming")  # now allowed

    def test_blocked_skills_comma_list(self, boost, tapped):
        r = boost("policy", "set", "blocked_skills", "cowboy-coding,evil")
        assert 'set blocked_skills = ["cowboy-coding", "evil"]' in r.out
        r = boost("install", "cowboy-coding", expect=1)
        assert "skill 'cowboy-coding' is on the blocklist" in r.err

    def test_unknown_key(self, boost, sandbox):
        r = boost("policy", "set", "nope", "1", expect=1)
        assert "unknown policy key 'nope'" in r.err
        assert "blocked_skills" in r.err  # hint lists valid keys
        r = boost("policy", "set", "pin_only", expect=1)
        assert "policy set requires a VALUE" in r.err

    def test_check_clean_vs_violations(self, boost, installed):
        r = boost("policy", "check")
        assert "policy check passed (1 skills)" in r.out
        r = boost("policy", "check", "--json")
        assert json.loads(r.out) == {
            "skills": 1, "counts": {"skill": 1, "rule": 0, "workflow": 0},
            "total": 1, "violations": [], "pin_only": False, "unpinned": []}
        boost("policy", "set", "blocked_skills", "brainstorming")
        r = boost("policy", "check", expect=1)
        assert "on the blocklist" in r.out
        assert "1 policy violation(s) across 1 installed item(s)" in r.err
        r = boost("policy", "check", "--json", expect=1)
        assert json.loads(r.out)["violations"] == [
            {"skill": "brainstorming", "violation": "on the blocklist"}]

    def test_check_min_quality_and_pin_only_note(self, boost, installed):
        from boost_cli.core import store
        score, _ = util.score_skill(store.skill_store_dir("brainstorming"))
        boost("policy", "set", "min_quality_score", "101")
        boost("policy", "set", "pin_only", "true")
        r = boost("policy", "check", expect=1)
        assert "pin-only mode is on — installs/updates are frozen" in r.out
        assert "1 unpinned item(s): brainstorming" in r.out
        assert "quality score %d < required 101" % score in r.out


# ---------------------------------------------------------------- onboard

class TestOnboard:
    def test_dry_run_writes_nothing(self, boost, sandbox, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        r = boost("onboard", "--repo", repo, "--dry-run")
        assert "would write" in r.out
        assert ".boost/telemetry.json" in r.out
        assert ".github/workflows/boost-skill-inventory.yml" in r.out
        assert ".skill-lock.json" in r.out
        assert not (repo / ".boost").exists()
        assert not (repo / ".github").exists()

    def test_real_run_writes_files(self, boost, installed, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        r = boost("onboard", "--repo", repo)
        assert r.out.count("created") == 3
        telem = json.loads((repo / ".boost" / "telemetry.json").read_text(encoding="utf-8"))
        assert telem["enabled"] is True
        assert telem["share_pulse"] is True
        assert telem["by"] == getpass.getuser()
        yml = (repo / ".github" / "workflows" /
               "boost-skill-inventory.yml").read_text(encoding="utf-8")
        assert "name: boost skill inventory" in yml
        assert yml.count(".skill-lock.json") >= 2
        lock = json.loads((repo / ".skill-lock.json").read_text(encoding="utf-8"))
        assert lock["version"] == 3 and "brainstorming" in lock["skills"]
        assert journal.events(action="onboard")

    def test_pr_without_gh_fails_before_writing(self, boost, sandbox, tmp_path,
                                                monkeypatch):
        repo = _mk_repo(tmp_path / "repo")
        # shutil is shared module-wide: only hide gh, keep git discoverable
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: None if c == "gh" else "/usr/bin/" + c)
        r = boost("onboard", "--repo", repo, "--pr", expect=1)
        assert "the `gh` CLI is required for --pr" in r.err
        assert not (repo / ".boost").exists()

    def test_pr_success_commits_branch(self, boost, sandbox, tmp_path,
                                       monkeypatch):
        repo = _mk_repo(tmp_path / "repo")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)
        calls = []
        real_run = subprocess.run

        def fake_run(cmd, **kw):  # intercept only gh; git must stay real
            if cmd and cmd[0] == "gh":
                calls.append(list(cmd))
                return _proc(cmd, 0, out="https://github.com/o/r/pull/7\n")
            return real_run(cmd, **kw)

        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        r = boost("onboard", "--repo", repo, "--pr")
        assert "opened PR https://github.com/o/r/pull/7" in r.out
        assert calls == [["gh", "pr", "create", "--fill"]]
        head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=str(repo), capture_output=True, text=True)
        assert head.stdout.strip() == "boost/onboard-skill-tracker"
        subject = subprocess.run(["git", "log", "-1", "--pretty=%s"],
                                 cwd=str(repo), capture_output=True, text=True)
        assert subject.stdout.strip() == "chore: add boost skill tracking (boost onboard)"

    def test_pr_gh_failure(self, boost, sandbox, tmp_path, monkeypatch):
        repo = _mk_repo(tmp_path / "repo")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)
        real_run = subprocess.run
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: _proc(cmd, 1, err="boom")
            if cmd and cmd[0] == "gh" else real_run(cmd, **kw))
        r = boost("onboard", "--repo", repo, "--pr", expect=1)
        assert "gh pr create failed: boom" in r.err
        assert "boost/onboard-skill-tracker" in r.err  # hint names the branch

    def test_pr_preconditions(self, boost, sandbox, tmp_path):
        r = boost("onboard", "--repo", "/no/such/dir", expect=1)
        assert "is not a directory" in r.err
        plain = tmp_path / "plain"
        plain.mkdir()
        r = boost("onboard", "--repo", plain, "--pr", expect=1)
        assert "is not a git repository" in r.err
        dirty = _mk_repo(tmp_path / "dirty")
        (dirty / "untracked.txt").write_text("x", encoding="utf-8")
        r = boost("onboard", "--repo", dirty, "--pr", expect=1)
        assert "is not clean" in r.err


class TestOnboardOverwrite:
    """Re-running onboard must not silently replace a repo's own files.

    The interesting file is ``.skill-lock.json``: a repo that tracks its own
    lock gets it replaced by whatever *this machine* has installed, and the
    old code still printed "created". Every test here therefore asserts on
    file contents, not just on the message.
    """

    LOCK = ".skill-lock.json"
    TELEMETRY = ".boost/telemetry.json"
    WORKFLOW = ".github/workflows/boost-skill-inventory.yml"

    def _seeded(self, boost, tmp_path):
        """A repo already onboarded, with a hand-edited lock file."""
        repo = tmp_path / "repo"
        repo.mkdir()
        boost("onboard", "--repo", repo)             # BOOST_ASSUME_YES: creates
        (repo / self.LOCK).write_text('{"mine": true}\n', encoding="utf-8")
        return repo

    def test_declining_leaves_the_existing_file_byte_for_byte(
            self, boost, installed, tmp_path, monkeypatch):
        repo = self._seeded(boost, tmp_path)
        monkeypatch.delenv("BOOST_ASSUME_YES")   # stdin is not a tty -> "no"
        r = boost("onboard", "--repo", repo)
        assert (repo / self.LOCK).read_text(encoding="utf-8") == '{"mine": true}\n'
        assert "skipped" in r.out
        assert "created %s" % self.LOCK not in r.out

    def test_force_overwrites_and_says_updated_not_created(
            self, boost, installed, tmp_path, monkeypatch):
        repo = self._seeded(boost, tmp_path)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("onboard", "--repo", repo, "--force")
        lock = json.loads((repo / self.LOCK).read_text(encoding="utf-8"))
        assert "brainstorming" in lock["skills"], "the real lock, not the stub"
        assert "updated" in r.out
        # "created" was the lie the old code told about every overwrite.
        assert "created" not in r.out

    def test_answering_yes_at_the_prompt_overwrites(
            self, boost, installed, tmp_path):
        # BOOST_ASSUME_YES is the fixture default, i.e. the user said yes.
        repo = self._seeded(boost, tmp_path)
        r = boost("onboard", "--repo", repo)
        lock = json.loads((repo / self.LOCK).read_text(encoding="utf-8"))
        assert "brainstorming" in lock["skills"]
        assert "updated" in r.out

    def test_rerun_with_no_changes_reports_telemetry_unchanged(
            self, boost, installed, tmp_path, monkeypatch):
        # telemetry.json's own "created" field must not defeat the
        # byte-for-byte unchanged check documented on _write_onboard_file:
        # a second run with nothing else different should never say
        # "updated" for a file whose content didn't actually change. Force
        # two distinct wall-clock instants so this can't pass by luck (two
        # fast invocations landing in the same second, as a real run can).
        counter = itertools.count()
        monkeypatch.setattr(
            "boost_cli.commands.configuration.util.now_iso",
            lambda: "2026-01-01T00:00:%02dZ" % next(counter))
        repo = tmp_path / "repo"
        repo.mkdir()
        boost("onboard", "--repo", repo)
        before = (repo / self.TELEMETRY).read_text(encoding="utf-8")

        r = boost("onboard", "--repo", repo, "--force")
        after = (repo / self.TELEMETRY).read_text(encoding="utf-8")

        assert after == before, "telemetry.json changed on a no-op re-run"
        telemetry_line = next(l for l in r.out.splitlines()
                              if l.strip().endswith(self.TELEMETRY))
        assert telemetry_line.strip().startswith("unchanged")

    def test_an_existing_file_boost_cannot_read_is_still_protected(
            self, boost, installed, tmp_path, monkeypatch):
        # The identical-content shortcut reads the file; a binary or
        # permission-denied file must fall back to asking, not to overwriting.
        repo = self._seeded(boost, tmp_path)
        (repo / self.WORKFLOW).write_bytes(b"\xff\xfe not utf-8")
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("onboard", "--repo", repo)
        assert (repo / self.WORKFLOW).read_bytes() == b"\xff\xfe not utf-8"
        assert "skipped" in r.out

    def test_the_hidden_yes_alias_also_overwrites(
            self, boost, installed, tmp_path, monkeypatch):
        repo = self._seeded(boost, tmp_path)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        boost("onboard", "--repo", repo, "--yes")
        assert '{"mine": true}' not in (repo / self.LOCK).read_text(encoding="utf-8")

    def test_identical_content_is_never_prompted_for(
            self, boost, installed, tmp_path, monkeypatch):
        # The workflow YAML regenerates byte-for-byte, so a second run has
        # nothing to ask about it. Asking anyway trains users to say yes.
        repo = self._seeded(boost, tmp_path)
        # Leave *only* the workflow: telemetry carries a timestamp and the lock
        # is live machine state, so neither is a stable "identical" case.
        (repo / self.TELEMETRY).unlink()
        (repo / self.LOCK).unlink()
        monkeypatch.delenv("BOOST_ASSUME_YES")
        monkeypatch.setattr("boost_cli.core.output.confirm",
                            lambda *a, **k: pytest.fail(
                                "prompted to overwrite an identical file"))
        r = boost("onboard", "--repo", repo)
        assert "unchanged" in r.out
        assert self.WORKFLOW in r.out

    def test_dry_run_distinguishes_write_from_overwrite(
            self, boost, installed, tmp_path):
        repo = self._seeded(boost, tmp_path)
        r = boost("onboard", "--repo", repo, "--dry-run")
        assert "would overwrite" in r.out
        assert "would write" not in r.out, "every file already exists here"
        assert (repo / self.LOCK).read_text(encoding="utf-8") == '{"mine": true}\n'

    def test_declining_everything_journals_nothing(
            self, boost, installed, tmp_path, monkeypatch):
        repo = self._seeded(boost, tmp_path)
        # Make all three differ so all three get a prompt, then decline them.
        (repo / self.TELEMETRY).write_text("{}\n", encoding="utf-8")
        (repo / self.WORKFLOW).write_text("# theirs\n", encoding="utf-8")
        before = len(journal.events(action="onboard"))
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("onboard", "--repo", repo)
        assert "nothing to do" in r.out
        assert len(journal.events(action="onboard")) == before, \
            "a no-op run must not add an onboard event"

    def test_pr_stages_only_the_files_it_actually_wrote(
            self, boost, installed, tmp_path, monkeypatch):
        repo = _mk_repo(tmp_path / "repo")
        (repo / self.LOCK).write_text('{"mine": true}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "our own lock")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)
        real_run = subprocess.run
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: _proc(cmd, 0, out="https://github.com/o/r/pull/9\n")
            if cmd and cmd[0] == "gh" else real_run(cmd, **kw))
        monkeypatch.delenv("BOOST_ASSUME_YES")     # decline the lock overwrite
        boost("onboard", "--repo", repo, "--pr")

        names = subprocess.run(["git", "show", "--name-only", "--pretty=", "HEAD"],
                               cwd=str(repo), capture_output=True, text=True)
        staged = set(names.stdout.split())
        assert staged == {self.TELEMETRY, self.WORKFLOW}
        assert (repo / self.LOCK).read_text(encoding="utf-8") == '{"mine": true}\n'

    def test_pr_with_nothing_to_write_leaves_no_branch_behind(
            self, boost, installed, tmp_path, monkeypatch):
        repo = _mk_repo(tmp_path / "repo")
        for rel, body in ((self.TELEMETRY, "{}\n"), (self.WORKFLOW, "# theirs\n"),
                          (self.LOCK, '{"mine": true}\n')):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(body, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "already ours")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("onboard", "--repo", repo, "--pr")
        assert "nothing to do" in r.out
        head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=str(repo), capture_output=True, text=True)
        assert head.stdout.strip() != "boost/onboard-skill-tracker", \
            "an empty branch would fail on `git commit` with nothing staged"


# ---------------------------------------------------------------- completions

class TestCompletions:
    """The scripts are shims now; what they must do is delegate.

    The previous tests asserted the emitted *text* — that a bash wordlist
    equalled COMMANDS, that there were 79 zsh entries. Every one passed while
    `boost install <TAB>` offered command names in bash, local filenames in
    zsh and nothing in fish, because none of them asked what a shell would
    actually propose. Behaviour is pinned in tests/unit/test_complete.py; these
    pin the contract that the script is a shim rather than a second copy of the
    command list.
    """

    def test_each_shell_delegates_to_the_completer(self, boost, sandbox):
        for shell in ("bash", "zsh", "fish"):
            r = boost("completions", shell)
            assert "__complete" in r.out, shell

    def test_no_script_embeds_a_static_command_list(self, boost, sandbox):
        # A baked-in list silently drifts from cli.COMMANDS the next time a
        # command is added — which is how flags came to be missing entirely.
        for shell in ("bash", "zsh", "fish"):
            r = boost("completions", shell)
            assert "uninstall" not in r.out, shell

    def test_bash_installs_a_function_not_a_wordlist(self, boost, sandbox):
        # `complete -W` is position-independent by definition, so it re-offers
        # command names where an argument belongs. Only `-F` can be contextual.
        r = boost("completions", "bash")
        assert "complete -F _boost_complete boost" in r.out
        assert "complete -W" not in r.out

    def test_zsh_preserves_an_empty_current_word(self, boost, sandbox):
        # Unquoted, zsh drops the empty word, so `boost install <TAB>` arrives
        # as two words and completes command names instead of skills. Verified
        # against real zsh; this pins the quoting that fixes it.
        r = boost("completions", "zsh")
        assert '"${(@)words[1,$CURRENT]}"' in r.out

    def test_fish_disables_the_filename_fallback(self, boost, sandbox):
        # Without -f, fish offers local filenames once the subcommand is typed.
        r = boost("completions", "fish")
        assert "complete -c boost -f" in r.out

    def test_bad_shell_rc2_and_shell_env_default(self, boost, sandbox,
                                                 monkeypatch):
        r = boost("completions", "powershell", expect=2)
        assert "invalid choice" in r.err
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        assert "fish" in boost("completions").out
        monkeypatch.setenv("SHELL", "/bin/weirdsh")
        assert "_boost_complete" in boost("completions").out

    def test_eval_flag_prints_the_eval_safe_variant(self, boost, sandbox):
        r = boost("completions", "zsh", "--eval")
        assert r.out.rstrip().endswith("compdef _boost boost")
        assert '_boost "$@"' not in r.out
        assert "boost __complete" in r.out


class TestCompletionsInstall:
    """`boost completions --install` — the one-shot alternative to the
    copy-paste-into-your-rc-file instructions `INSTALL_HINT` used to be.
    """

    def test_explicit_shell_wires_the_matching_rc_file(self, boost, sandbox):
        r = boost("completions", "bash", "--install")
        assert "wired boost completions into ~/.bashrc" in r.out
        assert "restart your shell" in r.out
        text = (sandbox / ".bashrc").read_text(encoding="utf-8")
        assert 'eval "$(boost completions bash --eval)"' in text

    def test_auto_detects_shell_from_env(self, boost, sandbox, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/local/bin/zsh")
        boost("completions", "--install")
        assert (sandbox / ".zshrc").exists()
        assert not (sandbox / ".bashrc").exists()

    def test_running_install_twice_does_not_duplicate_the_block(self, boost,
                                                                 sandbox):
        boost("completions", "bash", "--install")
        boost("completions", "bash", "--install")
        text = (sandbox / ".bashrc").read_text(encoding="utf-8")
        assert text.count("# >>> boost completions >>>") == 1

    def test_preserves_the_users_existing_rc_content(self, boost, sandbox):
        (sandbox / ".bashrc").write_text("export EDITOR=vim\n", encoding="utf-8")
        boost("completions", "bash", "--install")
        text = (sandbox / ".bashrc").read_text(encoding="utf-8")
        assert text.startswith("export EDITOR=vim\n")

    def test_uninstall_removes_exactly_what_install_added(self, boost, sandbox):
        (sandbox / ".bashrc").write_text("export EDITOR=vim\n", encoding="utf-8")
        boost("completions", "bash", "--install")
        r = boost("completions", "bash", "--uninstall")
        assert "removed boost completions from ~/.bashrc" in r.out
        assert (sandbox / ".bashrc").read_text(encoding="utf-8") == "export EDITOR=vim\n"

    def test_fish_has_no_one_shot_install_yet(self, boost, sandbox):
        r = boost("completions", "fish", "--install", expect=1)
        assert "no one-shot install for fish yet" in r.err
        assert "boost completions fish" in r.err

    def test_install_and_uninstall_are_mutually_exclusive(self, boost, sandbox):
        r = boost("completions", "bash", "--install", "--uninstall", expect=2)
        assert "not allowed with argument" in r.err


class TestHiddenCompleter:
    def test_it_prints_one_candidate_per_line(self, boost, sandbox):
        r = boost("__complete", "boost", "inst")
        assert "install" in r.out.split("\n")

    def test_it_is_not_advertised_as_a_command(self, boost, sandbox):
        # It is not a row in cli.COMMANDS, so it must not reach --help,
        # docs/commands.html, or the command counts.
        assert "__complete" not in boost("--help").out

    def test_it_exits_zero_on_nonsense(self, boost, sandbox):
        # Called on every TAB: a non-zero exit or a traceback would land in
        # the line the user is typing.
        assert boost("__complete").out == ""
        assert boost("__complete", "boost", "nosuchcommand", "x").out == ""


# ---------------------------------------------------------------- schedule

class TestScheduleDarwin:
    """Darwin branches, with sys.platform faked (CI also runs on Linux)."""

    @pytest.fixture(autouse=True)
    def _darwin(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")

    def test_status_fresh(self, boost, sandbox):
        r = boost("schedule")
        assert "darwin (launchd)" in r.out
        assert "no" in r.out
        assert "enable with `boost schedule enable" in r.out
        r = boost("schedule", "status", "--json")
        assert json.loads(r.out) == {"platform": "darwin", "backend": "launchd",
                                     "scheduled": False, "interval": None,
                                     "next_run": None}

    def test_enable_writes_plist_and_loads(self, boost, sandbox, monkeypatch):
        # force launcher() onto its checkout-shim fallback regardless of
        # whether the dev machine has `boost` on PATH
        monkeypatch.setattr("boost_cli.core.paths.shutil.which",
                            lambda c: None)
        calls = []
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: calls.append(list(cmd)) or _proc(cmd, 0))
        r = boost("schedule", "enable")
        plist = sandbox / "Library" / "LaunchAgents" / "com.boost.sync.plist"
        assert plist.exists()
        body = plist.read_text(encoding="utf-8")
        assert "<integer>21600</integer>" in body
        assert "<string>update</string>" in body
        assert "com.boost.sync" in body
        assert str(paths.repo_root() / "boost") in body
        assert "wrote ~/Library/LaunchAgents/com.boost.sync.plist" in r.out
        assert "`boost update` scheduled every 6h" in r.out
        assert calls[0][:2] == ["launchctl", "unload"]
        assert calls[1][:3] == ["launchctl", "load", "-w"]
        assert journal.events(action="schedule")[0]["interval"] == "6h"

        r = boost("schedule", "status", "--json")
        data = json.loads(r.out)
        assert data["scheduled"] is True
        assert data["interval"] == "6h"
        assert data["next_run"]
        r = boost("schedule", "status")
        assert "every 6h" in r.out

    def test_enable_daily_and_load_failure(self, boost, sandbox, monkeypatch):
        def fake_run(cmd, **kw):
            rc = 1 if cmd[:2] == ["launchctl", "load"] else 0
            return _proc(cmd, rc, err="Load failed: 5")
        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        r = boost("schedule", "enable", "--interval", "daily")
        plist = sandbox / "Library" / "LaunchAgents" / "com.boost.sync.plist"
        assert "<integer>86400</integer>" in plist.read_text(encoding="utf-8")
        assert "launchctl load failed: Load failed: 5" in r.out

    def test_disable_removes_plist(self, boost, sandbox, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: calls.append(list(cmd)) or _proc(cmd, 0))
        boost("schedule", "enable")
        plist = sandbox / "Library" / "LaunchAgents" / "com.boost.sync.plist"
        assert plist.exists()
        r = boost("schedule", "disable")
        assert "automatic sync disabled" in r.out
        assert not plist.exists()
        assert ["launchctl", "unload", "-w", str(plist)] in calls
        r = boost("schedule", "disable")
        assert "no schedule was configured" in r.out


class TestScheduleCron:
    """Non-darwin branches, with sys.platform and crontab faked."""

    @pytest.fixture(autouse=True)
    def _linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

    def test_status_reads_crontab(self, boost, sandbox, monkeypatch):
        line = "0 */6 * * * /x/boost update >> /y/log 2>&1 # boost-sync"
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: _proc(cmd, 0, out=line + "\n"))
        r = boost("schedule", "status", "--json")
        data = json.loads(r.out)
        assert data == {"platform": "linux", "backend": "cron",
                        "scheduled": True, "interval": "6h",
                        "next_run": data["next_run"]}
        assert data["next_run"]

    def test_status_custom_spec(self, boost, sandbox, monkeypatch):
        line = "30 6 * * * /x/boost update # boost-sync"
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: _proc(cmd, 0, out=line + "\n"))
        r = boost("schedule", "status", "--json")
        data = json.loads(r.out)
        assert data["interval"] == "30 6 * * *"
        assert data["next_run"].endswith("06:30")

    def test_enable_writes_cron_entry(self, boost, sandbox, monkeypatch):
        writes = []

        def fake_run(cmd, **kw):
            if cmd == ["crontab", "-l"]:
                return _proc(cmd, 1, err="no crontab for user")
            writes.append(kw.get("input"))
            return _proc(cmd, 0)

        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        r = boost("schedule", "enable", "--interval", "12h")
        assert "`boost update` scheduled every 12h via cron" in r.out
        assert len(writes) == 1
        assert writes[0].startswith("0 */12 * * * ")
        assert writes[0].rstrip().endswith("# boost-sync")

    def test_enable_when_crontab_unusable(self, boost, sandbox, monkeypatch):
        def no_crontab(cmd, **kw):
            raise OSError("no crontab binary")
        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            no_crontab)
        r = boost("schedule", "enable")
        assert "crontab is not available — add this line yourself:" in r.out
        assert "# boost-sync" in r.out

    def test_disable_rewrites_crontab(self, boost, sandbox, monkeypatch):
        keep = "@daily /bin/other-job"
        mine = "0 */6 * * * /x/boost update # boost-sync"
        writes = []

        def fake_run(cmd, **kw):
            if cmd == ["crontab", "-l"]:
                return _proc(cmd, 0, out=keep + "\n" + mine + "\n")
            writes.append(kw.get("input"))
            return _proc(cmd, 0)

        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        r = boost("schedule", "disable")
        assert "automatic sync disabled" in r.out
        assert writes == [keep + "\n"]


# ---------------------------------------------------------------- serve

class TestServe:
    def test_endpoints(self, boost, installed, monkeypatch):
        from boost_cli.cli import main
        from boost_cli.core import serve as serve_mod
        captured = {}
        real = serve_mod.ThreadingHTTPServer

        class Capturing(real):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                captured["server"] = self

        monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", Capturing)
        # server_bind() calls socket.getfqdn(), whose reverse-DNS lookup can
        # hang for many seconds on macOS CI runners; stub it out
        monkeypatch.setattr(socket, "getfqdn", lambda name="": "localhost")
        t = threading.Thread(target=main, args=(["serve", "--port", "0"],),
                             daemon=True)
        t.start()
        try:
            deadline = time.time() + 30
            while "server" not in captured and time.time() < deadline:
                time.sleep(0.01)
            assert "server" in captured, "serve thread never bound its socket"
            port = captured["server"].server_address[1]
            base = "http://127.0.0.1:%d" % port

            def get(path):
                with urllib.request.urlopen(base + path, timeout=5) as resp:
                    return resp.read().decode()

            entries = json.loads(get("/catalog.json"))
            assert {e["name"] for e in entries} == {
                "brainstorming", "commit-messages", "cowboy-coding",
                "jira-integration", "tdd-workflow"}

            lock = json.loads(get("/installed.json"))
            assert lock["version"] == 3
            assert "brainstorming" in lock["skills"]

            text = get("/skill/brainstorming")
            assert text.startswith("---")
            assert "name: brainstorming" in text
            # not installed -> served straight from the tap clone
            assert get("/skill/tdd-workflow").startswith("---")

            page = get("/")
            # The page is a shell; the rows arrive over fetch. So it is asserted
            # to be the shell, and the numbers that used to be baked into it are
            # asserted where they now come from. Deliberately NOT "brainstorming
            # appears in the HTML" — the whole point is that third-party names
            # and descriptions never reach the markup.
            assert 'id="rows"' in page and 'id="gcanvas"' in page
            assert "brainstorming" not in page

            found = json.loads(get("/search.json"))
            assert found["total"] == 5
            rows = {r["name"]: r for r in found["rows"]}
            assert rows["brainstorming"]["installed"] is True
            assert rows["tdd-workflow"]["installed"] is False
            assert "kind:skill" in rows["brainstorming"]["tags"]
            assert sum(dict(found["facets"]["kind"]).values()) == 5

            hit = json.loads(get("/search.json?q=brainstorming"))
            assert [r["name"] for r in hit["rows"]] == ["brainstorming"]

            tagged = json.loads(get("/search.json?tag=state:installed"))
            assert [r["name"] for r in tagged["rows"]] == ["brainstorming"]

            graph = json.loads(get("/graph.json"))
            # One tap, so one node holding all five — and no edges, because an
            # overlap needs a name carried by two different taps. The tap's
            # name is a tempdir basename, so it is counted, not spelled.
            assert len(graph["nodes"]) == 1
            assert graph["nodes"][0]["size"] == 5
            assert graph["links"] == []
            assert graph["graph"]["items"] == 5

            with pytest.raises(urllib.error.HTTPError) as exc:
                get("/nope")
            assert exc.value.code == 404
            assert json.loads(exc.value.read().decode()) == {"error": "not found"}

            with pytest.raises(urllib.error.HTTPError) as exc:
                get("/skill/ghost")
            assert exc.value.code == 404
            assert "no skill named 'ghost'" in json.loads(
                exc.value.read().decode())["error"]

            # The nosniff header exists only on the wire, so the unit tests
            # cannot see it at all — and it is what keeps a body we typed
            # application/json from being sniffed as markup. Asserted on a 200
            # and on a 404, because the error paths are the ones that carry
            # anything derived from the request.
            with urllib.request.urlopen(base + "/catalog.json", timeout=5) as r:
                assert r.headers["X-Content-Type-Options"] == "nosniff"

            # Percent-encoded because http.client refuses unsafe bytes in a
            # request line; route() unquotes before matching, so this is the
            # same path an attacker's browser would send.
            with pytest.raises(urllib.error.HTTPError) as exc:
                get("/skill/" + urllib.parse.quote("<script>alert(1)</script>"))
            assert exc.value.code == 404
            assert exc.value.headers["X-Content-Type-Options"] == "nosniff"
            refused = exc.value.read().decode()
            assert json.loads(refused) == {"error": "invalid skill name"}
            assert "<script>" not in refused and "alert" not in refused
        finally:
            if "server" in captured:
                captured["server"].shutdown()
            t.join(timeout=5)

    def test_port_in_use(self, boost, sandbox):
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            r = boost("serve", "--port", str(port), expect=1)
            assert "port %d is already in use" % port in r.err
            assert "pick another with --port" in r.err
        finally:
            sock.close()


# ---------------------------------------------------------------- mcp

def _rpc(id_, method, **params):
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params:
        msg["params"] = params
    return json.dumps(msg)


def _call(id_, tool, **arguments):
    return _rpc(id_, "tools/call", name=tool, arguments=arguments)


class TestMcp:
    def test_stdio_protocol(self, boost, tapped, monkeypatch):
        lines = [
            _rpc(1, "initialize"),
            json.dumps({"jsonrpc": "2.0",
                        "method": "notifications/initialized"}),
            _rpc(2, "tools/list"),
            _call(3, "boost_search", query="jira"),
            _call(4, "boost_doctor"),
            _rpc(5, "no/such"),
            "this is not json",
            _rpc(6, "ping"),
            _call(7, "bogus_tool"),
            _call(8, "boost_install", name="brainstorming"),
            _call(9, "boost_list"),
            _call(10, "boost_info", name="brainstorming"),
            _call(11, "boost_info", name="zzz"),
            _call(12, "boost_search", query="zzzz"),
            _call(13, "boost_install", name="ghost"),
        ]
        monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
        r = boost("mcp", "--stdio")
        resps = [json.loads(l) for l in r.out.splitlines()]
        assert len(resps) == 14  # 13 ids + 1 parse error; notification silent
        by_id = {m.get("id"): m for m in resps}

        assert by_id[1]["result"]["protocolVersion"] == "2024-11-05"
        server_info = by_id[1]["result"]["serverInfo"]
        assert server_info["name"] == "boost"
        assert isinstance(server_info["version"], str) and server_info["version"]
        tools = by_id[2]["result"]["tools"]
        assert [t["name"] for t in tools] == [
            "boost_search", "boost_list", "boost_info", "boost_install",
            "boost_doctor", "boost_discover_github"]
        assert all(t["inputSchema"]["type"] == "object" for t in tools)

        def text(id_):
            return by_id[id_]["result"]["content"][0]["text"]

        assert ("jira-integration — Sync commits and PRs to Jira tickets "
                "(fixture-tap)") in text(3)
        assert "installed skills: 0" in text(4)
        assert "taps: 1 (5 items available)" in text(4)
        assert "healthy — no issues found" in text(4)
        assert "isError" not in by_id[4]["result"]

        assert by_id[5]["error"] == {"code": -32601,
                                     "message": "method not found: no/such"}
        assert by_id[None]["error"]["code"] == -32700
        assert by_id[6]["result"] == {}
        assert by_id[7]["error"]["code"] == -32602

        assert "installed brainstorming v1.4.0 from fixture-tap" in text(8)
        # gemini reads the canonical store directly, so it is never symlinked —
        # but the response MUST still say the skill reached it. A Gemini agent
        # that sees only "linked agents: claude-code, windsurf, cursor" concludes
        # the install missed it and rebuilds the work by hand, which is the one
        # failure this tool exists to prevent.
        assert "linked agents: claude-code, windsurf, cursor" in text(8)
        assert "available without linking" in text(8)
        assert text(8).rstrip().endswith("directly): gemini\nquality score: 95/100")
        assert "quality score:" in text(8)
        assert "brainstorming v1.4.0 (fixture-tap)" in text(9)
        assert "installed: yes" in text(10)
        assert "version: 1.4.0" in text(10)
        assert "no skill named 'zzz'" in text(11)
        assert by_id[11]["result"]["isError"] is True
        assert "no skills match 'zzzz'" in text(12)
        assert "Error: no skill named 'ghost' in any tap" in text(13)
        assert by_id[13]["result"]["isError"] is True

        lock = json.loads(paths.lockfile_path().read_text(encoding="utf-8"))
        assert "brainstorming" in lock["skills"]  # id 8 really installed

    def test_boost_search_prefers_full_content_index(self, boost, tapped):
        from boost_cli.commands import configuration
        from boost_cli.core import rag
        boost("reindex")
        assert rag.ready() is True
        text, is_err = configuration._mcp_tool(
            "boost_search", {"query": "brainstorming"})
        assert is_err is False
        assert "brainstorming" in text
        assert "(fixture-tap)" in text

    def test_boost_search_indexed_no_match(self, boost, tapped):
        from boost_cli.commands import configuration
        boost("reindex")
        text, is_err = configuration._mcp_tool(
            "boost_search", {"query": "zzzznothing"})
        assert is_err is False
        assert "no skills match 'zzzznothing'" in text

    def test_boost_search_on_a_fresh_machine_reports_setup_not_a_miss(
            self, sandbox):
        # The first question any agent ever asks a newly registered server,
        # on a machine with nothing tapped. It used to answer "no skills
        # match 'X'" — true, and byte-identical to a genuine miss, so the
        # agent learns the catalog is empty and stops asking. It must instead
        # name the state and the command that changes it.
        from boost_cli.commands import configuration
        text, is_err = configuration._mcp_tool(
            "boost_search", {"query": "set up code review for a python repo"})
        assert is_err is False
        assert "no skills match" not in text
        assert "nothing is tapped yet" in text
        assert "boost tap --defaults" in text

    def test_boost_doctor_does_not_call_an_untapped_machine_healthy(
            self, sandbox):
        # Every check passes because there is nothing to check. "healthy — no
        # issues found" printed directly under "taps: 0 (0 items available)"
        # is the one clean bill of health that misleads.
        from boost_cli.commands import configuration
        text, _is_err = configuration._mcp_tool("boost_doctor", {})
        assert "taps: 0" in text
        assert "healthy — no issues found" not in text
        assert "nothing is searchable yet" in text

    def test_boost_search_marks_the_kind_of_every_hit(self, boost, tapped,
                                                      monkeypatch):
        # boost_install's description tells the caller to check what kind of
        # thing they are installing, because a rule merges into the context
        # file rather than copying into the store. That check is only
        # possible if the reply it applies to says which hits are rules — so
        # this pins the RENDERING of a mixed result set, with the ranking
        # itself stubbed out (rag's own tests own that half).
        from boost_cli.commands import configuration
        from boost_cli.core import rag
        mixed = [
            {"entry": {"name": "brainstorming", "kind": "skill",
                       "description": "diverge then converge", "tap": "t"}},
            {"entry": {"name": "house-style", "kind": "rule",
                       "description": "prefer the logger", "tap": "t"}},
            {"entry": {"name": "ship-it", "kind": "workflow",
                       "description": "release checklist", "tap": "t"}},
        ]
        monkeypatch.setattr(rag, "search",
                            lambda *a, **kw: (mixed, rag.LLM_RANKER))
        text, is_err = configuration._mcp_tool(
            "boost_search", {"query": "anything"})
        assert is_err is False
        assert "brainstorming — diverge then converge (t)" in text
        assert "house-style [rule] — prefer the logger (t)" in text
        assert "ship-it [workflow] — release checklist (t)" in text

    def _seed_rule_and_workflow(self):
        import hashlib

        from boost_cli.core import lockfile
        rp = paths.home() / ".cursor" / "rules" / "house.mdc"
        rp.parent.mkdir(parents=True)
        rp.write_text("rule body", encoding="utf-8")
        lockfile.set_rule("house-style", {
            "kind": "rule", "version": "1.0.0", "tap": "rule-tap",
            "pinned": True, "installed_at": "2026-01-01T00:00:00Z",
            "materializations": [
                {"agent": "cursor", "mode": "file", "path": str(rp),
                 "sha256": hashlib.sha256(b"rule body").hexdigest()}]})
        lockfile.set_workflow("ship-it", {
            "kind": "workflow", "version": "2.0.0", "tap": "rule-tap",
            "slot": "commands", "materializations": []})
        return rp

    def test_boost_list_includes_rules_and_workflows(self, boost, tapped):
        # The MCP surface must agree with `boost list`: answering "no skills
        # installed" with a rule present is the bug this pins closed.
        from boost_cli.commands import configuration
        boost("install", "brainstorming")
        self._seed_rule_and_workflow()
        text, is_err = configuration._mcp_tool("boost_list", {})
        assert is_err is False
        assert "brainstorming v1.4.0 (fixture-tap)" in text
        assert "house-style v1.0.0 (rule-tap) [rule] [pinned]" in text
        assert "ship-it v2.0.0 (rule-tap) [workflow]" in text

    def test_boost_list_empty_state(self, boost, sandbox):
        # Relaxed from equality: the reply now closes with the per-kind
        # coverage footer, in the empty state too. That is deliberate — a
        # machine with nothing installed is exactly where "what do I have" is
        # least useful on its own, and where a bare "nothing installed" leaves
        # an agent with no reason to look further. The opening sentence is
        # unchanged, which is what this test was pinning.
        from boost_cli.commands import configuration
        text, is_err = configuration._mcp_tool("boost_list", {})
        assert text.startswith("nothing installed")
        assert "0 skills · 0 rules · 0 workflows" in text
        assert is_err is False

    def test_boost_info_on_an_installed_rule(self, boost, tapped):
        from boost_cli.commands import configuration
        self._seed_rule_and_workflow()
        text, is_err = configuration._mcp_tool("boost_info",
                                               {"name": "house-style"})
        assert is_err is False
        assert "kind: rule" in text
        assert "version: 1.0.0" in text
        assert "tap: rule-tap" in text
        assert "installed: yes (2026-01-01T00:00:00Z)" in text
        assert "agents: cursor" in text
        assert "pinned: yes" in text

    def test_boost_doctor_counts_and_checks_rules(self, boost, tapped):
        from boost_cli.commands import configuration
        rp = self._seed_rule_and_workflow()
        text, is_err = configuration._mcp_tool("boost_doctor", {})
        assert "installed rules: 1 · workflows: 1" in text
        assert "healthy — no issues found" in text
        assert is_err is False

        # Edited in place: sync_plan cannot see this (the file exists) — only
        # the recorded materialization digest can.
        rp.write_text("tampered body", encoding="utf-8")
        text, is_err = configuration._mcp_tool("boost_doctor", {})
        assert "rule house-style: modified since install" in text
        assert "1 issue(s) — run `boost doctor` for details" in text
        assert is_err is True

        rp.unlink()      # the cursor materialization vanishes entirely
        text, is_err = configuration._mcp_tool("boost_doctor", {})
        assert "missing_materializations: ('rule', 'house-style')" in text
        assert "1 issue(s) — run `boost sync` to fix" in text
        assert is_err is True

    def test_registry_dispatches_and_lists_all_tools(self, sandbox):
        from boost_cli.commands import configuration
        # tools/list payload and the dispatcher share one registry
        assert configuration.REGISTRY.specs() == configuration._MCP_TOOLS
        assert "boost_discover_github" in configuration.REGISTRY.names()
        assert configuration._mcp_tool("nonexistent_tool", {}) == (None, False)

    def test_tool_descriptions_are_intent_framed(self, sandbox):
        # The descriptions must tell an agent WHEN to reach for boost, not just
        # what each tool does. On Gemini CLI these carry the whole load: it
        # appends server `instructions` to the GEMINI.md memory tier, so the
        # function declarations are the only boost text in context at the
        # moment the tool-call decision is actually made.
        from boost_cli.commands import configuration
        specs = {s["name"]: s["description"].lower()
                 for s in configuration.REGISTRY.specs()}
        # search leads with the observable trigger and states its cost; a miss
        # is named as a real outcome so it does not read as a wasted call.
        assert "has a name" in specs["boost_search"]
        assert "read-only" in specs["boost_search"]
        assert "build it yourself" in specs["boost_search"]
        # authoring survives ONLY here, as a clause — never as a co-equal
        # trigger. Promoting it back cost boost its primary use once already.
        assert "from scratch" in specs["boost_search"]
        # list is the free half of the check — capability already on the box.
        assert "installed" in specs["boost_list"]
        assert "read-only" in specs["boost_list"]
        # ...and being free, its trigger must not be STRICTER than the one on
        # the 10-15s tool. It said "worth a call at the start of anything that
        # will take more than a few steps" while boost_search invited a call
        # on two much looser signals — so an agent applying both literally
        # would pay for the expensive check and skip the instant one. A free,
        # instant, read-only tool has no threshold worth computing.
        assert "more than a few steps" not in specs["boost_list"]
        assert "whenever" in specs["boost_list"]
        # install points back at the search that should precede it
        assert "boost_search" in specs["boost_install"]
        # info is a name lookup, NOT a step between search and install. It has
        # to say so, or an agent reinstates the hop the flow just dropped.
        assert "by name" in specs["boost_info"]
        assert "do not need this between a search and an install" in specs["boost_info"]

    def test_tool_descriptions_earn_the_call_without_overselling_it(self, sandbox):
        # The descriptions were rewritten to pull harder, because on Gemini CLI
        # they are the only boost text at the decision point. Pulling harder is
        # allowed to cost accuracy in exactly zero places, so this pins the
        # parts that make the pull legitimate rather than merely loud.
        from boost_cli.commands import configuration
        specs = {s["name"]: s["description"].lower()
                 for s in configuration.REGISTRY.specs()}

        # The rerank figures stay OUT of the tool description, deliberately.
        # They are real -- _tool_search's own comment records "the rerank moves
        # hit@1 from 0.791 to 0.945" on the 91-query golden set, which is where
        # mcp.INSTRUCTIONS' "95% against 79%" comes from -- but 0.791 is the
        # BM25 baseline over the SIX-repo corpus, and tests/eval/baseline.json
        # records 0.4725 for the twenty-repo corpus that replaced it precisely
        # because six was unrealistically small (see CLAUDE.md). Quoting 79%
        # as today's baseline overstates it by 31 points. A number that precise
        # at the decision point, drifted from the corpus it was measured on, is
        # the flattering-but-stale claim the cost test below exists to prevent.
        # State the mechanism; leave the arithmetic to the eval gate.
        assert "95%" not in specs["boost_search"]

        # The description still says the rerank happens ("ranks the matches
        # with an LLM"), so the REPLY has to say when it did not — otherwise
        # the degraded order is indistinguishable from the promised one. See
        # TestSearchNamesItsRanker below.
        assert "llm" in specs["boost_search"]
        # Stating the benefit must never quietly drop the cost with it.
        # A description whose job is to make a tool worth reaching for is the
        # one place a flattering lie discredits everything around it.
        assert "seconds" in specs["boost_search"]
        assert "instant" not in specs["boost_search"]
        for bad in ("always call", "you must", "never skip"):
            assert bad not in specs["boost_search"], (
                "coercive framing: an agent that is ordered rather than "
                "persuaded routes around the tool the first time it misses")

        # Non-capture moved onto the tool itself for the same Gemini reason: an
        # agent that expects a hit to seize the task is safer not looking.
        assert "the task stays yours" in specs["boost_search"]

        # No claimed corpus size. "thousands of vetted skills" shipped for a
        # long time and is false exactly when it matters most — at a new user's
        # first search. config.DEFAULT_TAPS is seven repos totalling ~950
        # est_items; the tens of thousands only exist once someone has tapped
        # hundreds of registries. Describe the scope ("every registry you have
        # tapped"), never a number the install cannot back.
        assert "thousands" not in specs["boost_search"]

        # install wires ENABLED agents, not all known ones (agents.py:28) --
        # promising "every agent" writes a cheque the enabled-flag can bounce.
        assert "enabled" in specs["boost_install"]

        # doctor used to describe only its inputs. What makes it worth a call
        # is that it ends at an action, not a symptom -- but `boost sync` is
        # not that action for every class it counts: out_of_scope_links is
        # "reported, never auto-removed" (store.sync_plan) and needs --prune,
        # so the description has to carry the exception or an agent runs the
        # named fix and watches the issue survive it.
        assert "next action" in specs["boost_doctor"]
        assert "--prune" in specs["boost_doctor"]

        # Ship the real cost. docs/roadmap/items/mcp-search-cost-was-
        # understated.md measured this path at 11.7-17.0s (median ~12) and
        # exists because "about a second" shipped once already; "a few seconds"
        # is the same understatement wearing a vaguer hat.
        assert "10-15 seconds" in specs["boost_search"]
        assert "a few seconds" not in specs["boost_search"]

        # "vetted" claims item-level curation boost does not do: registries
        # carry curated/confidence, individual skills do not, any repo can be
        # tapped, and _tool_install scans every install for prompt injection
        # and tells the caller to read it before acting on it. A description
        # cannot promise vetting the install path explicitly distrusts.
        assert "vetted" not in specs["boost_search"]

        # _tool_search passes no kind filter, so a match can be a RULE, and
        # _install_rule merges into ~/.claude/CLAUDE.md instead of copying into
        # the store. CLAUDE.md calls that more invasive than a skill; the
        # description must not imply every install is a benign file copy.
        assert "rule" in specs["boost_install"]

        # discover exists to stop an empty search reading as "nobody solved
        # this" -- the reading that makes an agent give up rather than widen.
        assert "empty" in specs["boost_discover_github"]

        # install is the one place an agent gets the mechanism wrong: Gemini is
        # NOT symlinked, it reads the canonical store directly, and a
        # description that implies four symlinks teaches a wrong mental model.
        assert "gemini" in specs["boost_install"]
        assert "directly" in specs["boost_install"]

    def test_discover_github_missing_gh_degrades(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: None)
        text, is_err = configuration._mcp_tool("boost_discover_github",
                                               {"query": "react"})
        assert is_err is True
        assert "gh" in text and "brew install gh" in text

    def test_discover_github_lists_repos(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, discovery
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(
            discovery, "github_skill_search",
            lambda query="", limit=20: [
                {"repo": "octo/skills", "path": "a/SKILL.md", "url": "u",
                 "description": "great skills"},
                {"repo": "acme/pack", "path": "b/SKILL.md", "url": "u",
                 "description": ""}])
        text, is_err = configuration._mcp_tool("boost_discover_github",
                                               {"query": "react", "limit": 5})
        assert is_err is False
        assert "octo/skills — great skills" in text
        assert "acme/pack — b/SKILL.md" in text          # falls back to path

    def test_discover_github_no_results(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, discovery
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(discovery, "github_skill_search",
                            lambda query="", limit=20: [])
        text, is_err = configuration._mcp_tool("boost_discover_github", {})
        assert is_err is False
        assert "no SKILL.md repositories found" in text

    def test_discover_github_search_failure(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, discovery
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/gh")
        monkeypatch.setattr(discovery, "github_skill_search",
                            lambda query="", limit=20: None)
        text, is_err = configuration._mcp_tool("boost_discover_github", {})
        assert is_err is True
        assert "GitHub code search failed" in text

    # ── mcp register / unregister ────────────────────────────────────────
    # boost registers itself with every agent CLI that speaks MCP, and the two
    # grammars disagree on almost every detail: Claude wants
    # `add <name> [options] -- <command>` (its `-e` is variadic, so a name
    # placed after it is swallowed as another env var); Gemini wants
    # `add [options] <name> <commandOrUrl> [args...]` with no `--` (which its
    # trailing variadic would capture and hand to boost as a literal argument).
    # Every test below captures the argv the fake CLI receives — an argv that
    # is merely plausible fails silently, on someone else's machine.

    def _fake_clis(self, monkeypatch, *present):
        """Put exactly ``present`` agent CLIs on PATH; return captured argvs.

        One patch covers every lookup (``shutil`` is one shared module
        object). ``boost`` itself is never "present", which keeps
        ``paths.launcher()`` on its checkout-shim fallback so the expected
        argv is stable.
        """
        monkeypatch.setattr(
            "boost_cli.commands.configuration.shutil.which",
            lambda c: "/usr/local/bin/" + c if c in present else None)
        calls = []

        def fake_run(cmd, **kw):
            calls.append(list(cmd))
            return _proc(cmd, 0, out="Added stdio MCP server boost\n")

        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        return calls

    def _shim(self):
        return str(paths.repo_root() / "boost")

    def _claude_add(self):
        return ["claude", "mcp", "add", "boost", "--scope", "user",
                "-e", "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
                "-e", "no_proxy=*",
                "--", self._shim(), "mcp", "--stdio"]

    def _gemini_add(self):
        return ["gemini", "mcp", "add", "--scope", "user",
                "-e", "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
                "-e", "no_proxy=*",
                "boost", self._shim(), "mcp", "--stdio"]

    def test_register_seeds_the_catalog_on_an_empty_machine(
            self, boost, sandbox, monkeypatch):
        # The point of the whole change: `boost mcp` is the only command a new
        # user is told to run, so it has to leave them with a server that can
        # answer something. BOOST_NO_SEED is cleared explicitly (the conftest
        # sets it so no other test clones anything) and the clone itself is
        # faked — this pins the WIRING, not the network.
        from boost_cli.core import bootstrap, catalog, config, registry
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        seeded = []

        class _Tap:
            def __init__(self, name):
                self.name = name

        monkeypatch.setattr(registry, "add",
                            lambda url, **kw: (
                                seeded.append(url),
                                _Tap(url.split("github.com/")[-1]))[1])
        monkeypatch.setattr(catalog, "rebuild_tap", lambda tap: [{}] * 4)
        self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register")
        assert len(seeded) == len(config.DEFAULT_TAPS)
        assert "items searchable" in r.out
        # Seeding must not displace the thing the user actually asked for.
        assert ("registered boost as an MCP server for Claude Code "
                "(scope: user)") in r.out

    def test_the_sandbox_fixture_really_suppresses_the_seed(
            self, boost, sandbox, monkeypatch):
        # The guard that makes every OTHER test in this file safe. Removing
        # BOOST_NO_SEED from conftest (or forgetting it in a new harness, as
        # the behave environment did) produced no failing test at all — the
        # only symptom was silent network traffic in CI. This is that test:
        # it does NOT clear the variable, and fails loudly if anything taps.
        from boost_cli.core import registry
        monkeypatch.setattr(registry, "add", lambda *a, **kw: pytest.fail(
            "seeded under the sandbox fixture — the BOOST_NO_SEED guard is "
            "gone, and every test that runs `boost mcp` now hits the network"))
        self._fake_clis(monkeypatch, "claude")
        boost("mcp", "register")

    def test_a_failed_clone_is_reported_without_losing_the_registration(
            self, boost, sandbox, monkeypatch):
        # The seed runs on a command whose actual request was "register the
        # MCP server". A dead remote costs a reported line, never the server.
        from boost_cli.core import bootstrap, catalog, config, registry
        from boost_cli.errors import BoostError
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        doomed = str(config.DEFAULT_TAPS[0]["name"])

        class _Tap:
            def __init__(self, name):
                self.name = name

        def flaky_add(url, **kw):
            name = url.split("github.com/")[-1]
            if name == doomed:
                raise BoostError("could not clone %s" % name)
            return _Tap(name)

        monkeypatch.setattr(registry, "add", flaky_add)
        monkeypatch.setattr(catalog, "rebuild_tap", lambda tap: [{}] * 4)
        self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register")
        assert "could not tap %s" % doomed in r.out + r.err
        assert "1 could not be fetched" in r.out
        assert "registered boost as an MCP server" in r.out

    def test_a_totally_dead_network_still_registers(self, boost, sandbox,
                                                    monkeypatch):
        from boost_cli.core import bootstrap, registry
        from boost_cli.errors import BoostError
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        monkeypatch.setattr(registry, "add", lambda *a, **kw: (_ for _ in ()).throw(
            BoostError("network is unreachable")))
        self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register")
        assert "could not reach any default registry" in r.out + r.err
        assert "registered boost as an MCP server" in r.out

    def test_an_unknown_host_fails_before_touching_the_network(
            self, boost, sandbox, monkeypatch):
        # Seeding used to run first, so a typo'd --host spent 14-45s and half
        # a gigabyte before argparse's own error.
        from boost_cli.core import bootstrap, registry
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        monkeypatch.setattr(registry, "add", lambda *a, **kw: pytest.fail(
            "cloned before the host name was validated"))
        r = boost("mcp", "register", "--host", "bogus", expect=1)
        assert "unknown MCP host" in r.err

    def test_seed_and_no_seed_together_are_rejected(self, boost, sandbox):
        # Two explicitly typed flags that contradict each other must not
        # resolve silently — least of all toward the network-touching side.
        r = boost("mcp", "register", "--seed", "--no-seed", expect=2)
        assert "not allowed with" in r.err

    def test_register_leaves_a_configured_machine_alone(
            self, boost, tapped, monkeypatch):
        # Re-running `boost mcp` on a machine that already has taps must not
        # re-clone anything: that would be boost editing state nobody asked
        # it to touch.
        from boost_cli.core import bootstrap, registry
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        monkeypatch.setattr(registry, "add", lambda *a, **kw: pytest.fail(
            "re-tapped a machine that already had taps"))
        self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register")
        assert "items searchable" not in r.out

    def test_no_seed_keeps_registration_offline(self, boost, sandbox,
                                                monkeypatch):
        from boost_cli.core import bootstrap, registry
        monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
        monkeypatch.setattr(registry, "add", lambda *a, **kw: pytest.fail(
            "--no-seed still tapped"))
        self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register", "--no-seed")
        assert "registered boost as an MCP server" in r.out

    def test_register_with_only_claude_cli(self, boost, sandbox, monkeypatch):
        calls = self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register")
        assert calls == [self._claude_add()]
        assert "Added stdio MCP server boost" in r.out
        assert ("registered boost as an MCP server for Claude Code "
                "(scope: user)") in r.out
        # a host that is simply not installed is neither a failure nor noise
        assert "Gemini CLI" not in r.out
        assert "no agent CLI found" not in r.out
        assert journal.events(action="mcp")[0]["hosts"] == "claude"

    def test_register_with_only_gemini_cli(self, boost, sandbox, monkeypatch):
        calls = self._fake_clis(monkeypatch, "gemini")
        r = boost("mcp", "register")
        assert calls == [self._gemini_add()]
        assert "Added stdio MCP server boost" in r.out
        assert ("registered boost as an MCP server for Gemini CLI "
                "(scope: user)") in r.out
        assert "Claude Code" not in r.out
        assert journal.events(action="mcp")[0]["hosts"] == "gemini"

    def test_register_with_both_clis_registers_both(self, boost, sandbox,
                                                    monkeypatch):
        calls = self._fake_clis(monkeypatch, "claude", "gemini")
        r = boost("mcp", "register")
        assert calls == [self._claude_add(), self._gemini_add()]
        assert ("registered boost as an MCP server for Claude Code "
                "(scope: user)") in r.out
        assert ("registered boost as an MCP server for Gemini CLI "
                "(scope: user)") in r.out
        assert journal.events(action="mcp")[0]["hosts"] == "claude,gemini"

    def test_register_without_any_cli_prints_manual_commands(self, boost,
                                                             sandbox,
                                                             monkeypatch):
        calls = self._fake_clis(monkeypatch)          # no agent CLI on PATH
        r = boost("mcp", "register")
        assert calls == []                            # nothing was run
        assert "no agent CLI found (looked for: claude, gemini)" in r.out
        assert " ".join(self._claude_add()) in r.out
        assert " ".join(self._gemini_add()) in r.out
        assert journal.events(action="mcp")[0]["hosts"] == ""

        r = boost("mcp", "unregister")
        assert "claude mcp remove boost" in r.out
        assert "gemini mcp remove --scope user boost" in r.out
        assert journal.events(action="mcp")[0]["subject"] == "unregister"

    def test_explicit_host_registers_only_that_host(self, boost, sandbox,
                                                    monkeypatch):
        calls = self._fake_clis(monkeypatch, "claude", "gemini")
        r = boost("mcp", "register", "--host", "gemini")
        assert calls == [self._gemini_add()]          # claude was not a target
        assert ("registered boost as an MCP server for Gemini CLI "
                "(scope: user)") in r.out
        assert "Claude Code" not in r.out

    def test_explicit_host_missing_prints_that_hosts_command(self, boost,
                                                             sandbox,
                                                             monkeypatch):
        # naming a host you have not installed yet must still show its argv —
        # `auto` is the mode that skips silently, not `--host <name>`.
        calls = self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register", "--host", "gemini")
        assert calls == []
        assert "`gemini` CLI not found — run this yourself:" in r.out
        assert " ".join(self._gemini_add()) in r.out
        assert "claude mcp add" not in r.out
        assert "no agent CLI found" not in r.out      # the named host said it

    def test_host_all_reports_hosts_that_are_not_installed(self, boost, sandbox,
                                                           monkeypatch):
        # `all` is `auto` without the skip: a machine being set up sees the
        # argv for an agent CLI it does not have yet.
        calls = self._fake_clis(monkeypatch, "claude")
        r = boost("mcp", "register", "--host", "all")
        assert calls == [self._claude_add()]
        assert ("registered boost as an MCP server for Claude Code "
                "(scope: user)") in r.out
        assert "`gemini` CLI not found — run this yourself:" in r.out
        assert " ".join(self._gemini_add()) in r.out

    def test_unknown_host_rc1(self, boost, sandbox, monkeypatch):
        self._fake_clis(monkeypatch, "claude", "gemini")
        r = boost("mcp", "register", "--host", "bogus", expect=1)
        assert "unknown MCP host 'bogus'" in r.err
        assert "known hosts: claude, gemini" in r.err

    def test_unregister_uses_each_hosts_grammar(self, boost, sandbox,
                                                monkeypatch):
        calls = self._fake_clis(monkeypatch, "claude", "gemini")
        r = boost("mcp", "unregister")
        # `gemini mcp remove` defaults to --scope project and would report
        # "not found" while leaving the user-scope entry in place, so the
        # scope flag is mandatory on the way out; claude's takes none.
        assert calls == [["claude", "mcp", "remove", "boost"],
                         ["gemini", "mcp", "remove", "--scope", "user",
                          "boost"]]
        assert ("unregistered boost as an MCP server for Claude Code "
                "(scope: user)") in r.out
        assert ("unregistered boost as an MCP server for Gemini CLI "
                "(scope: user)") in r.out
        assert journal.events(action="mcp")[0]["subject"] == "unregister"

    def test_register_names_server_before_env_flags(self, boost, sandbox,
                                                     monkeypatch):
        # Regression: `claude`'s `-e` is variadic, so the server name must come
        # before the first `-e` or it is swallowed as another env var
        # ("Invalid environment variable format: boost"). Pin name < any `-e`,
        # and `--` immediately before the command boost is launched with.
        calls = self._fake_clis(monkeypatch, "claude")
        boost("mcp", "register")
        cmd = calls[0]
        assert cmd[:4] == ["claude", "mcp", "add", "boost"]
        assert cmd.index("boost") < cmd.index("-e")
        assert cmd[cmd.index("--") + 1] == self._shim()

    def test_gemini_puts_flags_before_the_name_and_omits_the_separator(
            self, boost, sandbox, monkeypatch):
        # Regression: gemini's `add` takes yargs positionals
        # (`[options] <name> <commandOrUrl> [args...]`), so flags may precede
        # the name — but a `--` would be captured by the trailing variadic and
        # passed through to boost as a literal argument.
        calls = self._fake_clis(monkeypatch, "gemini")
        boost("mcp", "register")
        cmd = calls[0]
        assert cmd[:3] == ["gemini", "mcp", "add"]
        assert cmd.index("-e") < cmd.index("boost")
        assert "--" not in cmd
        assert cmd[cmd.index("boost") + 1] == self._shim()

    def test_register_failure(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/local/bin/" + c)
        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            lambda cmd, **kw: _proc(cmd, 1, err="no auth"))
        r = boost("mcp", "register", expect=1)
        assert "claude mcp register failed: no auth" in r.err
        # the failing host names itself — not a generic "an agent CLI failed"
        r = boost("mcp", "register", "--host", "gemini", expect=1)
        assert "gemini mcp register failed: no auth" in r.err


# ---------------------------------------------------------------- self-update

class TestSelfUpdate:
    def _not_a_checkout(self, monkeypatch, sandbox):
        """repo_root() normally resolves to the real boost checkout (a git repo
        both locally and in CI) — point it at the sandbox so the pip/pipx paths
        are reachable, and make a real upgrade impossible.

        The second half is not paranoia: while these tests were being written,
        a detection bug sent one of them down the pip branch for real, and it
        installed boost-skill-cli from PyPI over the editable checkout. A test
        must not be one bad branch away from mutating the machine.
        """
        monkeypatch.setattr("boost_cli.core.paths.repo_root", lambda: sandbox)

        def never(cmd, **kw):
            raise AssertionError("this test must not run an upgrade: %s" % cmd)
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade", never)

    def _pipx_install(self, monkeypatch, sandbox):
        self._not_a_checkout(monkeypatch, sandbox)
        prefix = sandbox / "pipx" / "venvs" / "boost-skill-cli"
        prefix.mkdir(parents=True)
        (prefix / "pipx_metadata.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr("sys.prefix", str(prefix))
        monkeypatch.setattr("boost_cli.core.selfupdate.shutil.which",
                            lambda t: "/opt/bin/" + t)

    def test_pipx_install_upgrades_with_pipx(self, boost, sandbox, monkeypatch):
        # The old behaviour: rc=1, "boost is not running from a git checkout",
        # and a hint telling a PyPI user to go clone the repo instead.
        self._pipx_install(monkeypatch, sandbox)
        r = boost("self-update", "--dry-run")
        assert "installed with: pipx" in r.out
        assert ("would run: /opt/bin/pipx upgrade boost-skill-cli "
                "--pip-args=--no-cache-dir") in r.out

    def test_plain_pip_install_upgrades_with_this_interpreter(
            self, boost, sandbox, monkeypatch):
        self._not_a_checkout(monkeypatch, sandbox)
        monkeypatch.setattr("sys.prefix", str(sandbox))
        monkeypatch.setattr("boost_cli.core.selfupdate.installed_version",
                            lambda: "1.0.0")
        r = boost("self-update", "--dry-run")
        assert "installed with: pip" in r.out
        assert ("would run: %s -m pip install --no-cache-dir --upgrade "
                "boost-skill-cli" % sys.executable) in r.out

    def test_pipx_upgrade_reports_the_new_version(self, boost, sandbox,
                                                  monkeypatch):
        self._pipx_install(monkeypatch, sandbox)
        ran = []
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade",
                            lambda cmd, **kw: ran.append(cmd))
        monkeypatch.setattr("boost_cli.core.selfupdate.observed_version",
                            lambda: "9.9.9")
        r = boost("self-update")
        from boost_cli import __version__
        assert ran == [["/opt/bin/pipx", "upgrade", "boost-skill-cli",
                        "--pip-args=--no-cache-dir"]]
        assert ("boost v%s → v9.9.9" % __version__) in r.out
        ev = journal.events(action="self-update")[0]
        assert ev["subject"] == "9.9.9" and ev["method"] == "pipx"

    def _no_op_upgrade(self, monkeypatch, sandbox, latest):
        """A manager that exits 0 and leaves the version exactly where it was.

        `latest` is what PyPI is made to report — None for "PyPI would not say".
        """
        from boost_cli import __version__
        self._pipx_install(monkeypatch, sandbox)
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade",
                            lambda cmd, **kw: None)
        monkeypatch.setattr("boost_cli.core.selfupdate.observed_version",
                            lambda: __version__)
        monkeypatch.setattr("boost_cli.core.selfupdate.latest_version",
                            lambda *a, **kw: latest)
        return __version__

    def test_a_no_op_upgrade_that_leaves_you_behind_is_not_up_to_date(
            self, boost, sandbox, monkeypatch):
        # The bug, end to end. pipx exits 0, pip says "Requirement already
        # satisfied (1.0.422)" because PyPI's simple index was still cached
        # from before the 1.0.423 upload, the version does not move — and boost
        # used to print "already up to date (v1.0.422)". It never asked PyPI.
        here = self._no_op_upgrade(monkeypatch, sandbox, latest="99.0.0")
        r = boost("self-update", expect=1)
        assert "already up to date" not in r.out
        assert ("pipx exited 0 but boost is still v%s — PyPI has v99.0.0"
                % here) in r.err
        # The hint has to be actionable: a plain `upgrade` has already been
        # tried and declined, so it must pin the version and force it.
        assert "pipx install --force boost-skill-cli==99.0.0" in r.err

    def test_a_no_op_upgrade_at_the_latest_version_is_up_to_date(
            self, boost, sandbox, monkeypatch):
        # PyPI agrees this version is the newest, so the claim is earned.
        from boost_cli import __version__
        here = self._no_op_upgrade(monkeypatch, sandbox, latest=__version__)
        r = boost("self-update")
        assert ("already up to date (v%s)" % here) in r.out

    def test_a_no_op_upgrade_offline_admits_it_could_not_confirm(
            self, boost, sandbox, monkeypatch):
        # PyPI unreachable. "Nothing changed" is all boost observed, so that is
        # all it may claim — asserting "up to date" here is the original bug
        # with a different cause.
        here = self._no_op_upgrade(monkeypatch, sandbox, latest=None)
        r = boost("self-update")
        assert ("boost is unchanged (v%s)" % here) in r.out
        assert "could not reach PyPI to confirm" in r.out
        assert "already up to date" not in r.out

    def test_an_upgrade_that_moved_does_not_ask_pypi(self, boost, sandbox,
                                                     monkeypatch):
        # The version moved, so the question is already answered. Asking PyPI
        # anyway would put a network round-trip on the happy path.
        self._pipx_install(monkeypatch, sandbox)
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade",
                            lambda cmd, **kw: None)
        monkeypatch.setattr("boost_cli.core.selfupdate.observed_version",
                            lambda: "9.9.9")

        def never(*a, **kw):
            raise AssertionError("a successful upgrade must not query PyPI")
        monkeypatch.setattr("boost_cli.core.selfupdate.latest_version", never)
        assert "→ v9.9.9" in boost("self-update").out

    def test_upgrade_that_reveals_no_version_does_not_claim_one(
            self, boost, sandbox, monkeypatch):
        self._pipx_install(monkeypatch, sandbox)
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade",
                            lambda cmd, **kw: None)
        monkeypatch.setattr("boost_cli.core.selfupdate.observed_version",
                            lambda: None)
        r = boost("self-update")
        assert "upgraded via pipx; run `boost --version` to confirm" in r.out
        assert "→" not in r.out

    def test_failed_upgrade_surfaces_the_managers_message(
            self, boost, sandbox, monkeypatch):
        self._pipx_install(monkeypatch, sandbox)

        def boom(cmd, **kw):
            raise BoostError("upgrade failed (pipx exited 1)",
                             hint="ERROR: No matching distribution")
        monkeypatch.setattr("boost_cli.core.selfupdate.run_upgrade", boom)
        r = boost("self-update", expect=1)
        assert "upgrade failed (pipx exited 1)" in r.err
        assert "No matching distribution" in r.err

    def test_unknown_install_says_so_instead_of_guessing_pip(
            self, boost, sandbox, monkeypatch):
        self._not_a_checkout(monkeypatch, sandbox)
        monkeypatch.setattr("sys.prefix", str(sandbox))
        monkeypatch.setattr("boost_cli.core.selfupdate.installed_version",
                            lambda: None)
        r = boost("self-update", expect=1)
        assert "cannot work out how boost was installed" in r.err
        assert "pipx upgrade boost-skill-cli" in r.err

    def test_git_checkout_dry_run_changes_nothing(self, boost, sandbox,
                                                  monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.is_repo", lambda p: True)

        def no_git(*a, **kw):
            raise AssertionError("--dry-run must not run git")
        monkeypatch.setattr("boost_cli.core.gitutil.run", no_git)
        r = boost("self-update", "--dry-run")
        assert "installed with: git checkout" in r.out
        assert "pull --ff-only" in r.out

    def _fake_git(self, monkeypatch, *, before, after, described):
        """Stub gitutil so self-update sees a controlled HEAD move + describe.

        ``rev-parse HEAD`` returns ``before`` until the pull runs, ``after``
        afterwards; ``describe`` returns ``described``; ``pull`` is a no-op.
        """
        calls = []
        pulled = {"done": False}
        monkeypatch.setattr("boost_cli.core.gitutil.is_repo", lambda p: True)

        def fake_run(args, **kw):
            calls.append(list(args))
            if "pull" in args:
                pulled["done"] = True
                return _proc(args, 0)
            if "rev-parse" in args:
                return _proc(args, 0, out=(after if pulled["done"] else before))
            if "describe" in args:
                return _proc(args, 0, out=described)
            return _proc(args, 0)

        monkeypatch.setattr("boost_cli.core.gitutil.run", fake_run)
        return calls

    def test_reports_already_up_to_date_when_head_unchanged(
            self, boost, sandbox, monkeypatch):
        # HEAD is identical before and after the pull -> nothing landed
        calls = self._fake_git(monkeypatch, before="sha1\n", after="sha1\n",
                               described="v2.3.3\n")
        r = boost("self-update")
        root = paths.repo_root()
        from boost_cli import __version__
        assert ["-C", str(root), "pull", "--ff-only"] in calls
        assert ("already up to date (v%s)" % __version__) in r.out
        assert "→" not in r.out
        ev = journal.events(action="self-update")[0]
        assert ev["subject"] == __version__ and ev["previous"] == __version__

    def test_reports_new_version_when_pull_advances_head(
            self, boost, sandbox, monkeypatch):
        # the pull fast-forwards HEAD -> report the git-described new version.
        # This path was unreachable before the fix (the old code grepped
        # __init__.py for a __version__ literal setuptools-scm never writes).
        self._fake_git(monkeypatch, before="oldsha\n", after="newsha\n",
                       described="v9.9.9\n")
        r = boost("self-update")
        from boost_cli import __version__
        assert ("boost v%s → v9.9.9" % __version__) in r.out
        ev = journal.events(action="self-update")[0]
        assert ev["subject"] == "9.9.9"          # git-derived, not the stale const
        assert ev["previous"] == __version__


class TestSearchNamesItsRanker:
    """The reply has to say which ranking produced it.

    `boost_search`'s description tells the calling agent an LLM reranks every
    match, "which is what makes the top result worth acting on rather than
    skimming ten". With no AI configured that rerank silently degrades to the
    retrieval order and the reply was byte-for-byte the shape of a reranked
    one — same ten lines, same confidence. `rag.rerank` already computes the
    only signal that distinguishes them; the handler discarded it.
    """

    def test_a_degraded_search_says_the_rerank_did_not_run(self, monkeypatch):
        from boost_cli.commands import configuration
        from boost_cli.core import rag
        monkeypatch.setattr(
            rag, "ensure", lambda *a, **k: True)
        monkeypatch.setattr(rag, "search", lambda *a, **k: (
            [{"entry": {"name": "x", "description": "d", "tap": "t"}}],
            "BM25 full-content"))
        text, _ = configuration._tool_search({"query": "anything"})
        assert "did NOT run" in text
        assert "BM25 full-content" in text
        assert "ANTHROPIC_API_KEY" in text

    def test_a_reranked_search_says_so_without_the_warning(self, monkeypatch):
        from boost_cli.commands import configuration
        from boost_cli.core import rag
        monkeypatch.setattr(rag, "ensure", lambda *a, **k: True)
        monkeypatch.setattr(rag, "search", lambda *a, **k: (
            [{"entry": {"name": "x", "description": "d", "tap": "t"}}],
            rag.LLM_RANKER))
        text, _ = configuration._tool_search({"query": "anything"})
        assert "(ranked by %s)" % rag.LLM_RANKER in text
        assert "did NOT run" not in text

    def test_rerank_returns_that_label_only_when_the_llm_answered(
            self, monkeypatch, sandbox):
        """The producer and the consumer of the label must agree.

        `rag.LLM_RANKER` exists so this is impossible to drift rather than
        merely unlikely — the note in the MCP handler keys on it, and every
        other value means "the rerank did not happen".
        """
        from boost_cli.core import ai, rag
        hits = [{"entry": {"name": "b", "kind": "skill", "description": "d"},
                 "snippet": ""},
                {"entry": {"name": "a", "kind": "skill", "description": "d"},
                 "snippet": ""}]

        monkeypatch.setattr(ai, "available", lambda: False)
        assert rag.rerank("q", hits, engine="BM25 full-content")[1] == \
            "BM25 full-content"

        monkeypatch.setattr(ai, "available", lambda: True)
        monkeypatch.setattr(ai, "ask", lambda *a, **k: '["a", "b"]')
        order, label = rag.rerank("q", hits, engine="BM25 full-content")
        assert label == rag.LLM_RANKER
        assert [h["entry"]["name"] for h in order] == ["a", "b"]

        # Repeating the SAME query now answers from the rerank cache: the
        # order is still the LLM's, so the label stays with it — no new ask.
        monkeypatch.setattr(ai, "ask",
                            lambda *a, **k: pytest.fail("cache must answer"))
        assert rag.rerank("q", hits, engine="BM25 full-content")[1] == \
            rag.LLM_RANKER

        # The model replied, but not with an order — the label must fall back
        # with the ordering, or it claims a rerank that did not take effect.
        # A fresh query, so the cache cannot answer for the degraded model.
        monkeypatch.setattr(ai, "ask", lambda *a, **k: "sorry, I cannot")
        assert rag.rerank("q2", hits, engine="BM25 full-content")[1] == \
            "BM25 full-content"
