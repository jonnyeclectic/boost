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
