# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[2] / "scripts" / "mutation_diff.py"
_spec = importlib.util.spec_from_file_location("mutation_diff", _P)
md = importlib.util.module_from_spec(_spec)
sys.modules["mutation_diff"] = md
_spec.loader.exec_module(md)


@pytest.fixture
def needs_mutmut():
    """Skip a test that reaches mutmut where mutmut is not installed.

    Per test, never per module: the `tests` cells install
    requirements/test-tools.txt (PyYAML, no mutmut), and the tests that need
    only the stdlib and PyYAML must keep running there. The mutmut-backed ones
    run in `mutation-plan`, whose venv is requirements/mutation-tools.txt,
    under BOOST_REQUIRE_MUTMUT=1: there a missing mutmut is an error, so the
    one place these tests run cannot quietly skip them all.
    """
    if os.environ.get("BOOST_REQUIRE_MUTMUT") == "1":
        import mutmut

        return mutmut
    return pytest.importorskip("mutmut")


def test_the_module_loads_without_mutmut():
    # Pinned where mutmut IS installed too, so the import can't creep back to
    # module level unnoticed: a `None` in sys.modules makes any `import
    # mutmut...` raise, exactly as an absent package would.
    code = (
        "import sys, importlib.util\n"
        "sys.modules['mutmut'] = None\n"
        "spec = importlib.util.spec_from_file_location('mutation_diff', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "sys.modules['mutation_diff'] = m\n"
        "spec.loader.exec_module(m)\n"
        "assert m.passes(m.Verdict(killed=8, denominator=10))\n"
        "assert m.changed_functions('def a(): pass\\n', None) == set()\n"
    )
    proc = subprocess.run([sys.executable, "-c", code, str(_P)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.usefixtures("needs_mutmut")
def test_body_edit_is_a_change():
    assert md.changed_functions(
        "def a():\n    return 1\n", "def a():\n    return 2\n"
    ) == {"x_a"}


@pytest.mark.usefixtures("needs_mutmut")
def test_new_function_counts_and_deleted_one_does_not():
    assert md.changed_functions(
        "def a(): pass\ndef b(): pass\n", "def a(): pass\ndef c(): pass\n"
    ) == {"x_c"}


@pytest.mark.usefixtures("needs_mutmut")
def test_new_file_everything_is_new():
    assert md.changed_functions(None, "def a(): pass\n") == {"x_a"}


@pytest.mark.usefixtures("needs_mutmut")
def test_method_edit_uses_mutmuts_mangled_name():
    base = "class K:\n    def m(self):\n        return 1\n"
    assert md.changed_functions(base, base.replace("1", "2")) == {"xǁKǁm"}


def test_deleted_file_has_no_scope():
    assert md.changed_functions("def a(): pass\n", None) == set()


@pytest.mark.usefixtures("needs_mutmut")
def test_unchanged_function_is_not_a_change():
    src = "def a():\n    return 1\n"
    assert md.changed_functions(src, src) == set()


def test_qualify():
    assert (
        md.qualify("boost_cli/core/store.py", "x_install")
        == "boost_cli.core.store.x_install"
    )
    assert (
        md.qualify("boost_cli/core/store.py", "xǁKǁm") == "boost_cli.core.store.xǁKǁm"
    )


def test_callers_are_direct_only():
    deps = {"m.x_a": ["m.x_b"], "m.x_b": ["m.x_c"]}
    assert md.direct_callers(deps, {"m.x_a"}) == {"m.x_b"}


def test_callers_exclude_the_changed_functions_themselves():
    deps = {"m.x_a": ["m.x_b", "m.x_a"], "m.x_b": ["m.x_a"]}
    assert md.direct_callers(deps, {"m.x_a", "m.x_b"}) == set()


def _reader(base, head):
    return lambda rev, path: base if rev == "base" else head


@pytest.mark.parametrize(
    "path,base,head,expect",
    [
        (
            "setup.cfg",
            "[mutmut]\nsource_paths = a\n",
            "[mutmut]\nsource_paths = b\n",
            True,
        ),
        (
            "setup.cfg",
            "[flake8]\nx=1\n[mutmut]\ns=a\n",
            "[flake8]\nx=2\n[mutmut]\ns=a\n",
            False,
        ),
        ("requirements/mutation-tools.txt", "a", "b", True),
        ("scripts/mutation_diff.py", "a", "b", True),
        ("scripts/mutation_plan.py", "a", "b", True),
        ("scripts/mutation_notes.md", "a", "b", False),
        ("scripts/other.py", "a", "b", False),
        (
            "pyproject.toml",
            "[tool.pytest.ini_options]\naddopts='-q'\n",
            "[tool.pytest.ini_options]\naddopts='-x'\n",
            True,
        ),
        (
            "pyproject.toml",
            "[project]\nversion='1'\n",
            "[project]\nversion='2'\n",
            False,
        ),
        ("tests/unit/test_x.py", "a", "b", False),
    ],
)
def test_full_run_triggers(path, base, head, expect):
    assert bool(md.full_run_reasons([path], _reader(base, head))) is expect


_PROJECT = "[project]\nname = 'boost'\nversion = '%s'\n"
_MUTMUT_TOML = "[tool.mutmut]\ndo_not_mutate = [%s]\n"


@pytest.mark.parametrize(
    "base,head,want",
    [
        # mutmut 3.8.0 reads [tool.mutmut] in preference to setup.cfg, so
        # adding the table changes what every run mutates (review I3)...
        (_PROJECT % "1", _PROJECT % "1" + _MUTMUT_TOML % "'*store*'",
         ["pyproject.toml [tool.mutmut] changed"]),
        # ...and so does changing it
        (_PROJECT % "1" + _MUTMUT_TOML % "'a'", _PROJECT % "1" + _MUTMUT_TOML % "'b'",
         ["pyproject.toml [tool.mutmut] changed"]),
        (_PROJECT % "1" + _MUTMUT_TOML % "'a'", _PROJECT % "1",
         ["pyproject.toml [tool.mutmut] changed"]),
        # an unrelated edit, with the table present and unchanged, is not
        (_PROJECT % "1" + _MUTMUT_TOML % "'a'", _PROJECT % "2" + _MUTMUT_TOML % "'a'", []),
        (_PROJECT % "1", _PROJECT % "2", []),
        # both tables: one reason each
        (_PROJECT % "1",
         _PROJECT % "1" + "[tool.pytest.ini_options]\naddopts = '-x'\n"
         + _MUTMUT_TOML % "'a'",
         ["pyproject.toml [tool.pytest.ini_options] changed",
          "pyproject.toml [tool.mutmut] changed"]),
    ],
)
def test_pyproject_mutmut_table_is_a_trigger(base, head, want):
    assert md.full_run_reasons(["pyproject.toml"], _reader(base, head)) == want


@pytest.mark.parametrize(
    "path,want",
    [
        # mutmut's source_paths is recursive, but diff scope reads only
        # boost_cli/core/*.py: a subpackage would plan 0 shards and pass (M5)
        ("boost_cli/core/pkg/x.py", ["core subpackage file changed: boost_cli/core/pkg/x.py"]),
        ("boost_cli/core/pkg/__init__.py",
         ["core subpackage file changed: boost_cli/core/pkg/__init__.py"]),
        ("boost_cli/core/pkg/deep/y.py",
         ["core subpackage file changed: boost_cli/core/pkg/deep/y.py"]),
        ("boost_cli/core/pkg/notes.md", []),
        ("boost_cli/core/x.py", []),
        ("boost_cli/core/__init__.py", []),
        ("boost_cli/commands/x.py", []),
        # a conftest or a pytest.ini changes how every test runs, the same
        # reason [tool.pytest.ini_options] is a trigger
        ("tests/conftest.py", ["tests/conftest.py changed"]),
        ("tests/langchain/conftest.py", ["tests/langchain/conftest.py changed"]),
        ("conftest.py", ["conftest.py changed"]),
        ("pytest.ini", ["pytest.ini changed"]),
        ("tests/unit/pytest.ini", ["tests/unit/pytest.ini changed"]),
        ("tests/unit/test_conftest.py", []),
        ("tests/unit/pytest.ini.bak", []),
    ],
)
def test_subpackages_conftests_and_pytest_ini_are_triggers(path, want):
    read = _reader("def a():\n    return 1\n", "def a():\n    return 2\n")
    assert md.full_run_reasons([path], read) == want


def test_trigger_file_added_or_deleted_counts():
    assert md.full_run_reasons(
        ["setup.cfg"], lambda rev, p: None if rev == "base" else "[mutmut]\na=1\n"
    )
    assert md.full_run_reasons(
        ["setup.cfg"], lambda rev, p: "[mutmut]\na=1\n" if rev == "base" else None
    )


_CI = "jobs:\n  lint:\n    steps: [{run: %s}]\n  mutation-shard:\n    steps: [{run: %s}]\n"


def test_ci_yml_triggers_only_on_mutation_jobs():
    r = _reader(_CI % ("a", "x"), _CI % ("b", "x"))
    assert md.full_run_reasons([".github/workflows/ci.yml"], r) == []
    r = _reader(_CI % ("a", "x"), _CI % ("a", "y"))
    assert md.full_run_reasons([".github/workflows/ci.yml"], r)


def test_init_and_non_core_files_never_enter_scope():
    read = lambda rev, p: (
        "def a():\n    return 1\n" if rev == "base" else "def a():\n    return 2\n"
    )
    paths = [
        "boost_cli/core/__init__.py",
        "boost_cli/commands/x.py",
        "boost_cli/core/sub/y.py",
        "tests/unit/t.py",
    ]
    assert md.diff_scope(paths, read, {}) == []


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_scope_adds_callers_and_sorts():
    read = lambda rev, p: (
        "def a():\n    return 1\n" if rev == "base" else "def a():\n    return 2\n"
    )
    deps = {"boost_cli.core.store.x_a": ["boost_cli.core.cat.x_z"]}
    assert md.diff_scope(["boost_cli/core/store.py"], read, deps) == [
        "boost_cli.core.cat.x_z",
        "boost_cli.core.store.x_a",
    ]


def test_diff_scope_deleted_file_is_empty():
    read = lambda rev, p: "def a(): pass\n" if rev == "base" else None
    assert md.diff_scope(["boost_cli/core/store.py"], read, {}) == []


def _core(base, head):
    return md.full_run_reasons(["boost_cli/core/x.py"], _reader(base, head))


def test_unparsable_head_is_a_full_run_reason():
    assert _core("def a(): pass\n", "def a(:\n") == [
        "unparsable source: boost_cli/core/x.py (head)"
    ]


def test_unparsable_base_is_a_full_run_reason():
    assert _core("def a(:\n", "def a(): pass\n") == [
        "unparsable source: boost_cli/core/x.py (base)"
    ]


def test_parsable_core_source_and_init_have_no_reason():
    assert _core("def a(): pass\n", "def a(): return 1\n") == []
    assert (
        md.full_run_reasons(["boost_cli/core/__init__.py"], _reader("ok", "def a(:\n"))
        == []
    )


@pytest.mark.parametrize(
    "path,good,bad",
    [
        ("setup.cfg", "[mutmut]\na=1\n", "no section header\n"),
        ("pyproject.toml", "[project]\na=1\n", "a = = 1\n"),
        (".github/workflows/ci.yml", "jobs: {}\n", "jobs: [unclosed\n"),
        (".github/workflows/ci.yml", "jobs: {}\n", "jobs: [a, b]\n"),
        (".github/workflows/ci.yml", "jobs: {}\n", "jobs: 3\n"),
    ],
)
def test_unparsable_config_is_a_reason_not_a_crash(path, good, bad):
    want = [f"{path} unparsable"]
    assert md.full_run_reasons([path], _reader(good, bad)) == want
    assert md.full_run_reasons([path], _reader(bad, good)) == want


@pytest.mark.usefixtures("needs_mutmut")
def test_nested_class_method_uses_mutmuts_dotted_class_key():
    src = "class A:\n    class B:\n        def m(self):\n            return 1\n"
    assert md.changed_functions(src, src.replace("1", "2")) == {"xǁA.Bǁm"}


@pytest.mark.usefixtures("needs_mutmut")
def test_rename_as_delete_plus_add_scopes_only_the_new_file():
    src = "def a():\n    return 1\n"

    def read(rev, p):
        if rev == "base":
            return src if p.endswith("old.py") else None
        return src if p.endswith("new.py") else None

    paths = ["boost_cli/core/old.py", "boost_cli/core/new.py"]
    assert md.diff_scope(paths, read, {}) == ["boost_cli.core.new.x_a"]


# --------------------------------------------------------------------------
# Task 6: counting, packing, scoring, and the gate / compare CLIs
# --------------------------------------------------------------------------


def test_shard_count_follows_the_work():
    assert len(md.pack_functions({"f": 1500}, {})) == 1
    assert len(md.pack_functions({"f": 1501}, {})) == 2
    assert len(md.pack_functions({f"f{i}": 1500 for i in range(40)}, {})) == 16
    assert md.pack_functions({}, {}) == []


def test_packing_is_deterministic():
    c = {f"m.x_{i}": i + 1 for i in range(50)}
    assert md.pack_functions(c, {}, per_shard=100) == md.pack_functions(
        dict(reversed(c.items())), {}, per_shard=100
    )


def test_packing_balances_on_measured_time_not_count():
    # `slow` is a third of the mutants but most of the time: it gets a shard
    # to itself, and the unmeasured ones fall back to the mean per-mutant cost.
    counts = {"m.x_slow": 100, "m.x_a": 100, "m.x_b": 100}
    bins = md.pack_functions(counts, {"m.x_slow": 50.0, "m.x_a": 1.0}, per_shard=150)
    assert sorted(sorted(b) for b in bins) == [["m.x_a", "m.x_b"], ["m.x_slow"]]
    # Unmeasured `b` takes the mean (25.5 ms), so it outweighs measured `a`
    # and is placed first within its bin.
    assert bins[1] == ["m.x_b", "m.x_a"]


def test_packing_keeps_every_function_once():
    c = {f"m.x_{i}": (i % 7) + 1 for i in range(30)}
    bins = md.pack_functions(c, {}, per_shard=10)
    assert sorted(f for b in bins for f in b) == sorted(c)


def test_no_bin_takes_more_mutant_names_than_max_names():
    # `slow` is most of the time, so balancing on time alone hands all twenty
    # cheap functions to the other bin: 2000 names in one shard's argv.
    counts = {"m.x_slow": 100} | {f"m.x_{i:02}": 100 for i in range(20)}
    ms_per = {"m.x_slow": 50.0} | {f"m.x_{i:02}": 1.0 for i in range(20)}
    unbounded = md.pack_functions(counts, ms_per, max_names=10**9)
    assert max(sum(counts[f] for f in b) for b in unbounded) == 2000
    bins = md.pack_functions(counts, ms_per)
    assert max(sum(counts[f] for f in b) for b in bins) <= md.MAX_NAMES == 1500
    assert sorted(f for b in bins for f in b) == sorted(counts)


def test_packing_adds_a_bin_when_no_bin_has_room():
    # ceil(3000 / 1500) is 2, but no two of these fit one 1500-name shard.
    bins = md.pack_functions({"a": 1000, "b": 1000, "c": 1000}, {})
    assert sorted(sorted(b) for b in bins) == [["a"], ["b"], ["c"]]


def test_packing_past_the_shard_cap_overflows_for_the_planner_to_refuse():
    bins = md.pack_functions({f"f{i:02}": 1500 for i in range(17)}, {})
    assert len(bins) == md.MAX_SHARDS
    assert max(len(b) for b in bins) == 2  # 3000 names: mutation_plan goes full


@pytest.mark.usefixtures("needs_mutmut")
def test_mutant_names_are_mutmuts_exact_keys(tmp_path):
    (tmp_path / "setup.cfg").write_text(
        "[mutmut]\nsource_paths = boost_cli/core/\n", encoding="utf-8"
    )
    src = "def a(x):\n    return x + 1\n\n\ndef ab(x):\n    return x - 1\n"
    with md.mutmut_config(tmp_path):
        names = md.mutant_names("boost_cli/core/m.py", src)
        counts = md.mutant_counts("boost_cli/core/m.py", src)
    assert set(names) == {"x_a", "x_ab"}
    assert names["x_a"] == [f"{_A}__mutmut_{i}" for i in range(1, len(names["x_a"]) + 1)]
    assert counts == {f: len(n) for f, n in names.items()}
    # Exact names, so `x_a`'s can never select a mutant of `x_ab`.
    assert {md.function_of(n) for n in names["x_a"]} == {_A}


@pytest.mark.usefixtures("needs_mutmut")
def test_mutmut_restricts_the_clean_run_only_for_exact_names(monkeypatch):
    # Why the diff shards pass exact names: mutmut 3.8.0 looks each name's
    # function up in tests_by_mangled_function_name, whose keys carry no
    # `__mutmut_` suffix, so a `__mutmut_*` glob matches no key, selects no
    # test, and the clean run falls back to the whole unit suite.
    from mutmut.__main__ import tests_for_mutant_names

    # The module, not the `state()` function the package re-exports by name.
    mutmut_state = importlib.import_module("mutmut.state")

    fresh = mutmut_state.MutmutState()
    fresh.tests_by_mangled_function_name[_A] = {"test_a"}
    fresh.tests_by_mangled_function_name[_A + "b"] = {"test_ab"}
    monkeypatch.setattr(mutmut_state, "_state", fresh)
    assert tests_for_mutant_names([_A + "__mutmut_*"]) == set()
    assert tests_for_mutant_names([_A + "__mutmut_1", _A + "__mutmut_2"]) == {"test_a"}


@pytest.mark.parametrize(
    "qualified,path,mangled",
    [
        ("boost_cli.core.store.x_install", "boost_cli/core/store.py", "x_install"),
        ("boost_cli.core.store.x__install", "boost_cli/core/store.py", "x__install"),
        ("boost_cli.core.store.xǁKǁm", "boost_cli/core/store.py", "xǁKǁm"),
        ("boost_cli.core.store.xǁA.Bǁm", "boost_cli/core/store.py", "xǁA.Bǁm"),
    ],
)
def test_split_qualified_round_trips(qualified, path, mangled):
    assert md.split_qualified(qualified) == (path, mangled)
    assert md.qualify(path, mangled) == qualified


@pytest.mark.usefixtures("needs_mutmut")
def test_mutant_counts_uses_mutmuts_own_mutants(tmp_path):
    (tmp_path / "setup.cfg").write_text(
        "[mutmut]\nsource_paths = boost_cli/core/\n", encoding="utf-8"
    )
    (tmp_path / "boost_cli" / "core").mkdir(parents=True)
    src = (
        "def a(x):\n    return x + 1\n"
        "def b():\n    pass\n"
        "class K:\n    def m(self):\n        return 2 if self else 3\n"
    )
    with md.mutmut_config(tmp_path):
        counts = md.mutant_counts("boost_cli/core/m.py", src)
    assert set(counts) == {"x_a", "xǁKǁm"}  # `pass` has nothing to mutate
    assert all(n > 0 for n in counts.values())


@pytest.mark.usefixtures("needs_mutmut")
def test_mutmut_config_is_restored(tmp_path):
    from mutmut import configuration

    (tmp_path / "setup.cfg").write_text(
        "[mutmut]\nsource_paths = boost_cli/core/\n", encoding="utf-8"
    )
    (tmp_path / "boost_cli" / "core").mkdir(parents=True)
    before = configuration._config
    with md.mutmut_config(tmp_path):
        assert configuration._config is not None
    assert configuration._config is before


@pytest.mark.usefixtures("needs_mutmut")
def test_score_counts_like_mutation_gate():
    v = md.score({"a": 1, "b": 0, "c": 33, "d": 34, "e": 36})
    assert (v.killed, v.denominator) == (1, 4) and v.survivors == ["b"] and v.timeouts == ["e"]


@pytest.mark.usefixtures("needs_mutmut")
def test_type_check_catch_is_not_a_kill():
    # mutation_gate.py scores mutmut's `killed` count, which never includes
    # `caught by type check` (37): it sits in the denominator unkilled.
    v = md.score({"a": 1, "b": 37, "c": 3})
    assert (v.killed, v.denominator) == (2, 3)


@pytest.mark.usefixtures("needs_mutmut")
def test_unknown_exit_code_is_unkilled_and_does_not_grow_mutmuts_map():
    from mutmut.stats import status_by_exit_code

    before = dict(status_by_exit_code)
    v = md.score({"a": 1, "b": 99})
    assert (v.killed, v.denominator) == (1, 2)
    assert dict(status_by_exit_code) == before


@pytest.mark.usefixtures("needs_mutmut")
def test_small_scope_fails_on_any_survivor():
    assert not md.passes(md.score({"a": 1, "b": 1, "c": 0}))
    assert md.passes(md.score({"a": 1, "b": 1, "c": 1}))


@pytest.mark.usefixtures("needs_mutmut")
def test_unrun_fails_closed():
    assert not md.passes(md.score({"a": 1, "b": None}))


@pytest.mark.usefixtures("needs_mutmut")
def test_eighty_percent_boundary():
    codes = {str(i): (1 if i < 8 else 0) for i in range(10)}
    assert md.passes(md.score(codes))
    codes["9"] = 0
    codes["7"] = 0
    assert not md.passes(md.score(codes))


@pytest.mark.usefixtures("needs_mutmut")
def test_empty_scope_passes():
    assert md.passes(md.score({}))
    assert md.passes(md.score({"a": 34}))


# -- gate -------------------------------------------------------------------

_A = "boost_cli.core.m.x_a"
_K = "boost_cli.core.m.xǁKǁm"
_SRC = "def a(x):\n    return x + 1\n\n\nclass K:\n    def m(self):\n        return 2\n"


def _write_plan(tmp_path, plan):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return str(path)


def _n(q, count):
    """The exact names the planner writes for `q`'s first `count` mutants."""
    return [f"{q}__mutmut_{i}" for i in range(1, count + 1)]


def _diff_plan(tmp_path, shards, mutants, functions=None, counts=None):
    """A diff plan; `mutants` is required so every test states what it planned.

    `counts` is required in a plan, as the planner always writes it, and is
    derived from the names unless the test means it to disagree with them.
    """
    flat = list(dict.fromkeys(n.rpartition("__mutmut_")[0] for s in shards for n in s))
    if counts is None:
        counts = {q: sum(n.rpartition("__mutmut_")[0] == q for s in shards for n in s)
                  for q in flat}
    spec = {
        "shards": shards,
        "mutants": mutants,
        "functions": functions if functions is not None else flat,
        "counts": counts,
    }
    return _write_plan(
        tmp_path, {"gate_set": "diff", "reasons": ["test"], "sets": {"diff": spec}}
    )


def _meta(source, prefix, index, codes, name="m.py", nested=False):
    d = source / f"{prefix}{index}"
    if nested:
        d = d / "boost_cli" / "core"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.meta").write_text(
        json.dumps({"exit_code_by_key": codes}), encoding="utf-8"
    )


@pytest.fixture
def head_tree(tmp_path):
    core = tmp_path / "head" / "boost_cli" / "core"
    core.mkdir(parents=True)
    (core / "m.py").write_text(_SRC, encoding="utf-8")
    return tmp_path / "head"


def _gate(tmp_path, plan, head_tree, *extra):
    return md.main(
        [
            "gate",
            "--plan",
            plan,
            "--source",
            str(tmp_path / "src"),
            "--prefix",
            "mutation-diff-shard-",
            "--root",
            str(head_tree),
            *extra,
        ]
    )


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_reads_only_in_scope_keys(tmp_path, head_tree, monkeypatch):
    # shard .meta holds None for out-of-scope keys of the same file -> ignored, exit 0
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2)
    _meta(
        tmp_path / "src",
        "mutation-diff-shard-",
        0,
        {
            f"{_A}__mutmut_1": 1,
            f"{_A}__mutmut_2": 3,
            "boost_cli.core.m.x_ab__mutmut_1": None,  # prefix-alike, out of scope
            f"{_K}__mutmut_1": None,
        },
    )
    assert _gate(tmp_path, plan, head_tree) == 0


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_fails_and_annotates_a_survivor(tmp_path, head_tree, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    plan = _diff_plan(tmp_path, [_n(_A, 1), _n(_K, 2)], 3)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_K}__mutmut_1": None})
    _meta(tmp_path / "src", "mutation-diff-shard-", 1,
          {f"{_A}__mutmut_1": None, f"{_K}__mutmut_1": 0, f"{_K}__mutmut_2": 33},
          nested=True)
    assert _gate(tmp_path, plan, head_tree) == 1
    out = capsys.readouterr().out
    warnings = [line for line in out.splitlines() if line.startswith("::warning")]
    assert warnings == [
        f"::warning file=boost_cli/core/m.py,line=6::{_K}: 2 mutants not killed: "
        f"{_K}__mutmut_1 (survived), {_K}__mutmut_2 (no tests)"
    ]
    text = summary.read_text(encoding="utf-8")
    assert "1/3 killed" in text
    assert f"{_K}__mutmut_1" in text and f"{_K}__mutmut_2" in text


