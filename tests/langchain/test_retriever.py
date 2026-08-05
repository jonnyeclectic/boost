"""End-to-end: BoostRetriever against a real tapped + indexed corpus.

Every test drives ``invoke()`` — the public Runnable API a chain actually
calls — rather than the private ``_get_relevant_documents``, so the pydantic
field plumbing and the callback contract are exercised too.
"""
from __future__ import annotations

import pytest

pytest.importorskip(
    "langchain_core", minversion="1",
    reason="needs the [langchain] extra: pip install -e '.[langchain]' "
           "(an [eval] venv's langchain-core 0.3 must skip, not run)")

from langchain_core.documents import Document

from boost_langchain import BoostRetriever


def test_invoke_returns_documents_for_matching_query(indexed):
    docs = BoostRetriever().invoke("structured divergent thinking ideation")
    assert docs, "a query matching a fixture skill returned nothing"
    top = docs[0]
    assert isinstance(top, Document)
    assert top.metadata["name"] == "brainstorming"
    # Full body, not just the description — the content a chain would stuff.
    assert "never critique during the diverge phase" in top.page_content.lower()


def test_k_caps_the_result_count(indexed):
    # "always" appears in five skill bodies and the rule fixture, so the
    # uncapped pool is comfortably bigger than the small k.
    wide = BoostRetriever(k=8).invoke("always")
    assert len(wide) > 2
    assert len(BoostRetriever(k=2).invoke("always")) == 2


def test_kind_filter_restricts_to_rules(indexed):
    docs = BoostRetriever(kind="rule").invoke("python formatting conventions")
    assert docs
    assert all(d.metadata["kind"] == "rule" for d in docs)
    assert docs[0].metadata["name"] == "python-style"


def test_kind_filter_restricts_to_workflows(indexed):
    docs = BoostRetriever(kind="workflow").invoke("release checklist changelog")
    assert docs
    assert all(d.metadata["kind"] == "workflow" for d in docs)
    assert docs[0].metadata["name"] == "release-checklist"


def test_kind_filter_excludes_other_kinds(indexed):
    # "always" matches skills AND the rule; the skill filter must drop the rule.
    docs = BoostRetriever(kind="skill").invoke("always")
    assert docs
    assert all(d.metadata["kind"] == "skill" for d in docs)


def test_metadata_carries_provenance_and_engine(indexed):
    doc = BoostRetriever().invoke("structured divergent thinking ideation")[0]
    assert doc.metadata["tap"] == "fixture-tap"
    assert doc.metadata["source"] == "skills/brainstorming/SKILL.md"
    assert doc.metadata["version"] == "1.4.0"
    assert doc.metadata["kind"] == "skill"
    # Sandbox has no dense store and no keys, so the label must be BM25 —
    # anything else means the engine seam moved underneath this package.
    assert doc.metadata["engine"] == "BM25 full-content"


def test_empty_home_returns_empty_list(sandbox):
    # Nothing tapped: no index is buildable, and the retriever must mirror the
    # CLI's degrade-cleanly rule ([] rather than raise) so a chain keeps going.
    assert BoostRetriever().invoke("anything at all") == []


def test_full_content_false_uses_the_description(indexed):
    docs = BoostRetriever(full_content=False).invoke(
        "structured divergent thinking ideation")
    assert docs
    top = docs[0]
    assert top.metadata["name"] == "brainstorming"
    assert "Structured ideation" in top.page_content
    assert "diverge phase" not in top.page_content.lower()


def test_an_unknown_kind_is_rejected_at_construction(sandbox):
    # A typo'd kind would otherwise return [] for every query —
    # indistinguishable from an empty catalog, and silent.
    import pytest
    from pydantic import ValidationError

    from boost_langchain import BoostRetriever
    with pytest.raises(ValidationError):
        BoostRetriever(kind="plugin")


def test_a_negative_k_is_rejected_at_construction(sandbox):
    import pytest
    from pydantic import ValidationError

    from boost_langchain import BoostRetriever
    with pytest.raises(ValidationError):
        BoostRetriever(k=-1)
