# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: splitting one file's mutants across shards.

Sharding took the mutation gate from ~28 minutes to ~12, but it could not go
lower, because ``store.py`` is 1931 mutants — 18.4% of the repo — in a single
file, and longest-processing-time packing cannot place one file in two bins.
``mutation-shard (0)`` was the slowest leg of four consecutive six-shard runs.

Mutant names are addressable per function (``boost_cli.core.store.x_install__
mutmut_3``), so a file heavier than an even share is now split into one unit
per top-level function. Two properties have to survive that, and both are
asserted here rather than reasoned about:

* ``pattern_for`` must emit patterns that match nothing else — the hazard is a
  function name that prefixes another (``install`` vs ``install_from_path``).
* ``cmd_merge`` must keep failing CLOSED. mutmut counts an unrun mutant inside
  ``total``, so a partial merge would silently depress the score rather than
  error, and ``export-cicd-stats`` drops a file with no ``.meta`` from ``total``
  altogether — which would make the gate pass on a subset.
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "mutation_shards_subfile", ROOT / "scripts" / "mutation_shards.py")
ms = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ms)


def _tree_is_mutated():
    """True when this suite is running inside mutmut's rewritten copy.

    The mutation gate runs the unit suite from inside ``mutants/``, where every
    file under ``boost_cli/core`` has been rewritten — each function replaced by
    a family of ``x_<name>__mutmut_<n>`` variants. Assertions about the *shape*
    of the real tree (which file is heaviest, how it partitions) are meaningless
    against that copy and fail there, which is exactly what happened the first
    time this landed: all six shards went red on `test_store_py_is_split`.

    Skipping costs nothing. ``setup.cfg`` sets ``source_paths =
    boost_cli/core/``, so ``scripts/mutation_shards.py`` is never mutated —
    these tests kill no mutants and exist only to assert this repo's current
    shape. Everything else in this file builds its own tree under ``tmp_path``
    and runs identically in both places.
    """
    store = ROOT / "boost_cli" / "core" / "store.py"
    try:
        return "__mutmut_" in store.read_text(encoding="utf-8")
    except OSError:
        return True        # can't tell — don't assert against it


real_tree_only = pytest.mark.skipif(
    _tree_is_mutated(), reason="tree rewritten by mutmut; real-shape assertions "
                               "do not apply inside mutants/")


def _repo(tmp_path, files):
    """A fake checkout: {name: source text}."""
    core = tmp_path / "boost_cli" / "core"
    core.mkdir(parents=True)
    for name, text in files.items():
        (core / name).write_text(text)
    return tmp_path


def _fn(name, body_lines=3):
    return "def %s():\n%s\n" % (name, "\n".join(
        "    x = %d" % i for i in range(body_lines)))


def _big(name_prefix, count, body_lines=3):
    """A module of `count` top-level functions."""
    return "".join(_fn("%s_%d" % (name_prefix, i), body_lines)
                   for i in range(count))


