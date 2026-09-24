# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a dry run says what the real run will do, and nothing more.

A preview's one job is fidelity, and a confident wrong number is worse than no
number — the user acts on it. Ten measured divergences are pinned here:

* ``compact --dry-run`` counted freight by walking the working tree, but
  ``git sparse-checkout reapply`` only drops *tracked* paths outside the cone.
  A 1 MiB untracked ``scripts/junk.bin`` was promised ("would free 1.0MB") and
  the live run then printed "every tap is already compact" with the file still
  on disk.
* ``compact --dry-run --reclone`` printed byte-for-byte what the plain dry run
  printed, although a reclone removes the clone's whole ``.git`` *and* the
  untracked freight, then re-downloads a blobless clone whose size only the
  remote knows.
* ``heal --dry-run`` said "would restore X from its tap (or drop it from the
  lock)" on a state where ``sync_apply`` demonstrably reinstalls, previewed no
  rule/workflow repair at all, and promised a re-record over a corrupt lock
  that the live run leaves alone.
* ``heal --dry-run`` said "would create 11 missing directories" — the one
  repair that never named its paths.
* ``onboard --dry-run`` cut every preview at 24 lines with no marker (the lock
  preview ends mid-object), and ``--dry-run --pr`` outside a git repository
  exited 0 with no plan and no precondition failure.
* ``install <workflow> --agent codex --dry-run`` printed ``materialize → (no
  enabled agents)`` about an agent that is enabled, and exited 0 where the run
  raises — the preview reimplemented the narrowing instead of calling it.
* ``install <skill> --local --agent antigravity --dry-run`` printed its "would
  install … into <repo>" header with no ``copy →`` line under it and exited 0,
  where the run raises.
* ``install <skill> --agent cursor --dry-run`` dropped the "available to …
  (reads the store directly)" line the run prints, because it filtered the
  native-store agents by ``--agent`` — which `store.link_agents` documents as
  a lie, since the store is written however narrow the scope.
* ``install a b --agent codex --dry-run``, with ``b`` an item the narrowing
  refuses, printed ``a``'s plan and then exited out of the whole command —
  no plan for anything after ``b``, and not even the "dry run — nothing was
  changed" line — while the run installs ``a``, warns about ``b`` and carries
  on. The live loop had a per-entry handler and the preview loop had none.
* ``install <skill> --force --dry-run`` after ``install <skill> --agent
  cursor`` previewed a link into every linking agent, because it filtered
  ``linking_agents()`` by the *typed* ``--agent`` once, outside the entry
  loop, while the run replays the lock's recorded scope per entry.

The CLI tests drive the preview and the live run over the same state and
compare the two, because parity is the property; a test of the preview alone
can pass while it still disagrees with the run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from boost_cli.core import (
    agents,
    config,
    gitutil,
    lockfile,
    paths,
    registry,
    store,
    util,
)
from boost_cli.errors import BoostError

# Sizes are asserted exactly, never `> 0`: the defect was an *inflated* number,
# so a test that only checks for a number reproduces the bug it is pinning.
TRACKED_ASSET = 50_000     # skills/demo/assets/blob.bin  (tracked, off-cone)
TRACKED_VENDOR = 50_000    # node_modules/pkg.js          (tracked, off-cone)
UNTRACKED_JUNK = 1_048_576  # scripts/junk.bin             (untracked, off-cone)


def _compact():
    # Imported per test rather than at module level: on a tree without the
    # module only these tests should fail, not every CLI parity test below.
    from boost_cli.core import compact
    return compact


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=str(cwd), check=True, capture_output=True)


def _repo(dest):
    """A git repo shipping Markdown beside a chunk of tracked freight."""
    (dest / "skills" / "demo" / "assets").mkdir(parents=True)
    (dest / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\n\nBody.\n", encoding="utf-8")
    (dest / "skills" / "demo" / "assets" / "blob.bin").write_text(
        "x" * TRACKED_ASSET, encoding="utf-8")
    (dest / "node_modules").mkdir()
    (dest / "node_modules" / "pkg.js").write_text(
        "y" * TRACKED_VENDOR, encoding="utf-8")
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "init")
    return dest


def _fat_clone(src, dest):
    """A full (non-sparse) clone: every tap on disk before taps went sparse."""
    gitutil.clone_shallow(str(src), dest, sparse=False)
    return dest


def _plant_junk(clone):
    """The card's untracked 1 MiB file, in a directory outside the cone."""
    (clone / "scripts").mkdir(exist_ok=True)
    (clone / "scripts" / "junk.bin").write_bytes(b"\0" * UNTRACKED_JUNK)
    return clone / "scripts" / "junk.bin"


def _worktree_bytes(clone):
    """Bytes in the working tree, excluding `.git` — what `narrow` can free."""
    return sum(f.stat().st_size for f in clone.rglob("*")
               if f.is_file() and ".git" not in f.relative_to(clone).parts)


# ── 1. compact predicts only what `reapply` actually removes ─────────────

