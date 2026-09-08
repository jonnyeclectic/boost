# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the sharded mutation gate (scripts/mutation_shards.py).

Two properties matter and both are load-bearing for CI correctness:

1. Sharding is *lossless*: splitting the mutant set across N shards and merging
   the results reproduces exactly what one unsharded run would have produced.
2. Merging *fails closed*: any missing or half-finished shard is an error, never
   a quietly lower score. mutmut records an unrun mutant as ``None`` and
   mutation_gate.py divides by ``total - skipped``, so a partial merge that was
   allowed through would silently depress the score instead of failing.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mutation_shards.py"
_spec = importlib.util.spec_from_file_location("mutation_shards", SCRIPT)
ms = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ms)


# --------------------------------------------------------------------------
# scope: can the mutation score have changed?
# --------------------------------------------------------------------------

@pytest.mark.parametrize("changed", [
    ["docs/roadmap.html"],
    ["docs/roadmap/items/some-card.md", "README.md"],
    [".github/workflows/publish.yml"],
    ["style/boost.css", "docs/index.html"],
])
def test_irrelevant_changes_skip(changed):
    assert ms.is_relevant(changed) is False


@pytest.mark.parametrize("changed", [
    ["boost_cli/core/store.py"],
    # not core, but also_copy ships the whole package and tests import it
    ["boost_cli/commands/install.py"],
    ["boost_cli/cli.py"],
    # a new assertion can kill a survivor without touching any source
    ["tests/unit/test_store.py"],
    ["tests/conftest.py"],
    # mutmut's own configuration
    ["setup.cfg"],
    ["pyproject.toml"],
    # the pinned pytest/mutmut versions define what the score means
    ["requirements/mutation-tools.txt"],
    ["scripts/mutation_gate.py"],
    ["scripts/mutation_shards.py"],
    [".github/workflows/ci.yml"],
    # one relevant path among many irrelevant ones still counts
    ["docs/a.md", "README.md", "boost_cli/core/util.py"],
])
def test_relevant_changes_run(changed):
    assert ms.is_relevant(changed) is True


def test_scope_fails_safe_on_no_information(tmp_path, capsys):
    """No file list means we cannot prove the score is unchanged -> run it."""
    missing = tmp_path / "nope.txt"
    assert ms.cmd_scope(_ns(changed=str(missing))) == 0
    assert capsys.readouterr().out.strip() == "true"

    empty = tmp_path / "empty.txt"
    empty.write_text("")
    assert ms.cmd_scope(_ns(changed=str(empty))) == 0
    assert capsys.readouterr().out.strip() == "true"


def test_scope_blank_lines_are_not_a_change(tmp_path, capsys):
    listing = tmp_path / "changed.txt"
    listing.write_text("docs/a.md\n\n   \nREADME.md\n")
    assert ms.cmd_scope(_ns(changed=str(listing))) == 0
    assert capsys.readouterr().out.strip() == "false"


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------

def _repo(tmp_path, files):
    """A fake checkout: {name: line_count}."""
    core = tmp_path / "boost_cli" / "core"
    core.mkdir(parents=True)
    for name, lines in files.items():
        (core / name).write_text("".join("x = %d\n" % i for i in range(lines)))
    return tmp_path


def test_every_file_lands_in_exactly_one_shard(tmp_path):
    repo = _repo(tmp_path, {"a.py": 100, "b.py": 50, "c.py": 25, "d.py": 10})
    bins = ms.pack(repo, 3)
    placed = [f.name for b in bins for f in b]
    assert sorted(placed) == ["a.py", "b.py", "c.py", "d.py"]
    assert len(placed) == len(set(placed)), "a file was duplicated across shards"


def test_packing_is_deterministic(tmp_path):
    """Every shard runs pack() independently, so they must all agree."""
    repo = _repo(tmp_path, {"a.py": 30, "b.py": 30, "c.py": 30, "d.py": 30})
    first = [[f.name for f in b] for b in ms.pack(repo, 3)]
    for _ in range(5):
        assert [[f.name for f in b] for b in ms.pack(repo, 3)] == first


