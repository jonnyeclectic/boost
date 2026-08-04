"""A LangChain retriever over boost's tapped skill/rule/workflow catalog."""
from __future__ import annotations

from typing import Literal

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from boost_cli.core import rag


class BoostRetriever(BaseRetriever):
    """Retrieve tapped boost items as LangChain ``Document`` objects.

    This deliberately reuses boost's own engine (``rag.retrieve_any``) rather
    than re-embedding the catalog into a vector store. Retrieval quality is
    the reason: boost's Tier-1 eval gate floors recall@k, hit@1, MRR and
    nDCG@k over a golden set on every merge, so wrapping that engine means the
    retriever ships with numbers rather than claims — a fresh embedding
    pipeline here would start from zero evidence. Reuse also inherits the
    degrade ladder for free: hybrid RRF when the user has built a dense store,
    BM25 full-content otherwise, and never an API key as the entry fee.

    ``kind`` narrows results to one of boost's three item kinds ("skill",
    "rule", "workflow"); ``None`` searches all of them. ``full_content``
    controls whether a Document carries the item's whole body (what a chain
    stuffing context wants) or just its one-line description (what a router
    choosing among items wants).
    """

    # Validated at construction: a typo'd kind would otherwise return [] for
    # every query, indistinguishable from an empty catalog; a negative k
    # would silently drop the last hit via slice semantics.
    k: int = Field(default=8, ge=0)
    kind: Literal["skill", "rule", "workflow"] | None = None
    full_content: bool = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        # ensure() is what makes first use behave like `boost search`: it
        # builds the BM25 index from the tapped catalog on demand and is
        # incremental after that. Without it, a freshly tapped HOME would
        # answer [] until the user happened to run a CLI search first.
        rag.ensure()
        hits, engine = rag.retrieve_any(query, k=self.k, kind=self.kind)
        if hits is None:
            # No index of any kind could be built — nothing is tapped. Mirror
            # the CLI's degrade-cleanly rule: an empty shelf is an answer, not
            # an error, and a chain should keep running without boost context.
            return []
        docs: list[Document] = []
        for hit in hits:
            entry = hit["entry"]
            if self.full_content:
                content = rag.read_body(entry)
            else:
                content = entry.get("description") or rag.surface(entry)
            docs.append(Document(
                page_content=content,
                metadata={
                    "name": entry.get("name", ""),
                    "kind": entry.get("kind", "skill"),
                    "tap": entry.get("tap", ""),
                    "version": entry.get("version", ""),
                    "source": entry.get("skill_md", ""),
                    # Which engine actually answered (BM25 / dense / hybrid
                    # RRF). Carried per-document because it is the first thing
                    # to check when result quality surprises — see rag.rerank
                    # for why a guessed label is worse than none.
                    "engine": engine,
                },
            ))
        return docs
