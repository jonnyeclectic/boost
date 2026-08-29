# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a portable catalogue bundle, so a fresh install skips the tap.

`boost tap --defaults` is the slowest thing a new user does, and almost none of
the cost is the part they need. Measured on a real install: **459 tapped
registries** are 12 GB of shallow clones on disk, but the catalogue those clones
produce — the JSON boost actually searches — is **101.1 MB**, and **11.1 MB**
gzipped. Search works from it with no clone present at all; that was checked
before this module was written, against a cache-only HOME, and it returned the
right skill.

So the bundle carries the catalogue and nothing else. Three consequences the
tests below pin:

* The derived indexes are **excluded**. `rag_index.json`, `rag_postings.sqlite`
  and `rag_vectors.sqlite` are 3.8 GB of the 3.9 GB cache directory, they
  rebuild from the catalogue in seconds, and vectors are only valid inside the
  embedding space that made them — `reindex --export-shard` is the reviewed path
  for those, with provenance this format deliberately does not try to carry.
* Import **merges** rather than replaces, because the receiving machine may
  already have taps of its own and losing them silently would be worse than a
  slow tap.
* Extraction treats the archive as **hostile**. A bundle is a file people send
  each other, which makes it an untrusted input in the most ordinary way, and
  tar member names are the classic path-traversal vector.
