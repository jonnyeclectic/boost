# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
import sys

import pytest

from boost_cli.core import catalog, gitutil
from boost_cli.errors import BoostError


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
    """Run clone_shallow with gitutil._exec stubbed; return the argv it built."""
    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen.setdefault("calls", []).append(argv)
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gitutil, "has_git", lambda: True)
    monkeypatch.setattr(gitutil, "_exec", fake_run)
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
        monkeypatch.setattr(gitutil, "_exec", fake_run)

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
        add = next(c for c in seen["calls"] if "sparse-checkout" in c)
        assert "add" in add, "materialize must not clobber the existing cone"
        assert "/skills/foo/*" in add
        assert argv[-3:] == ["ls-files", "-t", "-z"], (
            "the widened dir must be checked before anything copies it")

    @pytest.mark.parametrize("rel", [".", "", "/"])
    def test_materializing_the_repo_root_widens_to_everything(
            self, monkeypatch, tmp_path, rel):
        """rel_dir "." means the whole repo is the skill, so the whole repo is
        checked out. This was a no-op, and a sparse clone's root holds only
        Markdown: the skill's scripts/ installed as nothing."""
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)

        gitutil.materialize(repo, rel)

        assert seen["calls"] == [
            ["git", "-c", "core.precomposeunicode=false", "-C", str(repo),
             "sparse-checkout", "add", "/*"],
            ["git", "-c", "core.precomposeunicode=false", "-C", str(repo),
             "ls-files", "-t", "-z"]]

    def test_a_root_already_widened_costs_no_subprocess(self, monkeypatch,
                                                        tmp_path):
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        info = tmp_path / "repo" / ".git" / "info"
        info.mkdir(parents=True)
        (info / "sparse-checkout").write_text("*.md\n/*\n", encoding="utf-8")

        gitutil.materialize(tmp_path / "repo", ".")

        assert "calls" not in seen

    def test_a_root_left_partly_skip_worktree_is_refused(self, monkeypatch,
                                                         tmp_path):
        """Every path belongs to the root, so any one left out fails it."""
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        monkeypatch.setattr(gitutil, "has_git", lambda: True)
        repo = tmp_path / "tap"
        (repo / ".git").mkdir(parents=True)

        def fake(argv, **_k):
            out = "H SKILL.md\0S scripts/run.sh\0S z/deep.py\0" \
                if "ls-files" in argv else ""
            return subprocess.CompletedProcess(argv, 0, out, "")
        monkeypatch.setattr(gitutil, "_exec", fake)

        with pytest.raises(BoostError) as err:
            gitutil.materialize(repo, ".")
        assert err.value.message == (
            "could not check out 2 files of the repo root from the tap tap "
            "(scripts/run.sh, z/deep.py), so installing it would copy a "
            "partial skill")

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

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="Windows forbids * ? \\ in file names")
    def test_a_dir_named_with_glob_characters_is_fetched_whole(self, tmp_path):
        """``glob[1]`` added verbatim is a character class matching ``glob1``:
        the real dir never checked out and its scripts installed as nothing."""
        src = tmp_path / "src"
        for name in ("glob[1]", "a*b?c\\d"):
            d = src / "skills" / name
            (d / "scripts").mkdir(parents=True)
            (d / "SKILL.md").write_text("---\nname: g\ndescription: g\n---\n",
                                        encoding="utf-8")
            (d / "scripts" / "run.sh").write_text("echo\n", encoding="utf-8")
        (src / "skills" / "glob1" / "scripts").mkdir(parents=True)
        (src / "skills" / "glob1" / "scripts" / "decoy.sh").write_text(
            "echo\n", encoding="utf-8")
        for argv in (["init", "-q", "-b", "main"], ["add", "-A"],
                     ["-c", "user.email=t@t", "-c", "user.name=t",
                      "commit", "-qm", "init"]):
            subprocess.run(["git", *argv], cwd=src, check=True,
                           capture_output=True)
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)

        gitutil.materialize(clone, "skills/glob[1]")
        gitutil.materialize(clone, "skills/a*b?c\\d/")

        assert (clone / "skills" / "glob[1]" / "scripts" / "run.sh").is_file()
        assert (clone / "skills" / "a*b?c\\d" / "scripts" / "run.sh").is_file()
        assert not (clone / "skills" / "glob1" / "scripts" / "decoy.sh").exists()
        cone = (clone / ".git" / "info" / "sparse-checkout").read_text(
            encoding="utf-8").splitlines()
        assert "/skills/glob\\[1\\]/*" in cone
        assert "/skills/a\\*b\\?c\\\\d/*" in cone

    def test_pull_preserves_the_sparse_checkout(self, tmp_path, fixture_tap_src):
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(fixture_tap_src), clone)

        gitutil.pull(clone)

        assert gitutil.is_sparse(clone)
        assert list(clone.rglob("SKILL.md")), "update must not empty the checkout"


