"""Functional tests: `boost adapt` — render a skill as framework source."""
from __future__ import annotations


def test_adapt_installed_skill_to_crewai_stdout(boost, installed):
    r = boost("adapt", installed, "--to", "crewai")
    assert "from crewai import Agent" in r.out
    assert "brainstorming = Agent(" in r.out
    assert 'role="brainstorming"' in r.out
    # emitted source must be valid Python
    compile(r.out, "<crewai>", "exec")


def test_adapt_to_agents_sdk(boost, installed):
    r = boost("adapt", installed, "--to", "agents-sdk")
    assert "from agents import Agent" in r.out
    assert 'name="brainstorming"' in r.out
    compile(r.out, "<sdk>", "exec")


def test_adapt_from_tap_without_installing(boost, tapped):
    # resolves via the tap clone even though nothing is installed
    r = boost("adapt", "brainstorming", "--to", "crewai")
    assert "brainstorming = Agent(" in r.out


def test_adapt_writes_file_with_o(boost, installed, tmp_path):
    dest = tmp_path / "out" / "reviewer.py"
    r = boost("adapt", installed, "--to", "crewai", "-o", str(dest))
    assert dest.exists()
    compile(dest.read_text(), "<crewai>", "exec")
    assert "adapted" in r.out  # success line


def test_unknown_framework_errors(boost, installed):
    r = boost("adapt", installed, "--to", "langchain", expect=1)
    assert "unknown framework" in (r.out + r.err).lower()


def test_missing_to_flag_errors(boost, installed):
    # --to is required
    boost("adapt", installed, expect=2)


def test_unknown_skill_errors(boost, tapped):
    boost("adapt", "does-not-exist", "--to", "crewai", expect=1)


def test_default_model_wires_boost_ai_model(boost, installed):
    # By default the exported agent is pinned to boost's configured ai.model,
    # normalized to a LiteLLM provider/model id.
    r = boost("adapt", installed, "--to", "crewai")
    assert "from crewai import Agent, LLM" in r.out
    assert "llm=LLM(model=\"anthropic/" in r.out
    compile(r.out, "<crewai>", "exec")


def test_model_none_opts_out(boost, installed):
    # `--model none` restores the framework's own default (no LLM wiring).
    r = boost("adapt", installed, "--to", "crewai", "--model", "none")
    assert "LLM" not in r.out
    assert "llm=" not in r.out
    compile(r.out, "<crewai>", "exec")


def test_custom_model_is_used_verbatim(boost, installed):
    r = boost("adapt", installed, "--to", "agents-sdk", "--model", "openai/gpt-4o")
    assert 'model=LitellmModel(model="openai/gpt-4o")' in r.out
    assert "from agents.extensions.models.litellm_model import LitellmModel" in r.out
    compile(r.out, "<sdk>", "exec")


def test_bare_model_gets_anthropic_prefix(boost, installed):
    r = boost("adapt", installed, "--to", "crewai", "--model", "claude-opus-4-8")
    assert 'model="anthropic/claude-opus-4-8"' in r.out
