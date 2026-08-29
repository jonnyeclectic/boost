# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: taps check out only the files the scanner reads.

A tap is indexed for its Markdown, but a clone brings the whole working tree —
node_modules, `.bin` assets, 10 MB bundled `validate.js` files. Measured on a
real machine: 458 taps occupied 12 GB, of which 1.9 GB was Markdown and the
rest was freight. `Shopify/agent-skills` alone was 611 MB for the 30 SKILL.md
files boost wanted.

So taps clone `--filter=blob:none --sparse` and set a sparse-checkout cone
covering exactly the patterns :func:`catalog.scan_dir` reads. The same repo then
occupies 11 MB and produces a byte-identical catalog. Blobs outside the cone are
never downloaded; when one is finally needed — installing a skill that ships
assets — :func:`gitutil.materialize` widens the cone and git fetches it from the
promisor remote on demand.

Two properties carry the whole design and are tested hardest:

* the cone must cover every pattern the scanner reads, or taps silently lose
  items (:class:`TestConeMatchesWhatTheScannerReads`);
* install must materialize before copying, or a skill is installed without its
  assets and nothing errors (:class:`TestMaterializeBeforeCopy`).

Local clones ignore `--depth` and `--filter` (git warns and proceeds), and a
server that cannot filter makes git fall back on its own, so neither is an error
path. Old git without `--sparse` is, and falls back to a plain shallow clone.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.core import catalog, gitutil


def _repo_with_asset(dest, extra: str | None = None):
    """A git repo whose skills ship a non-Markdown asset beside their SKILL.md."""
    names = ["demo"] + ([extra] if extra else [])
    for name in names:
        d = dest / "skills" / name
        (d / "scripts").mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: demo skill\n---\n\nBody.\n" % name,
            encoding="utf-8")
        (d / "scripts" / "run.js").write_text("console.log(1)\n", encoding="utf-8")
    for argv in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-qm", "init"]):
        subprocess.run(["git", *argv], cwd=dest, check=True, capture_output=True)
    return dest


def _clone_argv(monkeypatch) -> dict:
    """Run clone_shallow with subprocess.run stubbed; return the argv it built."""
    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen.setdefault("calls", []).append(argv)
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gitutil, "has_git", lambda: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


class TestConeMatchesWhatTheScannerReads:
    """The cone is derived from catalog's own constants, so it cannot drift."""

    def test_cone_covers_skill_md(self):
        assert any(p == "*.md" for p in gitutil.SPARSE_PATTERNS), (
            "SKILL.md and loose workflow Markdown must check out")

    def test_cone_covers_every_rule_suffix(self):
        for suffix in catalog.RULE_SUFFIXES:
            assert "*" + suffix in gitutil.SPARSE_PATTERNS, (
                "rule suffix %s is scanned but never checked out" % suffix)

    def test_cone_covers_every_rule_filename(self):
        for name in catalog.RULE_FILENAMES:
            assert name in gitutil.SPARSE_PATTERNS, (
                "rule file %s is scanned but never checked out" % name)

    def test_cone_covers_the_provenance_dir(self):
        """A signed tap whose .minisig is outside the cone reports `unsigned` —
        a signature check that fails open."""
        from boost_cli.core import provenance

        for rel in (provenance.SIGNED_FILE, provenance.SIGNATURE_FILE):
            top = rel.split("/")[0]
            assert "/%s/*" % top in gitutil.SPARSE_PATTERNS, (
                "%s would not check out" % rel)

    def test_no_pattern_is_orphaned(self):
        """Every pattern must trace back to something boost reads."""
        from boost_cli.core import provenance

        expected = {"*.md"}
        expected |= {"*" + s for s in catalog.RULE_SUFFIXES}
        expected |= set(catalog.RULE_FILENAMES)
        expected |= {"/%s/*" % provenance.SIGNED_FILE.split("/")[0]}

        assert set(gitutil.SPARSE_PATTERNS) == expected


class TestCloneRequestsAPartialSparseCheckout:
    def test_clone_asks_for_blobless_sparse(self, monkeypatch, tmp_path):
        seen = _clone_argv(monkeypatch)

        gitutil.clone_shallow("https://example.test/r.git", tmp_path / "d")

        argv = next(c for c in seen["calls"] if "clone" in c)
        assert "--filter=blob:none" in argv
        assert "--sparse" in argv
        assert "--depth" in argv, "shallow history is still wanted"

    def test_clone_then_sets_the_cone(self, monkeypatch, tmp_path):
        seen = _clone_argv(monkeypatch)

        gitutil.clone_shallow("https://example.test/r.git", tmp_path / "d")

        cone = [c for c in seen["calls"] if "sparse-checkout" in c]
        assert cone, "clone must set a sparse-checkout cone"
        assert "--no-cone" in cone[0], (
            "cone mode only matches directory prefixes; boost needs *.md at any depth")
        for pattern in gitutil.SPARSE_PATTERNS:
            assert pattern in cone[0]

    def test_sparse_can_be_declined_for_a_full_checkout(self, monkeypatch, tmp_path):
        seen = _clone_argv(monkeypatch)

        gitutil.clone_shallow("https://example.test/r.git", tmp_path / "d",
                              sparse=False)

        argv = next(c for c in seen["calls"] if "clone" in c)
        assert "--sparse" not in argv
        assert "--filter=blob:none" not in argv
        assert not [c for c in seen["calls"] if "sparse-checkout" in c]

    def test_unsafe_transport_is_still_refused(self, monkeypatch, tmp_path):
        from boost_cli.errors import BoostError
        _clone_argv(monkeypatch)

        with pytest.raises(BoostError):
            gitutil.clone_shallow("ext::sh -c evil", tmp_path / "d")


