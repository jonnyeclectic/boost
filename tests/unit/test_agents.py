# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/agents.py — agent targets and symlink dirs."""
from __future__ import annotations

from boost_cli.core import agents, config


class TestKnownAgents:
    def test_default_dirs_derive_from_sandbox_home(self, sandbox):
        known = agents.known_agents()
        assert list(known) == ["claude-code", "windsurf", "cursor", "gemini",
                               "antigravity"]
        assert known["claude-code"]["dir"] == sandbox / ".claude" / "skills"
        assert known["windsurf"]["dir"] == sandbox / ".windsurf" / "skills"
        assert known["cursor"]["dir"] == sandbox / ".cursor" / "skills"
        assert known["gemini"]["dir"] == sandbox / ".gemini" / "skills"
        assert (known["antigravity"]["dir"]
                == sandbox / ".gemini" / "antigravity-cli" / "skills")
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
            "gemini": sandbox / ".gemini" / "skills",
            "antigravity": sandbox / ".gemini" / "antigravity-cli" / "skills",
        }

    def test_disabled_agent_filtered_out(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        assert agents.enabled_agents() == {
            "claude-code": sandbox / ".claude" / "skills",
            "windsurf": sandbox / ".windsurf" / "skills",
            "gemini": sandbox / ".gemini" / "skills",
            "antigravity": sandbox / ".gemini" / "antigravity-cli" / "skills",
        }


class TestLinkingAgents:
    """The linking/native split — which agents need a skill symlinked in.

    Gemini CLI implements the Agent Skills standard and reads
    ``~/.agents/skills`` (boost's canonical store) directly, so linking for it
    would put one skill in two of its discovery tiers. These assertions pin
    that the two sets partition the enabled agents exactly, because a bug in
    either direction is silent: a missing link makes a skill invisible, and a
    surplus one makes Gemini log a conflict for every skill, every session.
    """

    def test_gemini_is_excluded_by_default(self, sandbox):
        assert agents.linking_agents() == {
            "claude-code": sandbox / ".claude" / "skills",
            "windsurf": sandbox / ".windsurf" / "skills",
            "cursor": sandbox / ".cursor" / "skills",
            "antigravity": sandbox / ".gemini" / "antigravity-cli" / "skills",
        }

    def test_antigravity_links_even_though_it_shares_geminis_tree(self,
                                                                  sandbox):
        # Antigravity CLI succeeds Gemini CLI and lives under ~/.gemini, but it
        # does not implement the Agent Skills standard: it reads neither
        # ~/.agents/skills nor the shared ~/.gemini/skills for CLI scope. So it
        # is a LINKING agent, unlike its predecessor — and the link goes into
        # its own tier, not the shared one, or Gemini would see the same skill
        # twice and log a conflict per skill per session.
        assert "antigravity" in agents.linking_agents()
        assert "antigravity" not in agents.native_store_agents()
        target = agents.linking_agents()["antigravity"]
        assert target != sandbox / ".gemini" / "skills"

    def test_project_scope_excludes_antigravity(self, sandbox):
        # Project scope derives `<repo>/.claude/skills` from the agent's own
        # dotdir, which holds only when the skills dir sits one level under it.
        # Antigravity's sits two (~/.gemini/antigravity-cli/skills), so the
        # derivation would make a dotless `<repo>/antigravity-cli/` nothing
        # reads — and boost would report a coverage it does not have.
        assert list(agents.project_agents()) == ["claude-code", "windsurf",
                                                 "cursor", "gemini"]
        assert agents.agents_for_scope(None) == agents.enabled_agents()
        assert agents.agents_for_scope("/repo") == agents.project_agents()

    def test_rules_and_workflows_skip_a_skills_only_agent(self, sandbox):
        # A skill is a directory boost symlinks; a rule and a workflow are
        # files in a format the agent must already read. Antigravity's are
        # unverified, so writing a plausible one would claim coverage that does
        # not exist — its rules arrive through the gemini entry anyway, which
        # writes the ~/.gemini/GEMINI.md it reads.
        assert "antigravity" not in agents.materializing_agents()
        assert "antigravity" in agents.enabled_agents()

    def test_native_store_agents_is_the_complement(self, sandbox):
        assert agents.native_store_agents() == {
            "gemini": sandbox / ".gemini" / "skills"}

    def test_the_two_sets_partition_enabled_agents(self, sandbox):
        linking, native = agents.linking_agents(), agents.native_store_agents()
        assert not set(linking) & set(native)
        assert {**linking, **native} == agents.enabled_agents()

    def test_links_skills_defaults_true_for_an_agent_that_omits_it(self, sandbox):
        # Every agent but gemini omits the key; none of them may be treated as
        # native or their skills stop being linked anywhere.
        known = agents.known_agents()
        assert known["claude-code"]["links_skills"] is True
        assert known["gemini"]["links_skills"] is False

    def test_a_hand_added_agent_links_by_default(self, sandbox):
        cfg = config.load()
        cfg["agents"]["zed"] = {"dir": "~/.zed/skills", "enabled": True}
        config.save(cfg)
        assert "zed" in agents.linking_agents()
        assert "zed" not in agents.native_store_agents()

    def test_links_skills_is_configurable_back_on(self, sandbox):
        # The documented escape hatch if the ~/.agents/skills alias is ever
        # narrowed: flipping the flag restores the symlink.
        cfg = config.load()
        cfg["agents"]["gemini"]["links_skills"] = True
        config.save(cfg)
        assert "gemini" in agents.linking_agents()
        assert agents.native_store_agents() == {}

    def test_a_disabled_native_agent_is_in_neither_set(self, sandbox):
        cfg = config.load()
        cfg["agents"]["gemini"]["enabled"] = False
        config.save(cfg)
        assert "gemini" not in agents.linking_agents()
        assert "gemini" not in agents.native_store_agents()


class TestDisplayName:
    def test_known_names(self):
        assert agents.display_name("claude-code") == "Claude Code"
        assert agents.display_name("windsurf") == "Windsurf"
        assert agents.display_name("cursor") == "Cursor"
        assert agents.display_name("gemini") == "Gemini CLI"

    def test_every_default_agent_has_a_display_name(self, sandbox):
        # a new agent added to config DEFAULTS without a DISPLAY entry would
        # surface its raw config key ("gemini") in user-facing output.
        for name in agents.known_agents():
            assert agents.display_name(name) != name

    def test_unknown_passthrough(self):
        assert agents.display_name("aider") == "aider"


class TestEnsureAgentDirs:
    def test_creates_every_linking_agents_dir(self, sandbox):
        agents.ensure_agent_dirs()
        for d in (".claude", ".windsurf", ".cursor"):
            assert (sandbox / d / "skills").is_dir()

    def test_a_native_store_agent_gets_no_empty_skills_dir(self, sandbox):
        # nothing is ever linked into ~/.gemini/skills, so creating it would
        # leave an empty directory that `boost heal` first reports as missing.
        agents.ensure_agent_dirs()
        assert not (sandbox / ".gemini" / "skills").exists()

    def test_dir_is_created_once_links_skills_is_on(self, sandbox):
        cfg = config.load()
        cfg["agents"]["gemini"]["links_skills"] = True
        config.save(cfg)
        agents.ensure_agent_dirs()
        assert (sandbox / ".gemini" / "skills").is_dir()

    def test_disabled_dir_not_created(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        agents.ensure_agent_dirs()
        assert (sandbox / ".claude" / "skills").is_dir()
        assert (sandbox / ".windsurf" / "skills").is_dir()
        assert not (sandbox / ".cursor" / "skills").exists()

    def test_is_idempotent_when_dirs_exist(self, sandbox):
        # a second call over already-existing dirs must not raise — pins
        # exist_ok=True (a False/dropped flag would raise FileExistsError).
        agents.ensure_agent_dirs()
        agents.ensure_agent_dirs()
        assert (sandbox / ".claude" / "skills").is_dir()
