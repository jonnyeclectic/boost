# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for core.adapters multi-agent path — subagent detection and the
CrewAI Crew / LangGraph StateGraph renderers.

Mutation-gated like the single-agent tests: assertions pin exact emitted
structure, prove the output is valid Python (`compile`), and prove escaped
literals round-trip, so any template mutation (dropped field, swapped kwarg,
broken edge wiring) fails a test.
"""
import pytest

from boost_cli.core import adapters


def _spec(name, description="d", instructions="body", tools=()):
    return adapters.AgentSpec(name, description, instructions, list(tools))


# --- parse_tools ----------------------------------------------------------

class TestParseTools:
    def test_list_normalized_and_deduped(self):
        # `Read`/`read` both normalize to `read` -> deduped; order preserved.
        assert adapters.parse_tools({"tools": ["Read", "read", "grep"]}) == ["read", "grep"]

    def test_comma_or_space_string(self):
        assert adapters.parse_tools({"tools": "read_file, grep bash"}) == \
            ["read_file", "grep", "bash"]

    def test_allowed_tools_key(self):
        assert adapters.parse_tools({"allowed-tools": "read_file"}) == ["read_file"]

    def test_allowed_tools_underscore_key(self):
        assert adapters.parse_tools({"allowed_tools": ["grep"]}) == ["grep"]

    def test_tools_key_wins_over_allowed(self):
        # `tools` is checked first; `allowed-tools` is ignored when both present.
        assert adapters.parse_tools({"tools": ["a"], "allowed-tools": ["b"]}) == ["a"]

    def test_missing_is_empty(self):
        assert adapters.parse_tools({"model": "x"}) == []

    def test_empty_value_is_empty(self):
        # a falsy value (empty list/str) is skipped, not treated as declared
        assert adapters.parse_tools({"tools": []}) == []
        assert adapters.parse_tools({"tools": ""}) == []

    def test_entries_normalizing_empty_are_dropped(self):
        # `***` -> "" after _ident; must not leak an empty identifier
        assert adapters.parse_tools({"tools": ["***", "grep"]}) == ["grep"]

    def test_empty_parts_skipped_not_terminating(self):
        # a blank entry must be *skipped* (continue), not end the scan (break),
        # so a later real tool still lands
        assert adapters.parse_tools({"tools": ["", "grep"]}) == ["grep"]
        assert adapters.parse_tools({"tools": "  grep"}) == ["grep"]

    def test_non_string_list_entries_coerced(self):
        assert adapters.parse_tools({"tools": [123, "grep"]}) == ["s_123", "grep"]


# --- discover_subagents ---------------------------------------------------

def _skill(tmp_path, subagents=None, dir_name="agents"):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: wf\ndescription: top\n---\nBody\n", encoding="utf-8")
    if subagents:
        d = tmp_path / dir_name
        d.mkdir()
        for fn, text in subagents.items():
            (d / fn).write_text(text, encoding="utf-8")
    return tmp_path


class TestDiscoverSubagents:
    def test_flat_skill_has_none(self, tmp_path):
        _skill(tmp_path)
        assert adapters.discover_subagents(tmp_path) == []

    def test_missing_dir_is_empty(self, tmp_path):
        assert adapters.discover_subagents(tmp_path / "nope") == []

    def test_none_arg_is_empty(self):
        assert adapters.discover_subagents(None) == []

    def test_finds_agents_sorted(self, tmp_path):
        _skill(tmp_path, {
            "reviewer.md": "---\nname: reviewer\ndescription: Reviews\n---\nR\n",
            "judge.md": "---\nname: judge\ndescription: Judges\n---\nJ\n",
        })
        specs = adapters.discover_subagents(tmp_path)
        # sorted by path: judge.md before reviewer.md
        assert [s.name for s in specs] == ["judge", "reviewer"]
        assert specs[0].instructions == "J"
        assert specs[0].description == "Judges"      # description carried, not None

    def test_subagents_dir_also_matches(self, tmp_path):
        _skill(tmp_path, {"a.md": "---\nname: a\ndescription: x\n---\nB\n"},
               dir_name="subagents")
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["a"]

    def test_nested_plugin_agents_dir(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("---\nname: wf\ndescription: t\n---\n", encoding="utf-8")
        nested = tmp_path / "plugins" / "x" / "agents"
        nested.mkdir(parents=True)
        (nested / "helper.md").write_text(
            "---\nname: helper\ndescription: Helps\n---\nH\n", encoding="utf-8")
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["helper"]

    def test_tools_parsed_from_subagent(self, tmp_path):
        _skill(tmp_path, {
            "a.md": "---\nname: a\ndescription: x\ntools: [read_file, grep]\n---\nB\n"})
        assert adapters.discover_subagents(tmp_path)[0].tools == ["read_file", "grep"]

    def test_missing_name_or_description_skipped(self, tmp_path):
        _skill(tmp_path, {
            "noname.md": "---\ndescription: has desc only\n---\nB\n",
            "nodesc.md": "---\nname: hasname\n---\nB\n",
            "ok.md": "---\nname: ok\ndescription: fine\n---\nB\n",
        })
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["ok"]

    def test_skill_md_never_a_subagent(self, tmp_path):
        # even a SKILL.md placed under agents/ is excluded by name — and being
        # skipped must not abort the walk (SKILL.md sorts before reviewer.md)
        _skill(tmp_path, {
            "SKILL.md": "---\nname: nested\ndescription: d\n---\nB\n",
            "reviewer.md": "---\nname: reviewer\ndescription: R\n---\nB\n",
        })
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["reviewer"]

    def test_non_agent_file_skipped_without_aborting_walk(self, tmp_path):
        # a stray root-level .md (sorts before agents/) is not under a subagent
        # dir -> skipped; the later real agent must still be found
        _skill(tmp_path, {"reviewer.md": "---\nname: reviewer\ndescription: R\n---\nB\n"})
        (tmp_path / "AAA.md").write_text(
            "---\nname: stray\ndescription: doc\n---\nB\n", encoding="utf-8")
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["reviewer"]

    def test_commands_dir_not_treated_as_subagent(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("---\nname: wf\ndescription: t\n---\n", encoding="utf-8")
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "slash.md").write_text(
            "---\nname: slash\ndescription: cmd\n---\nB\n", encoding="utf-8")
        assert adapters.discover_subagents(tmp_path) == []

    def test_non_markdown_ignored(self, tmp_path):
        _skill(tmp_path, {"a.md": "---\nname: a\ndescription: x\n---\nB\n"})
        (tmp_path / "agents" / "config.yaml").write_text("name: nope\n", encoding="utf-8")
        assert [s.name for s in adapters.discover_subagents(tmp_path)] == ["a"]

    def test_file_arg_is_empty(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text("---\nname: wf\ndescription: t\n---\n", encoding="utf-8")
        assert adapters.discover_subagents(f) == []   # not a directory


# --- helpers: idents & tool union ----------------------------------------

class TestUniqueHelpers:
    def test_idents_disambiguated_on_collision(self):
        specs = [_spec("Judge"), _spec("judge"), _spec("JUDGE")]
        assert adapters._unique_idents(specs) == ["judge", "judge_1", "judge_2"]

    def test_idents_distinct_unchanged(self):
        specs = [_spec("worker"), _spec("dedup-judge")]
        assert adapters._unique_idents(specs) == ["worker", "dedup_judge"]

    def test_tools_union_ordered_deduped(self):
        specs = [_spec("a", tools=["read", "grep"]),
                 _spec("b", tools=["grep", "bash"])]
        assert adapters._unique_tools(specs) == ["read", "grep", "bash"]

    def test_tools_union_empty(self):
        assert adapters._unique_tools([_spec("a"), _spec("b")]) == []


# --- render_crew ----------------------------------------------------------

CREW = [
    adapters.AgentSpec("rust-review", "Coordinate the review", "You orchestrate.", ["read_file"]),
    adapters.AgentSpec("dedup-judge", "Remove dupes", "Merge dupes.", []),
]

# A single agent declaring two tools — pins the `, ` join separator.
TWO_TOOL = [adapters.AgentSpec("worker", "Do work", "Work.", ["read_file", "grep"])]


class TestRenderCrew:
    def test_header_has_provenance_and_description(self):
        src = adapters.render_crew("rust-review", "A Rust review workflow", CREW)
        assert "boost adapt rust-review --to crewai" in src
        assert "# A Rust review workflow" in src

    def test_header_is_the_exact_banner(self):
        # pins the banner text and its --to <kind> verbatim
        src = adapters.render_crew("wf", "d", CREW)
        assert src.startswith(
            "# Generated by `boost adapt wf --to crewai`. Do not edit by hand.\n")

    def test_multiline_description_collapsed_to_one_comment(self):
        src = adapters.render_crew("wf", "line one\nline two", CREW)
        assert "# line one line two\n" in src   # newline -> space, still one line

    def test_empty_description_falls_back_to_workflow_name(self):
        src = adapters.render_crew("wf", "", CREW)
        assert "# wf\n" in src

    def test_imports_llm_only_with_model(self):
        assert "from crewai import Agent, Crew, Process, Task\n" in \
            adapters.render_crew("wf", "d", CREW)
        assert "from crewai import Agent, Crew, Process, Task, LLM\n" in \
            adapters.render_crew("wf", "d", CREW, "claude-opus-4-8")

    def test_tool_import_only_when_tools_present(self):
        assert "from crewai.tools import tool" in adapters.render_crew("wf", "d", CREW)
        no_tools = [_spec("a"), _spec("b")]
        assert "from crewai.tools import tool" not in \
            adapters.render_crew("wf", "d", no_tools)

    def test_agent_per_spec_with_role_goal_backstory(self):
        src = adapters.render_crew("wf", "d", CREW)
        assert "rust_review = Agent(" in src and "dedup_judge = Agent(" in src
        assert 'role="rust-review"' in src
        assert 'goal="Coordinate the review"' in src
        assert 'backstory="You orchestrate."' in src

    def test_tools_line_only_for_agents_that_declare_them(self):
        src = adapters.render_crew("wf", "d", CREW)
        assert "    tools=[read_file],\n" in src            # rust-review has one
        # dedup-judge declares none -> no tools line in its block
        dedup_block = src.split("dedup_judge = Agent(")[1].split(")")[0]
        assert "tools=" not in dedup_block

    def test_two_tools_joined_with_comma_space(self):
        src = adapters.render_crew("wf", "d", TWO_TOOL)
        assert "    tools=[read_file, grep],\n" in src

    def test_llm_line_present_with_model(self):
        src = adapters.render_crew("wf", "d", CREW, "claude-opus-4-8")
        assert 'llm=LLM(model="anthropic/claude-opus-4-8"),' in src

    def test_task_per_agent_and_crew_assembly(self):
        src = adapters.render_crew("wf", "d", CREW)
        assert "rust_review_task = Task(" in src
        assert "agent=rust_review," in src
        assert "crew = Crew(" in src                        # capital C, not shadowed
        assert "agents=[rust_review, dedup_judge]," in src
        assert "tasks=[rust_review_task, dedup_judge_task]," in src
        assert "process=Process.sequential," in src

    def test_task_carries_description_and_expected_output(self):
        # the Task's description / expected_output come from the spec, not `null`
        src = adapters.render_crew("wf", "d", CREW)
        assert 'description="Coordinate the review",' in src
        assert 'expected_output="The result of the rust-review step.",' in src

    def test_tool_stub_raises_not_implemented(self):
        src = adapters.render_crew("wf", "d", CREW)
        assert '@tool("read_file")' in src
        assert "def read_file(argument: str) -> str:" in src
        # quoted docstring pinned exactly (a wrapped literal would shift the quote)
        assert '"TODO: implement the read_file tool (declared by the skill)."' in src
        assert 'raise NotImplementedError("boost adapt: implement the \'read_file\' tool")' in src

    def test_tool_stubs_separated_cleanly(self):
        # two stubs joined by a blank line — no marker injected into the source
        src = adapters.render_crew("wf", "d", TWO_TOOL)
        assert 'tool")\n\n@tool("grep")' in src

    def test_output_compiles(self):
        for model in (None, "claude-opus-4-8"):
            compile(adapters.render_crew("wf", "d", CREW, model), "<crew>", "exec")

    def test_collision_idents_unique_in_output(self):
        coll = [_spec("Judge"), _spec("judge")]
        src = adapters.render_crew("wf", "d", coll)
        assert "judge = Agent(" in src and "judge_1 = Agent(" in src
        compile(src, "<coll>", "exec")

    @pytest.mark.parametrize("nasty", ['say "hi"', "a\nb", 'triple """ quote', "🚀"])
    def test_escaping_round_trips(self, nasty):
        spec = [adapters.AgentSpec("x", nasty, nasty, [])]
        src = adapters.render_crew("wf", nasty, spec)
        tree = compile(src, "<esc>", "exec")   # valid despite the payload
        assert tree is not None