def test_recorded_weights_beat_line_counts(tmp_path):
    """A small-but-dense file must be packed by its real mutant count."""
    repo = _repo(tmp_path, {"dense.py": 10, "sparse.py": 100})
    (repo / "scripts").mkdir()
    (repo / ms.WEIGHTS).write_text(json.dumps(
        {"mutants_by_file": {"dense.py": 5000, "sparse.py": 10}}))
    bins = ms.pack(repo, 2)
    # dense.py dominates, so it gets a shard to itself
    solo = [b for b in bins if [f.name for f in b] == ["dense.py"]]
    assert solo, "recorded weights were ignored: %s" % [[f.name for f in b] for b in bins]


def test_missing_weight_entries_fall_back_per_file(tmp_path):
    """A partial weights file is still useful; it must not poison the rest."""
    repo = _repo(tmp_path, {"known.py": 5, "unknown.py": 200})
    (repo / "scripts").mkdir()
    (repo / ms.WEIGHTS).write_text(json.dumps({"mutants_by_file": {"known.py": 9000}}))
    weight = ms.weight_fn(repo)
    assert weight(repo, repo / "boost_cli/core/known.py") == 9000     # recorded
    assert weight(repo, repo / "boost_cli/core/unknown.py") == 200    # line fallback


def test_corrupt_weights_file_is_ignored(tmp_path):
    repo = _repo(tmp_path, {"a.py": 10})
    (repo / "scripts").mkdir()
    (repo / ms.WEIGHTS).write_text("{not json")
    assert ms.load_weights(repo) == {}


def test_pattern_matches_real_mutmut_names():
    """mutmut names mutants `<dotted.module>.<mangled>__mutmut_<n>`."""
    repo = Path(__file__).resolve().parents[2]
    pattern = ms.pattern_for(repo, repo / "boost_cli/core/lockfile.py")
    assert pattern == "boost_cli.core.lockfile.*"
    import fnmatch
    assert fnmatch.fnmatch("boost_cli.core.lockfile.x__skeleton__mutmut_1", pattern)
    assert not fnmatch.fnmatch("boost_cli.core.store.x_install__mutmut_1", pattern)


def test_no_pattern_captures_another_files_mutants():
    """A shard must never steal a file it does not own.

    The hazard is a module name that prefixes another (`mcp` vs `mcpdecl`,
    `store` vs `stackprobe`): a pattern of `boost_cli.core.mcp*` would swallow
    mcpdecl's mutants, so mcpdecl would run twice and its owning shard's results
    would be overwritten. The trailing dot in `...mcp.*` is what prevents it, so
    assert that against the real source tree rather than trusting the reading.
    """
    import fnmatch
    repo = Path(__file__).resolve().parents[2]
    files = [f for f in ms.source_files(repo) if not ms.is_init(f)]
    assert len(files) > 1, "expected a populated boost_cli/core"
    patterns = {ms.rel_name(repo, f): ms.pattern_for(repo, f) for f in files}
    for owner, pattern in patterns.items():
        for other in patterns:
            if other == owner:
                continue
            dotted = other[:-3].replace("/", ".")
            foreign = "boost_cli.core.%s.x_fn__mutmut_1" % dotted
            assert not fnmatch.fnmatch(foreign, pattern), (
                "%s would capture %s's mutants" % (pattern, other))


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------

def _shard_artifacts(repo, parent, shards, results, flat=False):
    """Write each shard's .meta exactly as the CI artifact download would."""
    for i, b in enumerate(ms.pack(repo, shards)):
        d = parent / ("mutation-shard-%d" % i)
        d = d if flat else d / "boost_cli" / "core"
        d.mkdir(parents=True, exist_ok=True)
        for f in b:
            (d / (f.name + ".meta")).write_text(json.dumps({
                "exit_code_by_key": results[f.name],
                "type_check_error_by_key": {},
                "durations_by_key": {},
                "estimated_durations_by_key": {},
            }))


