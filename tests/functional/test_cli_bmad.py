"""Functional tests for `boost bmad` — npx/subprocess are stubbed out."""
from __future__ import annotations

import types
from pathlib import Path

import pytest

import boost_cli.commands.bmad as bmad
from boost_cli.core import claude_settings as cs


@pytest.fixture()
def npx(monkeypatch):
    """Stub `npx bmad-method install`: no network, but create realistic skills.

    Returns the list of commands the stub was invoked with, for assertions.
    """
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        directory = Path(cmd[cmd.index("--directory") + 1])
        skills = directory / ".claude" / "skills"
        for name in ("bmad-agent-dev", "bmad-agent-pm", "bmad-help"):
            d = skills / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")
        (directory / "_bmad").mkdir(exist_ok=True)
        (directory / "_bmad-output").mkdir(exist_ok=True)
        return types.SimpleNamespace(
            returncode=0, stdout="BMAD Method v6.10.0 installed", stderr="")

    monkeypatch.setattr(bmad.shutil, "which", lambda _n: "/usr/bin/npx")
    monkeypatch.setattr(bmad.subprocess, "run", fake_run)
    return calls


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    p = tmp_path / "proj"
    p.mkdir()
    monkeypatch.chdir(p)
    return p


class TestInstall:
    def test_project_install_builds_cmd_and_records_state(
            self, boost, sandbox, npx, proj):
        r = boost("bmad", "install")
        assert "installed BMAD" in r.out
        # correct installer invocation
        cmd = npx[0]
        assert cmd[:4] == ["npx", "--yes", "bmad-method@latest", "install"]
        assert "--directory" in cmd and str(proj) in cmd
        assert cmd[cmd.index("--tools") + 1] == "claude-code"
        assert cmd[cmd.index("--modules") + 1] == "bmm"
        # skills materialized + state recorded
        assert (proj / ".claude" / "skills" / "bmad-help").is_dir()
        st = bmad._get_scope_state("project")
        assert st["installed"] is True and st["version"] == "6.10.0"
        assert st["skills"] == 3

    def test_global_install_copies_only_skills(self, boost, sandbox, npx, proj):
        r = boost("bmad", "install", "--scope", "global")
        assert "globally" in r.out
        gskills = sandbox / ".claude" / "skills"
        assert {d.name for d in gskills.glob("bmad-*")} == {
            "bmad-agent-dev", "bmad-agent-pm", "bmad-help"}
        # no stray _bmad in $HOME (staged in temp, discarded)
        assert not (sandbox / "_bmad").exists()
        assert bmad._get_scope_state("global")["installed"] is True

    def test_install_with_startup_flag_enables_hook(
            self, boost, sandbox, npx, proj):
        boost("bmad", "install", "--startup")
        assert cs.has_hook("project", "SessionStart", "bmad", project_dir=proj)

    def test_missing_npx_errors(self, boost, sandbox, monkeypatch, proj):
        monkeypatch.setattr(bmad.shutil, "which", lambda _n: None)
        r = boost("bmad", "install", expect=1)
        assert "npx not found" in r.err


class TestStartupToggle:
    def test_on_off(self, boost, sandbox, proj):
        boost("bmad", "startup", "on")
        assert cs.has_hook("project", "SessionStart", "bmad", project_dir=proj)
        assert bmad._get_scope_state("project")["startup"] is True
        # hook command routes back through boost
        block = cs.load("project", proj)["hooks"]["SessionStart"][0]
        assert "bmad orient --scope project" in block["hooks"][0]["command"]
        assert block["matcher"] == "startup|resume|clear"

        boost("bmad", "startup", "off")
        assert not cs.has_hook("project", "SessionStart", "bmad", project_dir=proj)
        assert bmad._get_scope_state("project")["startup"] is False

    def test_status(self, boost, sandbox, proj):
        r = boost("bmad", "startup", "status")
        assert "BMAD startup" in r.out and "enabled" in r.out

    def test_global_scope(self, boost, sandbox, proj):
        boost("bmad", "startup", "on", "--scope", "global")
        assert cs.has_hook("global", "SessionStart", "bmad")


class TestOrient:
    def test_prints_only_when_enabled(self, boost, sandbox, proj):
        # off by default -> silent
        r = boost("bmad", "orient", "--scope", "project")
        assert r.out.strip() == ""
        # enabled -> prints orientation, incl. the quick-dev default bias
        boost("bmad", "startup", "on")
        r = boost("bmad", "orient", "--scope", "project")
        assert "BMAD MODE ACTIVE" in r.out
        assert "bmad-quick-dev" in r.out
        assert "Default bias" in r.out


