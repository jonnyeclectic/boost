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
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import hookhost


def _settings(home, host, name="settings.json"):
    p = home / hookhost.settings_dir(host) / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


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
    """Pretend every known host's CLI is installed."""
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