class TestSparseEscape:
    """A literal path spelled in git's no-cone (gitignore) pattern syntax."""

    @pytest.mark.parametrize(("rel", "want"), [
        ("skills/plain-name", "skills/plain-name"),
        ("glob[1]", "glob\\[1\\]"),
        ("a*b?c", "a\\*b\\?c"),
        ("back\\slash", "back\\\\slash"),
        ("!bang/#hash", "!bang/#hash"),
        ("trail  ", "trail\\ \\ "),
        ("mid dle", "mid dle"),
    ])
    def test_escapes_only_what_git_reads_as_special(self, rel, want):
        assert gitutil.sparse_escape(rel) == want

    def test_an_escaped_trailing_space_survives_reading_the_cone(self,
                                                                 tmp_path):
        info = tmp_path / ".git" / "info"
        info.mkdir(parents=True)
        (info / "sparse-checkout").write_text(
            "  /a\\ \n/b  \r\n# note\n\n", encoding="utf-8")
        assert gitutil._sparse_list(tmp_path) == {"/a\\ ", "/b"}


class TestMaterializePaths:
    """A skill's links into the rest of the tap: each target, as a file and
    as a dir, in one `add`."""

    def _repo(self, tmp_path, have=""):
        repo = tmp_path / "repo"
        (repo / ".git" / "info").mkdir(parents=True)
        (repo / ".git" / "info" / "sparse-checkout").write_text(
            have, encoding="utf-8")
        return repo

    def test_adds_each_path_as_file_and_dir_in_one_call(self, monkeypatch,
                                                        tmp_path):
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        repo = self._repo(tmp_path)
        gitutil.materialize_paths(repo, ["/shared/helper.py", "lib", ".", ""])
        ls = ["git", "-c", "core.precomposeunicode=false", "-C", str(repo),
              "ls-files", "-t", "-z"]
        assert seen["calls"] == [[
            "git", "-c", "core.precomposeunicode=false", "-C", str(repo),
            "sparse-checkout", "add", "/shared/helper.py", "/shared/helper.py/*", "/lib", "/lib/*"],
            ls, ls]

    def test_a_target_left_skip_worktree_is_refused(self, monkeypatch,
                                                    tmp_path):
        """A file target matches by its own path, a dir by its prefix; a
        sibling that only shares the prefix's spelling is not it."""
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        monkeypatch.setattr(gitutil, "has_git", lambda: True)

        def fake(argv, **_k):
            out = ("S shared/helper.py\0S lib/x.sh\0S library/y.sh\0"
                   if "ls-files" in argv else "")
            return subprocess.CompletedProcess(argv, 0, out, "")
        monkeypatch.setattr(gitutil, "_exec", fake)
        repo = self._repo(tmp_path)

        with pytest.raises(BoostError) as err:
            gitutil.materialize_paths(repo, ["shared/helper.py"])
        assert err.value.message.startswith(
            "could not check out 1 file of shared/helper.py from the repo tap "
            "(shared/helper.py)")
        with pytest.raises(BoostError) as err:
            gitutil.materialize_paths(repo, ["lib"])
        assert "1 file of lib from the repo tap (lib/x.sh)" in err.value.message

    def test_patterns_already_present_are_not_added_again(self, monkeypatch,
                                                          tmp_path):
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        repo = self._repo(tmp_path, "*.md\n/lib\n/lib/*\n")
        gitutil.materialize_paths(repo, ["lib"])
        assert "calls" not in seen
        gitutil.materialize_paths(repo, ["lib", "x"])
        assert seen["calls"][0][-2:] == ["/x", "/x/*"]
        assert "/lib" not in seen["calls"][0]

    def test_each_path_is_escaped_as_a_literal(self, monkeypatch, tmp_path):
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        repo = self._repo(tmp_path, "/x\\[1\\]\n/x\\[1\\]/*\n")
        gitutil.materialize_paths(repo, ["x[1]"])
        assert "calls" not in seen, "an escaped pattern must count as present"
        gitutil.materialize_paths(repo, ["s/h?.py"])
        assert seen["calls"][:1] == [[
            "git", "-c", "core.precomposeunicode=false", "-C", str(repo),
            "sparse-checkout", "add", "/s/h\\?.py", "/s/h\\?.py/*"]]

    def test_a_full_clone_is_left_alone(self, monkeypatch, tmp_path):
        seen = _clone_argv(monkeypatch)
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: False)
        gitutil.materialize_paths(self._repo(tmp_path), ["x"])
        assert "calls" not in seen

    def test_a_failed_fetch_names_the_paths_and_the_network(self, monkeypatch,
                                                            tmp_path):
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)

        def boom(*_a, **_k):
            raise BoostError("unable to access")
        monkeypatch.setattr(gitutil, "run", boom)
        with pytest.raises(BoostError) as err:
            gitutil.materialize_paths(self._repo(tmp_path), ["a", "b"])
        assert err.value.message == ("could not fetch a, b from the repo tap: "
                                     "unable to access")
        assert err.value.hint == ("this needs network — the tap stores only "
                                  "Markdown locally")


