# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: `boost compact` narrows existing clones to the Markdown cone.

Taps clone sparse from now on, but a machine that has been tapping for a while
has full clones already on disk — 458 of them, 12 GB, on the machine this was
built for. `compact` narrows them in place: applying the sparse cone to an
existing clone drops the freight out of the working tree without touching the
network. Measured on `github/awesome-copilot`: 177 MB -> 93 MB, all 1,736
Markdown files still there and zero non-Markdown files left.

The remaining floor is `.git` itself (76 MB of that 93 MB), because a clone that
already downloaded every blob cannot be made blobless in place. `--reclone`
trades network time for that last chunk.

The stat-cache detail is load-bearing and has its own test: git refuses to
remove a path it considers not up to date, so a clone whose mtimes have moved
(a restored backup, a copied BOOST_HOME) silently keeps every file and reports
success. `compact` refreshes the index first.
"""
from __future__ import annotations

import subprocess

from boost_cli.core import gitutil, paths, registry


def _fat_clone(src, dest):
    """A full (non-sparse) clone, as every pre-existing tap on disk is."""
    gitutil.clone_shallow(str(src), dest, sparse=False)
    return dest


def _repo(dest):
    """A git repo shipping Markdown beside a chunk of freight."""
    (dest / "skills" / "demo" / "assets").mkdir(parents=True)
    (dest / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\n\nBody.\n", encoding="utf-8")
    (dest / "skills" / "demo" / "assets" / "blob.bin").write_text(
        "x" * 50_000, encoding="utf-8")
    (dest / "node_modules").mkdir()
    (dest / "node_modules" / "pkg.js").write_text("y" * 50_000, encoding="utf-8")
    for argv in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-qm", "init"]):
        subprocess.run(["git", *argv], cwd=dest, check=True, capture_output=True)
    return dest


class TestCompactNarrowsInPlace:
    def test_freight_leaves_the_working_tree(self, boost, sandbox, tmp_path):
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        clone = registry.list_taps()[0].path
        # Simulate the pre-existing full clones this command exists for.
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])
        assert (clone / "node_modules" / "pkg.js").exists()

        boost("compact")

        assert not (clone / "node_modules" / "pkg.js").exists()
        assert not (clone / "skills" / "demo" / "assets" / "blob.bin").exists()

    def test_markdown_survives(self, boost, sandbox, tmp_path):
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        clone = registry.list_taps()[0].path
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])

        boost("compact")

        assert (clone / "skills" / "demo" / "SKILL.md").exists()

    def test_the_catalog_is_unchanged(self, boost, sandbox, tmp_path):
        """Narrowing must not cost the machine a single indexed item."""
        from boost_cli.core import catalog

        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        before = {(e["kind"], e["name"]) for e in catalog.all_entries()}

        boost("compact")

        assert {(e["kind"], e["name"]) for e in catalog.all_entries()} == before

    def test_dry_run_changes_nothing_and_names_a_real_figure(
            self, boost, sandbox, tmp_path):
        """The tap ships ~100 KB of freight; a run reporting 0 B is the bug
        where every path was excluded because clones live under ~/.boost."""
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        clone = registry.list_taps()[0].path
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])

        res = boost("compact", "--dry-run")

        assert (clone / "node_modules" / "pkg.js").exists()
        assert "would" in res.out.lower()
        assert "0 B would be freed" not in res.out
        assert "1 tap(s)" in res.out

    def test_a_stale_stat_cache_does_not_silently_skip_the_repo(
            self, boost, sandbox, tmp_path):
        """git leaves paths it thinks are dirty; a copied BOOST_HOME hits this."""
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        clone = registry.list_taps()[0].path
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])
        # Move every mtime so git's cached stat data no longer matches.
        for pth in clone.rglob("*"):
            if pth.is_file() and ".git" not in pth.parts:
                os_utime(pth)

        boost("compact")

        assert not (clone / "node_modules" / "pkg.js").exists(), (
            "compact must refresh the index before narrowing")

    def test_an_installed_skills_files_stay_complete(
            self, boost, sandbox, tmp_path):
        """Compacting must not strip the assets of a skill already installed."""
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        boost("install", "demo")

        boost("compact")

        dest = paths.store_dir() / "demo"
        assert (dest / "assets" / "blob.bin").exists(), (
            "installed copy lost its assets")

    def test_dry_run_does_not_promise_back_the_provenance_files(
            self, boost, sandbox, tmp_path):
        """`.boost/` survives the cone, so it is not freed and must not be counted."""
        src = _repo(tmp_path / "src")
        (src / ".boost").mkdir()
        (src / ".boost" / "tap.manifest").write_text("m" * 40_000, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=src, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "prov"], cwd=src, check=True,
                       capture_output=True)
        boost("tap", str(src))
        gitutil.run(["-C", str(registry.list_taps()[0].path),
                     "sparse-checkout", "disable"])

        res = boost("compact", "--dry-run")

        # 100 KB of freight is reported; the 40 KB manifest is kept, not freed.
        assert "0 B would be freed" not in res.out
        assert "140" not in res.out and "1.4" not in res.out, (
            "the manifest was counted as freight: %s" % res.out)

    def test_it_reports_what_it_freed(self, boost, sandbox, tmp_path):
        src = _repo(tmp_path / "src")
        boost("tap", str(src))
        gitutil.run(["-C", str(registry.list_taps()[0].path),
                     "sparse-checkout", "disable"])

        res = boost("compact")

        assert "freed" in res.out.lower()

    def test_compacting_twice_is_harmless(self, boost, sandbox, tmp_path):
        src = _repo(tmp_path / "src")
        boost("tap", str(src))

        boost("compact")
        res = boost("compact")

        assert res.rc == 0
        assert (registry.list_taps()[0].path / "skills" / "demo" / "SKILL.md").exists()


def os_utime(pth):
    import os
    st = pth.stat()
    os.utime(pth, (st.st_atime + 10_000, st.st_mtime + 10_000))
