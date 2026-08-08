"""A LangGraph node that pulls the right skill into a run, mid-run.

The alternative this exists to avoid is stuffing every procedure into the
system prompt up front: that spends context on procedures the run never
needs and stops scaling the moment the catalog does. Retrieving against the
current state instead means each turn carries only the procedures that turn
asked for.

Nothing in this module imports langgraph. A graph node is just a callable
from state to a partial state update, so building the callable against
``langchain_core`` types alone keeps langgraph out of the ``[langchain]``
extra entirely — install it only if your app actually runs graphs — while
the node still drops straight into ``builder.add_node``.
"""
from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from .retriever import BoostRetriever


def _last_human_text(messages: list[BaseMessage]) -> str:
    """The most recent human turn — the query the *current* state poses.

    Earlier human turns are already answered context; retrieving on them
    would re-inject procedures for questions the graph has moved past.
    ``.text`` rather than ``.content`` because content may be a block list.
    """
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.text
    return ""


def skill_context_node(
    retriever: BoostRetriever | None = None,
    k: int = 3,
    kind: str | None = None,
) -> Callable[[dict], dict]:
    """Build a graph node that injects relevant boost procedures as context.

    The returned callable reads the last human message from
    ``state["messages"]``, retrieves up to ``k`` matching catalog items, and
    returns ``{"messages": [SystemMessage(...)]}`` carrying their full
    bodies. Three choices worth knowing about:

    - **It degrades to a no-op.** No human turn, nothing tapped, or no match
      all return ``{}`` — in langgraph, "no state update". A graph wired
      through this node must keep working on a machine with an empty
      catalog, because retrieval here is an enhancement, not a dependency.
    - **Provenance rides along.** Every injected procedure is prefixed with
      its name, tap, in-repo path and version. Injected text steers the
      model, so when a run goes wrong the first question is *which* skill
      said that and *where it came from* — a poisoned or stale skill is
      traceable from the transcript alone, without re-running retrieval.
    - **``k`` defaults lower than the retriever's own.** These are full
      procedure bodies landing in a live conversation; three is a context
      budget, eight is a search page.

    Pass a configured ``retriever`` to control retrieval wholesale (it wins
    over ``k``/``kind``, which only shape the default ``BoostRetriever``).
    """
    if retriever is None:
        retriever = BoostRetriever(k=k, kind=kind, full_content=True)

    def boost_skill_context(state: dict) -> dict:
        query = _last_human_text(state.get("messages") or [])
        if not query.strip():
            return {}
        docs = retriever.invoke(query)
        if not docs:
            return {}
        blocks = []
        for doc in docs:
            meta = doc.metadata
            # ``path``, not ``source``: this text lands in a live conversation
            # and gets read out of transcripts on other machines, so provenance
            # must name the file in the upstream repo. The resolved path in
            # ``source`` would leak the local layout and identify a location
            # the reader does not have.
            prov = "%s:%s" % (meta.get("tap") or "?", meta.get("path") or "?")
            if meta.get("version"):
                prov = "%s @ %s" % (prov, meta["version"])
            blocks.append("### %s (%s — %s)\n\n%s" % (
                meta.get("name") or "unnamed",
                meta.get("kind") or "skill",
                prov,
                doc.page_content,
            ))
        content = (
            "Procedures from the boost catalog relevant to the current "
            "request. Apply the ones that fit; each is labeled with its "
            "source so it can be audited.\n\n%s" % "\n\n".join(blocks)
        )
        return {"messages": [SystemMessage(content=content)]}

    return boost_skill_context
