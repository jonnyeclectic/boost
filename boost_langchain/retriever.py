# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""A LangChain retriever over boost's tapped skill/rule/workflow catalog."""
from __future__ import annotations

from typing import Literal

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

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

    # pydantic v2 validates on __init__ but NOT on attribute set unless asked,
    # and langchain's own model_config does not ask. Without this every guard
    # below was construction-only, so the ordinary "build it, tune it later"
    # idiom — `r = BoostRetriever(); r.k = cfg.top_k` — walked straight past all
    # three. (`model_copy(update=...)` still bypasses them; pydantic documents
    # that as never validating, and there is no config that changes it.)
    model_config = ConfigDict(validate_assignment=True)

    # Validated at construction, because every one of these fails *silently* at
    # query time otherwise: a typo'd kind returns [] for every query,
    # indistinguishable from an empty catalog; a negative k drops the last hit
    # via slice semantics; and k=0 slices the hits to nothing, so the retriever
    # answers [] forever while looking perfectly healthy. The floor is 1 rather
    # than 0 for that last one — a retriever asked for no documents is a
    # construction mistake, and it should say so where the mistake was made.
    k: int = Field(default=8, ge=1)
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
            # Two paths, because they answer different questions and conflating
            # them is a silent failure. ``path`` is tap-relative: stable across
            # machines, and what a provenance line should quote (see
            # skill_context_node). ``source`` is the resolved one, because
            # LangChain's convention — and SkillMarkdownLoader right next door —
            # is that ``source`` locates the bytes. Advertising the relative
            # path as ``source`` gave chains something that reads as openable,
            # is not, and resolves against whatever the process CWD happens to
            # be. ``rag.entry_path`` returns None only for an entry with no
            # defining file, which no live catalog row has.
            src = rag.entry_path(entry)
            docs.append(Document(
                page_content=content,
                metadata={
                    "name": entry.get("name", ""),
                    "kind": entry.get("kind", "skill"),
                    "tap": entry.get("tap", ""),
                    "version": entry.get("version", ""),
                    "path": entry.get("skill_md", ""),
                    "source": str(src) if src is not None else "",
                    # Which engine actually answered (BM25 / dense / hybrid
                    # RRF). Carried per-document because it is the first thing
                    # to check when result quality surprises — see rag.rerank
                    # for why a guessed label is worse than none.
                    "engine": engine,
                },
            ))
        return docs