# --- render_graph ---------------------------------------------------------

class TestRenderGraph:
    def test_header_and_exact_imports(self):
        src = adapters.render_graph("wf", "d", CREW)
        assert src.startswith(
            "# Generated by `boost adapt wf --to langgraph`. Do not edit by hand.\n")
        assert "from langgraph.graph import END, START, MessagesState, StateGraph\n" in src
        assert "from langgraph.prebuilt import create_react_agent\n" in src

    def test_factory_name_and_signature(self):
        assert "def build_rust_review(model):" in \
            adapters.render_graph("rust-review", "d", CREW)
        assert 'def build_rust_review(model="anthropic:claude-opus-4-8"):' in \
            adapters.render_graph("rust-review", "d", CREW, "claude-opus-4-8")

    def test_factory_docstring(self):
        assert '    """Build and compile the wf crew as a graph."""' in \
            adapters.render_graph("wf", "d", CREW)

    def test_system_prompts_keyed_by_ident(self):
        src = adapters.render_graph("wf", "d", CREW)
        assert "\nSYSTEM_PROMPTS = {\n" in src        # its own module-level line
        assert '"rust_review": "You orchestrate."' in src
        assert '"dedup_judge": "Merge dupes."' in src

    def test_two_tools_joined_with_comma_space(self):
        assert "tools=[read_file, grep]" in adapters.render_graph("wf", "d", TWO_TOOL)

    def test_create_react_agent_per_spec_with_tools(self):
        src = adapters.render_graph("wf", "d", CREW)
        assert "rust_review = create_react_agent(model, tools=[read_file], " \
               'prompt=SYSTEM_PROMPTS["rust_review"])' in src
        assert "dedup_judge = create_react_agent(model, tools=[], " \
               'prompt=SYSTEM_PROMPTS["dedup_judge"])' in src

    def test_nodes_and_edges_wire_sequentially(self):
        src = adapters.render_graph("wf", "d", CREW)
        assert "    builder = StateGraph(MessagesState)" in src   # exact casing
        assert 'builder.add_node("rust_review", rust_review_node)' in src
        assert "builder.add_edge(START, \"rust_review\")" in src
        assert 'builder.add_edge("rust_review", "dedup_judge")' in src
        assert 'builder.add_edge("dedup_judge", END)' in src
        assert "return builder.compile()" in src

    def test_langchain_tool_import_and_stub(self):
        src = adapters.render_graph("wf", "d", CREW)
        assert "from langchain_core.tools import tool" in src
        assert "@tool\ndef read_file(argument: str) -> str:" in src
        no_tools = adapters.render_graph("wf", "d", [_spec("a"), _spec("b")])
        assert "from langchain_core.tools import tool" not in no_tools

    def test_langchain_tool_stubs_separated_cleanly(self):
        src = adapters.render_graph("wf", "d", TWO_TOOL)
        assert 'tool")\n\n@tool\ndef grep' in src   # clean blank-line separator

    def test_output_compiles(self):
        for model in (None, "openai/gpt-4o"):
            compile(adapters.render_graph("wf", "d", CREW, model), "<graph>", "exec")

    def test_langchain_model_colon_form(self):
        assert 'model="anthropic:x"' in adapters.render_graph("wf", "d", CREW, "x")
        assert 'model="anthropic:y"' in adapters.render_graph("wf", "d", CREW, "anthropic/y")


