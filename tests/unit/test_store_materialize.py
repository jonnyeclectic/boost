# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a sparse tap materializes a skill's files before they are copied.

Taps check out Markdown only (see ``test_gitutil_sparse``), so a skill that
ships ``scripts/`` or ``assets/`` has those paths present in the index but
absent from the working tree. ``store._copy_skill`` is a ``shutil.copytree``:
handed a partially-checked-out directory it copies what is there and reports
success, installing a skill whose scripts are silently missing. Nothing raises,
the lock file records a normal install, and the failure only surfaces when the
agent tries to run the script.

So :func:`store.source_dir_for` — the single chokepoint every consumer of a
tap's real files goes through (install, project install, ``sha256_dir``,
``boost info``) — materializes before it hands the path back.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.core import gitutil, registry, store
from boost_cli.errors import BoostError


@pytest.fixture()
def entry(boost, tapped):
    """A real catalog entry from the fixture tap."""
    from boost_cli.core import catalog
    entries = [e for e in catalog.all_entries()
               if e.get("kind", "skill") == "skill" and e["rel_dir"] != "."]
    assert entries, "fixture tap should ship a skill in a subdirectory"
    return entries[0]


class TestSourceDirMaterializes:
    def test_source_dir_for_materializes_the_skill_dir(self, entry, monkeypatch):
        seen: list = []
        monkeypatch.setattr(gitutil, "materialize",
                            lambda repo, rel: seen.append((repo, rel)))

        store.source_dir_for(entry)

        tap = registry.get(entry["tap"])
        assert (tap.path, entry["rel_dir"]) in seen, (
            "install would copytree a partially checked-out directory")

    def test_it_still_raises_when_the_source_really_is_gone(self, entry, monkeypatch):
        """Materializing must not paper over a genuinely missing skill."""
        monkeypatch.setattr(gitutil, "materialize", lambda repo, rel: None)
        tap = registry.get(entry["tap"])
        (tap.path / entry["rel_dir"] / "SKILL.md").unlink()

        with pytest.raises(BoostError):
            store.source_dir_for(entry)

    def test_an_unreachable_remote_is_explained_not_dumped(self, entry,
                                                           monkeypatch):
        """The one install step that can need the network deserves to say so.

        Driven through a failing `run` rather than a dead remote: the blobs a
        real fetch would want only go missing on a blobless clone, which needs
        a network origin to create.
        """
        tap = registry.get(entry["tap"])
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        monkeypatch.setattr(gitutil, "_sparse_list", lambda repo: set())

        def boom(argv, **kw):
            raise BoostError("git fetch failed: fatal: unable to access")

        monkeypatch.setattr(gitutil, "run", boom)

        with pytest.raises(BoostError) as excinfo:
            gitutil.materialize(tap.path, entry["rel_dir"])

        msg = str(excinfo.value)
        assert "could not fetch" in msg and entry["rel_dir"] in msg
        assert "-C" not in msg, "a global flag must not be named as the command"

    def test_an_offline_materialize_failure_names_the_cause(self, entry, monkeypatch):
        """A blob outside the cone needs the network; say so rather than
        reporting the skill as vanished."""
        def boom(repo, rel):
            raise BoostError("git sparse-checkout failed: could not fetch")

        monkeypatch.setattr(gitutil, "materialize", boom)

        with pytest.raises(BoostError) as excinfo:
            store.source_dir_for(entry)

        assert "vanished" not in str(excinfo.value).lower(), (
            "a fetch failure must not be reported as a missing source")


class TestASkillAtTheTapRoot:
    """Backfilled while touching `source_dir_for`: a `rel_dir` of "." is the
    tap root, and nothing pinned that the literal decides it."""

    def test_the_root_is_the_clone_itself(self, entry, monkeypatch):
        seen: list = []
        monkeypatch.setattr(gitutil, "materialize",
                            lambda repo, rel: seen.append((repo, rel)))
        tap = registry.get(entry["tap"])
        (tap.path / "SKILL.md").write_text("---\nname: root\n---\nb\n",
                                           encoding="utf-8")

        src = store.source_dir_for(dict(entry, name="root", rel_dir="."))

        assert src == tap.path
        assert seen == [(tap.path, ".")]