def test_sharded_merge_is_lossless(tmp_path, capsys):
    """The whole point: split N ways, merge, get the unsharded result back."""
    files = {"a.py": 100, "b.py": 60, "c.py": 30, "d.py": 20, "e.py": 10}
    repo = _repo(tmp_path, files)
    # a distinct, known result set per file
    results = {
        name: {"boost_cli.core.%s.x__f__mutmut_%d" % (name[:-3], i): (0 if i % 3 else 1)
               for i in range(1, lines // 5 + 2)}
        for name, lines in files.items()
    }
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 3, results)

    out = tmp_path / "merged"
    rc = ms.cmd_merge(_ns(root=str(repo), shards=3, into=str(out),
                          source=str(parent), prefix="mutation-shard-"))
    assert rc == 0, capsys.readouterr().out

    merged = {}
    for meta in (out / "boost_cli" / "core").glob("*.meta"):
        merged[meta.name[: -len(".meta")]] = json.loads(meta.read_text())["exit_code_by_key"]
    assert merged == results, "merge did not reproduce the unsharded results"


def test_merge_accepts_flattened_artifacts(tmp_path):
    """Artifact layout depends on the upload glob; both must work."""
    files = {"a.py": 40, "b.py": 20}
    repo = _repo(tmp_path, files)
    results = {n: {"boost_cli.core.%s.x__f__mutmut_1" % n[:-3]: 0} for n in files}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 2, results, flat=True)
    rc = ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    assert rc == 0


def test_merge_fails_closed_on_a_missing_shard(tmp_path, capsys):
    """A lost artifact must be an error, never a silently lower score."""
    files = {"a.py": 40, "b.py": 20}
    repo = _repo(tmp_path, files)
    results = {n: {"boost_cli.core.%s.x__f__mutmut_1" % n[:-3]: 0} for n in files}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 2, results)
    # simulate shard 1's upload never arriving
    import shutil
    shutil.rmtree(parent / "mutation-shard-1")

    rc = ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    assert rc == 1
    assert "INCOMPLETE" in capsys.readouterr().out


def test_merge_fails_closed_on_unrun_mutants(tmp_path, capsys):
    """A shard that died halfway leaves `None` exit codes — refuse to gate."""
    files = {"a.py": 40, "b.py": 20}
    repo = _repo(tmp_path, files)
    results = {n: {"boost_cli.core.%s.x__f__mutmut_1" % n[:-3]: 0} for n in files}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 2, results)
    for meta in parent.rglob("*.meta"):
        data = json.loads(meta.read_text())
        data["exit_code_by_key"] = dict.fromkeys(data["exit_code_by_key"])
        meta.write_text(json.dumps(data))
        break

    rc = ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    assert rc == 1
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out and "unrun" in out


class _ns:
    """Tiny argparse.Namespace stand-in with the defaults the commands expect."""

    def __init__(self, **kw):
        self.root = kw.pop("root", ".")
        self.changed = kw.pop("changed", "-")
        self.shards = kw.pop("shards", 1)
        self.into = kw.pop("into", "mutants")
        self.source = kw.pop("source", "shard-results")
        self.prefix = kw.pop("prefix", "mutation-shard-")
        self.index = kw.pop("index", None)
        self.explain = kw.pop("explain", False)
        assert not kw, kw


# --------------------------------------------------------------------------
# regressions found by adversarial review of the sharding change
# --------------------------------------------------------------------------

def test_nested_modules_are_sharded(tmp_path):
    """A subpackage must not vanish from the gate.

    mutmut walks source_paths with os.walk, so boost_cli/core/rag/bm25.py is
    mutated. If the planner's glob is non-recursive those mutants are assigned
    to no shard, and — worse than merely unmerged — mutmut's export-cicd-stats
    skips a path with no .meta, dropping it from `total` rather than counting it
    unkilled. The score would then be computed over a subset and the REQUIRED
    check would report PASS. Fail-open, so it gets an explicit test.
    """
    repo = _repo(tmp_path, {"flat.py": 20})
    nested = repo / "boost_cli" / "core" / "rag"
    nested.mkdir()
    (nested / "bm25.py").write_text("x = 1\n" * 30)
    (nested / "__init__.py").write_text("")

    found = {ms.rel_name(repo, f) for f in ms.source_files(repo)}
    assert "rag/bm25.py" in found, "nested module invisible to the planner"

    placed = {ms.rel_name(repo, f) for b in ms.pack(repo, 2) for f in b}
    assert placed == {"flat.py", "rag/bm25.py"}, placed
    assert ms.pattern_for(repo, nested / "bm25.py") == "boost_cli.core.rag.bm25.*"