def test_gate_has_no_switch_to_silence_its_annotations():
    # It binds on every PR that changes a core function, so a survivor is
    # always posted at its `def`. The switch existed for the advisory shadow
    # run alone.
    with pytest.raises(SystemExit):
        md.main(["gate", "--plan", "p", "--source", "s", "--prefix", "x",
                 "--no-annotations"])


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_annotation_lists_at_most_three(tmp_path, head_tree, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    plan = _diff_plan(tmp_path, [_n(_A, 5)], 5)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_{i}": 0 for i in range(1, 6)})
    assert _gate(tmp_path, plan, head_tree) == 1
    (warning,) = [x for x in capsys.readouterr().out.splitlines()
                  if x.startswith("::warning")]
    assert warning.startswith("::warning file=boost_cli/core/m.py,line=1::")
    assert "5 mutants not killed" in warning
    assert warning.count("__mutmut_") == 3


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_missing_shard_is_not_a_pass(tmp_path, head_tree, capsys):
    plan = _diff_plan(tmp_path, [_n(_A, 1), _n(_K, 1)], 2)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    assert _gate(tmp_path, plan, head_tree) == 2
    assert "shard 1: no artifact at" in capsys.readouterr().out


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_unrun_in_scope_key_is_exit_2(tmp_path, head_tree):
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": None})
    assert _gate(tmp_path, plan, head_tree) == 2


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_function_with_no_keys_is_exit_2(tmp_path, head_tree, capsys):
    # The planner counted mutants for it; a shard that produced none ran
    # something else, and scoring the rest would pass on a subset.
    plan = _diff_plan(tmp_path, [_n(_A, 1) + _n(_K, 1)], 2)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    assert _gate(tmp_path, plan, head_tree) == 2
    assert f"no mutants of {_K} (planned, never run)" in capsys.readouterr().out


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_fewer_mutants_than_planned_is_exit_2(tmp_path, head_tree):
    plan = _diff_plan(tmp_path, [_n(_A, 3)], 3)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 1})
    assert _gate(tmp_path, plan, head_tree) == 2


