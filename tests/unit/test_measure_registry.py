"""The rule behind `est_items`: one item, however many agents it renders for.

`scripts/measure_registry.py` exists because `len(catalog.scan_dir(repo))` stopped
being a count of items once registries began shipping a rendered copy per agent.
These tests build the two shapes that broke the naive counts — the same item
rendered into several dotdirs, and two different items that happen to share a
name — so the rule is pinned without needing a clone or the network.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "measure_registry.py"


def _load():
    spec = importlib.util.spec_from_file_location("measure_registry", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def measure_registry():
    if not _SCRIPT.exists():
        pytest.skip("repo-root scripts/ not reachable (e.g. mutation sandbox)")
    return _load()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _skill(agent: str, name: str = "impeccable") -> str:
    """A SKILL.md as a registry renders it for one particular agent."""
    return (
        "---\n"
        "name: %s\n"
        "description: design the thing\n"
        "---\n"
        "Run `node .%s/skills/%s/scripts/context.mjs` once per session.\n"
        % (name, agent, name))


class TestMirrorsCountOnce:
    def test_one_skill_rendered_for_many_agents_is_one_item(self, tmp_path,
                                                            measure_registry):
        agents = ["claude", "cursor", "gemini", "github", "grok", "kiro",
                  "opencode", "trae", "vibe"]
        for agent in agents:
            _write(tmp_path / (".%s" % agent) / "skills" / "impeccable" /
                   "SKILL.md", _skill(agent))
        counts = measure_registry.measure(tmp_path)
        assert counts == {"skill": 1}, (
            "%d rendered copies counted as %r" % (len(agents), counts))

    def test_per_agent_frontmatter_does_not_split_an_item(self, tmp_path,
                                                          measure_registry):
        """Claude's copy carries allowed-tools/argument-hint; Gemini's cannot.
        Same skill, so the frontmatter is dropped before hashing."""
        _write(tmp_path / ".claude" / "skills" / "s" / "SKILL.md",
               "---\nname: s\ndescription: d\n"
               "argument-hint: \"[target]\"\nallowed-tools:\n  - Bash(npx s *)\n"
               "---\nBody that does not vary.\n")
        _write(tmp_path / ".gemini" / "skills" / "s" / "SKILL.md",
               "---\nname: s\ndescription: d\n---\nBody that does not vary.\n")
        assert measure_registry.measure(tmp_path) == {"skill": 1}

    def test_plugin_packaging_mirror_counts_once(self, tmp_path,
                                                 measure_registry):
        """The shape that had `Owl-Listener/ai-design-skills` shipping as 80."""
        body = "---\nname: audit-prompt\ndescription: d\n---\nAudit it.\n"
        _write(tmp_path / "commands" / "prompt-architecture" /
               "audit-prompt.md", body)
        _write(tmp_path / "claude-plugin" / "prompt-architecture" /
               "commands" / "audit-prompt.md", body)
        assert measure_registry.measure(tmp_path) == {"workflow": 1}


class TestDistinctItemsStayDistinct:
    def test_same_name_different_body_is_two_items(self, tmp_path,
                                                   measure_registry):
        """`designer-skills` ships two unrelated `test-plan` commands."""
        _write(tmp_path / "design-research" / "commands" / "test-plan.md",
               "---\nname: test-plan\ndescription: d\n---\nPlan user research.\n")
        _write(tmp_path / "prototyping-testing" / "commands" / "test-plan.md",
               "---\nname: test-plan\ndescription: d\n---\nPlan prototype tests.\n")
        assert measure_registry.measure(tmp_path) == {"workflow": 2}

    def test_a_subagent_and_a_command_are_separate_items(self, tmp_path,
                                                         measure_registry):
        _write(tmp_path / ".claude" / "agents" / "design-review.md",
               "---\nname: design-review\ndescription: d\n---\nReview proactively.\n")
        _write(tmp_path / ".claude" / "commands" / "design-review.md",
               "---\nname: design-review\ndescription: d\n---\nRun the 7-phase review.\n")
        assert measure_registry.measure(tmp_path) == {"workflow": 2}

    def test_kinds_are_counted_separately(self, tmp_path, measure_registry):
        _write(tmp_path / "skills" / "a" / "SKILL.md",
               "---\nname: a\ndescription: d\n---\nSame text.\n")
        _write(tmp_path / "commands" / "a.md",
               "---\nname: a\ndescription: d\n---\nSame text.\n")
        assert measure_registry.measure(tmp_path) == {"skill": 1, "workflow": 1}


class TestFocusSuffix:
    def test_renders_the_tail_the_focus_strings_carry(self, measure_registry):
        assert measure_registry.focus_suffix(
            {"skill": 7, "workflow": 11}) == "(7 skills, 11 workflows)"

    def test_omits_absent_kinds(self, measure_registry):
        assert measure_registry.focus_suffix({"skill": 1}) == "(1 skills)"

    def test_empty_repo_says_so(self, measure_registry):
        assert measure_registry.focus_suffix({}) == "(no items)"


class TestCommittedCountsStayDerivable:
    def test_self_check_table_covers_the_corrected_row(self, measure_registry):
        """The 80 -> 62 correction is the reason --self-check exists; if the
        row leaves the table, nothing re-derives it from a clone again."""
        assert measure_registry.SELF_CHECK["Owl-Listener/ai-design-skills"] == 62

    def test_self_check_skips_cleanly_without_clones(self, tmp_path,
                                                     measure_registry):
        """It runs against ~/.boost/repos, which CI does not have."""
        assert measure_registry.main(["--self-check", str(tmp_path)]) == 0