class TestSparseLock:
    """git fails `sparse-checkout add` outright on its own lock file: 40
    parallel installs from one tap lost one, and a killed git's leftover
    lock failed every later install from that tap behind a "needs network"
    hint, though the tap was a local path."""

    BUSY = ("git sparse-checkout failed: fatal: Unable to create "
            "'/x/.git/info/sparse-checkout.lock': File exists.")

    def _repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git" / "info").mkdir(parents=True)
        (repo / ".git" / "info" / "sparse-checkout").write_text(
            "*.md\n", encoding="utf-8")
        return repo

    def _git(self, monkeypatch, *errors):
        """Stub `run` to raise ``errors`` in turn, then succeed."""
        calls: list = []
        queue = list(errors)

        def fake(argv, **_k):
            calls.append(argv)
            if queue:
                raise BoostError(queue.pop(0))
            return subprocess.CompletedProcess(argv, 0, "", "")
        monkeypatch.setattr(gitutil, "is_sparse", lambda repo: True)
        monkeypatch.setattr(gitutil, "run", fake)
        return calls

    def test_a_stale_git_lock_is_removed_and_the_add_retried(self, monkeypatch,
                                                             tmp_path):
        repo = self._repo(tmp_path)
        stale = repo / ".git" / "info" / "sparse-checkout.lock"
        stale.write_text("", encoding="utf-8")
        calls = self._git(monkeypatch, self.BUSY)
        gitutil.materialize(repo, "skills/a")
        add = ["-c", "core.precomposeunicode=false", "-C", str(repo),
               "sparse-checkout", "add", "/skills/a/*"]
        verify = ["-c", "core.precomposeunicode=false", "-C", str(repo),
                  "ls-files", "-t", "-z"]
        assert calls == [add, add, verify]
        assert not stale.exists()

    def test_a_lock_that_comes_back_says_so_not_network(self, monkeypatch,
                                                        tmp_path):
        repo = self._repo(tmp_path)
        calls = self._git(monkeypatch, self.BUSY, self.BUSY)
        with pytest.raises(BoostError) as err:
            gitutil.materialize(repo, "skills/a")
        assert len(calls) == 2
        assert err.value.message == ("could not fetch skills/a from the repo "
                                     "tap: " + self.BUSY)
        # The lock git names, not one boost reconstructs: git's is the path
        # that exists (a /var/folders HOME resolves to /private/var).
        assert err.value.hint == (
            "another git process is working in this tap's clone; if none is, "
            "remove /x/.git/info/sparse-checkout.lock")

    def test_a_lock_named_without_file_exists_is_not_retried(self, monkeypatch,
                                                              tmp_path):
        repo = self._repo(tmp_path)
        calls = self._git(monkeypatch, "fatal: could not open "
                          "'/x/.git/info/sparse-checkout.lock': Permission denied")
        with pytest.raises(BoostError) as err:
            gitutil.materialize(repo, "skills/a")
        assert len(calls) == 1
        assert err.value.hint is None

    def test_another_failure_is_not_retried(self, monkeypatch, tmp_path):
        repo = self._repo(tmp_path)
        calls = self._git(monkeypatch, "git sparse-checkout failed: fatal: "
                          "Could not read from remote repository.")
        with pytest.raises(BoostError) as err:
            gitutil.materialize_paths(repo, ["lib"])
        assert len(calls) == 1
        assert err.value.hint == gitutil.NETWORK_HINT

    @pytest.mark.parametrize("text", [
        "fatal: unable to access 'https://x/': SSL", "Could not resolve host: x",
        "failed to connect to x", "Connection reset by peer",
        "git fetch timed out after 300s", "network is unreachable"])
    def test_transport_failures_name_the_network(self, monkeypatch, tmp_path,
                                                 text):
        repo = self._repo(tmp_path)
        self._git(monkeypatch, text)
        with pytest.raises(BoostError) as err:
            gitutil.materialize(repo, "skills/a")
        assert err.value.hint == gitutil.NETWORK_HINT

    def test_an_unrecognised_failure_blames_nothing(self, monkeypatch, tmp_path):
        repo = self._repo(tmp_path)
        self._git(monkeypatch, "fatal: bad object deadbeef")
        with pytest.raises(BoostError) as err:
            gitutil.materialize(repo, "skills/a")
        assert err.value.hint is None
        assert err.value.message == ("could not fetch skills/a from the repo "
                                     "tap: fatal: bad object deadbeef")

    def test_the_cone_is_reread_inside_the_lock(self, monkeypatch, tmp_path):
        repo = self._repo(tmp_path)
        (repo / ".git" / "info" / "sparse-checkout").write_text(
            "*.md\n/skills/a/*\n", encoding="utf-8")
        calls = self._git(monkeypatch)
        gitutil._sparse_add(repo, ["/skills/a/*", "/skills/b/*"], "x")
        assert calls == [["-c", "core.precomposeunicode=false", "-C",
                          str(repo), "sparse-checkout", "add", "/skills/b/*"]]
        calls.clear()
        gitutil._sparse_add(repo, ["/skills/a/*"], "x")
        assert calls == []

    def test_waits_on_boost_s_own_lock(self, monkeypatch, tmp_path):
        from boost_cli.core import util
        repo = self._repo(tmp_path)
        self._git(monkeypatch)
        monkeypatch.setattr(gitutil, "SPARSE_LOCK_TIMEOUT", 0)
        with util.file_lock(repo / ".git" / "boost-sparse.lock"), \
                pytest.raises(BoostError, match=r"^another boost process has "
                              r"held the repo tap's checkout for over 0s$"):
            gitutil.materialize(repo, "skills/a")

    def test_set_cone_takes_the_same_lock(self, monkeypatch, tmp_path):
        # `_sparse_add` deletes a sparse-checkout.lock it finds while holding
        # boost's lock, so a `set` (boost compact) outside it could lose its
        # live git lock to a concurrent install.
        from boost_cli.core import util
        repo = self._repo(tmp_path)
        calls = self._git(monkeypatch)
        monkeypatch.setattr(gitutil, "SPARSE_LOCK_TIMEOUT", 0)
        with util.file_lock(repo / ".git" / "boost-sparse.lock"), \
                pytest.raises(BoostError, match=r"^another boost process has "
                              r"held the repo tap's checkout for over 0s$"):
            gitutil.set_sparse_cone(repo, ("*.md",))
        assert calls == []
        gitutil.set_sparse_cone(repo, ("*.md",))
        assert calls == [["-C", str(repo), "sparse-checkout", "set",
                          "--no-cone", "*.md"]]

    def test_a_gitfile_clone_gets_git_s_error_not_a_lock_crash(
            self, monkeypatch, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
        monkeypatch.setattr(gitutil, "_sparse_list", lambda r: set())
        calls = self._git(monkeypatch, "fatal: not a git repository")
        with pytest.raises(BoostError) as err:
            gitutil._sparse_add(repo, ["/skills/a/*"], "skills/a")
        assert len(calls) == 1
        assert err.value.message == ("could not fetch skills/a from the repo "
                                     "tap: fatal: not a git repository")

    def test_against_real_git_a_leftover_lock_no_longer_blocks(self, tmp_path):
        src = _repo_with_asset(tmp_path / "src")
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        (clone / ".git" / "info" / "sparse-checkout.lock").write_text(
            "", encoding="utf-8")
        gitutil.materialize(clone, "skills/demo")
        assert (clone / "skills" / "demo" / "scripts" / "run.js").exists()
        assert not (clone / ".git" / "info" / "sparse-checkout.lock").exists()

    def test_against_real_git_parallel_adds_all_land(self, tmp_path):
        import concurrent.futures
        src = tmp_path / "src"
        for i in range(1, 12):
            _write = src / "skills" / ("s%02d" % i) / "scripts"
            _write.mkdir(parents=True)
            (_write.parent / "SKILL.md").write_text(
                "---\nname: s%02d\ndescription: d\n---\n" % i, encoding="utf-8")
            (_write / "run.js").write_text("1\n", encoding="utf-8")
        _repo_with_asset(src)
        clone = tmp_path / "c"
        gitutil.clone_shallow(str(src), clone)
        names = ["s%02d" % i for i in range(1, 12)]
        with concurrent.futures.ThreadPoolExecutor(len(names)) as ex:
            list(ex.map(lambda n: gitutil.materialize(clone, "skills/" + n),
                        names))
        missing = [n for n in names
                   if not (clone / "skills" / n / "scripts" / "run.js").exists()]
        assert missing == []
