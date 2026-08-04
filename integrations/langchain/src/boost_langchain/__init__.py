"""LangChain bindings for boost's skill catalog.

Three seams, all thin on purpose: :class:`BoostRetriever` puts the tapped
catalog behind LangChain's retriever contract, :class:`SkillMarkdownLoader`
turns one SKILL.md into a Document, and :func:`skill_context_node` wraps the
retriever as a LangGraph-shaped node (built on ``langchain_core`` types only,
so langgraph stays an optional extra). Everything that decides *what comes
back* — ranking, fusion, dedupe, the degrade ladder — stays in
``boost_cli.core``, where it is measured by the repo's eval gate; this
package only translates the result into LangChain's types.
"""
from .graph import skill_context_node
from .loader import SkillMarkdownLoader
from .retriever import BoostRetriever

__all__ = ["BoostRetriever", "SkillMarkdownLoader", "skill_context_node"]
