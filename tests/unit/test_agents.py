"""Unit tests: boost_cli/core/agents.py — agent targets and symlink dirs."""
from __future__ import annotations

from boost_cli.core import agents, config


class TestKnownAgents:
    def test_default_dirs_derive_from_sandbox_home(self, sandbox):
        known = agents.known_agents()
        assert set(known) == {"claude-code", "windsurf", "cursor"}
        assert known["claude-code"]["dir"] == sandbox / ".claude" / "skills"
        assert known["windsurf"]["dir"] == sandbox / ".windsurf" / "skills"
        assert known["cursor"]["dir"] == sandbox / ".cursor" / "skills"
        assert all(spec["enabled"] is True for spec in known.values())

    def test_enabled_flag_honored_from_config(self, sandbox):
        cfg = config.load()
        cfg["agents"]["windsurf"]["enabled"] = False
        config.save(cfg)
        known = agents.known_agents()
        assert known["windsurf"]["enabled"] is False
        assert known["claude-code"]["enabled"] is True

    def test_custom_agent_enabled_defaults_true(self, sandbox):
        cfg = config.load()
        cfg["agents"]["aider"] = {"dir": "~/.aider/skills"}
        config.save(cfg)
        known = agents.known_agents()
        assert known["aider"]["enabled"] is True
        assert known["aider"]["dir"] == sandbox / ".aider" / "skills"


class TestEnabledAgents:
    def test_all_enabled_by_default(self, sandbox):
        assert agents.enabled_agents() == {
            "claude-code": sandbox / ".claude" / "skills",
            "windsurf": sandbox / ".windsurf" / "skills",
            "cursor": sandbox / ".cursor" / "skills",
        }

    def test_disabled_agent_filtered_out(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        assert agents.enabled_agents() == {
            "claude-code": sandbox / ".claude" / "skills",
            "windsurf": sandbox / ".windsurf" / "skills",
        }


class TestDisplayName:
    def test_known_names(self):
        assert agents.display_name("claude-code") == "Claude Code"
        assert agents.display_name("windsurf") == "Windsurf"
        assert agents.display_name("cursor") == "Cursor"

    def test_unknown_passthrough(self):
        assert agents.display_name("aider") == "aider"


class TestEnsureAgentDirs:
    def test_creates_all_enabled_dirs(self, sandbox):
        agents.ensure_agent_dirs()
        for d in (".claude", ".windsurf", ".cursor"):
            assert (sandbox / d / "skills").is_dir()

    def test_disabled_dir_not_created(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        agents.ensure_agent_dirs()
        assert (sandbox / ".claude" / "skills").is_dir()
        assert (sandbox / ".windsurf" / "skills").is_dir()
        assert not (sandbox / ".cursor" / "skills").exists()
