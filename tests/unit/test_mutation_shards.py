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
    # under the gate-script prefix, but a packing hint and not a gate script:
    # it moves which shard runs a mutant, never whether it is killed
    ["scripts/mutation_weights.json"],
    # a non-gate script is no more relevant than before
    ["scripts/build_roadmap.py"],
    # named like a pytest config file, but it is not one
    ["docs/pytest.toml.md"],
    ["docs/notes/.pytest.ini.bak"],
    # the puppeteer harnesses: Node, run by no mutant (a Dependabot npm bump)
    ["tests/visual/package.json", "tests/visual/package-lock.json"],
    ["tests/visual/visual_check.mjs", "docs/index.html"],
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
    ["conftest.py"],
    # pytest reads a pytest.ini before pyproject.toml's ini options, so it
    # changes how every test runs wherever it sits (mutation_diff makes it a
    # full-run trigger; that is only reachable if the change is relevant)
    ["pytest.ini"],
    ["tests/unit/pytest.ini"],
    # ...and so does each of pytest's other config files, outside tests/ too
    [".pytest.ini"],
    ["pytest.toml"],
    [".pytest.toml"],
    ["docs/pytest.toml"],
    # shared test support, a full-run trigger in mutation_diff
    ["tests/_tapped_support.py"],
    ["tests/make_fixture.py"],
    # mutmut's own configuration
    ["setup.cfg"],
    ["pyproject.toml"],
    # the pinned pytest/mutmut versions define what the score means
    ["requirements/mutation-tools.txt"],
    ["scripts/mutation_gate.py"],
    ["scripts/mutation_shards.py"],
    # any gate script, including ones that did not exist when the list was written
    ["scripts/mutation_plan.py"],
    [".github/workflows/ci.yml"],
    # one relevant path among many irrelevant ones still counts
    ["docs/a.md", "README.md", "boost_cli/core/util.py"],
    # tests/visual/ is excluded by kind, not by place: Python there still counts
    ["tests/visual/helper.py"],
    ["tests/visual/conftest.py"],
    ["tests/visual/pytest.ini"],
    ["tests/visual/a11y_check.mjs", "tests/unit/test_visual_harness_flags.py"],
    # only that subtree: a sibling that merely starts with the same letters
    ["tests/visualize/notes.md"],
])
def test_relevant_changes_run(changed):
    assert ms.is_relevant(changed) is True


def test_scope_fails_safe_on_no_information(tmp_path, capsys):
    """No file list means we cannot prove the score is unchanged -> run it."""
    missing = tmp_path / "nope.txt"
    assert ms.cmd_scope(_ns(changed=str(missing))) == 0
    assert capsys.readouterr().out.strip() == "true"

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert ms.cmd_scope(_ns(changed=str(empty))) == 0
    assert capsys.readouterr().out.strip() == "true"


def test_scope_blank_lines_are_not_a_change(tmp_path, capsys):
    listing = tmp_path / "changed.txt"
    listing.write_text("docs/a.md\n\n   \nREADME.md\n", encoding="utf-8")
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
        (core / name).write_text("".join("x = %d\n" % i for i in range(lines)),
                encoding="utf-8")
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
        {"mutants_by_file": {"dense.py": 5000, "sparse.py": 10}}), encoding="utf-8")
    bins = ms.pack(repo, 2)
    # dense.py dominates, so it gets a shard to itself
    solo = [b for b in bins if [f.name for f in b] == ["dense.py"]]
    assert solo, "recorded weights were ignored: %s" % [[f.name for f in b] for b in bins]


def test_missing_weight_entries_fall_back_per_file(tmp_path):
    """A partial weights file is still useful; it must not poison the rest."""
    repo = _repo(tmp_path, {"known.py": 5, "unknown.py": 200})
    (repo / "scripts").mkdir()
    (repo / ms.WEIGHTS).write_text(json.dumps({"mutants_by_file": {"known.py": 9000}}),
            encoding="utf-8")
    weight = ms.weight_fn(repo)
    assert weight(repo, repo / "boost_cli/core/known.py") == 9000     # recorded
    assert weight(repo, repo / "boost_cli/core/unknown.py") == 200    # line fallback


