"""End-to-end: skill_context_node against a real tapped + indexed corpus.

The node is exercised the way langgraph would use it — called with a state
dict of ``langchain_core`` message objects — but without langgraph itself,
because the node's contract is deliberately langgraph-free. One smoke test
at the bottom wires it into a real StateGraph and is skipped when the
``[langgraph]`` extra is not installed.
"""
from __future__ import annotations

import importlib.util

import pytest

pytest.importorskip(
    "langchain_core", minversion="1",
    reason="needs the [langchain] extra: pip install -e '.[langchain]' "
           "(an [eval] venv's langchain-core 0.3 must skip, not run)")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from boost_langchain import BoostRetriever, skill_context_node


def _content(update: dict) -> str:
    msgs = update["messages"]
    assert len(msgs) == 1 and isinstance(msgs[0], SystemMessage)
    return msgs[0].content


def test_injects_matching_skill_with_provenance(indexed):
    node = skill_context_node()
    update = node({"messages": [
        HumanMessage("structured divergent thinking ideation")]})
    content = _content(update)
    # The procedure body itself, not just its name — injection is the point.
    assert "never critique during the diverge phase" in content.lower()
    # Provenance prefix: name, kind, tap:path @ version.
    assert "### brainstorming (skill — fixture-tap:skills/brainstorming/SKILL.md @ 1.4.0)" in content


def test_injected_provenance_quotes_path_not_the_resolved_source(indexed):
    """The prefix quotes `path`, and specifically NOT `source`.

    This text lands in a live conversation and is read out of transcripts on
    other machines, so it must identify the file in the upstream repo — a
    `$HOME`-rooted path names a location the reader does not have and puts the
    local layout into the model's context. `metadata["source"]` is the resolved
    path precisely so this line can keep using `path` instead.

    Asserting against the retriever's own metadata rather than a literal is
    what makes this a real guard: it compares the two keys, so it fails on any
    build where they hold the same value — which is exactly the pre-split code.
    A version of this test that only checked for a hard-coded relative string
    passed against the bug it was written to prevent.
    """
    from pathlib import Path

    query = "structured divergent thinking ideation"
    doc = BoostRetriever(k=1).invoke(query)[0]
    content = _content(skill_context_node(k=1)({
        "messages": [HumanMessage(query)]}))

    assert doc.metadata["path"] in content, "provenance must quote the relative path"
    assert doc.metadata["source"] not in content, \
        "the resolved path must never reach the injected text"
    assert Path.home().as_posix() not in content


def test_k_caps_the_injected_procedures(indexed):
    # "always" matches five skill bodies plus the rule; count injected blocks
    # by their headers since they all share one SystemMessage.
    wide = _content(skill_context_node(k=8)({
        "messages": [HumanMessage("always")]}))
    narrow = _content(skill_context_node(k=2)({
        "messages": [HumanMessage("always")]}))
    assert wide.count("### ") > 2
    assert narrow.count("### ") == 2


def test_kind_filter_restricts_injection(indexed):
    content = _content(skill_context_node(kind="rule")({
        "messages": [HumanMessage("python formatting conventions")]}))
    assert "### python-style (rule — " in content
    assert "(skill — " not in content and "(workflow — " not in content


def test_last_human_message_is_the_query(indexed):
    # The earlier human turn asks about the workflow; the current one asks
    # about the skill. Only the current one may drive retrieval.
    update = skill_context_node()({"messages": [
        HumanMessage("release checklist changelog"),
        AIMessage("Here is the release checklist..."),
        HumanMessage("structured divergent thinking ideation"),
    ]})
    content = _content(update)
    assert "brainstorming" in content
    assert "release-checklist" not in content


def test_configured_retriever_wins_over_k_and_kind(indexed):
    retriever = BoostRetriever(k=1, kind="workflow")
    content = _content(skill_context_node(retriever=retriever, k=8)({
        "messages": [HumanMessage("release checklist changelog")]}))
    assert content.count("### ") == 1
    assert "### release-checklist (workflow — " in content


def test_empty_catalog_is_a_noop(sandbox):
    # Nothing tapped: the node must return "no state update", never raise —
    # a graph wired through it keeps running without boost context.
    assert skill_context_node()({
        "messages": [HumanMessage("anything at all")]}) == {}


def test_no_human_message_is_a_noop(indexed):
    node = skill_context_node()
    assert node({"messages": []}) == {}
    assert node({"messages": [
        SystemMessage("be terse"), AIMessage("ok")]}) == {}
    assert node({}) == {}


@pytest.mark.skipif(importlib.util.find_spec("langgraph") is None,
                    reason="the [langgraph] extra is not installed")
def test_node_runs_inside_a_real_stategraph(indexed):
    """Smoke: the callable drops into builder.add_node and the injected
    SystemMessage is visible to the next node via the messages reducer."""
    from langgraph.graph import END, START, MessagesState, StateGraph

    def responder(state):
        injected = [m for m in state["messages"]
                    if isinstance(m, SystemMessage)]
        return {"messages": [
            AIMessage("responding with %d injected procedure messages"
                      % len(injected))]}

    builder = StateGraph(MessagesState)
    builder.add_node("skills", skill_context_node(k=2))
    builder.add_node("responder", responder)
    builder.add_edge(START, "skills")
    builder.add_edge("skills", "responder")
    builder.add_edge("responder", END)
    graph = builder.compile()

    result = graph.invoke({"messages": [
        HumanMessage("structured divergent thinking ideation")]})
    msgs = result["messages"]
    assert isinstance(msgs[-1], AIMessage)
    assert msgs[-1].content == "responding with 1 injected procedure messages"
    injected = [m for m in msgs if isinstance(m, SystemMessage)]
    assert len(injected) == 1
    assert "brainstorming" in injected[0].content
