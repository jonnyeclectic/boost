# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Load one skill's SKILL.md as a LangChain ``Document``."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from boost_cli.core import frontmatter


class SkillMarkdownLoader(BaseLoader):
    """Yield a SKILL.md as one Document: body as content, frontmatter as metadata.

    One Document per skill, not one per chunk: a skill file is already the
    author's chosen unit of instruction, and boost's own indexer moved off
    chunking for the same reason (see rag._make_docs). Callers that want
    chunks can run any LangChain splitter over the result.

    Parsing reuses ``boost_cli.core.frontmatter`` rather than a YAML library
    so this loader reads a skill file *exactly* the way boost's catalog does —
    including the lossless-number rule that keeps ``version: 1.10`` from
    silently becoming ``1.1``.
    """

    def __init__(self, path: str | Path):
        """``path`` is a SKILL.md file, or a directory holding one."""
        self.path = Path(path)

    @classmethod
    def from_installed(cls, name: str) -> SkillMarkdownLoader:
        """Loader for a skill installed in boost's canonical store.

        Resolves through ``store.skill_store_dir`` so the path is the single
        source of truth every agent's symlink points at — not one particular
        agent's view of it — and so unsafe names are rejected exactly the way
        ``boost install`` rejects them (raises BoostError). A name installed
        as a rule or workflow is declined by kind rather than with a bare
        missing-file error: those kinds materialize into agent context files
        and keep no store copy to load.
        """
        from boost_cli.core import lockfile, store
        found = lockfile.find_any(name)
        if found is not None and found[0] != "skill":
            raise ValueError(
                "%s is a %s — it materializes into agent context files and "
                "has no store copy to load; retrieve it with "
                "BoostRetriever(kind=%r) instead" % (name, found[0], found[0]))
        return cls(store.skill_store_dir(name))

    def lazy_load(self) -> Iterator[Document]:
        path = self.path / "SKILL.md" if self.path.is_dir() else self.path
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = frontmatter.parse(text)
        # The real file path wins over any frontmatter key that happens to be
        # named "source": metadata provenance must state where the bytes came
        # from, and a self-reported value is the one thing that cannot.
        yield Document(page_content=body, metadata={**meta, "source": str(path)})
