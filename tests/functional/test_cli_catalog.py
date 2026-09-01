# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: `boost catalog` end to end, through the real CLI.

``tests/unit/test_catalogbundle.py`` covers the engine — what goes in a bundle,
what is refused coming out of one. This file covers the half a user actually
touches: the three modes of the command, the exit codes, and what is printed.

The distinction earns its own file because the command layer is where a bundle
stops being a data structure and becomes advice. Export tells the receiver what
to run; import tells them what now works and what still does not. Both of those
sentences are wrong in a specific way if the numbers behind them are wrong, and
neither is exercised by a test of the core module.
"""
from __future__ import annotations

import json
import shutil

from boost_cli.core import config, paths, registry


def _cache(name: str, entries: int = 2) -> None:
    """Write a catalogue cache file the way `catalog.build_cache` does."""
    paths.ensure_dirs()
    skills = [{"name": "s%d" % i, "description": "d%d" % i, "version": "1.0.0",
               "tap": name, "curated": False, "kind": "skill",
               "rel_dir": "s%d" % i, "skill_md": "s%d/SKILL.md" % i,
               "meta": {}, "search_blob": "s%d" % i} for i in range(entries)]
    (paths.cache_dir() / ("%s.json" % name.replace("/", "__"))).write_text(
        json.dumps({"tap": name, "url": "https://example.test/%s" % name,
                    "generated": "2026-08-10T00:00:00Z", "commit": "c0ffee",
                    "skills": skills}), encoding="utf-8")


def _tapped(*names: str) -> None:
    cfg = config.load()
    cfg["taps"] = [{"name": n, "url": "https://example.test/%s" % n,
                    "curated": False} for n in names]
    config.save(cfg)


class TestExport:
    def test_it_writes_a_bundle_and_says_what_is_in_it(self, boost, sandbox,
                                                       tmp_path):
        _tapped("acme/skills", "other/repo")
        _cache("acme/skills", entries=2)
        _cache("other/repo", entries=3)
        dest = tmp_path / "c.tgz"

        r = boost("catalog", "--export", str(dest))

        assert dest.exists()
        assert "2 taps" in r.out
        assert "5 entries" in r.out

    def test_it_names_the_command_the_receiver_runs(self, boost, sandbox,
                                                   tmp_path):
        # The export is useless without the other half of the instruction, and
        # the receiver is by definition not the person reading this terminal.
        _tapped("acme/skills")
        _cache("acme/skills")
        r = boost("catalog", "--export", str(tmp_path / "c.tgz"))
        assert "catalog --import" in r.out

    def test_a_tap_with_no_catalogue_is_named_not_just_counted(self, boost,
                                                              sandbox,
                                                              tmp_path):
        # Which registry the receiver will NOT get is the actionable part; a
        # bare "skipped 1" leaves them to find out by searching for something
        # that is silently absent.
        _tapped("acme/skills", "never/built")
        _cache("acme/skills")
        r = boost("catalog", "--export", str(tmp_path / "c.tgz"))
        assert "never/built" in r.err + r.out

    def test_exporting_nothing_fails_loudly(self, boost, sandbox, tmp_path):
        r = boost("catalog", "--export", str(tmp_path / "c.tgz"), expect=1)
        assert "nothing to export" in r.err

    def test_json_mode_is_machine_readable(self, boost, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills", entries=4)
        r = boost("catalog", "--export", str(tmp_path / "c.tgz"), "--json")
        stats = json.loads(r.out)
        assert stats["taps"] == 1 and stats["entries"] == 4
        assert stats["bytes"] > 0


class TestShow:
    def test_it_describes_a_bundle_without_importing_it(self, boost, sandbox,
                                                       tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills", entries=2)
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        # Wipe the machine: --show must read the FILE, not local state.
        config.save({"taps": []})
        for path in paths.cache_dir().glob("*.json"):
            path.unlink()

        r = boost("catalog", "--show", str(dest))

        assert "acme/skills" in r.out
        assert "2 entries" in r.out
        # ...and it must not have imported anything as a side effect.
        assert not list(paths.cache_dir().glob("acme__skills.json"))

    def test_show_json_returns_the_manifest(self, boost, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        manifest = json.loads(boost("catalog", "--show", str(dest),
                                    "--json").out)
        assert manifest["taps"][0]["name"] == "acme/skills"

    def test_showing_a_non_bundle_fails_with_a_clear_message(self, boost,
                                                            sandbox, tmp_path):
        bad = tmp_path / "notes.txt"
        bad.write_text("just some text", encoding="utf-8")
        r = boost("catalog", "--show", str(bad), expect=1)
        assert "bundle" in r.err.lower()

    def test_it_names_the_remainder_past_the_row_cap(self, boost, sandbox,
                                                     tmp_path):
        # The heading's own count must not contradict the table under it —
        # 22 taps in, a 20-row table, and nothing said about the other 2.
        names = ["acme/skills-%02d" % i for i in range(22)]
        _tapped(*names)
        for n in names:
            _cache(n)
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))

        r = boost("catalog", "--show", str(dest))

        assert "22 taps" in r.out
        assert "and 2 more" in r.out
        assert "--json" in r.out


class TestImport:
    def test_a_round_trip_restores_a_searchable_catalogue(self, boost, sandbox,
                                                          tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills", entries=2)
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        config.save({"taps": []})
        for path in paths.cache_dir().glob("*.json"):
            path.unlink()

        r = boost("catalog", "--import", str(dest))

        assert "1 new tap" in r.out
        assert (paths.cache_dir() / "acme__skills.json").exists()

    def test_it_says_what_still_needs_a_clone(self, boost, sandbox, tmp_path):
        # The one thing a bundle does NOT give you. Leaving it unsaid invites
        # "why did install just clone something" as the next question.
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        r = boost("catalog", "--import", str(dest))
        assert "install" in r.out and "clone" in r.out

    def test_install_after_import_clones_lazily_no_manual_update(
            self, boost, fixture_tap_src, tmp_path):
        # The promise this command makes (see the "clones just the one
        # registry it needs" hint below): after an import, `boost install`
        # must work on its own — no `boost update <tap>` in between. Real
        # tap (not the fabricated cache above) so a genuine clone happens.
        boost("tap", fixture_tap_src)
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))

        # Simulate the receiving machine: registered + cached, never cloned.
        tap = registry.get("fixture-tap")
        shutil.rmtree(tap.path)
        assert not tap.is_cloned

        boost("catalog", "--import", str(dest))
        assert not tap.is_cloned          # import itself must not clone

        r = boost("install", "brainstorming")
        assert "installed" in r.out.lower() or "brainstorming" in r.out
        assert (paths.store_dir() / "brainstorming" / "SKILL.md").exists()

    def test_importing_a_missing_file_fails_cleanly(self, boost, sandbox,
                                                    tmp_path):
        r = boost("catalog", "--import", str(tmp_path / "absent.tgz"),
                  expect=1)
        assert "no such bundle" in r.err

    def test_import_json_mode_is_machine_readable(self, boost, sandbox,
                                                  tmp_path):
        # The half a script consumes. `files` and `added` differ on a re-import
        # and a caller automating this needs both.
        _tapped("acme/skills")
        _cache("acme/skills", entries=3)
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        stats = json.loads(boost("catalog", "--import", str(dest),
                                 "--json").out)
        assert stats["files"] == 1 and stats["entries"] == 3
        assert stats["added"] == 0        # the tap is already configured

    def test_importing_a_tarball_that_is_not_a_bundle_says_so(self, boost,
                                                              sandbox,
                                                              tmp_path):
        # A real .tar.gz of something else — the likeliest wrong file to hand
        # this command, and it must not be mistaken for a corrupt bundle.
        import tarfile
        notes = tmp_path / "notes.txt"
        notes.write_text("hello", encoding="utf-8")
        bundle = tmp_path / "other.tgz"
        with tarfile.open(bundle, "w:gz") as tar:
            tar.add(str(notes), arcname="notes.txt")
        r = boost("catalog", "--import", str(bundle), expect=1)
        assert "not a boost catalogue bundle" in r.err

    def test_import_warns_about_taps_pointing_at_a_local_directory(
            self, boost, sandbox, tmp_path):
        local_dir = tmp_path / "local-repo"
        local_dir.mkdir()
        cfg = config.load()
        cfg["taps"] = [{"name": "acme/skills", "url": str(local_dir),
                        "curated": False}]
        config.save(cfg)
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        config.save({"taps": []})
        for path in paths.cache_dir().glob("*.json"):
            path.unlink()

        r = boost("catalog", "--import", str(dest))

        assert "acme/skills" in r.out + r.err
        assert "exporting machine" in r.out + r.err

    def test_import_of_a_remote_bundle_prints_no_local_tap_warning(
            self, boost, sandbox, tmp_path):
        _tapped("acme/skills")
        _cache("acme/skills")
        dest = tmp_path / "c.tgz"
        boost("catalog", "--export", str(dest))
        config.save({"taps": []})
        for path in paths.cache_dir().glob("*.json"):
            path.unlink()

        r = boost("catalog", "--import", str(dest))

        assert "exporting machine" not in r.out + r.err

    def test_the_three_modes_are_mutually_exclusive(self, boost, sandbox,
                                                    tmp_path):
        # argparse enforces it; asserting it keeps `--export X --import Y` from
        # ever becoming a silently-ordered operation.
        boost("catalog", "--export", str(tmp_path / "a.tgz"),
              "--import", str(tmp_path / "b.tgz"), expect=2)

    def test_calling_it_with_no_mode_is_an_error(self, boost, sandbox):
        boost("catalog", expect=2)