class TestTopLevelSymbols:
    """Which files can be split, and which must not be."""

    def test_plain_functions_are_addressable(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text(_fn("alpha") + _fn("beta"))
        assert ms.top_level_symbols(p) == ["alpha", "beta"]

    def test_a_class_with_methods_disables_splitting(self, tmp_path):
        # mutmut mangles a method's mutant name differently from a plain
        # function's. Guessing wrong yields a pattern matching nothing, so those
        # mutants would never run — and merge would (correctly) redden the
        # build. A file we cannot partition provably is one we leave whole.
        p = tmp_path / "m.py"
        p.write_text(_fn("alpha") + "class C:\n    def meth(self):\n        pass\n")
        assert ms.top_level_symbols(p) == []

    def test_a_bare_class_still_allows_splitting(self, tmp_path):
        # store.py's InstallResult is a NamedTuple with no method bodies; it
        # generates no mutants of its own, so it is not a reason to give up.
        p = tmp_path / "m.py"
        p.write_text(_fn("alpha") + _fn("beta") + "class C:\n    x = 1\n")
        assert ms.top_level_symbols(p) == ["alpha", "beta"]

    def test_duplicate_names_disable_splitting(self, tmp_path):
        # Two units sharing one pattern would both run the same mutants and one
        # shard's results would overwrite the other's.
        p = tmp_path / "m.py"
        p.write_text(_fn("alpha") + _fn("alpha"))
        assert ms.top_level_symbols(p) == []

    def test_unparseable_file_is_left_whole(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text("def (((\n")
        assert ms.top_level_symbols(p) == []


class TestSplittingPolicy:
    """Only a file that IS the floor gets split."""

    def test_a_light_file_is_not_split(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _big("f", 4)})
        units = ms.units_for(repo, repo / "boost_cli/core/a.py", ceiling=10_000)
        assert units == [ms.Unit(repo / "boost_cli/core/a.py")]
        assert units[0].symbol is None

    def test_a_file_over_the_ceiling_is_split(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _big("f", 6)})
        units = ms.units_for(repo, repo / "boost_cli/core/a.py", ceiling=1)
        assert len(units) == 6
        assert {u.symbol for u in units} == {"f_%d" % i for i in range(6)}

    def test_an_unsplittable_heavy_file_stays_whole(self, tmp_path):
        # Heavier than the ceiling but with no addressable partition: it must
        # stay whole rather than be dropped or half-assigned.
        repo = _repo(tmp_path, {"a.py": "class C:\n    def m(self):\n        pass\n"})
        units = ms.units_for(repo, repo / "boost_cli/core/a.py", ceiling=1)
        assert units == [ms.Unit(repo / "boost_cli/core/a.py")]

    def test_a_single_function_file_is_not_split(self, tmp_path):
        # Splitting into one unit would add a pattern for no benefit.
        repo = _repo(tmp_path, {"a.py": _fn("only", 50)})
        units = ms.units_for(repo, repo / "boost_cli/core/a.py", ceiling=1)
        assert units == [ms.Unit(repo / "boost_cli/core/a.py")]


class TestPatterns:
    """A unit's pattern must match its own mutants and nothing else."""

    @staticmethod
    def _mutant(module, symbol, n=1):
        return "boost_cli.core.%s.x_%s__mutmut_%d" % (module, symbol, n)

    def test_symbol_pattern_matches_its_own_mutants(self, tmp_path):
        repo = _repo(tmp_path, {"store.py": _fn("install")})
        pat = ms.pattern_for(repo, ms.Unit(repo / "boost_cli/core/store.py",
                                           "install"))
        assert fnmatch.fnmatch(self._mutant("store", "install", 7), pat)

    def test_a_prefix_name_does_not_capture_a_longer_one(self, tmp_path):
        # THE HAZARD: store.py really does have both `install` and
        # `install_from_path`. A pattern of `...x_install*` would swallow the
        # latter, so it would run in two shards and one result set would
        # overwrite the other.
        repo = _repo(tmp_path, {"store.py": _fn("install") + _fn("install_from_path")})
        pat = ms.pattern_for(repo, ms.Unit(repo / "boost_cli/core/store.py",
                                           "install"))
        assert not fnmatch.fnmatch(self._mutant("store", "install_from_path"), pat)

    def test_underscore_prefixed_names_round_trip(self, tmp_path):
        # mutmut turns `_install_rule` into `x__install_rule` — two underscores.
        repo = _repo(tmp_path, {"store.py": _fn("_install_rule")})
        pat = ms.pattern_for(repo, ms.Unit(repo / "boost_cli/core/store.py",
                                           "_install_rule"))
        assert fnmatch.fnmatch("boost_cli.core.store.x__install_rule__mutmut_2", pat)

    def test_whole_file_pattern_is_unchanged(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _fn("f")})
        assert ms.pattern_for(repo, repo / "boost_cli/core/a.py") == \
            "boost_cli.core.a.*"

    def test_a_path_still_works_where_a_unit_is_expected(self, tmp_path):
        # cmd_plan/cmd_merge pass Units now, but the function is public and
        # tests/other callers pass bare paths.
        repo = _repo(tmp_path, {"a.py": _fn("f")})
        assert ms.pattern_for(repo, ms.Unit(repo / "boost_cli/core/a.py")) == \
            ms.pattern_for(repo, repo / "boost_cli/core/a.py")

    def test_no_unit_pattern_captures_another_units_mutants(self, tmp_path):
        """Exhaustive over a split file: every pattern is disjoint."""
        names = ["install", "install_from_path", "_install_rule", "sync",
                 "sync_plan", "sync_apply", "uninstall", "uninstall_project"]
        repo = _repo(tmp_path, {"store.py": "".join(_fn(n) for n in names)})
        path = repo / "boost_cli/core/store.py"
        pats = {n: ms.pattern_for(repo, ms.Unit(path, n)) for n in names}
        for owner, pat in pats.items():
            for other in names:
                if other == owner:
                    continue
                assert not fnmatch.fnmatch(self._mutant("store", other), pat), \
                    "%s captures %s" % (pat, other)