def test_corrupt_weights_file_is_ignored(tmp_path):
    repo = _repo(tmp_path, {"a.py": 10})
    (repo / "scripts").mkdir()
    (repo / ms.WEIGHTS).write_text("{not json", encoding="utf-8")
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
            }), encoding="utf-8")


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
        merged[meta.name[: -len(".meta")]] = json.loads(
            meta.read_text(encoding="utf-8"))["exit_code_by_key"]
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
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["exit_code_by_key"] = dict.fromkeys(data["exit_code_by_key"])
        meta.write_text(json.dumps(data), encoding="utf-8")
        break

    rc = ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                          source=str(parent), prefix="mutation-shard-"))
    assert rc == 1
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out and "unrun" in out


def _two_shard_metas(tmp_path, hashes_by_shard):
    """One file owned by both shards (a lone file split per function)."""
    repo = _repo(tmp_path, {"a.py": 40})
    parent = tmp_path / "shard-results"
    for i, h in enumerate(hashes_by_shard):
        d = parent / ("mutation-shard-%d" % i) / "boost_cli" / "core"
        d.mkdir(parents=True)
        (d / "a.py.meta").write_text(json.dumps({
            "exit_code_by_key": {"m.x_a__mutmut_1": 0 if i == 0 else None,
                                 "m.x_b__mutmut_1": 0 if i == 1 else None},
            "hash_by_function_name": h,
            "type_check_error_by_key": {},
            "durations_by_key": {},
            "estimated_durations_by_key": {},
        }), encoding="utf-8")
    return repo, parent


def _merge_two(tmp_path, monkeypatch, hashes_by_shard):
    repo, parent = _two_shard_metas(tmp_path, hashes_by_shard)
    # Force both shards to own the file, as a per-function split does.
    monkeypatch.setattr(
        ms, "pack", lambda root, n: [[repo / "boost_cli" / "core" / "a.py"]] * 2)
    return ms.cmd_merge(_ns(root=str(repo), shards=2, into=str(tmp_path / "m"),
                            source=str(parent), prefix="mutation-shard-"))


def test_merge_round_trips_every_meta_field(tmp_path, monkeypatch):
    h = {"x_a": "h1", "x_b": "h2"}
    assert _merge_two(tmp_path, monkeypatch, [h, dict(h)]) == 0
    got = json.loads((tmp_path / "m" / "boost_cli" / "core"
                      / "a.py.meta").read_text(encoding="utf-8"))
    assert got["hash_by_function_name"] == h
    assert set(got) == {"exit_code_by_key", "hash_by_function_name",
                        "type_check_error_by_key", "durations_by_key",
                        "estimated_durations_by_key"}


def test_merge_fails_when_shards_disagree_on_a_hash(tmp_path, monkeypatch, capsys):
    rc = _merge_two(tmp_path, monkeypatch, [{"x_a": "h1"}, {"x_a": "other"}])
    assert rc == 1
    assert "shards disagree on function hashes" in capsys.readouterr().out


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
    (nested / "bm25.py").write_text("x = 1\n" * 30, encoding="utf-8")
    (nested / "__init__.py").write_text("", encoding="utf-8")

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
    (repo / "boost_cli" / "core" / "__init__.py").write_text("", encoding="utf-8")
    assert ms.pattern_for(repo, repo / "boost_cli/core/__init__.py") is None
    placed = {f.name for b in ms.pack(repo, 2) for f in b}
    assert "__init__.py" not in placed


def test_patterns_for_bin_drops_init_and_matches_plan_index(tmp_path, capsys):
    # One spelling of "what a shard runs", shared by `plan --index` and the
    # mutation_plan.py planner, so the two cannot disagree with the merge.
    repo = _repo(tmp_path, {"a.py": 10, "b.py": 10})
    init = ms.Unit(repo / "boost_cli" / "core" / "__init__.py")
    a = ms.Unit(repo / "boost_cli" / "core" / "a.py")
    assert ms.patterns_for_bin(repo, [init, a]) == ["boost_cli.core.a.*"]
    assert ms.patterns_for_bin(repo, [init]) == []
    for i, b in enumerate(ms.pack(repo, 2)):
        args = _ns(root=str(repo), shards=2, index=i)
        args.timeout_minutes = None
        assert ms.cmd_plan(args) == 0
        assert capsys.readouterr().out.split() == ms.patterns_for_bin(repo, b)