"""
from __future__ import annotations

import io
import json
import tarfile

import pytest

from boost_cli.core import catalogbundle, config, paths, registry
from boost_cli.errors import BoostError


def _cache(name: str, entries: int = 2, commit: str = "c0ffee") -> None:
    """Write a catalogue cache file the way `catalog.build_cache` does."""
    paths.ensure_dirs()
    safe = name.replace("/", "__")
    skills = [{"name": "s%d" % i, "description": "d%d" % i, "version": "1.0.0",
               "tap": name, "curated": False, "kind": "skill",
               "rel_dir": "s%d" % i, "skill_md": "s%d/SKILL.md" % i,
               "meta": {}, "search_blob": "s%d d%d" % (i, i)}
              for i in range(entries)]
    (paths.cache_dir() / ("%s.json" % safe)).write_text(json.dumps({
        "tap": name, "url": "https://example.test/%s" % name,
        "generated": "2026-08-10T00:00:00Z", "commit": commit,
        "skills": skills}), encoding="utf-8")


def _tapped(*names: str) -> None:
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": "https://example.test/%s" % n,
                    "curated": False} for n in names]
    config.save(cfg)


class TestExport:
    def test_a_bundle_is_written(self, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "catalogue.tgz"
        catalogbundle.export_bundle(dest)
        assert dest.exists() and dest.stat().st_size > 0

    def test_it_reports_what_it_packed(self, sandbox, tmp_path):
        _tapped("acme/skills", "other/repo")
        _cache("acme/skills", entries=2)
        _cache("other/repo", entries=3)
        stats = catalogbundle.export_bundle(tmp_path / "c.tgz")
        assert stats["taps"] == 2
        assert stats["entries"] == 5

    def test_the_derived_indexes_are_not_packed(self, sandbox, tmp_path):
        # 3.8 GB of the 3.9 GB cache dir, all of it rebuildable in seconds.
        # Shipping vectors here would also ship them without the provenance
        # `import_shard` refuses a mismatched shard on.
        #
        # This passes because export is driven by the TAP LIST — see the
        # companion test below, which pins that mechanism. An earlier revision
        # of the module carried an `_is_catalogue_file` filter that was never
        # called, and this assertion held with the filter neutered, so on its
        # own it says nothing about why the derived files stay out.
        _tapped("acme/skills")
        _cache("acme/skills")
        for junk in ("rag_index.json", "rag_postings.sqlite",
                     "rag_vectors.sqlite", "_names.txt"):
            (paths.cache_dir() / junk).write_text("x", encoding="utf-8")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        with tarfile.open(dest, "r:gz") as tar:
            names = tar.getnames()
        assert not [n for n in names if "rag_" in n or "_names" in n], names

    def test_only_configured_taps_are_packed(self, sandbox, tmp_path):
        """The actual mechanism, and the one a refactor would break.

        Export names each candidate from a configured tap rather than scanning
        the cache directory, so a catalogue left behind by a registry that was
        untapped is not shipped either — and any future rewrite to a directory
        walk fails here rather than silently re-admitting `rag_vectors.sqlite`.
        """
        _tapped("acme/skills")
        _cache("acme/skills")
        _cache("ghost/untapped")          # on disk, not in the tap list
        dest = tmp_path / "c.tgz"

        stats = catalogbundle.export_bundle(dest)

        assert stats["taps"] == 1
        with tarfile.open(dest, "r:gz") as tar:
            names = tar.getnames()
        assert not [n for n in names if "ghost" in n], names

    def test_a_tap_with_no_cache_file_is_skipped_not_fatal(self, sandbox, tmp_path):
        # A tap can be configured and not yet built. Refusing to export the
        # rest because of it would make the feature unusable mid-setup.
        _tapped("acme/skills", "never/built")
        _cache("acme/skills")
        stats = catalogbundle.export_bundle(tmp_path / "c.tgz")
        assert stats["taps"] == 1
        assert "never/built" in stats["skipped"]

    def test_exporting_nothing_is_refused(self, sandbox, tmp_path):
        # An empty bundle looks like a working one until someone imports it.
        with pytest.raises(BoostError):
            catalogbundle.export_bundle(tmp_path / "c.tgz")


class TestManifest:
    def test_the_manifest_names_the_format_version(self, sandbox, tmp_path):
        # A format that cannot say what it is cannot be rejected later.
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        assert catalogbundle.read_manifest(dest)["format"] == \
            catalogbundle.BUNDLE_FORMAT

    def test_the_manifest_carries_each_tap_url(self, sandbox, tmp_path):
        # The URL is what makes the imported catalogue actionable: `install`
        # still needs a clone, and without the URL there is nothing to clone.
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        taps = catalogbundle.read_manifest(dest)["taps"]
        assert taps[0]["url"] == "https://example.test/acme/skills"

    def test_a_future_format_is_refused(self, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        _rewrite_manifest(dest, {"format": catalogbundle.BUNDLE_FORMAT + 1,
                                 "taps": []})
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(dest)


def _rewrite_manifest(path, manifest) -> None:
    """Rebuild an archive with a replaced manifest, for the refusal tests."""
    with tarfile.open(path, "r:gz") as tar:
        members = [(m, tar.extractfile(m).read() if m.isfile() else b"")
                   for m in tar.getmembers()]
    with tarfile.open(path, "w:gz") as tar:
        for member, data in members:
            if member.name == catalogbundle.MANIFEST_NAME:
                data = json.dumps(manifest).encode("utf-8")
                member.size = len(data)
            tar.addfile(member, io.BytesIO(data))


class TestImport:
    def test_a_round_trip_restores_the_catalogue(self, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills", entries=2)
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        for path in paths.cache_dir().glob("*.json"):
            path.unlink()
        config.save({"taps": []})

        stats = catalogbundle.import_bundle(dest)

        assert stats["taps"] == 1
        assert (paths.cache_dir() / "acme__skills.json").exists()
        assert [t.name for t in registry.list_taps()] == ["acme/skills"]

    def test_import_merges_and_keeps_existing_taps(self, sandbox, tmp_path):
        # Replacing would silently discard work on the receiving machine.
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        _tapped("mine/own")

        catalogbundle.import_bundle(dest)

        assert {t.name for t in registry.list_taps()} == {"mine/own", "acme/skills"}

    def test_reimporting_does_not_duplicate_a_tap(self, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)

        catalogbundle.import_bundle(dest)
        catalogbundle.import_bundle(dest)

        assert [t.name for t in registry.list_taps()].count("acme/skills") == 1

    def test_an_unreadable_bundle_is_a_clear_error(self, sandbox, tmp_path):
        bad = tmp_path / "nope.tgz"
        bad.write_text("not a tarball", encoding="utf-8")
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bad)

    def test_a_missing_bundle_is_a_clear_error(self, sandbox, tmp_path):
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(tmp_path / "absent.tgz")


class TestTheArchiveIsTreatedAsHostile:
    """A bundle is a file people send each other. That is untrusted input.

    Every case here is a real tar trick, and each one is checked for *where the
    bytes landed*, not merely that the call returned — a traversal that raises
    after writing the file has still written the file.
    """

    @staticmethod
    def _hostile(path, member_name: str, data: bytes = b"{}") -> None:
        manifest = json.dumps({
            "format": catalogbundle.BUNDLE_FORMAT, "generated": "2026-01-01",
            "taps": [], "entries": 0}).encode("utf-8")
        with tarfile.open(path, "w:gz") as tar:
            info = tarfile.TarInfo(catalogbundle.MANIFEST_NAME)
            info.size = len(manifest)
            tar.addfile(info, io.BytesIO(manifest))
            info = tarfile.TarInfo(member_name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    @staticmethod
    def _tree() -> set:
        """Every file at or above BOOST_HOME that a traversal could reach.

        Snapshotting the tree beats asserting one guessed destination, and the
        first draft of these tests is why. It checked
        ``boost_home().parent / "pwned.json"`` against a payload of
        ``catalog/../../../../pwned.json`` — four levels up from the cache dir,
        which lands a level ABOVE the path being checked. The assertion probed
        somewhere the payload could not reach, so it would have held even if
        the write had happened. A diff of the whole tree cannot be off by one.
        """
        root = paths.boost_home().parent.parent
        return {p for p in root.rglob("*") if p.is_file()}

    def test_a_parent_traversal_member_is_not_written(self, sandbox, tmp_path):
        before = self._tree()
        bundle = tmp_path / "evil.tgz"
        self._hostile(bundle, "catalog/../../../../pwned.json")
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)
        assert self._tree() - before - {bundle} == set()

    def test_an_absolute_member_is_not_written(self, sandbox, tmp_path):
        target = tmp_path / "abs-pwned.json"
        before = self._tree()
        bundle = tmp_path / "evil.tgz"
        self._hostile(bundle, str(target).lstrip("/"))
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)
        assert not target.exists()
        assert self._tree() - before - {bundle} == set()

    def test_a_member_outside_the_catalog_prefix_is_refused(self, sandbox, tmp_path):
        # Everything the format defines lives under catalog/. Anything else is
        # someone testing what this code will accept.
        bundle = tmp_path / "evil.tgz"
        self._hostile(bundle, "config.json")
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)

    def test_a_symlink_member_is_refused(self, sandbox, tmp_path):
        # A symlink member is how an archive writes outside its own tree
        # without any name containing "..".
        bundle = tmp_path / "evil.tgz"
        manifest = json.dumps({"format": catalogbundle.BUNDLE_FORMAT,
                               "taps": [], "entries": 0}).encode("utf-8")
        with tarfile.open(bundle, "w:gz") as tar:
            info = tarfile.TarInfo(catalogbundle.MANIFEST_NAME)
            info.size = len(manifest)
            tar.addfile(info, io.BytesIO(manifest))
            link = tarfile.TarInfo("catalog/evil.json")
            link.type = tarfile.SYMTYPE
            link.linkname = str(tmp_path / "target.json")
            tar.addfile(link)
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)

    def test_too_many_members_is_refused(self, sandbox, tmp_path, monkeypatch):
        monkeypatch.setattr(catalogbundle, "MAX_MEMBERS", 2)
        bundle = tmp_path / "big.tgz"
        manifest = json.dumps({"format": catalogbundle.BUNDLE_FORMAT,
                               "taps": [], "entries": 0}).encode("utf-8")
        with tarfile.open(bundle, "w:gz") as tar:
            info = tarfile.TarInfo(catalogbundle.MANIFEST_NAME)
            info.size = len(manifest)
            tar.addfile(info, io.BytesIO(manifest))
            for i in range(5):
                info = tarfile.TarInfo("catalog/t%d.json" % i)
                info.size = 2
                tar.addfile(info, io.BytesIO(b"{}"))
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)

    def test_an_oversized_member_is_refused(self, sandbox, tmp_path, monkeypatch):
        # Decompression bomb: small on the wire, unbounded on disk.
        monkeypatch.setattr(catalogbundle, "MAX_MEMBER_BYTES", 8)
        bundle = tmp_path / "bomb.tgz"
        self._hostile(bundle, "catalog/big.json", data=b"{}" + b" " * 100)
        with pytest.raises(BoostError):
            catalogbundle.import_bundle(bundle)


class TestTheErrorPathsAreReachable:
    """Every branch here is a real failure someone will hit, not a rare one.

    A corrupt cache file, a full disk, a truncated download: each already had a
    hand-written message, and an unexercised error path is a message nobody has
    ever read. These assert the message, not merely the raise.
    """

    def test_a_corrupt_cache_file_is_skipped_not_fatal(self, sandbox, tmp_path):
        # Half-written JSON is what a killed `boost tap` leaves behind. Refusing
        # to export the other taps because of it would make a partial failure
        # into a total one.
        _tapped("acme/skills", "corrupt/one")
        _cache("acme/skills")
        (paths.cache_dir() / "corrupt__one.json").write_text(
            '{"tap": "corrupt/one", "skills": [', encoding="utf-8")

        stats = catalogbundle.export_bundle(tmp_path / "c.tgz")

        assert stats["taps"] == 1
        assert "corrupt/one" in stats["skipped"]

    def test_an_unwritable_destination_names_the_path(self, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        # A directory where the archive should go: open() fails with OSError,
        # which is the same shape as a full disk or a read-only mount.
        blocked = tmp_path / "taken.tgz"
        blocked.mkdir()
        with pytest.raises(BoostError) as caught:
            catalogbundle.export_bundle(blocked)
        assert "taken.tgz" in str(caught.value)

    def test_a_manifest_that_is_not_json_is_reported_as_malformed(
            self, sandbox, tmp_path):
        # A truncated download is still a valid gzip of a valid tar.
        bundle = tmp_path / "c.tgz"
        with tarfile.open(bundle, "w:gz") as tar:
            data = b"{not json at all"
            info = tarfile.TarInfo(catalogbundle.MANIFEST_NAME)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with pytest.raises(BoostError) as caught:
            catalogbundle.read_manifest(bundle)
        assert "malformed" in str(caught.value)

    def test_a_manifest_that_is_a_directory_is_refused(self, sandbox, tmp_path):
        # `getmember` succeeds for a directory entry, so without the isfile()
        # check `extractfile` returns None and the failure would surface as a
        # TypeError somewhere further down.
        bundle = tmp_path / "c.tgz"
        with tarfile.open(bundle, "w:gz") as tar:
            info = tarfile.TarInfo(catalogbundle.MANIFEST_NAME)
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        with pytest.raises(BoostError) as caught:
            catalogbundle.read_manifest(bundle)
        assert "not a file" in str(caught.value)

    def test_a_config_whose_taps_key_is_not_a_list_is_survivable(
            self, sandbox, tmp_path):
        # `config.load()` returns whatever is on disk. A hand-edited
        # `"taps": null` must import as "no existing taps", never raise —
        # registry.list_taps() already takes that position.
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        catalogbundle.export_bundle(dest)
        cfg = config.load()
        cfg["taps"] = None
        config.save(cfg)

        stats = catalogbundle.import_bundle(dest)

        assert stats["added"] == 1
        assert [t.name for t in registry.list_taps()] == ["acme/skills"]
