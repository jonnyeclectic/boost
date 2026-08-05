"""Functional tests for `boost bmad` — npx/subprocess are stubbed out.

Two surfaces live here. `install`/`init` delegate provisioning to
`npx bmad-method install` and are exercised against a stubbed installer. `on`,
`off` and `route` are the lightweight autopilot: no Node, no network, one
command, global by default — those are tested for real, end to end.
"""
from __future__ import annotations

import io
import json
import sys
import types
from pathlib import Path

import pytest

import boost_cli.commands.bmad as bmad
from boost_cli.core import bmad as core_bmad
from boost_cli.core import claude_settings as cs


def _hook_cmd(scope, event, name, project_dir=None):
    """The command string of one boost-managed hook, marker stripped."""
    rows = cs.list_hooks(scope, project_dir=project_dir)
    match = [r for r in rows if r["event"] == event and r["name"] == name]
    assert match, "no %s hook named %r in %s scope" % (event, name, scope)
    return match[0]["command"]


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
        # enabled -> prints the roster and the canonical v6 build skill
        boost("bmad", "startup", "on")
        r = boost("bmad", "orient", "--scope", "project")
        assert "BMAD autopilot active" in r.out
        assert "bmad-dev" in r.out and "Amelia" in r.out
        assert "bmad-build" in r.out
        # the v6 shims this text used to advertise are deprecated upstream
        assert "bmad-quick-dev" not in r.out

    def test_a_broken_state_file_never_breaks_the_session(
            self, boost, sandbox, proj):
        """A SessionStart hook that exits non-zero is a hook error every launch."""
        sp = bmad._state_path()
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text("{{{", encoding="utf-8")
        r = boost("bmad", "orient", "--scope", "global")
        assert r.rc == 0


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
    def test_uninstall_also_tears_down_the_autopilot(
            self, boost, sandbox, npx, proj):
        """Otherwise `uninstall` leaves the router banner on every prompt."""
        boost("bmad", "on", "--scope", "project")
        boost("bmad", "install")
        boost("bmad", "uninstall", "--yes")
        assert not cs.has_hook("project", "UserPromptSubmit", "bmad-route",
                               project_dir=proj)
        assert core_bmad.installed_personas(proj / ".claude" / "agents") == []

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

    def test_reports_autopilot_state(self, boost, sandbox, proj):
        # assert the rendered field, not the bare word: "off" also appears in
        # `router=off`, and "on" appears inside "pers-on-as", so a loose
        # substring check passes whatever the autopilot verdict actually is
        r = boost("bmad", "doctor")
        assert "autopilot=off" in r.out
        boost("bmad", "on")
        r = boost("bmad", "doctor")
        assert "autopilot=on" in r.out
        assert "%d personas" % len(core_bmad.PERSONAS) in r.out

    def test_autopilot_reads_as_off_when_the_hook_is_gone(
            self, boost, sandbox, proj):
        """State alone is not the truth — the router hook has to be there."""
        boost("bmad", "on")
        cs.remove_hook("global", "UserPromptSubmit", "bmad-route")
        assert "autopilot=off" in boost("bmad", "doctor").out

    def test_doctor_needs_no_node(self, boost, sandbox, monkeypatch, proj):
        """The lightweight path must not report as broken on a Node-free box."""
        monkeypatch.setattr(bmad.shutil, "which", lambda _n: None)
        r = boost("bmad", "doctor")
        assert r.rc == 0 and "MISSING" in r.out


# ------------------------------------------------------------------- autopilot