class TestCompactPredictsOnlyTrackedFreight:
    def test_a_tracked_file_outside_the_cone_is_promised(self, tmp_path):
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        assert _compact().freight_bytes(clone, []) == (
            TRACKED_ASSET + TRACKED_VENDOR)

    def test_an_untracked_file_is_not_promised(self, tmp_path):
        """`reapply` walks the index; a file git never heard of survives it."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")
        junk = _plant_junk(clone)

        assert _compact().freight_bytes(clone, []) == (
            TRACKED_ASSET + TRACKED_VENDOR)
        assert junk.exists()

    def test_the_prediction_is_what_narrow_frees(self, tmp_path):
        """Parity, measured rather than asserted: predict, apply, compare."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")
        _plant_junk(clone)
        predicted = _compact().freight_bytes(clone, [])
        before = _worktree_bytes(clone)

        gitutil.narrow(clone)

        assert before - _worktree_bytes(clone) == predicted

    def test_the_cone_prediction_matches_real_git_on_edge_names(self, tmp_path):
        """`in_cone` encodes what `--no-cone` keeps; this checks it against git
        itself on the names where a hand-written matcher could disagree."""
        src = tmp_path / "src"
        edge = {".boost/manifest.json": 11, "sub/.boost/x.json": 13,
                ".cursorrules": 17, "sub/.windsurfrules": 19,
                "README.MD": 23, "notes.md.bak": 29, "skills/a/SKILL.md": 31,
                # A pattern names a directory too, and git keeps its subtree.
                "docs.md/run.py": 41, ".clinerules/state/x.json": 43,
                # A bare rule name is a whole name, never a suffix.
                "sk/a.cursorrules": 37}
        for rel, size in edge.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text("x" * size, encoding="utf-8")
        _git(src, "init", "-q", "-b", "main")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "edges")
        clone = _fat_clone(src, tmp_path / "c")
        predicted = _compact().freight_bytes(clone, [])
        before = _worktree_bytes(clone)

        gitutil.narrow(clone)

        assert before - _worktree_bytes(clone) == predicted
        # sub/.boost, notes.md.bak and sk/a.cursorrules always go; README.MD
        # goes only where the clone matches case-sensitively (Linux), and
        # parity holds either way. docs.md/ and .clinerules/ stay whole.
        assert predicted == 13 + 29 + 37 + (
            0 if _compact().folds_case(clone) else 23)
        assert (clone / "docs.md" / "run.py").is_file()
        assert (clone / ".clinerules" / "state" / "x.json").is_file()

    @pytest.mark.parametrize("ignorecase", ["true", "false"])
    def test_parity_holds_whichever_way_the_clone_matches_case(
            self, tmp_path, ignorecase):
        """Both settings on one machine: flip the clone's `core.ignorecase`
        and git and the prediction must move together."""
        src = tmp_path / "src"
        (src / "skills" / "a").mkdir(parents=True)
        (src / "skills" / "a" / "SKILL.md").write_text("x" * 31, encoding="utf-8")
        (src / "README.MD").write_text("x" * 23, encoding="utf-8")
        _git(src, "init", "-q", "-b", "main")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "case")
        clone = _fat_clone(src, tmp_path / "c")
        _git(clone, "config", "core.ignorecase", ignorecase)
        predicted = _compact().freight_bytes(clone, [])
        before = _worktree_bytes(clone)

        gitutil.narrow(clone)

        assert before - _worktree_bytes(clone) == predicted
        assert predicted == (0 if ignorecase == "true" else 23)

    @pytest.mark.parametrize("keep", ["skills/demo", "skills/demo/", "/skills/demo"])
    def test_a_kept_source_dir_is_not_promised(self, tmp_path, keep):
        """An installed skill's assets are re-materialized, so never freed —
        however the lock spelled its `source_dir`."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        assert _compact().freight_bytes(clone, [keep]) == TRACKED_VENDOR

    def test_a_kept_prefix_is_a_directory_not_a_string_prefix(self, tmp_path):
        """`skills/dem` must not keep `skills/demo/…`: the prefix ends in `/`."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        assert _compact().freight_bytes(clone, ["skills/dem"]) == (
            TRACKED_ASSET + TRACKED_VENDOR)

    def test_a_tracked_symlink_counts_as_a_link_not_its_target(self, tmp_path):
        """`stat` follows a link, so a tracked `scripts/vendor -> ../node_modules/
        pkg.js` would count the 50 KB file twice — once for each path to it."""
        src = _repo(tmp_path / "src")
        (src / "scripts").mkdir()
        (src / "scripts" / "vendor.js").symlink_to("../node_modules/pkg.js")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "link")
        clone = _fat_clone(src, tmp_path / "c")
        assert (clone / "scripts" / "vendor.js").is_symlink()

        assert _compact().freight_bytes(clone, []) == (
            TRACKED_ASSET + TRACKED_VENDOR)

    def test_a_directory_git_cannot_read_is_not_guessed_at(self, tmp_path):
        """No index, no prediction — the real run fails here too."""
        plain = tmp_path / "plain"
        (plain / "skills").mkdir(parents=True)
        (plain / "skills" / "x.bin").write_text("z" * 100, encoding="utf-8")

        with pytest.raises(BoostError):
            _compact().freight_bytes(plain, [])

    @pytest.mark.parametrize(("rel", "kept"), [
        ("skills/demo/SKILL.md", True),       # *.md at any depth
        ("README.MD", False),                 # git's default: case matters
        ("rules/house.mdc", True),            # *.mdc
        (".cursorrules", True),               # an exact rule filename
        ("sub/.windsurfrules", True),         # … at any depth
        (".boost/manifest.json", True),       # /.boost/* — root-anchored
        ("sub/.boost/manifest.json", False),  # … and only at the root
        ("scripts/run.py", False),
        ("cursorrules", False),               # a name, not a suffix
        ("sk/a.cursorrules", False),          # … in either direction
        ("notes.md.bak", False),
        # gitignore syntax: a pattern names a directory as readily as a file,
        # and git keeps everything under a directory that matches.
        ("docs.md/run.py", True),             # *.md on a directory
        ("a/b.mdc/c.txt", True),              # *.mdc on a nested directory
        (".clinerules/state/x.json", True),   # a rule name on a directory
        ("sub/.windsurfrules/y.txt", True),   # … at any depth
        ("notes.md.bak/q.txt", False),        # the suffix still has to end it
        (".boost", False),                    # /.boost/* wants a child
        (".boost/sub/deep.json", True),       # … at any depth below the root
    ])
    def test_the_cone_is_the_one_git_applies(self, rel, kept):
        assert _compact().in_cone(rel) is kept

    @pytest.mark.parametrize(("rel", "kept"), [
        ("README.MD", True), ("Rules/House.MDC", True),
        (".CursorRules", True), (".BOOST/x.json", True), ("run.PY", False),
        ("Docs.MD/run.py", True), (".CLINERULES/s.json", True)])
    def test_a_case_folding_clone_folds_the_cone_too(self, rel, kept):
        assert _compact().in_cone(rel, ignorecase=True) is kept

    @pytest.mark.parametrize("ignorecase", ["true", "false"])
    @pytest.mark.parametrize("layout", [
        # The verifier's repro: a real registry's cline state directory.
        [".clinerules/intelligence/state/a.json",
         ".clinerules/intelligence/state/b.json",
         ".clinerules/rules.md", "skills/x/SKILL.md", "run.py"],
        ["docs.md/run.py", "docs.md/deep/er/x.bin", "a/b.mdc/c.txt",
         "sub/.cursorrules/x.json", ".windsurfrules/y.txt",
         "sk/a.cursorrules", "x.cursorrulesz", "cursorrules/z.txt",
         "notes.md.bak/q.txt", "md/r.txt", ".md", "dir/.mdc"],
        [".boost/manifest.json", ".boost/sub/deep.json", "sub/.boost/x.json",
         "sub/.boost/y/z.json", ".boostx/a.json", "x/.boost"],
        [".boost", "keep.md"],
        ["README.MD", "Docs.MD/run.py", ".CLINERULES/s.json",
         ".BOOST/x.json", "run.PY"],
    ], ids=["cline-state", "directory-names", "boost-anchor", "boost-file",
            "case"])
    def test_every_path_is_judged_the_way_git_judges_it(
            self, tmp_path, layout, ignorecase):
        """Path by path, not only in total: a matcher that kept one file too
        many and dropped another of the same size would pass a byte count."""
        src = tmp_path / "src"
        for n, rel in enumerate(layout, start=1):
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text("x" * n, encoding="utf-8")
        _git(src, "init", "-q", "-b", "main")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "layout")
        clone = _fat_clone(src, tmp_path / "c")
        _git(clone, "config", "core.ignorecase", ignorecase)
        fold = _compact().folds_case(clone)
        predicted = {rel: _compact().in_cone(rel, fold) for rel in layout}
        freight = _compact().freight_bytes(clone, [])
        before = _worktree_bytes(clone)

        gitutil.narrow(clone)

        assert {rel: (clone / rel).is_file() for rel in layout} == predicted
        assert before - _worktree_bytes(clone) == freight

    def test_case_folding_is_read_from_the_clone(self, tmp_path):
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")
        _git(clone, "config", "core.ignorecase", "true")
        assert _compact().folds_case(clone) is True
        _git(clone, "config", "core.ignorecase", "false")
        assert _compact().folds_case(clone) is False
        _git(clone, "config", "--unset", "core.ignorecase")
        assert _compact().folds_case(clone) is False

    def test_the_cli_no_longer_promises_the_untracked_megabyte(
            self, boost, tapped):
        clone = paths.repos_dir() / "fixture-tap"
        _plant_junk(clone)

        r = boost("compact", "fixture-tap", "--dry-run", "--json")

        assert json.loads(r.out)["bytes"] == 0

    def test_a_clone_git_cannot_read_fails_the_preview_like_the_run(
            self, boost, tapped):
        """The preview reads the index, so a clone git cannot open is an error
        row and exit 1 in both — not "0B would be freed" over a clone the live
        run then fails on."""
        clone = paths.repos_dir() / "fixture-tap"
        util.rmtree(clone / ".git")   # git objects are read-only on Windows
        # A gitfile to nowhere: fatal to git, and it never searches upward
        # into whatever repository the test's temp dir happens to sit in.
        (clone / ".git").write_text("gitdir: %s\n" % (clone.parent / "gone"),
                                    encoding="utf-8")

        preview = boost("compact", "fixture-tap", "--dry-run", "--json", expect=1)
        applied = boost("compact", "fixture-tap", "--json", expect=1)

        for r in (preview, applied):
            [row] = json.loads(r.out)["taps"]
            assert set(row) == {"tap", "error"}, row

    def test_the_cli_preview_is_the_figure_the_live_run_reports(
            self, boost, sandbox, tmp_path):
        """End to end, on a pre-sparse clone carrying tracked *and* untracked
        freight: the dry run's total is the live run's total."""
        boost("tap", _repo(tmp_path / "src"))
        clone = registry.list_taps()[0].path
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])
        _plant_junk(clone)

        predicted = json.loads(boost("compact", "--dry-run", "--json").out)
        freed = json.loads(boost("compact", "--json").out)

        assert predicted["bytes"] == TRACKED_ASSET + TRACKED_VENDOR
        # The live figure is `dir_size` before/after over the whole clone, so
        # it also carries git's own bookkeeping under `.git` (the sparse
        # config and index it rewrites) — bytes, where the defect was the
        # untracked megabyte.
        assert abs(freed["bytes"] - predicted["bytes"]) < 4096
        assert (clone / "scripts" / "junk.bin").exists()


    @pytest.mark.skipif(sys.platform == "win32",
                        reason="git checks symlinks out as plain files on "
                               "Windows by default")
    def test_symlinked_files_do_not_inflate_the_live_figure(
            self, boost, sandbox, tmp_path):
        """A tracked link counted its target's size before and 0 after, so
        the live run over-reported what it freed. One link points off-cone
        and one in-cone link dangles once its target goes. The preview
        skipped both, and it was the true figure."""
        src = _repo(tmp_path / "src")
        (src / "scripts").mkdir()
        (src / "scripts" / "big.txt").write_text("z" * 40_000, encoding="utf-8")
        (src / "scripts" / "vendor.js").symlink_to("../node_modules/pkg.js")
        (src / "skills" / "GUIDE.md").symlink_to("../scripts/big.txt")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", "links")
        boost("tap", str(src))
        clone = registry.list_taps()[0].path
        gitutil.run(["-C", str(clone), "sparse-checkout", "disable"])

        predicted = json.loads(boost("compact", "--dry-run", "--json").out)
        freed = json.loads(boost("compact", "--json").out)

        assert predicted["bytes"] == TRACKED_ASSET + TRACKED_VENDOR + 40_000
        assert abs(freed["bytes"] - predicted["bytes"]) < 4096