def test_init_files_get_no_pattern(tmp_path):
    """mutmut rewrites `.__init__.` out of mutant names, so no pattern fits.

    `boost_cli.core.__init__.*` matches nothing; `boost_cli.core.*` would match
    every other module in the package. Excluding them is the only correct
    option — but it is only *safe* while they generate nothing, which is what
    the merge-time check below enforces.
    """
    repo = _repo(tmp_path, {"a.py": 10})
    (repo / "boost_cli" / "core" / "__init__.py").write_text("")
    assert ms.pattern_for(repo, repo / "boost_cli/core/__init__.py") is None
    placed = {f.name for b in ms.pack(repo, 2) for f in b}
    assert "__init__.py" not in placed


def test_merge_rejects_a_file_no_shard_owned(tmp_path, capsys, monkeypatch):
    """The backstop: any file the planner missed must redden the gate."""
    files = {"a.py": 30, "b.py": 20}
    repo = _repo(tmp_path, files)
    results = {n: {"boost_cli.core.%s.x_fn__mutmut_1" % n[:-3]: 0} for n in files}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 2, results)

    # A file appears in the tree that the planner never enumerated.
    (repo / "boost_cli" / "core" / "ghost.py").write_text("x = 1\n")
    monkeypatch.setattr(ms, "pack", lambda root, shards: [
        [repo / "boost_cli/core/a.py"], [repo / "boost_cli/core/b.py"]])

    rc = ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "ghost.py" in out and "assigned to no shard" in out