def test_merge_rejects_a_file_no_shard_owned(tmp_path, capsys, monkeypatch):
    """The backstop: any file the planner missed must redden the gate."""
    files = {"a.py": 30, "b.py": 20}
    repo = _repo(tmp_path, files)
    results = {n: {"boost_cli.core.%s.x_fn__mutmut_1" % n[:-3]: 0} for n in files}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 2, results)

    # A file appears in the tree that the planner never enumerated.
    (repo / "boost_cli" / "core" / "ghost.py").write_text("x = 1\n", encoding="utf-8")
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
    (repo / "boost_cli" / "core" / "__init__.py").write_text("x = 1\n",
            encoding="utf-8")
    results = {"a.py": {"boost_cli.core.a.x_fn__mutmut_1": 0}}
    parent = tmp_path / "shard-results"
    _shard_artifacts(repo, parent, 1, results)
    # mutmut did produce mutants for __init__.py, and they ran nowhere
    init_meta = parent / "mutation-shard-0" / "boost_cli" / "core" / "__init__.py.meta"
    init_meta.write_text(json.dumps(
        {"exit_code_by_key": {"boost_cli.core.x_f__mutmut_1": None}}),
            encoding="utf-8")

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
    (nested / "util.py").write_text("x = 1\n" * 10, encoding="utf-8")
    names = {ms.rel_name(repo, f) for b in ms.pack(repo, 2) for f in b}
    assert names == {"util.py", "rag/util.py"}
    pats = {ms.pattern_for(repo, repo / "boost_cli/core/util.py"),
            ms.pattern_for(repo, nested / "util.py")}
    assert pats == {"boost_cli.core.util.*", "boost_cli.core.rag.util.*"}


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


# --------------------------------------------------------------------------
# merge --plan: ownership from the plan, and carried survivors
# (docs/superpowers/specs/2026-11-24-mutation-survivor-ledger.md)
# --------------------------------------------------------------------------

import fnmatch as _fnmatch  # noqa: E402

_REAL_ROOT = Path(__file__).resolve().parents[2]


def _real_tree_is_mutated() -> bool:
    try:
        return "__mutmut_" in (_REAL_ROOT / "boost_cli/core/store.py").read_text(encoding="utf-8")
    except OSError:
        return True


_LEDGER_KEYS = {
    "a.py": ["boost_cli.core.a.x_f__mutmut_%d" % n for n in (1, 2, 3)]
            + ["boost_cli.core.a.x_g__mutmut_%d" % n for n in (1, 2)],
    "b.py": ["boost_cli.core.b.x_h__mutmut_%d" % n for n in (1, 2)],
    "c.py": ["boost_cli.core.c.x_k__mutmut_1"],
}
#: What a plain run measured: a.f2 and c.k1 survived, the rest were killed.
_LEDGER_CODES = {k: (0 if k in ("boost_cli.core.a.x_f__mutmut_2",
                                "boost_cli.core.c.x_k__mutmut_1") else 1)
                 for keys in _LEDGER_KEYS.values() for k in keys}


def _ledger_repo(tmp_path):
    return _repo(tmp_path, {"a.py": 100, "b.py": 60, "c.py": 30})


def _selector_artifacts(parent, shards, codes=None, prefix="mutation-full-shard-"):
    """Each shard's .meta for every file, as mutmut writes them: a key is run
    (has its code and a duration) only when one of the shard's selectors
    fnmatches it -- mutmut's own filter -- and is `None` everywhere else."""
    codes = _LEDGER_CODES if codes is None else codes
    for i, selectors in enumerate(shards):
        d = parent / ("%s%d" % (prefix, i))
        d.mkdir(parents=True, exist_ok=True)
        for name, keys in _LEDGER_KEYS.items():
            ran = {k for k in keys if any(_fnmatch.fnmatchcase(k, s) for s in selectors)}
            (d / (name + ".meta")).write_text(json.dumps({
                "exit_code_by_key": {k: (codes[k] if k in ran else None) for k in keys},
                "hash_by_function_name": {},
                "type_check_error_by_key": {},
                "durations_by_key": dict.fromkeys(ran, 1.5),
                "estimated_durations_by_key": {},
            }), encoding="utf-8")


