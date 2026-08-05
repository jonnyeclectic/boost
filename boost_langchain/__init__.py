"""LangChain bindings for boost's skill catalog.

Three seams, all thin on purpose: :class:`BoostRetriever` puts the tapped
catalog behind LangChain's retriever contract, :class:`SkillMarkdownLoader`
turns one SKILL.md into a Document, and :func:`skill_context_node` wraps the
retriever as a LangGraph-shaped node (built on ``langchain_core`` types only,
so langgraph stays a separate install). Everything that decides *what comes
back* — ranking, fusion, dedupe, the degrade ladder — stays in
``boost_cli.core``, where it is measured by the repo's eval gate; this
package only translates the result into LangChain's types.

This package ships inside the ``boost-skill-cli`` wheel, but its
dependencies ride the opt-in ``[langchain]`` extra — the default install
stays zero-dependency, so the module files are always present while
``langchain_core`` may not be. The guard below turns that mismatch into the
one actionable message instead of a bare import error pointing at an
internal module.
"""
try:
    from .graph import skill_context_node
    from .loader import SkillMarkdownLoader
    from .retriever import BoostRetriever
except ModuleNotFoundError as exc:
    if (exc.name or "").partition(".")[0] in ("langchain_core", "pydantic"):
        raise ModuleNotFoundError(
            "boost_langchain ships with boost-skill-cli, but its LangChain "
            "dependencies are opt-in — install the extra: "
            "pip install 'boost-skill-cli[langchain]'"
        ) from exc
    raise

__all__ = ["BoostRetriever", "SkillMarkdownLoader", "skill_context_node"]