@real_tree_only
class TestRealTree:
    """Against the actual repo, where the numbers came from."""

    def test_store_py_is_split(self):
        bins = ms.pack(ROOT, 6)
        split = {u.symbol for b in bins for u in b if u.path.name == "store.py"}
        assert len(split) > 1, "store.py is the floor; it must be split"
        assert None not in split

    def test_store_py_functions_are_a_complete_partition(self):
        # Every function exactly once: a missing one would be unrun mutants, a
        # duplicated one would be two shards overwriting each other.
        bins = ms.pack(ROOT, 6)
        assigned = [u.symbol for b in bins for u in b if u.path.name == "store.py"]
        expected = ms.top_level_symbols(ROOT / "boost_cli/core/store.py")
        assert sorted(assigned) == sorted(expected)

    def test_the_split_lowers_the_critical_path(self):
        # The point of the change, asserted against the real weights.
        weight = ms.weight_fn(ROOT)
        files = [f for f in ms.source_files(ROOT) if not ms.is_init(f)]
        heaviest_file = max(weight(ROOT, f) for f in files)
        loads = [sum(ms.unit_weight(ROOT, u) for u in b) for b in ms.pack(ROOT, 6)]
        assert max(loads) < heaviest_file, \
            "critical path should now be below the heaviest single file"

    def test_every_unit_has_a_pattern(self):
        for b in ms.pack(ROOT, 6):
            for u in b:
                assert ms.pattern_for(ROOT, u), u

    def test_no_file_is_both_whole_and_split(self):
        bins = ms.pack(ROOT, 6)
        seen = {}
        for b in bins:
            for u in b:
                name = ms.rel_name(ROOT, u.path)
                kind = "whole" if u.symbol is None else "split"
                assert seen.setdefault(name, kind) == kind, name


