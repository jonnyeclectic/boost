# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end: SkillMarkdownLoader round-trips real SKILL.md files."""
from __future__ import annotations

import pytest

pytest.importorskip(
    "langchain_core", minversion="1",
    reason="needs the [langchain] extra: pip install -e '.[langchain]' "
           "(an [eval] venv's langchain-core 0.3 must skip, not run)")

from boost_langchain import SkillMarkdownLoader


def test_round_trips_frontmatter_and_body(fixture_tap_src):
    docs = SkillMarkdownLoader(
        fixture_tap_src / "skills" / "brainstorming" / "SKILL.md").load()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["name"] == "brainstorming"
    assert doc.metadata["version"] == "1.4.0"
    assert doc.metadata["tags"] == ["ideation", "thinking"]
    # The folded two-line description must come back as one line — this is
    # boost's own parser, so the loader sees what the catalog sees.
    assert doc.metadata["description"] == (
        "Structured ideation & divergent-thinking facilitation")
    assert doc.metadata["source"].endswith("SKILL.md")
    assert doc.page_content.startswith("# Brainstorming")
    assert "name: brainstorming" not in doc.page_content  # frontmatter stripped


def test_accepts_a_directory_holding_the_skill(fixture_tap_src):
    from_dir = SkillMarkdownLoader(
        fixture_tap_src / "skills" / "brainstorming").load()
    from_file = SkillMarkdownLoader(
        fixture_tap_src / "skills" / "brainstorming" / "SKILL.md").load()
    assert from_dir[0].page_content == from_file[0].page_content
    assert from_dir[0].metadata == from_file[0].metadata


def test_from_installed_resolves_the_canonical_store(indexed):
    from boost_cli.core import catalog, store
    store.install(catalog.resolve_one("brainstorming"))
    docs = SkillMarkdownLoader.from_installed("brainstorming").load()
    assert len(docs) == 1
    assert docs[0].metadata["name"] == "brainstorming"
    # The source must be the canonical store copy — the one path every
    # agent's symlink resolves to — not some agent's view of it.
    assert "/.agents/skills/brainstorming/" in (
        docs[0].metadata["source"].replace("\\", "/"))


def test_from_installed_rejects_unsafe_names(sandbox):
    from boost_cli.errors import BoostError
    with pytest.raises(BoostError):
        SkillMarkdownLoader.from_installed("../evil")


def test_missing_skill_raises_a_clear_error(sandbox):
    # Declined at from_installed, naming the skill and the scope it is absent
    # from — not a bare FileNotFoundError on a store path at load().
    from boost_cli.core import paths
    from boost_cli.errors import BoostError
    with pytest.raises(BoostError) as excinfo:
        SkillMarkdownLoader.from_installed("never-installed")
    assert str(excinfo.value) == (
        "never-installed is not installed in user scope (the canonical "
        "store, %s)" % paths.store_dir())
    assert excinfo.value.hint == "boost install never-installed"


def test_a_tapped_but_uninstalled_skill_is_declined(indexed):
    from boost_cli.errors import BoostError
    with pytest.raises(BoostError, match=r"^brainstorming is not installed "):
        SkillMarkdownLoader.from_installed("brainstorming")


def test_a_project_only_install_names_its_scope_and_copy(indexed):
    from boost_cli.core import catalog, integrity, scopes, store
    from boost_cli.errors import BoostError
    base = scopes.resolve_base(scopes.SCOPE_PROJECT)
    store.install(catalog.resolve_one("brainstorming"),
                  scope=scopes.SCOPE_PROJECT, base=base)
    _base, project = integrity.project_skills()
    local = integrity.project_skill_dir(project["brainstorming"], _base)
    assert local is not None
    with pytest.raises(BoostError) as excinfo:
        SkillMarkdownLoader.from_installed("brainstorming")
    assert str(excinfo.value) == (
        "brainstorming is installed only in project scope, at %s — "
        "from_installed reads the user-scope canonical store" % local)
    assert excinfo.value.hint == (
        "load the project copy with SkillMarkdownLoader(%r)" % str(local))
    # ...and the hint's loader works.
    assert SkillMarkdownLoader(local).load()[0].metadata["name"] == "brainstorming"


def test_an_unmanaged_store_copy_still_loads(sandbox):
    # A skill dropped into the store by hand has no lock row; the decline is
    # for an absent skill, not an unmanaged one.
    from boost_cli.core import paths
    d = paths.store_dir() / "hand-made"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: hand-made\n---\nbody\n",
                                encoding="utf-8")
    docs = SkillMarkdownLoader.from_installed("hand-made").load()
    assert docs[0].page_content.strip() == "body"


def test_from_installed_declines_a_rule_by_kind(sandbox):
    # A rule has no store copy; a bare FileNotFoundError would deny that the
    # name is installed at all — the decline must name the kind instead.
    import pytest

    from boost_cli.core import lockfile
    from boost_langchain import SkillMarkdownLoader
    lockfile.set_rule("house-style", {"kind": "rule", "version": "1.0.0",
                                      "tap": "t", "materializations": []})
    with pytest.raises(ValueError, match="house-style is a rule"):
        SkillMarkdownLoader.from_installed("house-style")