# ── 2. `--reclone` predicts a different thing, and declines a net total ──

class TestReclonePredictsTheRecloneItWillDo:
    def test_reclone_counts_the_untracked_bytes_a_plain_run_leaves(self, tmp_path):
        """`--reclone` is `rmtree` + fresh clone, so untracked freight does go."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")
        _plant_junk(clone)

        plan = _compact().plan(clone, [], reclone=True)

        assert plan.freight == TRACKED_ASSET + TRACKED_VENDOR + UNTRACKED_JUNK

    def test_a_plain_plan_does_not_touch_the_git_dir(self, tmp_path):
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        assert _compact().plan(clone, [], reclone=False).git_bytes == 0

    def test_reclone_accounts_for_the_whole_git_dir(self, tmp_path):
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        plan = _compact().plan(clone, [], reclone=True)

        assert plan.git_bytes == util.dir_size(clone / ".git")
        assert plan.git_bytes > 0
        assert plan.removes == plan.freight + plan.git_bytes

    def test_reclone_refuses_to_predict_a_net_total(self, tmp_path):
        """The re-download's size is the remote's answer, not ours."""
        clone = _fat_clone(_repo(tmp_path / "src"), tmp_path / "c")

        assert _compact().plan(clone, [], reclone=False).net == (
            TRACKED_ASSET + TRACKED_VENDOR)
        assert _compact().plan(clone, [], reclone=True).net is None

    def test_the_cli_says_something_different_with_reclone(self, boost, tapped):
        plain = boost("compact", "fixture-tap", "--dry-run").out
        recl = boost("compact", "fixture-tap", "--dry-run", "--reclone").out

        assert plain != recl
        assert "re-clone" in recl
        assert "would be freed" not in recl

    def test_reclone_reports_a_tap_that_has_no_freight_at_all(self, boost, tapped):
        """The live `--reclone` counts every tap as changed; so must the preview."""
        plain = boost("compact", "fixture-tap", "--dry-run").out
        recl = boost("compact", "fixture-tap", "--dry-run", "--reclone").out

        assert "fixture-tap" not in plain     # sparse already: nothing to free
        assert "fixture-tap" in recl

    def test_the_json_row_declines_an_after_it_cannot_know(self, boost, tapped):
        clone = paths.repos_dir() / "fixture-tap"
        _plant_junk(clone)

        r = boost("compact", "fixture-tap", "--dry-run", "--reclone", "--json")

        doc = json.loads(r.out)
        row = doc["taps"][0]
        assert row["reclone"] is True
        assert row["after"] is None
        assert row["bytes"] == UNTRACKED_JUNK
        assert row["git_bytes"] == util.dir_size(clone / ".git")
        assert doc["removes"] == UNTRACKED_JUNK + row["git_bytes"]


# ── 3. heal previews the branch `sync_apply` will take ───────────────────

def _heal_both(boost):
    """`heal --dry-run`, then `heal`, over one state: (preview, applied)."""
    return boost("heal", "--dry-run").out, boost("heal").out


def _local_skill(tmp_path, name="local-skill"):
    src = tmp_path / name
    src.mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nBody v1\n" % name,
        encoding="utf-8")
    return src


class TestHealPreviewsTheBranchItWillTake:
    def test_a_tap_reinstall_is_previewed_as_one(self, boost, installed):
        shutil.rmtree(paths.store_dir() / "brainstorming")

        preview, applied = _heal_both(boost)

        assert "would reinstall brainstorming from fixture-tap" in preview
        assert "or drop it from the lock" not in preview
        assert "reinstalled missing brainstorming from fixture-tap" in applied

    def test_a_source_that_is_gone_is_previewed_as_the_drop(self, boost,
                                                            installed):
        boost("untap", "fixture-tap")
        shutil.rmtree(paths.store_dir() / "brainstorming")

        preview, applied = _heal_both(boost)

        assert "would drop brainstorming from the lock" in preview
        assert "would reinstall" not in preview
        assert "dropped brainstorming from lock" in applied

    def test_a_local_source_is_previewed_by_its_path(self, boost, sandbox,
                                                     tmp_path):
        src = _local_skill(tmp_path)
        store.install_from_path(src)
        shutil.rmtree(paths.store_dir() / "local-skill")

        preview, applied = _heal_both(boost)

        assert "would reinstall local-skill from local source %s" % src in preview
        assert "reinstalled missing local-skill from local source %s" % src \
            in applied

    def test_a_local_source_without_its_skill_md_is_previewed_as_the_drop(
            self, boost, sandbox, tmp_path):
        """The directory is still there, but install_from_path needs its
        SKILL.md, so the run drops the entry — and the preview must say so
        rather than promise a reinstall from a path that cannot supply one."""
        src = _local_skill(tmp_path)
        store.install_from_path(src)
        shutil.rmtree(paths.store_dir() / "local-skill")
        (src / "SKILL.md").unlink()
        assert src.is_dir()

        preview, applied = _heal_both(boost)

        assert "would drop local-skill from the lock" in preview
        assert "would reinstall" not in preview
        assert "dropped local-skill from lock" in applied
        assert lockfile.get_skill("local-skill") is None

    def test_a_pin_that_blocks_the_repair_is_previewed_as_declined(
            self, boost, sandbox, tmp_path):
        src = _local_skill(tmp_path)
        store.install_from_path(src)
        entry = lockfile.get_skill("local-skill")
        entry["pinned"] = True
        lockfile.set_skill("local-skill", entry)
        shutil.rmtree(paths.store_dir() / "local-skill")
        (src / "SKILL.md").write_text(
            "---\nname: local-skill\nversion: 2.0.0\n---\n\nBody v2\n",
            encoding="utf-8")

        preview, applied = _heal_both(boost)

        declined = "local-skill is pinned and its local source has moved"
        assert declined in preview
        assert "would reinstall" not in preview
        assert "would drop" not in preview
        assert declined in applied

    def test_a_missing_rule_file_is_previewed(self, boost, fixture_tap_src,
                                              tmp_path):
        """The dry run used to skip rule/workflow repairs entirely — and with
        nothing else to do, answer "nothing to heal" above a run that
        re-materializes."""
        tap_dir = tmp_path / "rule-tap"
        shutil.copytree(fixture_tap_src, tap_dir)
        (tap_dir / "rules").mkdir()
        (tap_dir / "rules" / "team.mdc").write_text(
            "---\nname: team-rules\n---\n\nAlways TDD.\n", encoding="utf-8")
        _git(tap_dir, "add", "-A")
        _git(tap_dir, "commit", "-qm", "add rule")
        boost("tap", tap_dir)
        boost("install", "team-rules")
        (paths.home() / ".cursor" / "rules" / "team-rules.mdc").unlink()

        preview, applied = _heal_both(boost)

        assert "would re-materialize rule team-rules from rule-tap" in preview
        assert "nothing to heal" not in preview
        assert "re-materialized rule team-rules from rule-tap" in applied

    def test_a_corrupt_lock_previews_no_re_record(self, boost, installed):
        """`sync_apply` re-records only over a *missing* lock; a corrupt one is
        `boost replay`'s job, so promising the re-record was a promise the
        run never keeps."""
        paths.lockfile_path().write_text("{oops", encoding="utf-8")

        preview, applied = _heal_both(boost)

        assert "re-record" not in preview
        assert "re-record" not in applied

    def test_a_store_dir_with_nothing_to_record_is_previewed_as_left(
            self, boost, installed):
        paths.lockfile_path().unlink()
        (paths.store_dir() / "husk").mkdir()

        preview, applied = _heal_both(boost)

        assert "would re-record brainstorming" in preview
        assert "would leave husk unrecorded (no SKILL.md to record)" in preview
        assert "would re-record husk" not in preview
        assert "left husk unrecorded (no SKILL.md to record)" in applied

    def test_the_preview_and_the_repair_share_one_decision(self, boost,
                                                           installed):
        shutil.rmtree(paths.store_dir() / "brainstorming")
        plan = store.sync_plan()

        predicted = store.sync_preview(plan)
        applied = store.sync_apply(plan)

        assert predicted == ["would reinstall brainstorming from fixture-tap"]
        assert "reinstalled missing brainstorming from fixture-tap" in applied

    def test_a_catalog_that_cannot_answer_is_a_drop_in_both(
            self, boost, installed, monkeypatch):
        from boost_cli.core import catalog
        shutil.rmtree(paths.store_dir() / "brainstorming")

        def refuse(*_a, **_k):
            raise BoostError("catalog unreadable")
        monkeypatch.setattr(catalog, "find", refuse)
        plan = store.sync_plan()

        assert store.sync_preview(plan) == [
            "would drop brainstorming from the lock (store dir missing, "
            "source gone)"]
        assert ("dropped brainstorming from lock (store dir missing, source "
                "gone)") in store.sync_apply(plan)

    def test_an_unreadable_pinned_source_fails_closed_in_both(
            self, boost, sandbox, tmp_path, monkeypatch):
        """A pin whose source cannot be hashed is declined, never guessed at."""
        src = _local_skill(tmp_path)
        store.install_from_path(src)
        entry = lockfile.get_skill("local-skill")
        entry["pinned"] = True
        lockfile.set_skill("local-skill", entry)
        shutil.rmtree(paths.store_dir() / "local-skill")

        def unreadable(_p):
            raise OSError("permission denied")
        monkeypatch.setattr(util, "sha256_dir", unreadable)
        plan = store.sync_plan()

        declined = "local-skill is pinned and its local source has moved"
        assert any(declined in ln for ln in store.sync_preview(plan))
        assert any(declined in ln for ln in store.sync_apply(plan))
        assert lockfile.get_skill("local-skill") is not None

    def test_the_preview_never_widens_a_sparse_cone(self, boost, installed,
                                                    monkeypatch):
        """A pin check hashes the tap source, and that materializes. In a dry
        run that is a `sparse-checkout add` — a write, sometimes a fetch — so
        the sha may only be computed for an entry a pin can actually block."""
        shutil.rmtree(paths.store_dir() / "brainstorming")
        widened: list = []
        real = gitutil.materialize
        monkeypatch.setattr(gitutil, "materialize",
                            lambda *a, **k: (widened.append(a), real(*a, **k))[1])

        store.sync_preview(store.sync_plan())

        assert widened == []


RULE = "---\nname: Team Conventions\n---\n\nAlways write tests first.\n"


@pytest.fixture()
def rule_tap(sandbox, fixture_tap_src, tmp_path):
    """The fixture tap plus one rule, with the rule's catalog entry."""
    from boost_cli.core import catalog
    tap_dir = tmp_path / "rule-tap"
    shutil.copytree(fixture_tap_src, tap_dir)
    (tap_dir / "rules").mkdir()
    (tap_dir / "rules" / "team.mdc").write_text(RULE, encoding="utf-8")
    _git(tap_dir, "add", "-A")
    _git(tap_dir, "commit", "-qm", "add rule")
    tap = registry.add(str(tap_dir))
    catalog.rebuild_tap(tap)
    [entry] = [e for e in catalog.find("team-conventions") if e["kind"] == "rule"]
    return tap, entry