class TestAutopilotOn:
    """`boost bmad on` is THE command: one call, global, no Node, no network."""

    def test_installs_personas_and_both_hooks_globally(
            self, boost, sandbox, monkeypatch, proj):
        # no npx on this machine — the lightweight path must not care
        monkeypatch.setattr(bmad.shutil, "which", lambda _n: None)

        r = boost("bmad", "on")

        agents = sandbox / ".claude" / "agents"
        assert core_bmad.installed_personas(agents) == sorted(
            p.slug for p in core_bmad.PERSONAS)
        assert cs.has_hook("global", "SessionStart", "bmad")
        assert cs.has_hook("global", "UserPromptSubmit", "bmad-route")
        assert "bmad route" in _hook_cmd("global", "UserPromptSubmit", "bmad-route")
        assert "bmad orient --scope global" in _hook_cmd(
            "global", "SessionStart", "bmad")

        st = bmad._get_scope_state("global")
        assert st["autopilot"] is True and st["startup"] is True
        assert st["personas"] == len(core_bmad.PERSONAS)
        assert "BMAD autopilot ON" in r.out
        # the agents dir is only watched if it existed at launch
        assert "restart" in r.out.lower()

    def test_both_hooks_cannot_report_failure(self, boost, sandbox, proj):
        """A boost older than this change does not know `bmad route` and exits
        2 — which on UserPromptSubmit erases the user's prompt. The hook is
        installed against whatever boost is on PATH, so the guard has to live in
        the shell, outside any version of boost."""
        boost("bmad", "on")
        for event, name in (("UserPromptSubmit", "bmad-route"),
                            ("SessionStart", "bmad")):
            assert _hook_cmd("global", event, name).endswith("|| true"), event

    def test_the_briefing_hook_names_the_scope_it_was_installed_for(
            self, boost, sandbox, proj):
        """`_orient` defaults to project scope, so a global `on` whose hook
        omitted `--scope global` would read project state and print nothing."""
        boost("bmad", "on")
        assert "--scope global" in _hook_cmd("global", "SessionStart", "bmad")
        r = boost("bmad", "orient", "--scope", "global")
        assert "BMAD autopilot active" in r.out

    def test_is_idempotent(self, boost, sandbox, proj):
        boost("bmad", "on")
        boost("bmad", "on")
        agents = sandbox / ".claude" / "agents"
        assert len(list(agents.glob("*.md"))) == len(core_bmad.PERSONAS)
        blocks = cs.load("global")["hooks"]["UserPromptSubmit"]
        assert sum(len(b["hooks"]) for b in blocks) == 1

    def test_project_scope_stays_in_the_project(self, boost, sandbox, proj):
        boost("bmad", "on", "--scope", "project")
        assert (proj / ".claude" / "agents" / "bmad-dev.md").is_file()
        assert not (sandbox / ".claude" / "agents").exists()
        assert cs.has_hook("project", "UserPromptSubmit", "bmad-route",
                           project_dir=proj)

    def test_does_not_disturb_a_users_own_hooks(self, boost, sandbox, proj):
        boost("hooks", "add", "UserPromptSubmit", "-c", "echo hi", "-n", "mine",
              "--scope", "global")
        boost("bmad", "on")
        boost("bmad", "off")
        assert cs.has_hook("global", "UserPromptSubmit", "mine")


class TestAutopilotOff:
    def test_removes_hooks_and_personas(self, boost, sandbox, proj):
        boost("bmad", "on")
        r = boost("bmad", "off")
        assert "BMAD autopilot OFF" in r.out
        assert not cs.has_hook("global", "SessionStart", "bmad")
        assert not cs.has_hook("global", "UserPromptSubmit", "bmad-route")
        assert core_bmad.installed_personas(sandbox / ".claude" / "agents") == []
        assert bmad._get_scope_state("global")["autopilot"] is False

    def test_off_without_on_is_harmless(self, boost, sandbox, proj):
        r = boost("bmad", "off")
        assert r.rc == 0

    def test_hand_edited_personas_survive(self, boost, sandbox, proj):
        boost("bmad", "on")
        mine = sandbox / ".claude" / "agents" / "bmad-dev.md"
        mine.write_text("---\nname: bmad-dev\n---\nmine now\n", encoding="utf-8")
        boost("bmad", "off")
        assert mine.read_text(encoding="utf-8") == (
            "---\nname: bmad-dev\n---\nmine now\n")

    def test_an_edited_persona_that_kept_the_stamp_also_survives(
            self, boost, sandbox, proj):
        """The realistic edit: change the body, leave the HTML comment alone."""
        boost("bmad", "on")
        mine = sandbox / ".claude" / "agents" / "bmad-dev.md"
        edited = mine.read_text(encoding="utf-8").replace(
            "Mission:", "Mission (house rules):")
        mine.write_text(edited, encoding="utf-8")

        r = boost("bmad", "on")               # re-running must not clobber it
        assert "kept your edits" in r.out and "bmad-dev" in r.out
        assert mine.read_text(encoding="utf-8") == edited

        boost("bmad", "off")                  # ...nor must tearing down
        assert mine.read_text(encoding="utf-8") == edited


