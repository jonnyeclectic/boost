# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A measured run can clear a class-bearing module for splitting.

``top_level_symbols`` refuses any module holding a class with methods, because
mutmut mangles a method's name differently from a plain function's and a wrong
guess leaves mutants unrun. With only an AST to go on that is the right call.

The cost of making it unconditional was not visible until the weights grew.
``registry.py`` holds one 30-line class, ``Tap``, which carries no recorded
mutants at all -- and that class alone makes the other 7.3 million weight-
milliseconds of the module one indivisible unit. An indivisible unit is a
*floor on the slowest shard* at every shard count, so the documented remedy
for a pack that does not fit ("re-measure and re-pack") cannot move it. On the
refreshed weights of #1022 that floor scores a 71.5-minute tail against a
75-minute cap -- 95% -- and adding shards changes the number not at all.

``measured_partition`` lifts the refusal for a module a real run has cleared,
and these tests pin both halves of that: that it lifts it only on proof, and
that the proof is the invariant it claims to be.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "mutation_shards.py"
CORE = ROOT / "boost_cli" / "core"

_spec = importlib.util.spec_from_file_location("mutation_shards_split", SCRIPT)
ms = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ms)


SOURCE = '''\
class Tap:
    """A class with a method is what the AST bail refuses on."""

    def label(self):
        return 1


def alpha():
    return 1


def beta():
    return 2
'''


def make_tree(tmp_path: Path, source: str, symbols: dict | None) -> Path:
    """A miniature checkout: one source file plus an optional weights file."""
    pkg = tmp_path / "boost_cli" / "core"
    pkg.mkdir(parents=True)
    (pkg / "sample.py").write_text(source, encoding="utf-8")
    if symbols is not None:
        weights = {
            "millis_by_file": {"sample.py": sum(symbols.values())},
            "millis_by_symbol": {"sample.py": symbols},
        }
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "mutation_weights.json").write_text(
            json.dumps(weights), encoding="utf-8")
    return pkg / "sample.py"


class TestTheAstBailIsStillTheDefault:
    def test_a_class_with_a_method_blocks_the_ast_route(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, None)
        assert ms.top_level_symbols(path) == [], \
            "top_level_symbols must keep refusing on the AST alone"

    def test_without_a_record_the_module_stays_whole(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, None)
        assert ms.measured_partition(tmp_path, path) == []
        # and therefore so does the unit list, at any ceiling
        assert ms.units_for(tmp_path, path, 1) == [ms.Unit(path)]


class TestProofUnlocksIt:
    def test_a_complete_record_clears_the_class(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, {"alpha": 10, "beta": 20})
        assert ms.measured_partition(tmp_path, path) == ["alpha", "beta"]

    def test_the_split_actually_happens_now(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, {"alpha": 10, "beta": 20})
        units = ms.units_for(tmp_path, path, 1)
        assert sorted(u.symbol for u in units) == ["alpha", "beta"], \
            "a cleared module over the ceiling must split per function"

    def test_a_cleared_module_under_the_ceiling_still_stays_whole(self, tmp_path):
        """Clearing is not a reason to split; exceeding the ceiling is."""
        path = make_tree(tmp_path, SOURCE, {"alpha": 10, "beta": 20})
        assert ms.units_for(tmp_path, path, 10 ** 9) == [ms.Unit(path)]


class TestTheProofIsNotAFormality:
    def test_a_recorded_name_from_inside_a_class_refuses(self, tmp_path):
        """`label` is a method, so its pattern would address nothing.

        `<module>.x_label__mutmut_*` never matches mutmut's
        `<module>.Tap.x_label__mutmut_*`, so splitting here would leave that
        method's mutants unrun.
        """
        path = make_tree(tmp_path, SOURCE,
                         {"alpha": 10, "beta": 20, "label": 5})
        assert ms.measured_partition(tmp_path, path) == []

    def test_a_recorded_name_that_is_gone_refuses(self, tmp_path):
        """A record naming a function the module no longer has is stale."""
        path = make_tree(tmp_path, SOURCE, {"alpha": 10, "removed": 7})
        assert ms.measured_partition(tmp_path, path) == []

    def test_duplicate_names_are_not_cleared_by_measurement(self, tmp_path):
        """Two units sharing one pattern overwrite each other's results.

        No amount of recorded timing makes that safe, so this bail is the one
        `measured_partition` must keep rather than re-derive.
        """
        dup = SOURCE + "\n\ndef alpha():\n    return 3\n"
        path = make_tree(tmp_path, dup, {"alpha": 10, "beta": 20})
        assert ms.measured_partition(tmp_path, path) == []

    def test_an_empty_record_refuses(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, {})
        assert ms.measured_partition(tmp_path, path) == []


class TestTheRecordIsProofNotThePartition:
    def test_a_function_added_since_the_measurement_still_gets_a_unit(
            self, tmp_path):
        """The split is over the AST, not over the recorded names.

        A function added after the weights were written has no record. If the
        partition came from the record it would be unaddressed by every shard,
        and `cmd_merge` would fail the build naming it. Splitting over the AST
        is what keeps the new function covered.
        """
        src = SOURCE + "\n\ndef gamma():\n    return 3\n"
        path = make_tree(tmp_path, src, {"alpha": 10, "beta": 20})
        assert ms.measured_partition(tmp_path, path) == [
            "alpha", "beta", "gamma"]
        units = ms.units_for(tmp_path, path, 1)
        assert "gamma" in {u.symbol for u in units}

    def test_every_unit_gets_a_distinct_addressable_pattern(self, tmp_path):
        path = make_tree(tmp_path, SOURCE, {"alpha": 10, "beta": 20})
        units = ms.units_for(tmp_path, path, 1)
        pats = [ms.pattern_for(tmp_path, u) for u in units]
        assert len(set(pats)) == len(pats), "two units share one pattern"
        for p in pats:
            assert p.endswith("__mutmut_*") and ".x_" in p


class TestTheInvariantHoldsOverTheRealTree:
    """The relaxation rests on a claim about this repository, so assert it.

    Over both committed weight generations no recorded symbol has ever come
    from inside a class. If that stops being true, `measured_partition`
    refuses and the module simply stays whole -- but the claim in its
    docstring would be false, and a reader should find out here rather than
    from a 40-minute merge failure.
    """

    def test_no_recorded_symbol_comes_from_inside_a_class(self):
        recorded = ms.load_symbol_durations(ROOT)
        if not recorded:
            pytest.skip("no committed per-symbol weights to check")
        checked = 0
        for name, syms in recorded.items():
            path = CORE / name
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            top = {n.name for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            stray = sorted(set(syms) - top)
            assert not stray, (
                "%s records %s, which is not a top-level def — "
                "pattern_for cannot address it" % (name, stray))
            checked += 1
        assert checked > 10, "expected to check many files, saw %d" % checked

    def test_a_class_bearing_module_is_actually_among_them(self):
        """Otherwise the test above passes by never meeting the hard case."""
        recorded = ms.load_symbol_durations(ROOT)
        if not recorded:
            pytest.skip("no committed per-symbol weights to check")
        with_classes = []
        for name in recorded:
            path = CORE / name
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(isinstance(n, ast.ClassDef)
                   and any(isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                           for m in n.body)
                   for n in tree.body):
                with_classes.append(name)
        assert with_classes, (
            "no class-bearing module carries recorded symbols — the "
            "invariant above is vacuous")
        assert ms.top_level_symbols(CORE / with_classes[0]) == [], \
            "that module should be one the AST route refuses"
