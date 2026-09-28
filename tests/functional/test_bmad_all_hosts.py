# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost bmad on` installs its hooks on every installed host, idempotently.

The autopilot's two hooks were written to Claude's settings.json and nowhere
else, even after `boost hooks` learned about a second host: `_autopilot_on`
called `claude_settings.add_hook` without a `host=`, so it took the default.
A user with Gemini CLI installed had to add both by hand, translating the event
names themselves -- which is the part boost exists to know.

Idempotence is asserted rather than assumed because these hooks are written
into a file the user owns and may re-run `bmad on` against at any time.

The fan-out is over `hookhost.hosts()`, so anything asserting *which* hosts
were written reads that table rather than naming two: a third host (Codex)
turned `(claude, gemini)` into a hardcoded expectation that was simply out of
date, and the same assertion derived from the table would have kept passing.
Per-host *facts* still get named literally — that is what they are for.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import hookhost


def _settings(home, host, name=None):
    # Codex reads `hooks.json`, not `settings.json`, so the filename comes
    # from the table too — a test hardcoding it would read an empty dict for
    # a file that was written correctly, and pass by asserting absence.
    p = home / hookhost.settings_dir(host) / (name or hookhost.settings_file(host))
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _at(path):
    """The settings at an explicit path — a relocated `$CODEX_HOME`'s file."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _boost_hooks(data):
    """{event: [names]} for the hooks boost owns, by its `# boost:` marker."""
    found = {}
    for event, entries in (data.get("hooks") or {}).items():
        for block in entries:
            for h in block.get("hooks", []):
                if "# boost:" in h.get("command", ""):
                    found.setdefault(event, []).append(
                        h["command"].rsplit("# boost:", 1)[1].strip())
    return found


@pytest.fixture()
def both_hosts(sandbox, monkeypatch):
    """Pretend every known host's CLI is installed.

    Named for the two it covered when it was written; it has always meant
    *every* host, which is why it patches `which` rather than listing them.
    """
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    return sandbox


class TestAutopilotFansOut:
    def test_hooks_land_on_every_installed_host(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        home = both_hosts
        claude = _boost_hooks(_settings(home, hookhost.CLAUDE))
        gemini = _boost_hooks(_settings(home, hookhost.GEMINI))
        assert "bmad" in claude.get("SessionStart", [])
        assert "bmad-route" in claude.get("UserPromptSubmit", [])
        # Gemini spells them differently; boost must translate, not copy.
        assert "bmad" in gemini.get("SessionStart", []), gemini
        assert "bmad-route" in gemini.get("BeforeAgent", []), gemini

    def test_gemini_timeout_is_milliseconds(self, both_hosts, boost):
        """The unit bug boost exists to absorb: 10s is 10000 on Gemini."""
        boost("bmad", "on", "--scope", "global")
        data = _settings(both_hosts, hookhost.GEMINI)
        entries = [h for blocks in data["hooks"].values()
                   for b in blocks for h in b.get("hooks", [])]
        assert entries, data
        assert all(h["timeout"] == 10000 for h in entries), entries

    def test_running_twice_does_not_duplicate(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        first = _settings(both_hosts, hookhost.GEMINI)
        boost("bmad", "on", "--scope", "global")
        assert _settings(both_hosts, hookhost.GEMINI) == first

    def test_off_removes_them_from_every_host(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        boost("bmad", "off", "--scope", "global")
        for host in (hookhost.CLAUDE, hookhost.GEMINI):
            assert _boost_hooks(_settings(both_hosts, host)) == {}, host


class TestUninstalledHostsAreSkipped:
    def test_a_host_without_its_cli_gets_no_settings_file(self, sandbox, boost,
                                                          monkeypatch):
        """Writing into ~/.gemini for someone who has no Gemini is litter."""
        monkeypatch.setattr("shutil.which",
                            lambda name: "/usr/bin/claude" if name == "claude" else None)
        boost("bmad", "on", "--scope", "global")
        gem = sandbox / hookhost.settings_dir(hookhost.GEMINI) / "settings.json"
        assert not gem.exists(), "wrote Gemini settings with no Gemini installed"
        assert _boost_hooks(_settings(sandbox, hookhost.CLAUDE)), "Claude missed"


class TestHostSelectionRule:
    """Claude unconditionally; a second host on evidence that it is in use.

    The rule is not `boost mcp register`'s. That command shells out to
    `claude mcp add` and genuinely cannot work without the binary; this one
    only writes a settings.json. Gating Claude on `shutil.which` would leave a
    user running inside Claude Code with no hooks whenever the launcher is not
    on boost's PATH — which is exactly what an existing test caught.
    """

    def test_claude_gets_hooks_even_with_no_cli_anywhere(self, sandbox, boost,
                                                         monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _n: None)
        boost("bmad", "on", "--scope", "global")
        assert _boost_hooks(_settings(sandbox, hookhost.CLAUDE)), \
            "Claude must get hooks regardless of what is on PATH"

    def test_a_dotdir_is_evidence_enough_without_the_cli(self, sandbox, boost,
                                                         monkeypatch):
        """Someone who has run Gemini has ~/.gemini, whatever their PATH says."""
        monkeypatch.setattr("shutil.which", lambda _n: None)
        (sandbox / hookhost.settings_dir(hookhost.GEMINI)).mkdir(parents=True)
        boost("bmad", "on", "--scope", "global")
        assert _boost_hooks(_settings(sandbox, hookhost.GEMINI)), \
            "an existing dotdir should have earned the hooks"

    def test_no_cli_and_no_dotdir_means_no_file(self, sandbox, boost,
                                                monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _n: None)
        boost("bmad", "on", "--scope", "global")
        gem = sandbox / hookhost.settings_dir(hookhost.GEMINI) / "settings.json"
        assert not gem.exists()


def _commands(data):
    """{event: command} for boost's own hooks, marker included."""
    return {event: h["command"]
            for event, entries in (data.get("hooks") or {}).items()
            for block in entries for h in block.get("hooks", [])
            if "# boost:" in h.get("command", "")}