class TestRoute:
    """The UserPromptSubmit hook target. It runs on every prompt, so its
    contract is: never fail, never block, and say nothing about a non-task."""

    def _pipe(self, monkeypatch, payload):
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    def test_emits_the_hook_json_contract(self, boost, sandbox, monkeypatch, proj):
        (proj / "tests").mkdir()
        (proj / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
        self._pipe(monkeypatch, json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "prompt": "implement the new export command",
            "cwd": str(proj)}))

        r = boost("bmad", "route")

        payload = json.loads(r.out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "bmad-dev" in ctx and "Amelia" in ctx
        assert "make check" in ctx and "tests/" in ctx

    def test_uses_the_cwd_the_hook_reports_not_its_own(
            self, boost, sandbox, monkeypatch, tmp_path, proj):
        """The hook may run anywhere; `cwd` from stdin is the project."""
        elsewhere = tmp_path / "elsewhere"
        (elsewhere / "spec").mkdir(parents=True)
        self._pipe(monkeypatch, json.dumps({
            "prompt": "fix the crash in store.install", "cwd": str(elsewhere)}))
        r = boost("bmad", "route")
        assert "spec/" in r.out

    def test_trivial_prompts_produce_no_output_at_all(
            self, boost, sandbox, monkeypatch, proj):
        self._pipe(monkeypatch, json.dumps({"prompt": "what is a tap?"}))
        r = boost("bmad", "route")
        assert r.out == "" and r.rc == 0

    def test_accepts_a_positional_prompt_for_humans(self, boost, sandbox, proj):
        r = boost("bmad", "route", "add tests for catalog.scan_dir", "--plain")
        assert "bmad-tea" in r.out and "Murat" in r.out
        assert not r.out.startswith("{")

    def test_plain_stdin_is_treated_as_the_prompt(
            self, boost, sandbox, monkeypatch, proj):
        self._pipe(monkeypatch, "refactor the dense retrieval engine")
        r = boost("bmad", "route", "--plain")
        assert "bmad-dev" in r.out

    @pytest.mark.parametrize("payload", ["", "   ", "not json at all {", "null"])
    def test_never_fails_on_junk_input(
            self, boost, sandbox, monkeypatch, proj, payload):
        """Exit 2 on UserPromptSubmit *erases the user's prompt*. Never exit 2."""
        self._pipe(monkeypatch, payload)
        r = boost("bmad", "route", expect=None)
        assert r.rc == 0

    def test_survives_an_unreadable_stdin(self, boost, sandbox, monkeypatch, proj):
        """Note the out-of-band flag: `_route` swallows every exception, so a
        test that signalled failure by raising inside it would convert its own
        failure into the success it asserts."""
        called = []

        class Exploding:
            def isatty(self):
                return False

            def read(self):
                called.append("read")
                raise OSError("stdin is gone")

        monkeypatch.setattr(sys, "stdin", Exploding())
        r = boost("bmad", "route", expect=None)
        assert called == ["read"]          # it really did go down that path
        assert r.rc == 0 and r.out == ""

    def test_an_interactive_stdin_is_not_read(self, boost, sandbox, monkeypatch,
                                              proj):
        """`boost bmad route` at a prompt must return, not hang on EOF.

        Asserted on a recorded flag rather than by raising: an `AssertionError`
        here would be caught by `_route`'s never-block handler and the test
        would pass while the command hung in real use.
        """
        reads = []

        class Tty:
            def isatty(self):
                return True

            def read(self):
                reads.append("read")
                return ""

        monkeypatch.setattr(sys, "stdin", Tty())
        r = boost("bmad", "route")
        assert reads == [], "an interactive stdin must never be read"
        assert r.out == ""

    def test_a_project_signal_failure_still_exits_zero(
            self, boost, sandbox, monkeypatch, proj):
        monkeypatch.setattr(core_bmad, "project_signals",
                            lambda _root: (_ for _ in ()).throw(RuntimeError("nope")))
        self._pipe(monkeypatch, json.dumps({"prompt": "implement the thing"}))
        r = boost("bmad", "route", expect=None)
        assert r.rc == 0


class TestPersonas:
    def test_lists_the_roster_and_where_it_would_land(self, boost, sandbox, proj):
        r = boost("bmad", "personas")
        for p in core_bmad.PERSONAS:
            assert p.slug in r.out and p.character in r.out
        assert "not installed" in r.out

    def test_reports_installed_after_on(self, boost, sandbox, proj):
        boost("bmad", "on")
        r = boost("bmad", "personas")
        assert "not installed" not in r.out
