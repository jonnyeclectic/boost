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
    compile(dest.read_text(encoding="utf-8"), "<crewai>", "exec")
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


# --- multi-agent skills: crew / graph -------------------------------------

def _add_subagents(installed):
    """Drop two subagents next to the installed skill's SKILL.md."""
    from boost_cli.core import store
    agents = store.skill_store_dir(installed) / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: Reviews the diff\ntools: [read_file, grep]\n"
        "---\nReview carefully.\n", encoding="utf-8")
    (agents / "judge.md").write_text(
        "---\nname: judge\ndescription: Judges findings\n---\nJudge fairly.\n",
        encoding="utf-8")


def test_multi_agent_skill_renders_crew(boost, installed):
    _add_subagents(installed)
    r = boost("adapt", installed, "--to", "crewai", "--model", "none")
    # primary + two subagents, assembled into a sequential Crew
    assert "from crewai import Agent, Crew, Process, Task" in r.out
    assert "brainstorming = Agent(" in r.out
    assert "reviewer = Agent(" in r.out and "judge = Agent(" in r.out
    assert "process=Process.sequential," in r.out
    # a declared tool surfaces as a stub
    assert '@tool("read_file")' in r.out
    compile(r.out, "<crew>", "exec")


def test_multi_agent_skill_renders_graph(boost, installed):
    _add_subagents(installed)
    r = boost("adapt", installed, "--to", "langgraph", "--model", "none")
    assert "def build_brainstorming(model):" in r.out
    assert "create_react_agent(model" in r.out
    assert "builder.add_edge(START, " in r.out
    compile(r.out, "<graph>", "exec")


def test_multi_agent_writes_crew_of_n_summary(boost, installed, tmp_path):
    _add_subagents(installed)
    dest = tmp_path / "crew.py"
    r = boost("adapt", installed, "--to", "crewai", "--model", "none", "-o", str(dest))
    assert "crew of 3" in r.out          # primary + 2 subagents
    compile(dest.read_text(encoding="utf-8"), "<crew>", "exec")


def test_multi_agent_target_without_crew_falls_back_with_note(boost, installed):
    _add_subagents(installed)
    r = boost("adapt", installed, "--to", "agents-sdk", "--model", "none")
    # agents-sdk has no crew path -> single Agent, subagents dropped with a note
    assert "brainstorming = Agent(" in r.out
    assert "reviewer = Agent(" not in r.out
    assert "declares 2 subagent" in r.err
    compile(r.out, "<sdk>", "exec")