def test_gate_without_a_diff_set_is_exit_2(tmp_path, head_tree):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"gate_set": "full", "reasons": [], "sets": {}}),
                    encoding="utf-8")
    assert _gate(tmp_path, str(path), head_tree) == 2


def test_gate_empty_scope_passes_with_no_artifacts(tmp_path, head_tree):
    plan = _diff_plan(tmp_path, [], 0, functions=[])
    assert _gate(tmp_path, plan, head_tree) == 0


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_honours_min_and_small(tmp_path, head_tree, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    plan = _diff_plan(tmp_path, [_n(_A, 3)], 3)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 1, f"{_A}__mutmut_3": 0})
    assert _gate(tmp_path, plan, head_tree) == 1
    assert _gate(tmp_path, plan, head_tree, "--small", "3", "--min", "60") == 0


@pytest.mark.parametrize(
    "src,mangled,line",
    [
        (_SRC, "x_a", 1),
        (_SRC, "xǁKǁm", 6),
        ("class A:\n    class B:\n        def m(self): pass\n", "xǁA.Bǁm", 3),
        ("def a(:\n", "x_a", None),
        (_SRC, "x_gone", None),
    ],
)
@pytest.mark.usefixtures("needs_mutmut")
def test_def_line(src, mangled, line):
    assert md.def_line(src, mangled) == line