def _write_plan(tmp_path, shards, carried=None, run_id=7):
    full = {"shards": shards, "mutants": None}
    if carried is not None:
        full["carried"] = carried
        full["ledger"] = {"used": True, "run_id": run_id}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"gate_set": "full", "reasons": [], "sets": {"full": full}}),
                    encoding="utf-8")
    return str(path)


def _merge(repo, tmp_path, shards, plan=None):
    args = _ns(root=str(repo), shards=shards, into=str(tmp_path / "m"),
               source=str(tmp_path / "shard-results"), prefix="mutation-full-shard-")
    args.plan = plan
    args.set = "full"
    return ms.cmd_merge(args)


def _merged(tmp_path):
    out = {}
    for meta in (tmp_path / "m" / "boost_cli" / "core").glob("*.meta"):
        out.update(json.loads(meta.read_text(encoding="utf-8"))["exit_code_by_key"])
    return out


#: A ledgered repack: a.py split by name and by function, b.py whole, and
#: c.py's only mutant carried, so no selector names c.py at all.
_REPACK = [["boost_cli.core.a.x_f__mutmut_1", "boost_cli.core.a.x_f__mutmut_3",
            "boost_cli.core.b.*"],
           ["boost_cli.core.a.x_g__mutmut_*"]]
_CARRIED = ["boost_cli.core.a.x_f__mutmut_2", "boost_cli.core.c.x_k__mutmut_1"]


def test_the_carried_exit_is_the_constant_zero():
    # mutmut's table reads 0 as "survived"; test_mutation_ledger.py pins that
    # against the installed mutmut. Here: it is a constant, not a lookup.
    assert ms.CARRIED_EXIT == 0


@pytest.mark.parametrize("selector, file", [
    ("boost_cli.core.store.*", "store.py"),
    ("boost_cli.core.rag.bm25.*", "rag/bm25.py"),
    ("boost_cli.core.catalog.xǁ*", "catalog.py"),
    ("boost_cli.core.store.x_install__mutmut_*", "store.py"),
    ("boost_cli.core.store.x_install__mutmut_12", "store.py"),
    ("boost_cli.core.m.xǁA.Bǁm__mutmut_3", "m.py"),
    ("boost_cli.core.rag.bm25.xǁKǁm__mutmut_*", "rag/bm25.py"),
    # nothing a full plan writes, so nothing the merge will map
    ("boost_cli.core.*x", None),
    ("other.module.*", None),
    ("boost_cli.core.store.x_a__mutmut_0", None),
    ("boost_cli.core.store.x_*__mutmut_*", None),
    ("*", None),
    ("", None),
])
def test_a_selector_maps_to_exactly_its_file(selector, file):
    assert ms.selector_file(selector) == file


def test_every_key_a_selector_matches_lies_in_the_file_it_maps_to():
    # Cross-checked against fnmatch itself (mutmut's filter), not against the
    # merge's own reading: whatever a shard ran, the merge reads it from the
    # file the selector names.
    keys = ["boost_cli.core.store.x_install__mutmut_1",
            "boost_cli.core.store.x_install_from_path__mutmut_1",
            "boost_cli.core.store.xǁLockǁacquire__mutmut_2",
            "boost_cli.core.storex.x_install__mutmut_1",
            "boost_cli.core.m.xǁA.Bǁm__mutmut_3",
            "boost_cli.core.rag.bm25.x_score__mutmut_1",
            "boost_cli.core.rag.x_score__mutmut_1"]
    files = {"boost_cli.core.store": "store.py", "boost_cli.core.storex": "storex.py",
             "boost_cli.core.m": "m.py", "boost_cli.core.rag.bm25": "rag/bm25.py",
             "boost_cli.core.rag": "rag.py"}

    def file_of(key):
        return next(f for mod, f in sorted(files.items(), key=lambda t: -len(t[0]))
                    if key.startswith(mod + ".x"))

    selectors = ["boost_cli.core.store.*", "boost_cli.core.store.xǁ*",
                 "boost_cli.core.store.x_install__mutmut_*",
                 "boost_cli.core.m.xǁA.Bǁm__mutmut_*",
                 "boost_cli.core.rag.bm25.*", "boost_cli.core.rag.x_score__mutmut_*",
                 *keys]
    for sel in selectors:
        hits = [k for k in keys if _fnmatch.fnmatchcase(k, sel)]
        assert hits, sel
        assert {file_of(k) for k in hits} == {ms.selector_file(sel)}, sel
    # the anchoring that keeps `install` from swallowing `install_from_path`
    assert not _fnmatch.fnmatchcase("boost_cli.core.store.x_install_from_path__mutmut_1",
                                    "boost_cli.core.store.x_install__mutmut_*")