class TestOnlyASkillHasASourceDir:
    """A rule or workflow is one file, so it has no skill dir to widen for.

    ``boost info`` and ``boost deps`` ask ``source_dir_for`` about every
    not-installed catalog entry and swallow the BoostError. For a rule or a
    workflow the SKILL.md check always fails, but it ran *after*
    ``materialize``, so two read-only commands wrote ``/rules/*`` or
    ``/commands/*`` into the tap's sparse-checkout file and then threw the
    directory away (docs/roadmap/items/
    info-deps-materialize-a-dir-they-then-reject.md). The kind decides it,
    before the tap is cloned or widened.
    """

    @pytest.fixture()
    def materialized(self, monkeypatch):
        seen: list = []
        monkeypatch.setattr(gitutil, "materialize",
                            lambda repo, rel: seen.append((repo, rel)))
        return seen

    @pytest.mark.parametrize("kind, rel_dir, skill_md", [
        ("rule", "rules", "rules/x-item.mdc"),
        ("workflow", "commands", "commands/x-item.md"),
    ])
    def test_a_rule_or_workflow_is_refused_before_materializing(
            self, entry, materialized, kind, rel_dir, skill_md):
        other = {"name": "x-item", "kind": kind, "tap": entry["tap"],
                 "rel_dir": rel_dir, "skill_md": skill_md}

        with pytest.raises(BoostError) as excinfo:
            store.source_dir_for(other)

        assert materialized == [], "a read-only lookup widened the sparse cone"
        assert excinfo.value.message == (
            "x-item is a %s, not a skill: it has no source directory" % kind)

    def test_the_kind_decides_even_when_the_dir_holds_a_skill(
            self, entry, materialized):
        """Not the SKILL.md check: a rule beside a skill is still a rule."""
        rule = dict(entry, name="x-item", kind="rule",
                    skill_md=entry["rel_dir"] + "/.cursorrules")

        with pytest.raises(BoostError):
            store.source_dir_for(rule)

        assert materialized == []

    def test_a_rule_does_not_clone_a_tap_that_is_only_registered(
            self, entry, monkeypatch):
        tap = registry.get(entry["tap"])
        shutil.rmtree(tap.path)
        clones: list = []
        monkeypatch.setattr(gitutil, "clone_shallow",
                            lambda *a, **k: clones.append(a))
        rule = {"name": "x-item", "kind": "rule", "tap": entry["tap"],
                "rel_dir": "rules", "skill_md": "rules/x-item.mdc"}

        with pytest.raises(BoostError):
            store.source_dir_for(rule)

        assert clones == [] and not tap.is_cloned

    def test_an_entry_with_no_kind_is_still_a_skill(self, entry, materialized):
        """`quality._drift_status` builds its entry with no ``kind`` at all."""
        legacy = {k: v for k, v in entry.items() if k != "kind"}
        tap = registry.get(entry["tap"])

        src = store.source_dir_for(legacy)

        assert src == tap.path / entry["rel_dir"]
        assert materialized == [(tap.path, entry["rel_dir"])]


class TestInstallFromASparseTapIsComplete:
    def test_installed_skill_has_every_file_the_tap_ships(
            self, boost, tapped, sandbox):
        """The end-to-end property: install from a sparse tap loses nothing."""
        from boost_cli.core import catalog, paths

        entries = [e for e in catalog.all_entries()
                   if e.get("kind", "skill") == "skill" and e["rel_dir"] != "."]
        name = entries[0]["name"]
        src = store.source_dir_for(entries[0])
        want = {p.relative_to(src) for p in src.rglob("*")
                if p.is_file() and ".git" not in p.parts}

        boost("install", name)

        dest = paths.store_dir() / name
        got = {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
        assert want <= got, "installed skill is missing %r" % sorted(want - got)