class TestWeighting:
    """Weight tiers, and the scale-mixing they must not do."""

    def test_a_file_missing_a_duration_is_imputed_not_mixed(self, tmp_path):
        # Milliseconds run to five digits where counts run to three, so a file
        # weighted in ms beside files weighted in counts would outweigh the
        # whole repo and take a shard to itself. Impute it at the measured rate
        # instead — same unit, so the packer stays commensurable.
        repo = _repo(tmp_path, {"a.py": _fn("f"), "b.py": _fn("g")})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100, "b.py": 50},
            "millis_by_file": {"a.py": 90_000},          # b.py unmeasured
        }))
        weight = ms.weight_fn(repo)
        assert weight(repo, repo / "boost_cli/core/a.py") == 90_000
        # 900 ms/mutant measured on a.py, applied to b.py's 50 mutants.
        assert weight(repo, repo / "boost_cli/core/b.py") == 45_000

    def test_one_unmeasured_file_does_not_disable_time_weighting(self, tmp_path):
        # THE REGRESSION THIS REPLACES: requiring a complete record meant one
        # short file of 46 silently dropped the planner back to counting
        # mutants — which is exactly what the first real run produced
        # (util.py), and it would have looked like the feature simply not
        # working.
        repo = _repo(tmp_path, {"a.py": _fn("f"), "b.py": _fn("g")})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100, "b.py": 50},
            "millis_by_file": {"a.py": 90_000},
        }))
        weight = ms.weight_fn(repo)
        assert weight(repo, repo / "boost_cli/core/a.py") > 1000, \
            "time weighting must still be in play"

    def test_no_durations_at_all_falls_back_to_counts(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _fn("f"), "b.py": _fn("g")})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100, "b.py": 50},
        }))
        weight = ms.weight_fn(repo)
        assert weight(repo, repo / "boost_cli/core/a.py") == 100
        assert weight(repo, repo / "boost_cli/core/b.py") == 50

    def test_complete_millisecond_coverage_is_used(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _fn("f"), "b.py": _fn("g")})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100, "b.py": 100},
            "millis_by_file": {"a.py": 90_000, "b.py": 1_000},
        }))
        weight = ms.weight_fn(repo)
        assert weight(repo, repo / "boost_cli/core/a.py") == 90_000
        assert weight(repo, repo / "boost_cli/core/b.py") == 1_000

    def test_a_units_share_prefers_measured_time_over_count(self, tmp_path):
        # THE SECOND PROXY ERROR: count is as poor a stand-in for time *within*
        # a file as across the repo. Measured on store.py, per-mutant cost runs
        # 0.273 s to 3.900 s across its functions — 14.3x — and `install` is 36%
        # of the file's time from 12% of its mutants. Apportioning by count sent
        # that function's shard to 8.9 min against a 4.8 min sibling.
        repo = _repo(tmp_path, {"a.py": _big("f", 2)})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100},
            "millis_by_file": {"a.py": 10_000},
            # equal counts, wildly unequal time
            "mutants_by_symbol": {"a.py": {"f_0": 50, "f_1": 50}},
            "millis_by_symbol": {"a.py": {"f_0": 9_000, "f_1": 1_000}},
        }))
        path = repo / "boost_cli/core/a.py"
        slow = ms.unit_weight(repo, ms.Unit(path, "f_0"))
        fast = ms.unit_weight(repo, ms.Unit(path, "f_1"))
        assert slow == 9_000 and fast == 1_000, (slow, fast)

    def test_a_units_share_falls_back_to_counts_when_untimed(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _big("f", 2)})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 100},
            "mutants_by_symbol": {"a.py": {"f_0": 75, "f_1": 25}},
        }))
        path = repo / "boost_cli/core/a.py"
        assert ms.unit_weight(repo, ms.Unit(path, "f_0")) == 75
        assert ms.unit_weight(repo, ms.Unit(path, "f_1")) == 25

    def test_a_units_weight_is_a_share_of_its_files(self, tmp_path):
        # Keeping units commensurable with whole files is what lets the packer
        # mix them in one bin.
        repo = _repo(tmp_path, {"a.py": _big("f", 4)})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text(json.dumps({
            "mutants_by_file": {"a.py": 400},
            "mutants_by_symbol": {"a.py": {"f_0": 100, "f_1": 100,
                                           "f_2": 100, "f_3": 100}},
        }))
        path = repo / "boost_cli/core/a.py"
        total = sum(ms.unit_weight(repo, ms.Unit(path, "f_%d" % i)) for i in range(4))
        assert total == ms.weight_fn(repo)(repo, path)

    def test_corrupt_weights_do_not_crash_the_split(self, tmp_path):
        repo = _repo(tmp_path, {"a.py": _big("f", 3)})
        (repo / "scripts").mkdir()
        (repo / "scripts" / "mutation_weights.json").write_text("{not json")
        assert ms.pack(repo, 2)          # falls back to line counts

    def test_a_unit_weight_is_never_zero(self, tmp_path):
        # A 0-weight unit makes the packing order ambiguous between runs.
        repo = _repo(tmp_path, {"a.py": _big("f", 30, body_lines=1)})
        path = repo / "boost_cli/core/a.py"
        for sym in ms.top_level_symbols(path):
            assert ms.unit_weight(repo, ms.Unit(path, sym)) >= 1