# --- dispatch -------------------------------------------------------------

class TestMultiDispatch:
    def test_supports_multi(self):
        assert adapters.supports_multi("crewai") is True
        assert adapters.supports_multi("langgraph") is True
        assert adapters.supports_multi("agents-sdk") is False

    def test_multi_formats_keys(self):
        assert sorted(adapters.MULTI_FORMATS) == ["crewai", "langgraph"]

    def test_render_multi_dispatches(self):
        crew = adapters.render_multi("crewai", "wf", "d", CREW)
        graph = adapters.render_multi("langgraph", "wf", "d", CREW)
        assert "from crewai import Agent" in crew
        assert "create_react_agent" in graph

    def test_render_multi_passes_model_through(self):
        # the `model` arg must reach the renderer (not be dropped/replaced)
        crew = adapters.render_multi("crewai", "wf", "d", CREW, "claude-opus-4-8")
        assert 'LLM(model="anthropic/claude-opus-4-8")' in crew
        graph = adapters.render_multi("langgraph", "wf", "d", CREW, "claude-opus-4-8")
        assert 'model="anthropic:claude-opus-4-8"' in graph

    def test_render_multi_unknown_raises(self):
        with pytest.raises(KeyError):
            adapters.render_multi("agents-sdk", "wf", "d", CREW)