class TestDisableEnable:
    def _seed_skills(self, scope_dir):
        skills = scope_dir / ".claude" / "skills"
        for n in ("bmad-help", "bmad-agent-dev"):
            (skills / n).mkdir(parents=True)
        (skills / "other-skill").mkdir(parents=True)

    def test_disable_quarantines_and_enable_restores(
            self, boost, sandbox, proj):
        self._seed_skills(proj)
        boost("bmad", "startup", "on")

        r = boost("bmad", "disable")
        assert "quarantined 2 BMAD skill(s)" in r.out
        skills = proj / ".claude" / "skills"
        assert not list(skills.glob("bmad-*"))       # bmad-* moved out
        assert (skills / "other-skill").exists()      # non-BMAD untouched
        assert not cs.has_hook("project", "SessionStart", "bmad", project_dir=proj)

        r = boost("bmad", "enable")
        assert "restored 2 BMAD skill(s)" in r.out
        assert {d.name for d in skills.glob("bmad-*")} == {
            "bmad-help", "bmad-agent-dev"}

    def test_enable_with_nothing_warns(self, boost, sandbox, proj):
        r = boost("bmad", "enable")
        assert "nothing quarantined" in r.out


class TestUninstall:
    def test_removes_skills_and_runtime(self, boost, sandbox, npx, proj):
        boost("bmad", "install", "--startup")
        assert (proj / "_bmad").exists()
        r = boost("bmad", "uninstall", "--yes")
        assert "removed BMAD (project)" in r.out
        assert not list((proj / ".claude" / "skills").glob("bmad-*"))
        assert not (proj / "_bmad").exists()
        assert not (proj / "_bmad-output").exists()
        assert not cs.has_hook("project", "SessionStart", "bmad", project_dir=proj)
        assert bmad._get_scope_state("project") == {}


class TestInit:
    def test_init_provisions_runtime(self, boost, sandbox, npx, proj):
        r = boost("bmad", "init")
        assert "BMAD runtime ready" in r.out
        assert (proj / "_bmad").exists()
        assert bmad._get_scope_state("project")["installed"] is True


class TestInstallerFailures:
    def test_nonzero_exit_errors(self, boost, sandbox, monkeypatch, proj):
        import types as _t
        monkeypatch.setattr(bmad.shutil, "which", lambda _n: "/usr/bin/npx")
        monkeypatch.setattr(bmad.subprocess, "run", lambda *a, **k:
                            _t.SimpleNamespace(returncode=1, stdout="", stderr="boom"))
        r = boost("bmad", "install", expect=1)
        assert "bmad install failed" in r.err and "boom" in r.err

    def test_oserror_is_wrapped(self, boost, sandbox, monkeypatch, proj):
        def boom(*a, **k):
            raise OSError("no exec")
        monkeypatch.setattr(bmad.shutil, "which", lambda _n: "/usr/bin/npx")
        monkeypatch.setattr(bmad.subprocess, "run", boom)
        r = boost("bmad", "install", expect=1)
        assert "bmad install failed" in r.err


class TestUninstallGlobalAndAbort:
    def test_global_uninstall_clears_state(self, boost, sandbox, npx, proj):
        boost("bmad", "install", "--scope", "global")
        assert list((sandbox / ".claude" / "skills").glob("bmad-*"))
        boost("bmad", "uninstall", "--scope", "global", "--yes")
        assert not list((sandbox / ".claude" / "skills").glob("bmad-*"))
        assert bmad._get_scope_state("global") == {}

    def test_uninstall_aborts_without_confirmation(
            self, boost, sandbox, monkeypatch, proj):
        (proj / ".claude" / "skills" / "bmad-help").mkdir(parents=True)
        monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)  # stdin not a tty -> No
        r = boost("bmad", "uninstall")
        assert "aborted" in r.out
        assert (proj / ".claude" / "skills" / "bmad-help").exists()


class TestResilience:
    def test_global_reinstall_overwrites(self, boost, sandbox, npx, proj):
        boost("bmad", "install", "--scope", "global")
        boost("bmad", "install", "--scope", "global")  # second pass overwrites
        assert {d.name for d in (sandbox / ".claude" / "skills").glob("bmad-*")} == {
            "bmad-agent-dev", "bmad-agent-pm", "bmad-help"}

    def test_corrupt_state_file_ignored(self, boost, sandbox, proj):
        sp = bmad._state_path()
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text("{ not valid json", encoding="utf-8")
        r = boost("bmad", "doctor")  # must not crash
        assert "BMAD status" in r.out


class TestDoctor:
    def test_reports(self, boost, sandbox, proj):
        r = boost("bmad", "doctor")
        assert "BMAD status" in r.out
        assert "global" in r.out and "project" in r.out
