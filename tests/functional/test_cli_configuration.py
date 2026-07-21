"""Functional tests: Configuration commands, in-process.

config / clean / create / policy / onboard / completions / schedule /
serve / mcp / self-update. External tools (launchctl, crontab, gh, claude,
git-for-self-update) are monkeypatched in the module under test.
"""
from __future__ import annotations

import getpass
import io
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from boost_cli.core import frontmatter, journal, paths, policy, util


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t"]
                   + list(args), cwd=str(cwd), check=True, capture_output=True)


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
        ghost = paths.home() / ".claude" / "skills" / "ghost"
        ghost.symlink_to(paths.home() / "nowhere")
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
        assert json.loads(r.out) == {"skills": 1, "violations": [],
                                     "pin_only": False, "unpinned": []}
        boost("policy", "set", "blocked_skills", "brainstorming")
        r = boost("policy", "check", expect=1)
        assert "on the blocklist" in r.out
        assert "1 policy violation(s) across 1 installed skill(s)" in r.err
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
        assert "1 unpinned skill(s): brainstorming" in r.out
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


# ---------------------------------------------------------------- completions

class TestCompletions:
    def test_bash_lists_all_commands(self, boost, sandbox):
        from boost_cli.cli import COMMANDS
        r = boost("completions", "bash")
        line = next(l for l in r.out.splitlines()
                    if l.startswith('complete -W "'))
        names = set(line.split('"')[1].split())
        assert names == {n for n, _g, _m, _s in COMMANDS}
        assert len(names) == 76
        assert "# install: boost completions bash >> ~/.bashrc" in r.out

    def test_zsh_compdef_with_summaries(self, boost, sandbox):
        r = boost("completions", "zsh")
        assert r.out.splitlines()[0] == "#compdef boost"
        assert "'install:Install a skill from a tap registry'" in r.out
        entries = [l for l in r.out.splitlines() if l.startswith("    '")]
        assert len(entries) == 76
        assert "_describe -t commands 'boost command' _boost_commands" in r.out

    def test_fish_complete_lines(self, boost, sandbox):
        r = boost("completions", "fish")
        lines = [l for l in r.out.splitlines()
                 if l.startswith("complete -c boost -n __fish_use_subcommand -a ")]
        assert len(lines) == 76
        assert ("complete -c boost -n __fish_use_subcommand -a install "
                "-d 'Install a skill from a tap registry'") in lines

    def test_bad_shell_rc2_and_shell_env_default(self, boost, sandbox,
                                                 monkeypatch):
        r = boost("completions", "powershell", expect=2)
        assert "invalid choice" in r.err
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        r = boost("completions")
        assert "# boost fish completion" in r.out
        monkeypatch.setenv("SHELL", "/bin/weirdsh")
        r = boost("completions")
        assert "# boost bash completion" in r.out


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
        from boost_cli.core import serve as serve_mod
        from boost_cli.cli import main
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
            assert "1 installed · 5 available across 1 taps" in page
            assert "brainstorming" in page

            with pytest.raises(urllib.error.HTTPError) as exc:
                get("/nope")
            assert exc.value.code == 404
            assert json.loads(exc.value.read().decode()) == {"error": "not found"}

            with pytest.raises(urllib.error.HTTPError) as exc:
                get("/skill/ghost")
            assert exc.value.code == 404
            assert "no skill named 'ghost'" in json.loads(
                exc.value.read().decode())["error"]
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
        assert "taps: 1 (5 skills available)" in text(4)
        assert "healthy — no issues found" in text(4)
        assert "isError" not in by_id[4]["result"]

        assert by_id[5]["error"] == {"code": -32601,
                                     "message": "method not found: no/such"}
        assert by_id[None]["error"]["code"] == -32700
        assert by_id[6]["result"] == {}
        assert by_id[7]["error"]["code"] == -32602

        assert "installed brainstorming v1.4.0 from fixture-tap" in text(8)
        assert "linked agents: claude-code, windsurf, cursor" in text(8)
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

    def test_registry_dispatches_and_lists_all_tools(self, sandbox):
        from boost_cli.commands import configuration
        # tools/list payload and the dispatcher share one registry
        assert configuration._MCP_TOOLS == configuration.REGISTRY.specs()
        assert "boost_discover_github" in configuration.REGISTRY.names()
        assert configuration._mcp_tool("nonexistent_tool", {}) == (None, False)

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

    def test_register_without_claude_prints_manual_command(self, boost, sandbox,
                                                           monkeypatch):
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: None)
        shim = str(paths.repo_root() / "boost")
        r = boost("mcp", "register")
        assert "`claude` CLI not found — run this yourself:" in r.out
        assert ("claude mcp add boost --scope user "
                "-e OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES -e no_proxy=* "
                "-- %s mcp --stdio" % shim) in r.out
        r = boost("mcp", "unregister")
        assert "claude mcp remove boost" in r.out
        assert journal.events(action="mcp")[0]["subject"] == "unregister"

    def test_register_with_claude_cli(self, boost, sandbox, monkeypatch):
        # one patch covers both lookups (shutil is shared): find `claude`,
        # keep launcher() on its checkout-shim fallback
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/local/bin/claude"
                            if c == "claude" else None)
        calls = []

        def fake_run(cmd, **kw):
            calls.append(list(cmd))
            return _proc(cmd, 0, out="Added stdio MCP server boost\n")

        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            fake_run)
        r = boost("mcp", "register")
        assert calls == [["claude", "mcp", "add", "boost", "--scope", "user",
                          "-e", "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES",
                          "-e", "no_proxy=*",
                          "--", str(paths.repo_root() / "boost"),
                          "mcp", "--stdio"]]
        assert "Added stdio MCP server boost" in r.out
        assert "registered boost as an MCP server (scope: user)" in r.out

    def test_register_names_server_before_env_flags(self, boost, sandbox,
                                                     monkeypatch):
        # Regression: `claude`'s `-e` is variadic, so the server name must come
        # before the first `-e` or it is swallowed as another env var
        # ("Invalid environment variable format: boost"). Pin name < any `-e`.
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/local/bin/claude"
                            if c == "claude" else None)
        calls = []
        monkeypatch.setattr(
            "boost_cli.commands.configuration.subprocess.run",
            lambda cmd, **kw: (calls.append(list(cmd)) or _proc(cmd, 0)))
        boost("mcp", "register")
        cmd = calls[0]
        assert cmd[:4] == ["claude", "mcp", "add", "boost"]
        assert cmd.index("boost") < cmd.index("-e")

    def test_register_failure(self, boost, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/local/bin/claude")
        monkeypatch.setattr("boost_cli.commands.configuration.subprocess.run",
                            lambda cmd, **kw: _proc(cmd, 1, err="no auth"))
        r = boost("mcp", "register", expect=1)
        assert "claude mcp register failed: no auth" in r.err


# ---------------------------------------------------------------- self-update

class TestSelfUpdate:
    def test_non_git_checkout_fails_with_hint(self, boost, sandbox, monkeypatch):
        # repo_root() normally resolves to the real boost checkout (a git
        # repo, both locally and in CI); point it at the sandbox instead
        monkeypatch.setattr("boost_cli.core.paths.repo_root", lambda: sandbox)
        r = boost("self-update", expect=1)
        assert "boost is not running from a git checkout" in r.err
        assert "git clone the boost repo" in r.err

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