# -- compare ----------------------------------------------------------------


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_flags_a_flip_and_excludes_timeouts(tmp_path, capsys):
    plan = _diff_plan(tmp_path, [_n(_A, 4)], 4)
    _meta(tmp_path / "full", "mutation-full-shard-", 0,
          {f"{_A}__mutmut_{i}": None for i in range(1, 5)} | {"other": 0})
    _meta(tmp_path / "full", "mutation-full-shard-", 1,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 0, f"{_A}__mutmut_3": 36,
           f"{_A}__mutmut_4": 33, "other": None})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 3, f"{_A}__mutmut_2": 1, f"{_A}__mutmut_3": 1,
           f"{_A}__mutmut_4": 0})
    rc = md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                  "--diff-source", str(tmp_path / "diff")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "agree 2, disagree 1, excluded-timeouts 1" in out
    assert f"{_A}__mutmut_2: full=survived diff=killed" in out
    assert f"{_A}__mutmut_3" in out  # the excluded timeout is listed too


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_agreement_exits_0(tmp_path, capsys):
    plan = _diff_plan(tmp_path, [_n(_A, 1)], 1)
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {f"{_A}__mutmut_1": 1})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 0
    assert "agree 1, disagree 0, excluded-timeouts 0" in capsys.readouterr().out


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_counts_a_key_missing_from_the_full_run_as_disagreement(tmp_path, capsys):
    plan = _diff_plan(tmp_path, [_n(_A, 1)], 1)
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {f"{_A}__mutmut_1": None})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 1
    assert "full=not checked diff=killed" in capsys.readouterr().out


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_with_no_full_shards_is_exit_2(tmp_path):
    plan = _diff_plan(tmp_path, [_n(_A, 1)], 1)
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    (tmp_path / "full").mkdir()
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 2