class TestMaterializationRepairsAgree:
    """The rule/workflow half of `sync_apply`, read through the same planner."""

    def _both(self):
        plan = store.sync_plan()
        return store.sync_preview(plan), store.sync_apply(plan)

    def test_a_project_rule_repairs_into_its_own_repo(self, rule_tap, tmp_path):
        """The plan carries the lock's scope and base; dropping them turned a
        project rule's repair into a refused user-scope install."""
        _tap, entry = rule_tap
        repo = tmp_path / "repo"
        repo.mkdir()
        store.install(entry, scope="project", base=str(repo))
        mdc = repo / ".cursor" / "rules" / "team-conventions.mdc"
        mdc.unlink()

        preview, applied = self._both()

        assert preview == ["would re-materialize rule team-conventions from "
                           "rule-tap"]
        assert "re-materialized rule team-conventions from rule-tap" in applied
        assert mdc.is_file()
        assert not (paths.home() / ".cursor" / "rules"
                    / "team-conventions.mdc").exists()

    def test_a_fallback_warning_is_previewed_too(self, rule_tap):
        from boost_cli.core import catalog
        tap, entry = rule_tap
        store.install(entry)
        (tap.path / "rules" / "mirror.mdc").write_text(RULE, encoding="utf-8")
        (tap.path / "rules" / "team.mdc").unlink()
        catalog.rebuild_tap(tap)
        (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").unlink()

        preview, applied = self._both()

        warned = [ln for ln in preview if "no longer at its installed source" in ln]
        assert warned, preview
        assert warned[0] in applied

    def test_a_skill_of_the_same_name_is_not_a_rule_source(self, rule_tap):
        """Matches are filtered by kind: with the rule's file gone, a skill
        called `team-conventions` must not be installed as its repair."""
        from boost_cli.core import catalog
        tap, entry = rule_tap
        store.install(entry)
        (tap.path / "rules" / "team.mdc").unlink()
        skill = tap.path / "skills" / "team-conventions"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: team-conventions\ndescription: d\n---\n\nBody.\n",
            encoding="utf-8")
        catalog.rebuild_tap(tap)
        (paths.home() / ".cursor" / "rules" / "team-conventions.mdc").unlink()

        preview, applied = self._both()

        gone = ("rule team-conventions has a missing materialization but its "
                "source is gone — run `boost update` or reinstall")
        assert preview == [gone]
        assert gone in applied
        assert not (paths.store_dir() / "team-conventions").exists()