def _write_shard_metas(parent, prefix, bins, repo, results):
    """Write each shard's .meta the way the CI artifact download lays it out.

    Mirrors mutmut: a shard's .meta for a split file lists EVERY key in that
    file, with None against the mutants that shard was not asked to run.
    """
    for i, b in enumerate(bins):
        d = parent / ("%s%d" % (prefix, i)) / "boost_cli" / "core"
        d.mkdir(parents=True, exist_ok=True)
        # One .meta per FILE per shard, covering every unit of that file the
        # shard owns — mutmut is handed all its patterns at once and writes the
        # file's results in one go. Writing per-unit would have the second unit
        # clobber the first, which is a property of this fixture, not of mutmut.
        per_file = {}
        for u in b:
            per_file.setdefault(ms.rel_name(repo, u), []).append(u.symbol)
        for name, symbols in per_file.items():
            codes = dict.fromkeys(results[name])       # every key, all None
            for symbol in symbols:
                for key, value in results[name].items():
                    if symbol is None or ".x_%s__mutmut_" % symbol in key:
                        codes[key] = value
            (d / (name + ".meta")).write_text(json.dumps({
                "exit_code_by_key": codes, "type_check_error_by_key": {},
                "durations_by_key": {}, "estimated_durations_by_key": {}}))