def test_merge_rejects_init_that_gained_mutants(tmp_path, capsys):
    """If __init__.py ever generates mutants, say so instead of skipping them."""
    files = {"a.py": 30}
    repo = _repo(tmp_path, files)
    (repo / "boost_cli" / "core" / "__init__.py").write_text("x = 1\n")
    results = {"a.py": {"boost_cli.core.a.x_fn__mutmut_1": 0}}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 1, results)
    # mutmut did produce mutants for __init__.py, and they ran nowhere
    init_meta = parent / "mutation-shard-0" / "boost_cli" / "core" / "__init__.py.meta"
    init_meta.write_text(json.dumps({"exit_code_by_key": {"boost_cli.core.x_f__mutmut_1": None}}))

    rc = ms.cmd_merge(_ns(root=str(repo), shards=1, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "__init__.py" in out


def test_same_basename_in_different_packages_stays_distinct(tmp_path):
    """core/util.py and core/rag/util.py must not be conflated by basename."""
    repo = _repo(tmp_path, {"util.py": 40})
    nested = repo / "boost_cli" / "core" / "rag"
    nested.mkdir()
    (nested / "util.py").write_text("x = 1\n" * 10)
    names = {ms.rel_name(repo, f) for b in ms.pack(repo, 2) for f in b}
    assert names == {"util.py", "rag/util.py"}
    pats = {ms.pattern_for(repo, repo / "boost_cli/core/util.py"),
            ms.pattern_for(repo, nested / "util.py")}
    assert pats == {"boost_cli.core.util.*", "boost_cli.core.rag.util.*"}


# --------------------------------------------------------------------------
# cache-key: the hash half of a shard's actions/cache key
# --------------------------------------------------------------------------

def _cache_repo(tmp_path):
    """A fake checkout with one file under every CACHE_KEY_PREFIXES entry,
    plus a core source file and an irrelevant doc, so a single fixture can
    exercise inclusion, exclusion, and irrelevance in one place."""
    (tmp_path / "boost_cli" / "core").mkdir(parents=True)
    (tmp_path / "boost_cli" / "core" / "store.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_store.py").write_text("def test_a(): pass\n")
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "mutation-tools.txt").write_text("mutmut==3.7.0\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "mutation_gate.py").write_text("# gate\n")
    (tmp_path / "scripts" / "mutation_shards.py").write_text("# shards\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (tmp_path / "setup.cfg").write_text("[mutmut]\n")
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text("<html></html>\n")
    return tmp_path


def test_cache_key_paths_covers_every_prefix_and_excludes_core(tmp_path):
    repo = _cache_repo(tmp_path)
    names = {p.relative_to(repo).as_posix() for p in ms.cache_key_paths(repo)}
    assert names == {
        "tests/test_store.py",
        "requirements/mutation-tools.txt",
        "scripts/mutation_gate.py",
        "scripts/mutation_shards.py",
        ".github/workflows/ci.yml",
        "setup.cfg",
        "pyproject.toml",
    }
    assert "boost_cli/core/store.py" not in names
    assert "docs/index.html" not in names


def test_cache_key_paths_skips_missing_files(tmp_path):
    """A fixture repo that only sets up part of the tree still works."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("x = 1\n")
    assert [p.name for p in ms.cache_key_paths(tmp_path)] == ["test_a.py"]


def test_cache_key_hash_is_deterministic(tmp_path):
    repo = _cache_repo(tmp_path)
    first = ms.cache_key_hash(repo)
    for _ in range(3):
        assert ms.cache_key_hash(repo) == first


def test_cache_key_hash_changes_when_a_relevant_file_changes(tmp_path):
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / "tests" / "test_store.py").write_text("def test_a(): assert False\n")
    assert ms.cache_key_hash(repo) != before


def test_cache_key_hash_changes_when_the_gate_scripts_change(tmp_path):
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / "scripts" / "mutation_gate.py").write_text("# gate v2\n")
    assert ms.cache_key_hash(repo) != before


def test_cache_key_hash_changes_when_ci_yml_changes(tmp_path):
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: push\n")
    assert ms.cache_key_hash(repo) != before

def test_cache_key_hash_ignores_core_source_changes(tmp_path):
    """The whole point: mutmut's own per-file hashing already handles
    boost_cli/ reuse, so the cache key must not evict on a core-only edit."""
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / "boost_cli" / "core" / "store.py").write_text("x = 2\n")
    assert ms.cache_key_hash(repo) == before


def test_cache_key_hash_ignores_irrelevant_files(tmp_path):
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / "docs" / "index.html").write_text("<html>changed</html>\n")
    (repo / "README.md").write_text("hello\n")
    assert ms.cache_key_hash(repo) == before


def test_cache_key_hash_changes_on_a_new_relevant_file(tmp_path):
    """Content alone is not enough: adding a file must also change the key,
    or a brand-new test would silently reuse a cache that never ran it."""
    repo = _cache_repo(tmp_path)
    before = ms.cache_key_hash(repo)
    (repo / "tests" / "test_new.py").write_text("def test_b(): pass\n")
    assert ms.cache_key_hash(repo) != before


def test_cache_key_hash_distinguishes_same_bytes_at_different_paths(tmp_path):
    """Renaming a same-content file must change the key: the path is hashed
    in too, not just the concatenated bytes."""
    repo_a = tmp_path / "a"
    (repo_a / "tests").mkdir(parents=True)
    (repo_a / "tests" / "test_one.py").write_text("x = 1\n")
    repo_b = tmp_path / "b"
    (repo_b / "tests").mkdir(parents=True)
    (repo_b / "tests" / "test_two.py").write_text("x = 1\n")
    assert ms.cache_key_hash(repo_a) != ms.cache_key_hash(repo_b)


def test_cache_key_hash_is_a_hex_sha256(tmp_path):
    repo = _cache_repo(tmp_path)
    key = ms.cache_key_hash(repo)
    assert len(key) == 64
    int(key, 16)  # raises ValueError if not valid hex


def test_cmd_cache_key_prints_the_hash(tmp_path, capsys):
    repo = _cache_repo(tmp_path)
    rc = ms.cmd_cache_key(_ns(root=str(repo)))
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == ms.cache_key_hash(repo)


def test_pattern_is_dotted_on_every_platform(monkeypatch):
    """The dotted prefix must not depend on the OS path separator.

    `str(Path("boost_cli/core"))` is "boost_cli\\core" on Windows, so building
    the prefix with str() makes the "/"->"." replacement a no-op there and every
    shard pattern comes out as "boost_cli\\core.<mod>.*", matching no mutant at
    all. Each shard would then run nothing, merge would report every file unrun,
    and the required check would go red on Windows only. Caught by the Windows
    test legs; this asserts it everywhere so the Linux legs cannot stay blind.
    """
    from pathlib import PureWindowsPath
    monkeypatch.setattr(ms, "SOURCE", PureWindowsPath("boost_cli/core"))
    assert ms.SOURCE.as_posix().replace("/", ".") == "boost_cli.core"
    assert "\\" not in ms.SOURCE.as_posix()