def test_gate_runs_as_a_script(tmp_path):
    # A fresh process, as CI runs it: nothing has registered the module first.
    plan = _diff_plan(tmp_path, [], 0, functions=[])
    proc = subprocess.run(
        [sys.executable, str(_P), "gate", "--plan", plan, "--source",
         str(tmp_path / "src"), "--prefix", "mutation-diff-shard-"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0/0 killed" in proc.stdout


# -- fix round 1: the gate validates the plan before it scores --------------

_PA = "boost_cli.core.m.x_a__mutmut_1"


@pytest.mark.parametrize(
    "spec,meta,complaint",
    [
        # Each of the first five exited 0 before validation (review I-1).
        ({}, None, "shards"),
        ({"shards": None, "mutants": 0, "functions": []}, None, "shards"),
        ({"shards": [], "mutants": "12", "functions": []}, None, "mutants"),
        # 1 of N keys present: with no integer count nothing noticed the gap,
        # and the gate printed 1/1 killed, PASS.
        ({"shards": [[_PA]], "mutants": None, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "mutants"),
        ({"shards": [[_PA], []], "mutants": 1, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "shard 1"),
        # ...and the neighbours of those shapes.
        ({"shards": [[_PA]], "mutants": True, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "mutants"),
        ({"shards": [], "mutants": -1, "functions": []}, None, "mutants"),
        # `mutants: 0` with work planned would make the `<` check vacuous.
        ({"shards": [[_PA]], "mutants": 0, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "mutants"),
        ({"shards": [], "mutants": 3, "functions": []}, None, "mutants"),
        ({"shards": [[_PA, 7]], "mutants": 1, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "shard 0"),
        ({"shards": [_PA], "mutants": 1, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "shard 0"),
        ({"shards": [], "mutants": 0}, None, "functions"),
        ({"shards": [], "mutants": 0, "functions": [None]}, None, "functions"),
        ({"shards": [], "mutants": 0, "functions": "x"}, None, "functions"),
        ([], None, "sets.diff"),
        # `counts` is required: the planner always writes it, and without it
        # one function's shortfall can hide behind another's surplus.
        ({"shards": [[_PA]], "mutants": 1, "functions": [_A]},
         {f"{_A}__mutmut_1": 1}, "counts"),
        ({"shards": [], "mutants": 0, "functions": []}, None, "counts"),
        # Exact names only: a glob would put mutmut's clean run back on the
        # whole unit suite, and a name the gate cannot split is unscorable.
        ({"shards": [[f"{_A}__mutmut_*"]], "mutants": 1, "functions": [_A],
          "counts": {_A: 1}}, {f"{_A}__mutmut_1": 1}, "not an exact mutant name"),
        ({"shards": [[f"{_A}__mutmut_0"]], "mutants": 1, "functions": [_A],
          "counts": {_A: 1}}, None, "not an exact mutant name"),
        ({"shards": [[f"{_A}__mutmut_1\nx__mutmut_1"]], "mutants": 1,
          "functions": [_A], "counts": {_A: 1}}, None, "not an exact mutant name"),
        ({"shards": [[_PA, _PA]], "mutants": 2, "functions": [_A],
          "counts": {_A: 2}}, None, "named twice"),
        # The gate reads a function from the one shard that ran it.
        ({"shards": [[_PA], [f"{_A}__mutmut_2"]], "mutants": 2, "functions": [_A],
          "counts": {_A: 2}}, None, "split across shards 0 and 1"),
    ],
)
def test_gate_refuses_a_malformed_diff_set(tmp_path, head_tree, capsys, spec, meta, complaint):
    plan = _write_plan(tmp_path, {"gate_set": "diff", "sets": {"diff": spec}})
    if meta is not None:
        _meta(tmp_path / "src", "mutation-diff-shard-", 0, meta)
    assert _gate(tmp_path, plan, head_tree) == 2
    out = capsys.readouterr().out
    assert "malformed plan" in out and complaint in out, out


@pytest.mark.parametrize("plan", [[], "diff", {"sets": []}, {"sets": None}])
def test_gate_refuses_a_plan_that_is_not_a_mapping(tmp_path, head_tree, capsys, plan):
    assert _gate(tmp_path, _write_plan(tmp_path, plan), head_tree) == 2
    assert "malformed plan" in capsys.readouterr().out


def test_compare_refuses_a_malformed_diff_set(tmp_path, capsys):
    plan = _write_plan(tmp_path, {"sets": {"diff": {"shards": None}}})
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "f"),
                    "--diff-source", str(tmp_path / "d")]) == 2
    assert "malformed plan" in capsys.readouterr().out


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_per_function_counts_catch_an_offsetting_shortfall(tmp_path, head_tree, capsys):
    # The total matches (3 == 3), but `a` lost a mutant and `K.m` gained one:
    # only per-function counts can tell (review M-4).
    plan = _diff_plan(tmp_path, [_n(_A, 2) + _n(_K, 1)], 3)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_K}__mutmut_1": 1, f"{_K}__mutmut_2": 1})
    assert _gate(tmp_path, plan, head_tree) == 2
    out = capsys.readouterr().out
    assert (f"{_A}: planner counted 2 mutants; shards hold 1 of them, "
            f"missing {_A}__mutmut_2") in out
    # And the surplus is named too: a mutant of a scoped function that the
    # planner never named was never run, so `K.m` would score on a subset.
    assert f"{_K}: shard 0 holds 1 mutants the planner never named: {_K}__mutmut_2" in out


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_reads_exactly_the_planned_names(tmp_path, head_tree, monkeypatch, capsys):
    # Same count, different mutants: the shard ran 1 and 3 where the plan
    # named 1 and 2. A count alone would score it 2/2 killed.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": None, f"{_A}__mutmut_3": 1})
    assert _gate(tmp_path, plan, head_tree) == 2
    out = capsys.readouterr().out
    assert f"never named: {_A}__mutmut_3" in out
    assert "INCOMPLETE" in out


@pytest.mark.parametrize(
    "counts",
    [
        {_A: 1},              # sums to 1, the plan says 2 and names 2
        {_A: 3},              # sums to 3, the shard names 2
        {_A: 1, "other": 1},  # keyed by a function no shard runs
        {_A: "2"},
        {_A: 0},
        [_A],
    ],
)
def test_gate_refuses_inconsistent_counts(tmp_path, head_tree, capsys, counts):
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2, counts=counts)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 1})
    assert _gate(tmp_path, plan, head_tree) == 2
    out = capsys.readouterr().out
    assert "malformed plan" in out and "counts" in out


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_with_exact_counts_passes(tmp_path, head_tree):
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2, counts={_A: 2})
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 1})
    assert _gate(tmp_path, plan, head_tree) == 0