class TestEachHostAnswersInItsOwnFormat:
    """Gemini's hooks ask for Gemini's output; Claude's bytes do not move."""

    def test_gemini_commands_name_their_host_and_claudes_do_not(
            self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        gemini = _commands(_settings(both_hosts, hookhost.GEMINI))
        claude = _commands(_settings(both_hosts, hookhost.CLAUDE))
        assert "bmad route --scope global --host gemini 2>/dev/null || true" in (
            gemini["BeforeAgent"])
        assert "bmad orient --scope global --host gemini 2>/dev/null || true" in (
            gemini["SessionStart"])
        assert "--host" not in claude["UserPromptSubmit"]
        assert "bmad route --scope global || true" in claude["UserPromptSubmit"]
        assert "bmad orient --scope global || true" in claude["SessionStart"]

    def test_startup_on_names_the_host_too(self, both_hosts, boost):
        boost("bmad", "startup", "on", "--scope", "global")
        gemini = _commands(_settings(both_hosts, hookhost.GEMINI))
        assert "--host gemini" in gemini["SessionStart"]


class TestHostFlag:
    """`--host` overrides the evidence rule, so Claude-only is one flag."""

    def test_host_claude_never_writes_gemini_settings(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global", "--host", "claude")
        gem = both_hosts / hookhost.settings_dir(hookhost.GEMINI) / "settings.json"
        assert not gem.exists()
        assert _boost_hooks(_settings(both_hosts, hookhost.CLAUDE))

    def test_host_gemini_writes_only_gemini_hooks(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global", "--host", "gemini")
        assert _boost_hooks(_settings(both_hosts, hookhost.GEMINI))
        assert not _boost_hooks(_settings(both_hosts, hookhost.CLAUDE))

    def test_host_auto_is_the_evidence_rule(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global", "--host", "auto")
        for host in (hookhost.CLAUDE, hookhost.GEMINI):
            assert _boost_hooks(_settings(both_hosts, host)), host

    def test_startup_on_honours_it(self, both_hosts, boost):
        boost("bmad", "startup", "on", "--scope", "global", "--host", "claude")
        gem = both_hosts / hookhost.settings_dir(hookhost.GEMINI) / "settings.json"
        assert not gem.exists()


class TestReportsEveryHost:
    """A Gemini-only autopilot is a real install, and must read as one.

    Before `--host`, `_hook_hosts` always returned Claude first, so asking
    Claude alone was a safe shortcut. It is not any more: `doctor` called a
    working Gemini install `autopilot=off router=off`.
    """

    def test_doctor_names_the_host_that_has_the_hooks(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global", "--host", "gemini")
        r = boost("bmad", "doctor")
        assert "autopilot=on" in r.out
        assert "router=on (gemini)" in r.out and "briefing=on (gemini)" in r.out

    def test_claude_only_stays_unqualified(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global", "--host", "claude")
        r = boost("bmad", "doctor")
        assert "router=on  " in r.out and "(gemini)" not in r.out

    def test_every_host_is_listed(self, both_hosts, boost):
        # Derived from the table: the fan-out is over `hookhost.hosts()` and
        # `_hosts_with` reports in that same order, so a fourth host extends
        # this line rather than breaking it.
        boost("bmad", "on", "--scope", "global")
        assert ("router=on (%s)" % ", ".join(hookhost.hosts())
                in boost("bmad", "doctor").out)

    def test_startup_status_names_the_host_too(self, both_hosts, boost):
        boost("bmad", "startup", "on", "--scope", "global", "--host", "gemini")
        r = boost("bmad", "startup", "status", "--scope", "global")
        assert "present (gemini)" in r.out

    def test_nothing_installed_still_reads_off(self, both_hosts, boost):
        r = boost("bmad", "doctor")
        assert "router=off" in r.out and "briefing=off" in r.out


class TestCodexJoinsTheFanOut:
    """The third host, and the two things about it that are silent if wrong.

    Codex reads `$CODEX_HOME/hooks.json` in **seconds**, so a fan-out that
    took the Gemini branch for "not Claude" would write a file Codex never
    opens, with a 10-millisecond timeout, and report success either way.
    """

    def test_the_autopilot_hooks_reach_codex(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        codex = _boost_hooks(_settings(both_hosts, hookhost.CODEX))
        # Codex spells both events the way Claude does — the translation is
        # the identity here, which is exactly why the *file* is the test.
        assert "bmad" in codex.get("SessionStart", []), codex
        assert "bmad-route" in codex.get("UserPromptSubmit", []), codex

    def test_it_lands_in_hooks_json_not_settings_json(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        dotdir = both_hosts / hookhost.settings_dir(hookhost.CODEX)
        assert (dotdir / "hooks.json").exists()
        assert not (dotdir / "settings.json").exists()

    def test_the_timeout_stays_in_seconds(self, both_hosts, boost):
        """Claude's unit, not Gemini's: 10 is 10, not 10000."""
        boost("bmad", "on", "--scope", "global")
        data = _settings(both_hosts, hookhost.CODEX)
        entries = [h for blocks in data["hooks"].values()
                   for b in blocks for h in b.get("hooks", [])]
        assert entries, data
        assert all(h["timeout"] == 10 for h in entries), entries

    def test_the_command_names_codex(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        codex = _commands(_settings(both_hosts, hookhost.CODEX))
        assert "bmad orient --scope global --host codex 2>/dev/null || true" in (
            codex["SessionStart"])

    def test_off_clears_codex_too(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        boost("bmad", "off", "--scope", "global")
        assert _boost_hooks(_settings(both_hosts, hookhost.CODEX)) == {}

    def test_running_twice_does_not_duplicate(self, both_hosts, boost):
        boost("bmad", "on", "--scope", "global")
        first = _settings(both_hosts, hookhost.CODEX)
        boost("bmad", "on", "--scope", "global")
        assert _settings(both_hosts, hookhost.CODEX) == first


class TestARelocatedCodexIsSkippedNotFatal:
    """`$CODEX_HOME` is ambient, so it can point outside the sandbox `$HOME`.

    `add_hook` refuses such a write, which is right for `boost hooks` and
    wrong for a sweep: the refusal would abort `bmad on` before Claude — the
    host that always gets hooks — was written at all.
    """

    @pytest.fixture()
    def escaping(self, both_hosts, monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "real-codex"))
        return tmp_path / "real-codex"

    def test_on_still_writes_the_other_hosts(self, both_hosts, escaping, boost):
        r = boost("bmad", "on", "--scope", "global")
        assert r.rc == 0, r.err
        assert _boost_hooks(_settings(both_hosts, hookhost.CLAUDE))
        assert _boost_hooks(_settings(both_hosts, hookhost.GEMINI))
        assert not escaping.exists()

    def test_it_says_which_host_it_skipped(self, both_hosts, escaping, boost):
        r = boost("bmad", "on", "--scope", "global")
        assert "Codex CLI" in (r.out + r.err)

    def test_off_is_not_aborted_either(self, both_hosts, escaping, boost):
        boost("bmad", "on", "--scope", "global")
        r = boost("bmad", "off", "--scope", "global")
        assert r.rc == 0, r.err
        assert _boost_hooks(_settings(both_hosts, hookhost.CLAUDE)) == {}
        assert not escaping.exists()

    def test_naming_it_explicitly_still_refuses(self, both_hosts, escaping,
                                                boost):
        # The skip is for the sweep. Asking for the host by name is the
        # deliberate act, and it gets the refusal rather than silence.
        r = boost("bmad", "on", "--scope", "global", "--host", "codex",
                  expect=None)
        assert r.rc != 0
        assert "outside this" in (r.out + r.err)

    def test_it_refuses_before_writing_anything(self, both_hosts, escaping,
                                                boost, tmp_path):
        """An explicit refusal must land before the personas do.

        `on` used to resolve its hosts inside `_add_hook_everywhere`, which
        runs *after* `write_personas` and before `_set_scope_state` — so the
        refusal left persona files on disk that no state record claimed, and
        no `off` would ever mention.
        """
        boost("bmad", "on", "--scope", "global", "--host", "codex",
              expect=None)
        agents = both_hosts / ".claude" / "agents"
        assert not (agents.is_dir() and list(agents.glob("bmad-*.md")))
        assert not escaping.exists()

    def test_the_skip_is_said_once_not_once_per_hook(self, both_hosts,
                                                     escaping, boost):
        """`on` installs two hooks. The host list is one decision, not two."""
        r = boost("bmad", "on", "--scope", "global")
        assert (r.out + r.err).count("outside this $HOME") == 1


class TestForceIsTheWayBack:
    """Without it, `doctor` could report a host that `off` refused to reach.

    An escaping `$CODEX_HOME` can already hold a boost hook — written by a
    pre-guard boost, a copied config, or `boost hooks add --force`. `doctor`
    reads it and says so; before `--force` existed, no `bmad` command could
    act on what `doctor` had just reported.
    """

    @pytest.fixture()
    def escaping(self, both_hosts, monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "real-codex"))
        return tmp_path / "real-codex"

    def test_on_force_writes_the_escaping_host(self, both_hosts, escaping,
                                               boost):
        r = boost("bmad", "on", "--scope", "global", "--force")
        assert r.rc == 0, r.err
        assert _boost_hooks(_at(escaping / "hooks.json"))
        # and the contained hosts are still written
        assert _boost_hooks(_settings(both_hosts, hookhost.CLAUDE))

    def test_off_force_clears_it_again(self, both_hosts, escaping, boost):
        boost("bmad", "on", "--scope", "global", "--force")
        r = boost("bmad", "off", "--scope", "global", "--force")
        assert r.rc == 0, r.err
        assert _boost_hooks(_at(escaping / "hooks.json")) == {}

    def test_off_without_force_leaves_it_and_says_so(self, both_hosts,
                                                     escaping, boost):
        boost("bmad", "on", "--scope", "global", "--force")
        r = boost("bmad", "off", "--scope", "global")
        assert r.rc == 0, r.err
        assert _boost_hooks(_at(escaping / "hooks.json"))
        assert "outside this $HOME" in (r.out + r.err)

    def test_naming_the_host_with_force_writes_only_it(self, both_hosts,
                                                       escaping, boost):
        r = boost("bmad", "on", "--scope", "global", "--host", "codex",
                  "--force")
        assert r.rc == 0, r.err
        assert _boost_hooks(_at(escaping / "hooks.json"))
        assert _boost_hooks(_settings(both_hosts, hookhost.CLAUDE)) == {}

    def test_doctor_and_off_now_agree(self, both_hosts, escaping, boost):
        # The defect this flag closes: `doctor` reported a host `off` could
        # not reach, and nothing could reconcile the two.
        boost("bmad", "on", "--scope", "global", "--force")
        assert "codex" in boost("bmad", "doctor").out
        boost("bmad", "off", "--scope", "global", "--force")
        assert "codex" not in boost("bmad", "doctor").out