@pytest.mark.skipif(_real_tree_is_mutated(), reason="tree rewritten by mutmut; packing it is slow")
def test_the_committed_plans_ownership_is_the_committed_packs():
    # The plain full plan, read back as the merge reads a plan, names exactly
    # the owners `pack` does -- including every split file's functions.
    bins = ms.pack(_REAL_ROOT, ms.SHARDS)
    shards = [ms.patterns_for_bin(_REAL_ROOT, b) for b in bins]
    assert ms.plan_ownership(shards) == ms.pack_ownership(_REAL_ROOT, ms.SHARDS)


def test_a_plain_plan_merges_exactly_as_the_pack_does(tmp_path, capsys):
    repo = _ledger_repo(tmp_path)
    shards = [ms.patterns_for_bin(repo, b) for b in ms.pack(repo, 2)]
    _selector_artifacts(tmp_path / "shard-results", shards)
    plan = _write_plan(tmp_path, shards)
    assert _merge(repo, tmp_path, 2, plan) == 0, capsys.readouterr().out
    assert _merged(tmp_path) == _LEDGER_CODES
    assert not (tmp_path / "m" / ms.CARRIED_RECORD).exists()


def test_a_plan_that_carries_nothing_must_be_the_committed_pack(tmp_path, capsys):
    # A ledger-weighted repack that ends up carrying nothing would otherwise
    # merge on ownership nobody checked against the committed pack.
    repo = _ledger_repo(tmp_path)
    moved = [["boost_cli.core.a.x_f__mutmut_*", "boost_cli.core.c.*"],
             ["boost_cli.core.a.x_g__mutmut_*", "boost_cli.core.b.*"]]
    _selector_artifacts(tmp_path / "shard-results", moved)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, moved)) == 1
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out and "not the committed 2-way pack" in out


def test_a_ledgered_repack_merges_with_its_plan_and_injects_the_constant(tmp_path, capsys):
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, _REPACK, _CARRIED)) == 0, \
        capsys.readouterr().out
    out = capsys.readouterr().out
    assert "(2 carried from ledger run 7)" in out
    merged = _merged(tmp_path)
    # Every key accounted for; the carried ones are exactly CARRIED_EXIT and
    # the rest exactly what their shard measured.
    assert set(merged) == set(_LEDGER_CODES)
    for key, code in merged.items():
        assert code == (ms.CARRIED_EXIT if key in _CARRIED else _LEDGER_CODES[key]), key
    record = json.loads((tmp_path / "m" / ms.CARRIED_RECORD).read_text(encoding="utf-8"))
    assert record["carried"] == sorted(_CARRIED)


def test_the_verifiers_bug_a_ledgered_repack_without_its_plan_is_refused(tmp_path, capsys):
    # Ownership re-derived from `pack` reads the moved mutants as unrun.
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    assert _merge(repo, tmp_path, 2, plan=None) == 1
    assert "unrun" in capsys.readouterr().out


def test_a_carried_key_a_shard_also_ran_is_refused(tmp_path, capsys):
    repo = _ledger_repo(tmp_path)
    ran_it_too = [_REPACK[0] + ["boost_cli.core.a.x_f__mutmut_2"], _REPACK[1]]
    _selector_artifacts(tmp_path / "shard-results", ran_it_too)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, ran_it_too, _CARRIED)) == 1
    out = capsys.readouterr().out
    assert "carried mutant boost_cli.core.a.x_f__mutmut_2 was also run by shard 0" in out


