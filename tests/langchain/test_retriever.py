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
    # `path` is tap-relative: stable across machines, and what a provenance
    # line should quote (see skill_context_node).
    assert doc.metadata["path"] == "skills/brainstorming/SKILL.md"
    assert doc.metadata["version"] == "1.4.0"
    assert doc.metadata["kind"] == "skill"


def test_source_metadata_is_an_openable_path(indexed):
    """`source` must locate the bytes, matching SkillMarkdownLoader.

    LangChain's convention — and this package's own loader (loader.py sets
    ``source`` to ``str(path)``) — is that ``source`` resolves. It used to carry
    the tap-relative path instead, which reads as openable, is not, and fails
    silently: any citation or re-read chain gets a path relative to the process
    CWD that happens not to exist.
    """
    from pathlib import Path

    doc = BoostRetriever().invoke("structured divergent thinking ideation")[0]
    src = Path(doc.metadata["source"])
    assert src.is_absolute(), "source must not be relative to the process CWD"
    assert src.is_file(), "source must name a file that exists"
    assert src.name == "SKILL.md"
    # The bytes behind it are the ones that were retrieved, not a same-named
    # file somewhere else on the machine.
    assert "never critique during the diverge phase" in src.read_text(
        encoding="utf-8").lower()
    # And it still ends with the tap-relative path it was resolved from.
    assert src.as_posix().endswith(doc.metadata["path"])
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


def test_a_zero_k_is_rejected_at_construction(sandbox):
    # k=0 is the same silent failure the kind and negative-k guards exist to
    # prevent, and the one the floor used to let through: retrieve_any slices
    # its hits to [:0], so the retriever answers [] for every query forever —
    # indistinguishable from an empty catalog. A retriever asked for nothing
    # is a construction mistake, so it fails at construction.
    import pytest
    from pydantic import ValidationError

    from boost_langchain import BoostRetriever
    with pytest.raises(ValidationError):
        BoostRetriever(k=0)


def test_the_guards_hold_on_assignment_not_just_construction(sandbox):
    """`r.k = 0` must fail the same way `BoostRetriever(k=0)` does.

    pydantic v2 does not validate on attribute set unless the model asks for it,
    and langchain's own model_config does not. So every guard here — the kind
    literal, the negative k, the new floor — was defeated by the ordinary
    "build it, tune it later" idiom (`r = BoostRetriever(); r.k = cfg.top_k`),
    which lands in exactly the silent-empty failure the guards exist to prevent.
    Construction-time validation is worth nothing if assignment skips it.
    """
    import pytest
    from pydantic import ValidationError

    from boost_langchain import BoostRetriever
    r = BoostRetriever()
    for field, bad in (("k", 0), ("k", -1), ("kind", "plugin")):
        with pytest.raises(ValidationError):
            setattr(r, field, bad)
    # ...and a legitimate assignment still works, so the guard is a floor and
    # not a freeze.
    r.k = 3
    assert r.k == 3


def test_a_zero_k_is_rejected_through_the_graph_node_too(sandbox):
    # skill_context_node builds the default retriever from its own k, so the
    # floor has to hold on that path as well — not just direct construction.
    import pytest
    from pydantic import ValidationError

    from boost_langchain import skill_context_node
    with pytest.raises(ValidationError):
        skill_context_node(k=0)