class TestHealNamesTheDirectoriesItCreates:
    def _named(self, out):
        return {ln.split("would create directory ", 1)[1].strip()
                for ln in out.splitlines() if "would create directory " in ln}

    def test_missing_directories_are_named(self, boost, sandbox):
        r = boost("heal", "--dry-run")

        assert "~/.agents/skills" in self._named(r.out)
        assert "missing directories" not in r.out

    def test_the_named_set_is_exactly_what_heal_creates(self, boost, sandbox):
        wanted = [*paths.boost_dirs(), *agents.linking_agents().values()]

        named = self._named(boost("heal", "--dry-run").out)
        # Read after the preview, not before: invoking boost at all creates
        # ~/.boost/logs, so those two exist by the time heal looks.
        absent = {paths.tilde(d) for d in wanted if not d.is_dir()}
        assert absent, "a fresh HOME must have directories to create"
        boost("heal")

        assert named == absent
        assert all(d.is_dir() for d in wanted)

    def test_heal_makes_no_skills_dir_nothing_links_into(self, boost,
                                                          sandbox):
        # Pinned on agents.ensure_agent_dirs until heal, its last caller, took
        # over: an empty ~/.gemini/skills (a native-store agent) or a disabled
        # agent's dir is one heal would later report as missing.
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        boost("heal")
        assert (sandbox / ".claude" / "skills").is_dir()
        assert not (sandbox / ".gemini" / "skills").exists()
        assert not (sandbox / ".cursor" / "skills").exists()

    def test_ensure_dirs_creates_every_boost_dir(self, sandbox):
        paths.ensure_dirs()

        assert all(d.is_dir() for d in paths.boost_dirs())
        assert paths.store_dir() in paths.boost_dirs()


