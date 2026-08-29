# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
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
from ._compat import supported_langchain_core

try:
    from .graph import skill_context_node
    from .loader import SkillMarkdownLoader
    from .retriever import BoostRetriever
except ModuleNotFoundError as exc:
    _root = (exc.name or "").partition(".")[0]
    if _root in ("langchain_core", "pydantic"):
        raise ModuleNotFoundError(
            "boost_langchain ships with boost-skill-cli, but its LangChain "
            "dependencies are opt-in — install the extra: "
            "pip install 'boost-skill-cli[langchain]'",
            name=_root,
        ) from exc
    raise

# The imports above SUCCEED on langchain-core 0.3 — the [eval] extra's pin —
# and then fail subtly at runtime (see _compat). Enforce the declared major
# here, where the failure can name the fix, instead of surfacing later as an
# AttributeError mid-graph.
import langchain_core as _langchain_core

if not supported_langchain_core(getattr(_langchain_core, "__version__", "")):
    raise ImportError(
        "boost_langchain requires langchain-core>=1,<2 but %s is installed. "
        "The [eval] extra pins the langchain 0.3 stack, so [eval] and "
        "[langchain] cannot share an environment until ragas ships its "
        "langchain-1.x fix — reinstall with: "
        "pip install 'boost-skill-cli[langchain]'"
        % getattr(_langchain_core, "__version__", "unknown"))

__all__ = ["BoostRetriever", "SkillMarkdownLoader", "skill_context_node"]