class TestMergeAcrossSplitShards:
    """The completeness assertion, which must keep failing closed."""

    @staticmethod
    def _setup(tmp_path, symbols=("alpha", "beta", "gamma", "delta")):
        repo = _repo(tmp_path, {"big.py": "".join(_fn(s, 20) for s in symbols),
                                "small.py": _fn("tiny")})
        results = {
            "big.py": {"boost_cli.core.big.x_%s__mutmut_%d" % (s, n): 0
                       for s in symbols for n in (1, 2)},
            "small.py": {"boost_cli.core.small.x_tiny__mutmut_1": 0},
        }
        return repo, results

    def _merge(self, tmp_path, repo, results, shards=2, mutate=None):
        bins = ms.pack(repo, shards)
        art = tmp_path / "artifacts"
        _write_shard_metas(art, "mutation-shard-", bins, repo, results)
        if mutate:
            mutate(art)
        into = tmp_path / "merged"
        args = type("A", (), {"root": str(repo), "shards": shards,
                              "source": str(art), "prefix": "mutation-shard-",
                              "into": str(into)})()
        return ms.cmd_merge(args), into

    def test_a_split_file_merges_losslessly(self, tmp_path, capsys):
        repo, results = self._setup(tmp_path)
        rc, into = self._merge(tmp_path, repo, results)
        assert rc == 0, capsys.readouterr().out
        merged = json.loads(
            (into / "boost_cli/core/big.py.meta").read_text())["exit_code_by_key"]
        assert merged == results["big.py"], "union must reproduce the whole file"

    def test_a_function_no_shard_ran_fails_closed(self, tmp_path, capsys):
        """The scenario the card demands: a partition gap must ERROR."""
        repo, results = self._setup(tmp_path)

        def drop_alpha(art):
            for meta in art.rglob("big.py.meta"):
                data = json.loads(meta.read_text())
                for key in data["exit_code_by_key"]:
                    if ".x_alpha__mutmut_" in key:
                        data["exit_code_by_key"][key] = None
                meta.write_text(json.dumps(data))

        rc, _ = self._merge(tmp_path, repo, results, mutate=drop_alpha)
        assert rc == 1
        out = capsys.readouterr().out
        assert "INCOMPLETE" in out
        assert "alpha" in out, "name the function that never ran"

    def test_a_missing_shard_artifact_fails_closed(self, tmp_path, capsys):
        repo, results = self._setup(tmp_path)

        def remove_one(art):
            for meta in (art / "mutation-shard-1").rglob("*.meta"):
                meta.unlink()

        rc, _ = self._merge(tmp_path, repo, results, mutate=remove_one)
        assert rc == 1
        assert "INCOMPLETE" in capsys.readouterr().out

    def test_merge_still_works_when_nothing_is_split(self, tmp_path, capsys):
        # The unsplit path must be untouched by all of this.
        repo = _repo(tmp_path, {"a.py": _fn("f"), "b.py": _fn("g")})
        results = {"a.py": {"boost_cli.core.a.x_f__mutmut_1": 0},
                   "b.py": {"boost_cli.core.b.x_g__mutmut_1": 1}}
        rc, into = self._merge(tmp_path, repo, results, shards=2)
        assert rc == 0, capsys.readouterr().out
        for name in ("a.py", "b.py"):
            assert (into / "boost_cli/core" / (name + ".meta")).exists()

    def test_a_surviving_mutant_is_not_mistaken_for_an_unrun_one(self, tmp_path,
                                                                 capsys):
        # exit code 1 means "survived" — a real result the gate must see, not a
        # gap. Only None means unrun. Conflating them would fail every build
        # that has a survivor.
        repo, results = self._setup(tmp_path)
        for key in list(results["big.py"]):
            results["big.py"][key] = 1
        rc, _ = self._merge(tmp_path, repo, results)
        assert rc == 0, capsys.readouterr().out

    def test_merged_meta_keeps_the_parallel_key_maps(self, tmp_path):
        # export-cicd-stats reads a .meta shaped like an unsharded one.
        repo, results = self._setup(tmp_path)
        _rc, into = self._merge(tmp_path, repo, results)
        data = json.loads((into / "boost_cli/core/big.py.meta").read_text())
        for field in ("exit_code_by_key", "type_check_error_by_key",
                      "durations_by_key", "estimated_durations_by_key"):
            assert field in data, field


class TestPlanCli:
    """The command CI actually runs."""

    def test_plan_emits_patterns_for_every_shard(self, tmp_path, capsys):
        repo = _repo(tmp_path, {"big.py": _big("f", 8, 20), "s.py": _fn("g")})
        for index in range(3):
            args = type("A", (), {"root": str(repo), "shards": 3,
                                  "index": index, "explain": False})()
            assert ms.cmd_plan(args) == 0
            assert capsys.readouterr().out.strip(), \
                "shard %d planned nothing — CI refuses to run unfiltered" % index

    def test_explain_reports_what_was_split(self, tmp_path, capsys):
        repo = _repo(tmp_path, {"big.py": _big("f", 8, 20), "s.py": _fn("g")})
        args = type("A", (), {"root": str(repo), "shards": 2, "index": None,
                              "explain": True})()
        assert ms.cmd_plan(args) == 0
        assert "split files : big.py" in capsys.readouterr().out