# ── 4. onboard's preview marks what it hides, and checks --pr first ──────

class TestOnboardPreviewIsHonest:
    def test_head_lines_marks_nothing_when_nothing_is_hidden(self):
        text = "\n".join("l%d" % i for i in range(24))

        lines, more = util.head_lines(text, 24)

        assert lines == text.splitlines()
        assert more == 0

    def test_head_lines_counts_exactly_what_it_cut(self):
        text = "\n".join("l%d" % i for i in range(30))

        lines, more = util.head_lines(text, 24)

        assert lines == ["l%d" % i for i in range(24)]
        assert more == 6

    def test_head_lines_on_an_empty_body(self):
        assert util.head_lines("", 24) == ([], 0)

    def test_the_lock_preview_says_how_many_lines_it_hid(self, boost, installed,
                                                         tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        lock_lines = len(json.dumps(lockfile.portable(lockfile.read()),
                                    indent=2, sort_keys=True).splitlines())
        assert lock_lines > 24, "the fixture lock must be long enough to cut"

        r = boost("onboard", "--repo", repo, "--dry-run")

        assert "… %d more lines" % (lock_lines - 24) in r.out

    def test_dry_run_pr_outside_a_git_repo_fails_the_precondition(
            self, boost, sandbox, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()

        r = boost("onboard", "--repo", plain, "--dry-run", "--pr", expect=1)

        assert "is not a git repository" in r.err
        assert not (plain / ".boost").exists()

    def test_dry_run_pr_in_a_clean_repo_prints_the_plan(self, boost, sandbox,
                                                        tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "README.md").write_text("hi\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)

        r = boost("onboard", "--repo", repo, "--dry-run", "--pr")

        assert "boost/onboard-skill-tracker" in r.out
        assert "gh pr create" in r.out
        assert not (repo / ".boost").exists()   # still a dry run

    def test_dry_run_pr_still_refuses_a_dirty_tree(self, boost, sandbox,
                                                   tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "README.md").write_text("hi\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")
        (repo / "untracked.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)

        r = boost("onboard", "--repo", repo, "--dry-run", "--pr", expect=1)

        assert "is not clean" in r.err

    def test_an_onboarded_repo_previews_the_no_op_the_run_takes(
            self, boost, installed, tmp_path, monkeypatch):
        """Byte-identical files are skipped by the real run, which then opens
        no PR; the preview must not promise a commit it will not make."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "README.md").write_text("hi\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")
        boost("onboard", "--repo", repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "onboard")
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: "/usr/bin/" + c)

        preview = boost("onboard", "--repo", repo, "--dry-run", "--pr").out
        applied = boost("onboard", "--repo", repo).out

        assert "would overwrite" not in preview
        assert "gh pr create" not in preview
        assert "already onboarded" in preview
        assert "already onboarded" in applied

    def test_dry_run_pr_without_gh_fails_the_precondition(
            self, boost, sandbox, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "README.md").write_text("hi\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")
        real = shutil.which
        monkeypatch.setattr("boost_cli.commands.configuration.shutil.which",
                            lambda c: None if c == "gh" else real(c))

        r = boost("onboard", "--repo", repo, "--dry-run", "--pr", expect=1)

        assert "`gh` CLI is required" in r.err


WORKFLOW = ("---\nname: ship-it\ndescription: release helper\n"
            "allowed-tools: Bash\n---\n\nRun the release.\n")


@pytest.fixture()
def kind_tap(sandbox, fixture_tap_src, tmp_path):
    """The fixture tap plus one rule and one workflow, with their entries."""
    from boost_cli.core import catalog
    tap_dir = tmp_path / "kind-tap"
    shutil.copytree(fixture_tap_src, tap_dir)
    (tap_dir / "rules").mkdir()
    (tap_dir / "rules" / "team.mdc").write_text(RULE, encoding="utf-8")
    (tap_dir / "commands").mkdir()
    (tap_dir / "commands" / "ship-it.md").write_text(WORKFLOW, encoding="utf-8")
    _git(tap_dir, "add", "-A")
    _git(tap_dir, "commit", "-qm", "add rule and workflow")
    tap = registry.add(str(tap_dir))
    catalog.rebuild_tap(tap)
    return tap


class TestAnEmptyTargetSetRefusesInBothModes:
    """A preview that exits 0 where the run exits 1 is the worst kind.

    Both cases below reach an agent set that is empty for the *kind* being
    installed, and the preview reported them as a benign fact and stopped:
    ``materialize → (no enabled agents)`` about an agent that is enabled, and —
    for a project skill — the "would install … into <repo>" header with no
    ``copy →`` line under it. The live run raises in both. They diverged
    because the preview reimplemented the narrowing as a list comprehension
    instead of calling the one the install calls; it now calls
    `store.narrow_materializing` / `store.narrow_project_agents`, so the two
    cannot drift apart again without a type error.

    Asserted as *parity*, not as a fixed string: the preview and the run are
    driven over the same state and their exit code and message compared.
    """

    def _both(self, boost, *argv):
        live = boost(*argv, expect=None)
        dry = boost(*argv, "--dry-run", expect=None)
        return dry, live

    def test_a_workflow_narrowed_to_an_agent_with_no_command_format(
            self, boost, kind_tap):
        """Codex is enabled and takes rules; it has no slash-command format,
        so `workflow_agents` excludes it and the narrowing is empty."""
        dry, live = self._both(boost, "install", "ship-it", "--agent", "codex")

        assert live.rc == 1 and dry.rc == 1
        assert "no agent left to install workflow ship-it into" in live.err
        assert dry.err == live.err
        # A guard, not the discriminator: the old `only_agents and not
        # kept` already refused a *narrowed* empty set, so the live run
        # wrote no row before this change either. `dry.rc == 1` is what
        # fails against the old preview.
        assert lockfile.get_workflow("ship-it") is None

    def test_a_project_skill_narrowed_to_an_agent_with_no_project_path(
            self, boost, kind_tap, tmp_path, monkeypatch):
        """Antigravity is enabled but `project_scope: False` — its user layout
        is two levels under ~/.gemini and it has no repo-local path."""
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        monkeypatch.chdir(repo)

        dry, live = self._both(boost, "install", "brainstorming", "--local",
                               "--agent", "antigravity")

        assert live.rc == 1 and dry.rc == 1
        assert "no agent left to install brainstorming into" in live.err
        assert dry.err == live.err
        assert not (repo / ".boost").exists()

    def test_a_rule_with_every_materializing_agent_disabled(self, boost, kind_tap):
        """The un-narrowed road to the same empty set: no `--agent` at all,
        just a config in which nothing can take a rule. The guard used to be
        `only_agents and not kept`, so this one wrote `materializations: []`
        and exited 0 — invisible to `sync_plan`, which asks `any([])`."""
        cfg = config.load()
        for name in cfg["agents"]:
            cfg["agents"][name]["enabled"] = False
        config.save(cfg)

        dry, live = self._both(boost, "install", "team-conventions")

        assert live.rc == 1 and dry.rc == 1
        assert "no enabled agent takes a rule" in live.err
        assert dry.err == live.err
        assert lockfile.get_rule("team-conventions") is None


class TestNativeStoreAccessIsPreviewedLikeItIsReported:
    """`--agent` scopes *links*, not store access — and the preview said
    otherwise.

    `store.link_agents` deliberately leaves `res.native` unfiltered, with a
    comment saying a filter there would be a lie: the canonical store is
    written by every install however narrow the scope, so the skill really is
    visible to a native-store agent either way. The preview filtered it, and
    dropped the "available to … (reads the store directly)" line that the run
    then prints — under-reporting exactly the agents Codex just doubled.
    """

    def test_a_narrowed_install_previews_the_native_line_it_prints(
            self, boost, tapped):
        dry = boost("install", "brainstorming", "--agent", "cursor", "--dry-run")
        live = boost("install", "brainstorming", "--agent", "cursor")

        native = list(agents.native_store_agents())
        assert native, "fixture config has no native-store agent to test with"
        for a in native:
            label = agents.display_name(a)
            assert label in dry.out, "preview omits %s" % label
            assert label in live.out


class TestOneRefusedEntryDoesNotSilenceTheRestOfThePreview:
    """The preview loop had no per-entry `BoostError` handler, and this branch
    is what first gave it something to raise.

    The live loop catches a refusal, warns, counts it and carries on whenever
    the request names more than one item — so `install a b` installs `a`.
    Routing the preview through the same narrowing made it raise out of the
    whole command instead: no plan for anything after the refused name, and
    not even the "dry run — nothing was changed" line that tells the user the
    exit code was a preview's. The parity fix created the divergence, so the
    fix has to carry its own regression test.
    """

    def test_a_refused_second_entry_leaves_the_first_ones_plan_printed(
            self, boost, kind_tap):
        dry = boost("install", "brainstorming", "ship-it", "--agent", "codex",
                    "--dry-run", expect=None)
        live = boost("install", "brainstorming", "ship-it", "--agent", "codex",
                     expect=None)

        assert dry.rc == 1 and live.rc == 1
        # The entry that survives the narrowing is still planned — the plan
        # line itself, not just the name, which a warning would also carry.
        assert "would install brainstorming" in dry.out
        # …the one that does not is a warning, not an abort. `out.warn`
        # writes to stdout, which is also where the live run's
        # per-entry warning lands, so the two are compared there.
        msg = "no agent left to install workflow ship-it into"
        assert msg in dry.out
        assert msg in live.out
        # …and the marker that makes the exit code readable is still printed.
        assert "dry run — nothing was changed" in dry.out
        assert lockfile.get_workflow("ship-it") is None


class TestAReinstallPreviewsTheLinkScopeItWillReplay:
    """`store.install` replays the lock's recorded agent scope through
    `preserved_agent_scope` before linking; the preview filtered
    `linking_agents()` by the *typed* `--agent` alone, once, outside the entry
    loop. So after a narrowed install, `--force --dry-run` promised a link into
    every agent and the run relinked the recorded one — the same defect the
    rule and workflow branches had, left open on the commonest shape.
    """

    def test_a_forced_reinstall_previews_only_the_recorded_agents(
            self, boost, tapped):
        boost("install", "brainstorming", "--agent", "cursor")
        others = [a for a in agents.linking_agents() if a != "cursor"]
        assert others, "fixture config has only one linking agent"

        dry = boost("install", "brainstorming", "--force", "--dry-run")
        # Both halves, because parity is the property: a preview-only test
        # would still pass the day `store.install` stopped replaying the
        # recorded scope, and it is the run's behaviour that makes the
        # preview's narrow answer the right one.
        live = boost("install", "brainstorming", "--force")

        link_line = [ln for ln in dry.out.splitlines() if "link  →" in ln]
        assert link_line, dry.out
        live_line = [ln for ln in live.out.splitlines() if "linked →" in ln]
        assert live_line, live.out
        assert "cursor" in link_line[0]
        assert "cursor" in live_line[0]
        for a in others:
            assert a not in link_line[0], "preview widens the recorded scope"
            assert a not in live_line[0], "run widens the recorded scope"