def test_a_carried_key_not_generated_at_this_commit_is_refused(tmp_path, capsys):
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    carried = [*_CARRIED, "boost_cli.core.b.x_h__mutmut_9"]
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, _REPACK, carried)) == 1
    assert "boost_cli.core.b.x_h__mutmut_9 is not generated at this commit" in \
        capsys.readouterr().out


def test_an_uncarried_unrun_key_still_fails_closed(tmp_path, capsys):
    # a.f3 is neither named by any shard nor carried.
    repo = _ledger_repo(tmp_path)
    short = [["boost_cli.core.a.x_f__mutmut_1", "boost_cli.core.b.*"],
             ["boost_cli.core.a.x_g__mutmut_*"]]
    _selector_artifacts(tmp_path / "shard-results", short)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, short, _CARRIED)) == 1
    out = capsys.readouterr().out
    assert "a.py: 1/5 mutants unrun" in out and "x_f__mutmut_3" in out


def test_a_file_whose_every_mutant_is_carried_needs_no_selector(tmp_path, capsys):
    # c.py is named by no selector; without an owner the backstop would call
    # it "assigned to no shard" and every ledgered run would be red.
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, _REPACK, _CARRIED)) == 0
    assert _merged(tmp_path)["boost_cli.core.c.x_k__mutmut_1"] == ms.CARRIED_EXIT
    # ... and only carried rows get that pass: drop c.k1 from the carried list
    # and c.py is unowned and unrun again.
    capsys.readouterr()
    assert _merge(repo, tmp_path, 2,
                  _write_plan(tmp_path, _REPACK, _CARRIED[:1])) == 1
    assert "c.py: mutatable but assigned to no shard" in capsys.readouterr().out


@pytest.mark.parametrize("plan, said", [
    ({"sets": {}}, "no set 'full'"),
    ({"sets": {"full": {"shards": [["boost_cli.core.a.*"]]}}}, "not --shards 2"),
    ({"sets": {"full": {"shards": [["boost_cli.core.a.*"], ["a weird *"]]}}},
     "is not a full-set selector"),
    ({"sets": {"full": {"shards": _REPACK, "carried": []}}}, "non-empty list"),
    ({"sets": {"full": {"shards": _REPACK, "carried": ["boost_cli.core.a.x_f__mutmut_*"]}}},
     "is not an exact mutant name"),
    ({"sets": {"full": {"shards": _REPACK, "carried": _CARRIED + _CARRIED[:1]}}},
     "distinct"),
])
def test_a_plan_the_merge_cannot_read_is_refused(tmp_path, capsys, plan, said):
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert _merge(repo, tmp_path, 2, str(path)) == 1
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out and said in out


def test_weights_refuse_a_ledgered_merge(tmp_path, capsys):
    # A carried row has no duration, so the merged times are killed-only work.
    repo = _ledger_repo(tmp_path)
    _selector_artifacts(tmp_path / "shard-results", _REPACK)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, _REPACK, _CARRIED)) == 0
    args = type("A", (), {"root": str(repo), "source": str(tmp_path / "m"), "out": None})()
    (repo / "scripts").mkdir(exist_ok=True)
    assert ms.cmd_weights(args) == 1
    assert ms.CARRIED_RECORD in capsys.readouterr().out
    assert not (repo / ms.WEIGHTS).exists()


def test_a_plain_merge_clears_a_stale_carried_record(tmp_path, capsys):
    # The record describes the last merge into this directory, never an older one.
    repo = _ledger_repo(tmp_path)
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / ms.CARRIED_RECORD).write_text("{}", encoding="utf-8")
    shards = [ms.patterns_for_bin(repo, b) for b in ms.pack(repo, 2)]
    _selector_artifacts(tmp_path / "shard-results", shards)
    assert _merge(repo, tmp_path, 2, _write_plan(tmp_path, shards)) == 0
    assert not (tmp_path / "m" / ms.CARRIED_RECORD).exists()