class TestWeightsRecording:
    """cmd_weights turns a finished run into better hints for the next one."""

    @staticmethod
    def _meta(tmp_path, codes, durations=None):
        src = tmp_path / "mutants" / "boost_cli" / "core"
        src.mkdir(parents=True)
        (src / "store.py.meta").write_text(json.dumps({
            "exit_code_by_key": codes,
            "durations_by_key": durations or {},
        }))
        return tmp_path

    def _run(self, tmp_path, repo, codes, durations=None):
        self._meta(tmp_path, codes, durations)
        (repo / "scripts").mkdir(exist_ok=True)
        args = type("A", (), {"root": str(repo), "source": str(tmp_path / "mutants")})()
        rc = ms.cmd_weights(args)
        return rc, json.loads((repo / "scripts" / "mutation_weights.json").read_text())

    def test_per_symbol_counts_are_recorded(self, tmp_path):
        repo = _repo(tmp_path / "r", {"store.py": _fn("install")})
        codes = {"boost_cli.core.store.x_install__mutmut_%d" % n: 0 for n in (1, 2, 3)}
        codes["boost_cli.core.store.x_sync__mutmut_1"] = 0
        rc, data = self._run(tmp_path, repo, codes)
        assert rc == 0
        assert data["mutants_by_symbol"]["store.py"] == {"install": 3, "sync": 1}

    def test_durations_are_recorded_only_when_complete(self, tmp_path):
        repo = _repo(tmp_path / "r", {"store.py": _fn("install")})
        codes = {"boost_cli.core.store.x_install__mutmut_%d" % n: 0 for n in (1, 2)}
        rc, data = self._run(tmp_path, repo, codes,
                             durations={"boost_cli.core.store.x_install__mutmut_1": 5})
        assert rc == 0
        assert data["millis_by_file"] == {}, \
            "a partial duration record must not weight the file"

    def test_durations_are_summed_and_converted_to_milliseconds(self, tmp_path):
        # mutmut records SECONDS as floats (measured: 0.24-7.93 per mutant).
        # Storing the raw sum under a millis name was a 1000x mislabel — it
        # made store.py's real 2360 s of test time read as 2.4 s.
        repo = _repo(tmp_path / "r", {"store.py": _fn("install")})
        keys = ["boost_cli.core.store.x_install__mutmut_%d" % n for n in (1, 2)]
        rc, data = self._run(tmp_path, repo, dict.fromkeys(keys, 0),
                             durations={keys[0]: 40, keys[1]: 60})
        assert rc == 0
        assert data["millis_by_file"]["store.py"] == 100_000

    def test_sub_second_durations_survive_the_conversion(self, tmp_path):
        # The common case: most mutants take a fraction of a second, and
        # truncating to whole seconds would round the majority of them to 0.
        repo = _repo(tmp_path / "r", {"store.py": _fn("install")})
        keys = ["boost_cli.core.store.x_install__mutmut_%d" % n for n in (1, 2)]
        rc, data = self._run(tmp_path, repo, dict.fromkeys(keys, 0),
                             durations={keys[0]: 0.24, keys[1]: 0.26})
        assert rc == 0
        assert data["millis_by_file"]["store.py"] == 500

    def test_a_malformed_key_is_skipped_not_fatal(self, tmp_path):
        repo = _repo(tmp_path / "r", {"store.py": _fn("install")})
        codes = {"not_a_mutant_key": 0,
                 "boost_cli.core.store.x_install__mutmut_1": 0}
        rc, data = self._run(tmp_path, repo, codes)
        assert rc == 0
        assert data["mutants_by_symbol"]["store.py"] == {"install": 1}


@real_tree_only
@pytest.mark.parametrize("shards", [1, 2, 3, 6, 12])
def test_the_partition_is_complete_at_every_shard_count(shards):
    """No mutant is dropped or duplicated, whatever the matrix width."""
    bins = ms.pack(ROOT, shards)
    units = [u for b in bins for u in b]
    assert len(units) == len({(ms.rel_name(ROOT, u.path), u.symbol) for u in units})
    for f in ms.source_files(ROOT):
        if ms.is_init(f):
            continue
        mine = [u for u in units if u.path == f]
        assert mine, "%s was assigned to no shard" % ms.rel_name(ROOT, f)
        if mine[0].symbol is None:
            assert len(mine) == 1
        else:
            assert sorted(u.symbol for u in mine) == sorted(ms.top_level_symbols(f))