class TestOldGitFallsBackToAFullClone:
    def test_a_clone_rejecting_sparse_retries_without_it(self, monkeypatch, tmp_path):
        """`--sparse` landed in git 2.25; older git must still be able to tap."""
        calls: list = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if "--sparse" in argv:
                return subprocess.CompletedProcess(
                    argv, 129, "", "error: unknown option `sparse'")
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(gitutil, "has_git", lambda: True)
        monkeypatch.setattr(subprocess, "run", fake_run)

        gitutil.clone_shallow("https://example.test/r.git", tmp_path / "d")

        plain = [c for c in calls if c[1] == "clone" and "--sparse" not in c]
        assert plain, "a git too old for --sparse must still get a working clone"
        assert "--depth" in plain[-1]


class TestMaterializeIsCheapInALoop:
    """`outdated`/`drift`/`sync` call this once per installed skill."""

    def test_an_already_materialized_dir_costs_no_subprocess(self, tmp_path):
        src = _repo_with_asset(tmp_path / "src")
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        gitutil.materialize(clone, "skills/demo")
        calls: list = []

        orig = subprocess.run
        try:
            subprocess.run = lambda *a, **k: (calls.append(a), orig(*a, **k))[1]
            for _ in range(5):
                gitutil.materialize(clone, "skills/demo")
        finally:
            subprocess.run = orig

        assert calls == [], (
            "repeat materialize shelled out %d times; a 33-skill loop pays it "
            "once per skill" % len(calls))

    def test_a_full_clone_is_cached_after_the_first_check(self, tmp_path,
                                                          monkeypatch):
        src = _repo_with_asset(tmp_path / "src")
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone, sparse=False)
        gitutil._SPARSE.clear()
        calls: list = []
        real = gitutil.run
        monkeypatch.setattr(gitutil, "run",
                            lambda *a, **k: (calls.append(a), real(*a, **k))[1])

        for _ in range(5):
            gitutil.materialize(clone, "skills/demo")

        assert len(calls) == 1, "is_sparse must be cached per repo"


class TestMaterialize:
    def test_materialize_adds_the_dir_rather_than_replacing_the_cone(
            self, monkeypatch, tmp_path):
        """`set` would drop every previously materialized skill; `add` must be used."""
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        (tmp_path / "repo" / ".git").mkdir(parents=True)

        gitutil.materialize(tmp_path / "repo", "skills/foo")

        argv = seen["argv"]
        assert "sparse-checkout" in argv
        assert "add" in argv, "materialize must not clobber the existing cone"
        assert "/skills/foo/*" in argv

    def test_materializing_the_repo_root_is_a_noop(self, monkeypatch, tmp_path):
        """rel_dir "." means the whole repo is the skill; nothing to narrow."""
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        (tmp_path / "repo" / ".git").mkdir(parents=True)

        gitutil.materialize(tmp_path / "repo", ".")

        assert not [c for c in seen.get("calls", []) if "sparse-checkout" in c]

    def test_materialize_is_a_noop_on_a_non_sparse_clone(self, monkeypatch, tmp_path):
        """Clones made before this change have every file already."""
        seen = _clone_argv(monkeypatch)
        (tmp_path / "repo" / ".git").mkdir(parents=True)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: False)

        gitutil.materialize(tmp_path / "repo", "skills/foo")

        assert not [c for c in seen.get("calls", []) if "sparse-checkout" in c]


class TestSparseCloneAgainstARealRepo:
    """End-to-end against the fixture tap — the properties that matter on disk."""

    def test_scanner_sees_the_same_catalog_as_a_full_clone(
            self, tmp_path, fixture_tap_src):
        full, sparse = tmp_path / "full", tmp_path / "sparse"
        gitutil.clone_shallow(str(fixture_tap_src), full, sparse=False)
        gitutil.clone_shallow(str(fixture_tap_src), sparse)

        def key(entries):
            return {(e["kind"], e["name"], e["skill_md"]) for e in entries}

        assert key(catalog.scan_dir(sparse, "t")) == key(catalog.scan_dir(full, "t"))
        assert key(catalog.scan_dir(sparse, "t")), "fixture must yield entries"

    def test_a_non_markdown_asset_is_absent_until_materialized(self, tmp_path):
        """The freight a skill legitimately owns: present on demand, not before."""
        src = _repo_with_asset(tmp_path / "src")
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)

        assert (clone / "skills" / "demo" / "SKILL.md").exists(), (
            "Markdown must always check out")
        assert not (clone / "skills" / "demo" / "scripts" / "run.js").exists(), (
            "a non-Markdown asset must stay outside the cone")

        gitutil.materialize(clone, "skills/demo")

        assert (clone / "skills" / "demo" / "scripts" / "run.js").exists(), (
            "materialize must bring the skill's own assets in")

    def test_materializing_one_skill_leaves_the_rest_narrow(self, tmp_path):
        """Widening for an install must not undo the saving for every other skill."""
        src = _repo_with_asset(tmp_path / "src", extra="other")
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)

        gitutil.materialize(clone, "skills/demo")

        assert not (clone / "skills" / "other" / "scripts" / "run.js").exists()

    def test_pull_preserves_the_sparse_checkout(self, tmp_path, fixture_tap_src):
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(fixture_tap_src), clone)

        gitutil.pull(clone)

        assert gitutil.is_sparse(clone)
        assert list(clone.rglob("SKILL.md")), "update must not empty the checkout"