# -- fix round 1: escaping (review M-1) and compare ordering (M-2) ----------


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_escapes_the_annotation_file_property(tmp_path, head_tree, monkeypatch, capsys):
    # A PR-controlled file name must not be able to inject `,line=9` (or a
    # newline) into the workflow command's properties.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    q = "boost_cli.core.a,line=9.x_f"
    plan = _diff_plan(tmp_path, [_n(q, 1)], 1)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0, {f"{q}__mutmut_1": 0},
          name="a,line=9.py")
    assert _gate(tmp_path, plan, head_tree) == 1
    (warning,) = [x for x in capsys.readouterr().out.splitlines()
                  if x.startswith("::warning")]
    assert warning.startswith("::warning file=boost_cli/core/a%2Cline=9.py,line=1::")


def test_gate_escapes_raw_keys_on_every_output_line(tmp_path, head_tree, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    plan = _diff_plan(tmp_path, [[_PA]], 1)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1\n::error::injected": None})
    assert _gate(tmp_path, plan, head_tree) == 2
    out = capsys.readouterr().out
    assert not any(line.startswith("::error") for line in out.splitlines()), out
    assert "%0A::error::injected" in out


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_escapes_raw_keys(tmp_path, capsys):
    plan = _diff_plan(tmp_path, [[_PA]], 1)
    key = f"{_A}__mutmut_1\n::error::injected"
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {key: 0})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, {key: 1})
    # 2, not 1: the diff side never ran the planned name, which is a missing
    # result before it is a disagreement.
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 2
    out = capsys.readouterr().out
    assert not any(line.startswith("::error") for line in out.splitlines()), out
    assert "%0A::error::injected" in out


@pytest.mark.usefixtures("needs_mutmut")
def test_compare_counts_a_one_sided_timeout_as_disagreement(tmp_path, capsys):
    # Absent on one side is a missing result, not a timeout to excuse (M-2).
    plan = _diff_plan(tmp_path, [_n(_A, 2)], 2)
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {f"{_A}__mutmut_1": 1})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_A}__mutmut_2": 36})
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 1
    out = capsys.readouterr().out
    assert "agree 1, disagree 1, excluded-timeouts 0" in out
    assert "full=absent diff=timeout" in out
