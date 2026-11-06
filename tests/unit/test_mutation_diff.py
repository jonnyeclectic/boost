# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
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


#: mutmut's status names for the exit codes these tests write, as
#: `status_by_exit_code` holds them (pinned against mutmut itself below). The
#: comparison and the scoped verdicts only need the name of each code, so with
#: this table they run in every `tests` cell -- which has no mutmut -- and not
#: only in `mutation-plan`.
_STATUS = {None: "not checked", 0: "survived", 1: "killed", 3: "killed", 5: "no tests",
           33: "no tests", 34: "skipped", 36: "timeout", 37: "caught by type check"}


@pytest.fixture
def statuses(monkeypatch):
    """`status_of` without mutmut, from `_STATUS`; anything else is suspicious."""
    monkeypatch.setattr(md, "status_of", lambda code: _STATUS.get(code, "suspicious"))


@pytest.mark.usefixtures("needs_mutmut")
def test_the_status_table_is_mutmuts():
    from mutmut.stats import status_by_exit_code

    before = dict(status_by_exit_code)
    for code in [*_STATUS, 99]:
        assert md.status_of(code) == _STATUS.get(code, "suspicious"), code
    assert dict(status_by_exit_code) == before


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
        "assert m.evidence_status(problems=False, disagree=0, compared=0, functions=0,"
        " full_ok=True, diff_ok=True) == 'VACUOUS'\n"
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
_PYTEST_TOML = "[tool.pytest]\naddopts = [%s]\n"


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
        # pytest 9's native [tool.pytest] table configures every test run too:
        # added, changed, removed...
        (_PROJECT % "1", _PROJECT % "1" + _PYTEST_TOML % "'-x'",
         ["pyproject.toml [tool.pytest] changed"]),
        (_PROJECT % "1" + _PYTEST_TOML % "'-q'", _PROJECT % "1" + _PYTEST_TOML % "'-x'",
         ["pyproject.toml [tool.pytest] changed"]),
        (_PROJECT % "1" + _PYTEST_TOML % "'-q'", _PROJECT % "1",
         ["pyproject.toml [tool.pytest] changed"]),
        # ...but not by an unrelated edit, and an ini_options edit is reported
        # once, under its own name
        (_PROJECT % "1" + _PYTEST_TOML % "'-q'", _PROJECT % "2" + _PYTEST_TOML % "'-q'", []),
        (_PROJECT % "1" + "[tool.pytest.ini_options]\naddopts = '-q'\n",
         _PROJECT % "1" + "[tool.pytest.ini_options]\naddopts = '-x'\n",
         ["pyproject.toml [tool.pytest.ini_options] changed"]),
        # a `tool` or `tool.pytest` that is no table is an unparsable config,
        # not an AttributeError out of the planner
        (_PROJECT % "1", "tool = 3\n" + _PROJECT % "1", ["pyproject.toml unparsable"]),
        (_PROJECT % "1", "[tool]\npytest = 'x'\n", ["pyproject.toml unparsable"]),
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
        # pytest's other config files, wherever they sit
        (".pytest.ini", [".pytest.ini changed"]),
        ("pytest.toml", ["pytest.toml changed"]),
        (".pytest.toml", [".pytest.toml changed"]),
        ("tests/unit/pytest.toml", ["tests/unit/pytest.toml changed"]),
        ("tests/unit/pytest.toml.bak", []),
        # the test tree's shared support reaches every test, as conftest does
        ("tests/_tapped_support.py", ["test support changed: tests/_tapped_support.py"]),
        ("tests/make_fixture.py", ["test support changed: tests/make_fixture.py"]),
        # ...but only at the top of tests/, and only Python
        ("tests/unit/_helpers.py", []),
        ("tests/unit/make_fixture.py", []),
        ("tests/_notes.md", []),
        ("tests/test_make_fixture.py", []),
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
        # a top level that is no mapping has no `jobs` to read: an
        # AttributeError out of the planner before it was a reason
        (".github/workflows/ci.yml", "jobs: {}\n", "- a\n"),
        (".github/workflows/ci.yml", "jobs: {}\n", "3\n"),
        (".github/workflows/ci.yml", "jobs: {}\n", '"text"\n'),
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


@pytest.mark.usefixtures("needs_mutmut")
def test_gate_no_annotations_keeps_the_verdict_and_summary(
        tmp_path, head_tree, monkeypatch, capsys):
    # Shadow mode: the diff gate decides nothing yet, so it must not post a
    # warning on every changed function of every PR -- but its verdict, exit
    # code and summary are the data the shadow report compares.
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    plan = _diff_plan(tmp_path, [_n(_A, 1), _n(_K, 2)], 3)
    _meta(tmp_path / "src", "mutation-diff-shard-", 0,
          {f"{_A}__mutmut_1": 1, f"{_K}__mutmut_1": None})
    _meta(tmp_path / "src", "mutation-diff-shard-", 1,
          {f"{_A}__mutmut_1": None, f"{_K}__mutmut_1": 0, f"{_K}__mutmut_2": 33})
    assert _gate(tmp_path, plan, head_tree, "--no-annotations") == 1
    out = capsys.readouterr().out
    assert "::" not in out, out
    assert "mutation diff gate: FAIL" in out
    text = summary.read_text(encoding="utf-8")
    assert "1/3 killed" in text
    assert f"{_K}__mutmut_1" in text and f"{_K}__mutmut_2" in text


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


@pytest.mark.usefixtures("statuses")
def test_compare_agreement_over_one_mutant_is_vacuous(tmp_path, capsys):
    # This exited 0 before, and 0 read as agreement: one mutant agreeing says
    # nothing about whether the diff gate measures what the full gate does.
    plan = _diff_plan(tmp_path, [_n(_A, 1)], 1)
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {f"{_A}__mutmut_1": 1})
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, {f"{_A}__mutmut_1": 1})
    assert md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff")]) == 3
    out = capsys.readouterr().out
    assert "agree 1, disagree 0, excluded-timeouts 0" in out
    assert "shadow evidence: VACUOUS — compared 1 mutants over 1 functions" in out


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


# -- shadow evidence: what one comparison counts for -------------------------

_B = "boost_cli.core.m.x_b"
_STATUS_ORDER = ["INCOMPLETE", "DISAGREE", "ALARM", "VACUOUS", "AGREE"]


def _facts(status):
    """The weakest facts that produce `status` on their own."""
    base = {"problems": False, "disagree": 0, "compared": md.EVIDENCE_MIN_MUTANTS,
            "functions": md.EVIDENCE_MIN_FUNCTIONS, "full_ok": True, "diff_ok": True}
    return base | {"INCOMPLETE": {"problems": True}, "DISAGREE": {"disagree": 1},
                   "ALARM": {"diff_ok": False}, "VACUOUS": {"compared": 0},
                   "AGREE": {}}[status]


def test_the_status_names_and_exit_codes():
    assert set(md.STATUSES) == set(_STATUS_ORDER) == set(md.COMPARE_EXIT)
    assert md.COMPARE_EXIT == {"AGREE": 0, "DISAGREE": 1, "ALARM": 1, "INCOMPLETE": 2,
                               "VACUOUS": 3}
    # 1 is an uncaught exception's exit, 2 argparse's: VACUOUS has its own.
    assert md.COMPARE_EXIT["VACUOUS"] not in (0, 1, 2)


@pytest.mark.parametrize("strong", _STATUS_ORDER)
@pytest.mark.parametrize("weak", _STATUS_ORDER)
def test_the_more_serious_status_wins(strong, weak):
    # Every pair of statuses' facts at once: the earlier in the order wins.
    a, b = _facts(strong), _facts(weak)
    both = {"problems": a["problems"] or b["problems"],
            "disagree": max(a["disagree"], b["disagree"]),
            "compared": min(a["compared"], b["compared"]),
            "functions": min(a["functions"], b["functions"]),
            "full_ok": a["full_ok"] and b["full_ok"], "diff_ok": a["diff_ok"] and b["diff_ok"]}
    want = min(strong, weak, key=_STATUS_ORDER.index)
    assert md.evidence_status(**both) == want
    assert md.evidence_status(**a) == strong


@pytest.mark.parametrize("compared, functions, status", [
    (199, 3, "VACUOUS"), (200, 3, "AGREE"), (200, 2, "VACUOUS"), (10_000, 2, "VACUOUS"),
    (0, 0, "VACUOUS"), (201, 4, "AGREE"),
])
def test_the_vacuous_thresholds_are_inclusive(compared, functions, status):
    assert (md.EVIDENCE_MIN_MUTANTS, md.EVIDENCE_MIN_FUNCTIONS) == (200, 3)
    assert md.evidence_status(problems=False, disagree=0, compared=compared,
                              functions=functions, full_ok=True, diff_ok=True) == status


def test_an_alarm_is_either_direction_and_a_shared_fail_is_not_one():
    kw = {"problems": False, "disagree": 0, "compared": 500, "functions": 9}
    assert md.evidence_status(**kw, full_ok=False, diff_ok=True) == "ALARM"
    assert md.evidence_status(**kw, full_ok=True, diff_ok=False) == "ALARM"
    assert md.evidence_status(**kw, full_ok=False, diff_ok=False) == "AGREE"


def test_compare_and_gate_share_their_thresholds(monkeypatch, tmp_path):
    import argparse

    got = {}
    real = argparse.ArgumentParser.parse_args

    def capture(self, args=None, namespace=None):
        ns = real(self, args, namespace)
        got[ns.cmd] = (ns.min, ns.small)
        raise SystemExit(0)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    for argv in (["gate", "--plan", "p", "--source", "s", "--prefix", "x"],
                 ["compare", "--plan", "p", "--full-source", "f", "--diff-source", "d"]):
        with pytest.raises(SystemExit):
            md.main(argv)
    assert got == {"gate": (80.0, 10), "compare": (80.0, 10)}


def _big(tmp_path, counts, *, full=None, diff=None, extra_full=None):
    """A diff plan of `counts` mutants per function, all killed on both sides
    bar the overrides, in one diff shard and one full shard (both m.py)."""
    names = [n for q, c in counts.items() for n in _n(q, c)]
    plan = _diff_plan(tmp_path, [names], len(names))
    _meta(tmp_path / "full", "mutation-full-shard-", 0,
          dict.fromkeys(names, 1) | (full or {}) | (extra_full or {}))
    _meta(tmp_path / "diff", "mutation-diff-shard-", 0, dict.fromkeys(names, 1) | (diff or {}))
    return plan


def _compare(tmp_path, plan, *extra):
    return md.main(["compare", "--plan", plan, "--full-source", str(tmp_path / "full"),
                    "--diff-source", str(tmp_path / "diff"), *extra])


def _evidence_line(out):
    (line,) = [x for x in out.splitlines() if x.startswith("shadow evidence: ")]
    return line


def test_the_run_41387907117_report_is_vacuous_not_agreement(tmp_path, capsys):
    # The one shadow report on record: a diff set with no shards beside a full
    # shard, "0/0 killed (100.0%) over 0 functions", and compare exit 0. It
    # now exits 3, and the shadow step reads 3 as a notice, not a green.
    plan = _diff_plan(tmp_path, [], 0, functions=[])
    _meta(tmp_path / "full", "mutation-full-shard-", 0, {f"{_A}__mutmut_1": 1})
    (tmp_path / "diff").mkdir()
    out_json = tmp_path / "e.json"
    assert _compare(tmp_path, plan, "--json", str(out_json)) == 3
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "agree 0, disagree 0, excluded-timeouts 0"
    assert _evidence_line(out) == (
        "shadow evidence: VACUOUS — compared 0 mutants over 0 functions (counts toward "
        "the bar only at >= 200 over >= 3)")
    assert json.loads(out_json.read_text(encoding="utf-8"))["status"] == "VACUOUS"


@pytest.mark.usefixtures("statuses")
def test_two_hundred_agreeing_over_three_functions_is_agree(tmp_path, capsys):
    plan = _big(tmp_path, {_A: 70, _B: 70, _K: 60},
                full={f"{_A}__mutmut_1": 0}, diff={f"{_A}__mutmut_1": 0})
    assert _compare(tmp_path, plan) == 0
    out = capsys.readouterr().out
    assert "agree 200, disagree 0, excluded-timeouts 0" in out
    assert ("scoped verdicts over 3 functions: full PASS (199/200), diff PASS (199/200)"
            in out)
    assert "ALARM" not in out
    assert _evidence_line(out) == ("shadow evidence: AGREE — compared 200 mutants over 3 "
                                   "functions (counts toward the bar)")


@pytest.mark.usefixtures("statuses")
@pytest.mark.parametrize("counts", [{_A: 100, _B: 100}, {_A: 70, _B: 70, _K: 59}],
                         ids=["200-over-2", "199-over-3"])
def test_short_of_either_threshold_is_vacuous(tmp_path, capsys, counts):
    assert _compare(tmp_path, _big(tmp_path, counts)) == 3
    assert "shadow evidence: VACUOUS" in _evidence_line(capsys.readouterr().out)


@pytest.mark.usefixtures("statuses")
def test_a_one_sided_timeout_that_flips_the_scoped_verdict_is_an_alarm(tmp_path, capsys):
    # Every compared mutant agrees -- the timeout is excluded -- but under ten
    # mutants every one must be killed, so the full run fails these functions
    # where the diff run passes them. Bound, the diff gate would pass this.
    plan = _big(tmp_path, {_A: 5}, full={f"{_A}__mutmut_5": 36})
    assert _compare(tmp_path, plan) == 1
    out = capsys.readouterr().out
    assert "agree 4, disagree 0, excluded-timeouts 1" in out
    assert "scoped verdicts over 1 functions: full FAIL (4/5), diff PASS (5/5)" in out
    assert ("ALARM: over the diff scope the full run FAILS and the diff run PASSES — "
            "bound, the diff gate would have passed what the full gate refuses on these "
            "same functions") in out
    assert "shadow evidence: ALARM" in _evidence_line(out)


@pytest.mark.usefixtures("statuses")
def test_the_mirror_alarm_names_the_other_direction(tmp_path, capsys):
    plan = _big(tmp_path, {_A: 5}, diff={f"{_A}__mutmut_5": 36})
    assert _compare(tmp_path, plan) == 1
    out = capsys.readouterr().out
    assert "full PASS (5/5), diff FAIL (4/5)" in out
    assert ("ALARM: over the diff scope the full run PASSES and the diff run FAILS — "
            "bound, the diff gate would have refused what the full gate passes") in out


@pytest.mark.usefixtures("statuses")
def test_a_survivor_outside_the_scope_is_not_an_alarm(tmp_path, capsys):
    # The full shard holds the whole file; a survivor in a function the PR did
    # not touch can fail the whole-codebase gate, but it is not the diff
    # gate's business and must not read as the diff gate's miss.
    plan = _big(tmp_path, {_A: 70, _B: 70, _K: 60},
                extra_full={"boost_cli.core.m.x_c__mutmut_1": 0,
                            "boost_cli.core.m.x_ab__mutmut_1": 0})
    assert _compare(tmp_path, plan) == 0
    out = capsys.readouterr().out
    assert "full PASS (200/200), diff PASS (200/200)" in out
    assert "x_c" not in out and "x_ab" not in out
    assert "ALARM" not in out


@pytest.mark.usefixtures("statuses")
def test_a_disagreement_outranks_everything_but_a_missing_result(tmp_path, capsys):
    plan = _big(tmp_path, {_A: 70, _B: 70, _K: 60}, full={f"{_A}__mutmut_1": 0})
    assert _compare(tmp_path, plan) == 1
    assert "shadow evidence: DISAGREE — compared 200 mutants" in _evidence_line(
        capsys.readouterr().out)


@pytest.mark.usefixtures("statuses")
@pytest.mark.parametrize("shape", ["agree", "vacuous", "alarm", "disagree", "incomplete",
                                   "malformed"])
def test_the_json_says_what_the_report_says_on_every_exit(tmp_path, capsys, monkeypatch, shape):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "41900000001")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("SHADOW_HEAD_SHA", "d" * 40)
    big = {_A: 70, _B: 70, _K: 60}
    plan = {
        "agree": lambda: _big(tmp_path, big),
        "vacuous": lambda: _big(tmp_path, {_A: 3}),
        "alarm": lambda: _big(tmp_path, {_A: 5}, full={f"{_A}__mutmut_5": 36}),
        "disagree": lambda: _big(tmp_path, big, diff={f"{_A}__mutmut_2": 0}),
        "incomplete": lambda: _diff_plan(tmp_path, [_n(_A, 1)], 1),
        "malformed": lambda: _write_plan(tmp_path, {"sets": {"diff": {"shards": None}}}),
    }[shape]()
    out_json = tmp_path / "evidence.json"
    rc = _compare(tmp_path, plan, "--json", str(out_json))
    printed = _evidence_line(capsys.readouterr().out).split()[2]
    rec = json.loads(out_json.read_text(encoding="utf-8"))
    assert rec["status"] == printed == shape.upper().replace("MALFORMED", "INCOMPLETE")
    assert rc == md.COMPARE_EXIT[rec["status"]]
    assert md._evidence_problems(rec) == []
    assert {k: rec[k] for k in ("schema", "event", "sha", "head_sha", "run_id",
                                "run_attempt", "min_mutants", "min_functions")} == {
        "schema": 2, "event": "schedule", "sha": "c" * 40, "head_sha": "d" * 40,
        "run_id": "41900000001", "run_attempt": "1", "min_mutants": 200, "min_functions": 3}
    # The scope is the digest of exactly the names compare scored; a plan it
    # could not read scored none.
    planned = json.loads(Path(plan).read_text(encoding="utf-8"))["sets"]["diff"]["shards"]
    assert rec["scope"] == md.scope_digest(
        [] if shape == "malformed" else [n for shard in planned for n in shard])
    if shape == "agree":
        assert {k: rec[k] for k in ("compared_mutants", "compared_functions", "agree",
                                    "disagree", "excluded_timeouts", "full_scoped",
                                    "diff_scoped")} == {
            "compared_mutants": 200, "compared_functions": 3, "agree": 200, "disagree": 0,
            "excluded_timeouts": 0, "full_scoped": "PASS", "diff_scoped": "PASS"}
    if shape == "malformed":
        assert (rec["full_scoped"], rec["diff_scoped"]) == (None, None)


@pytest.mark.usefixtures("statuses")
def test_a_nightly_shaped_plan_compares_and_records_its_base(tmp_path, capsys, monkeypatch):
    # What the nightly's shadow step hands compare: both sets, the diff one
    # marked advisory and carrying its base, the full one with every shard
    # of the night (here two, one holding m.py and one holding nothing).
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    monkeypatch.setenv("SHADOW_HEAD_SHA", "c" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "41900000002")
    path = Path(_big(tmp_path, {_A: 70, _B: 70, _K: 60}))
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["advisory"] = ["diff"]
    plan["sets"]["diff"]["base"] = "b" * 40
    plan["sets"]["full"] = {"shards": [["boost_cli.core.m.*"], ["boost_cli.core.n.*"]],
                            "mutants": None}
    path.write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "full" / "mutation-full-shard-1").mkdir()
    out_json = tmp_path / "e.json"
    assert _compare(tmp_path, str(path), "--json", str(out_json)) == 0
    assert "shadow evidence: AGREE — compared 200 mutants over 3 functions" in (
        capsys.readouterr().out)
    rec = json.loads(out_json.read_text(encoding="utf-8"))
    assert (rec["status"], rec["base"]) == ("AGREE", "b" * 40)
    assert md._evidence_problems(rec) == []
    assert md.qualifies(rec)


@pytest.mark.usefixtures("statuses")
def test_a_nightly_full_shard_missing_is_incomplete_not_agreement(tmp_path, capsys):
    path = Path(_big(tmp_path, {_A: 70, _B: 70, _K: 60}))
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["sets"]["full"] = {"shards": [["boost_cli.core.m.*"], ["boost_cli.core.n.*"]]}
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert _compare(tmp_path, str(path)) == 2
    assert "shadow evidence: INCOMPLETE" in _evidence_line(capsys.readouterr().out)


def test_the_json_records_the_plans_base_only_when_it_is_a_commit(tmp_path):
    assert md._plan_base({"sets": {"diff": {"base": "d" * 40}}}) == "d" * 40
    for plan in ({"sets": {"diff": {"base": "main"}}}, {"sets": {"diff": {}}}, {"sets": {}},
                 [], {"sets": None}, {"sets": {"diff": []}}):
        assert md._plan_base(plan) is None, plan


# -- evidence: counting reports against the bar -------------------------------

_REPO = 1304281190      # this repository's id, as the artifact listing gives it
_T0 = datetime(2026, 11, 5, tzinfo=UTC)
_SINCE = "2026-11-05T00:00:00Z"
_NOW = _T0 + timedelta(days=20)


def _iso(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Shelf:
    """Downloaded reports and the API listing that names them, as Step 6 saves both."""

    def __init__(self, tmp_path, t0=_T0):
        self.root = tmp_path / "evidence"
        self.root.mkdir()
        self.t0 = t0
        self.artifacts = []

    def add(self, *, branch="loop/topic", head=None, fork=False, expired=False,
            created=None, kept=90, download=True, **over):
        """One listed artifact plus (unless `download=False`) its report.

        By default an AGREE over 400 mutants with its own scope, from a run
        whose listing entry matches it in every field `evidence` checks.
        """
        n = len(self.artifacts) + 1
        artifact_id, run_id = 13200000000 + n, 41900000000 + n
        head = head or "%040x" % (0xA000 + n)
        on_main = branch == md.DEFAULT_BRANCH
        created = created or self.t0 + timedelta(hours=n)
        self.artifacts.append({
            "id": artifact_id, "name": md.EVIDENCE_ARTIFACT, "expired": expired,
            "created_at": _iso(created), "expires_at": _iso(created + timedelta(days=kept)),
            "workflow_run": {"id": run_id, "repository_id": _REPO,
                             "head_repository_id": _REPO + 1 if fork else _REPO,
                             "head_branch": branch, "head_sha": head}})
        rec = {"schema": 2, "status": "AGREE", "compared_mutants": 400,
               "compared_functions": 6, "agree": 400, "disagree": 0, "excluded_timeouts": 0,
               "full_scoped": "PASS", "diff_scoped": "PASS", "min_mutants": 200,
               "min_functions": 3, "base": None,
               "event": "schedule" if on_main else "pull_request",
               # A PR's GITHUB_SHA is its merge commit, new on every run.
               "sha": head if on_main else "%040x" % (0xB000 + n), "head_sha": head,
               "run_id": str(run_id), "run_attempt": "1",
               "scope": md.scope_digest(["scope-%d" % n])} | over
        if download:
            self.write(artifact_id, json.dumps(rec))
        return artifact_id, run_id

    def write(self, artifact_id, body):
        path = self.root / str(artifact_id) / md.EVIDENCE_FILE
        path.parent.mkdir(exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def pages(self, size=100, total=None):
        """The listing as saved pages, inside the reports dir as Step 6 keeps them."""
        paths = []
        for i in range(0, max(len(self.artifacts), 1), size):
            path = self.root / ("listing-%d.json" % (i // size + 1))
            path.write_text(json.dumps({
                "total_count": len(self.artifacts) if total is None else total,
                "artifacts": self.artifacts[i:i + size]}), encoding="utf-8")
            paths.append(path)
        return paths

    def argv(self, *extra, pages=None, since=_SINCE):
        args = ["evidence", "--reports", str(self.root), "--since", since]
        for p in self.pages() if pages is None else pages:
            args += ["--listing", str(p)]
        return args + list(extra)

    def evidence(self, *extra, **kw):
        return md.main(self.argv(*extra, **kw))


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "_now", lambda: _NOW)
    return _Shelf(tmp_path)


def _five(shelf, *, nightly=1):
    for i in range(5):
        shelf.add(branch=md.DEFAULT_BRANCH if i < nightly else "loop/topic-%d" % i)


def _summary(out):
    return out.splitlines()[-1]


def test_five_distinct_comparisons_with_a_nightly_meet_the_bar(shelf, capsys):
    _five(shelf)
    assert shelf.evidence() == 0
    out = capsys.readouterr().out
    assert _summary(out) == (
        "evidence: 5 of 5 AGREE reports from distinct comparisons (1 of 1 from schedule); "
        "5 read, 0 unreadable or unknown, 0 DISAGREE or ALARM")
    assert all(line.startswith("evidence: ") for line in out.splitlines())


def test_one_pr_re_run_after_each_merge_to_main_counts_once(shelf, capsys):
    # The review's case: strict up-to-date checks re-run an open train PR
    # after every merge to main, each time on a new merge commit (GITHUB_SHA)
    # and a new head. Four of those plus one nightly are two comparisons.
    shelf.add(branch=md.DEFAULT_BRANCH)
    for _ in range(4):
        shelf.add(branch="loop/train")
    assert shelf.evidence() == 3
    out = capsys.readouterr().out
    assert _summary(out).startswith(
        "evidence: 2 of 5 AGREE reports from distinct comparisons (1 of 1 from schedule)")
    assert out.count("the same branch as a report already counted -- counted once") == 3


def test_the_same_scope_on_another_branch_counts_once(shelf, capsys):
    _five(shelf)
    shelf.add(branch="loop/again", scope=md.scope_digest(["scope-5"]))
    assert shelf.evidence() == 0
    out = capsys.readouterr().out
    assert "5 of 5 AGREE" in _summary(out)
    assert "the same scope as a report already counted" in out


def test_a_nightly_is_kept_over_an_older_pr_sharing_its_scope(shelf, capsys):
    shared = md.scope_digest(["the-one-pr's-functions"])
    shelf.add(branch="loop/first", scope=shared)
    shelf.add(branch=md.DEFAULT_BRANCH, scope=shared)
    for i in range(3):
        shelf.add(branch="loop/topic-%d" % i)
    assert shelf.evidence() == 3
    assert "4 of 5 AGREE reports from distinct comparisons (1 of 1 from schedule)" in (
        _summary(capsys.readouterr().out))


@pytest.mark.parametrize("status", ["AGREE", "DISAGREE"])
@pytest.mark.parametrize("head_repo", ["fork", "deleted fork"])
def test_a_forks_artifact_is_never_read(shelf, capsys, monkeypatch, status, head_repo):
    # A fork's run uploads whatever JSON its own ci.yml writes: neither its
    # AGREE nor its DISAGREE is evidence.
    for i in range(4):
        shelf.add(branch=md.DEFAULT_BRANCH if i == 0 else "loop/topic-%d" % i)
    artifact_id, _ = shelf.add(branch="main", fork=True, status=status)
    if head_repo == "deleted fork":
        shelf.artifacts[-1]["workflow_run"]["head_repository_id"] = None
        shelf.artifacts[-1]["workflow_run"]["head_branch"] = None
    assert shelf.evidence() == 3
    out = capsys.readouterr().out
    assert "evidence: artifact %d (run " % artifact_id in out
    assert "from another repository -- not read" in out
    assert "4 of 5 AGREE" in _summary(out)


@pytest.mark.parametrize("branch, over, why", [
    ("loop/x", {"run_id": "1"}, "run_id 1, listed run"),
    ("loop/x", {"head_sha": "e" * 40}, "head_sha eeeeeeeeeeee, listed"),
    ("loop/x", {"event": "schedule"}, "says schedule, but its run is not on main's"),
    ("main", {"sha": "e" * 40}, "says schedule, but its run is not on main's"),
    ("main", {"event": "pull_request"}, "says pull_request, but its run is on main"),
], ids=["run", "head", "schedule-on-a-branch", "schedule-off-its-commit", "pr-on-main"])
def test_a_report_that_does_not_match_its_listed_run_is_unknown(shelf, capsys, branch,
                                                                 over, why):
    _five(shelf)
    shelf.add(branch=branch, **over)
    assert shelf.evidence() == 2
    out = capsys.readouterr().out
    assert "does not match its listed run (" in out and why in out
    assert "5 of 5 AGREE" in _summary(out)


def test_an_expired_report_in_the_window_is_unknown(shelf, capsys):
    _five(shelf)
    shelf.add(expired=True, download=False)
    assert shelf.evidence() == 2
    assert "expired before it was read -- it could have been a DISAGREE" in (
        capsys.readouterr().out)


def test_a_report_from_before_the_window_is_not_read(shelf, capsys):
    # E.g. artifact 13127375493, which predates the JSON: listed, never read.
    _five(shelf)
    shelf.add(created=_T0 - timedelta(days=3), expired=True, download=False)
    shelf.add(created=_T0 - timedelta(days=2), status="DISAGREE")
    assert shelf.evidence() == 0
    assert capsys.readouterr().out.count("from before --since -- not read") == 2


def test_a_listed_report_never_downloaded_is_unknown(shelf, capsys):
    _five(shelf)
    artifact_id, _ = shelf.add(download=False)
    assert shelf.evidence() == 2
    assert "listed, but no %d/%s was downloaded" % (artifact_id, md.EVIDENCE_FILE) in (
        capsys.readouterr().out)


def test_a_report_the_listing_does_not_name_is_unknown(shelf, capsys):
    _five(shelf)
    shelf.write(99, "{}")
    assert shelf.evidence() == 2
    assert "evidence: 99/%s: not in the listing -- list again, or remove it" % (
        md.EVIDENCE_FILE) in capsys.readouterr().out


@pytest.mark.parametrize("age_days, kept, rc", [(29, 30, 0), (30, 30, 2), (31, 30, 2),
                                                 (89, 90, 0), (91, 90, 2)])
def test_a_window_older_than_a_report_is_kept_is_unknown(shelf, capsys, age_days, kept, rc):
    # A report from the window's start may have expired out of the listing
    # unseen, and it could have been the DISAGREE that stops the plan.
    since = _NOW - timedelta(days=age_days)
    shelf.t0 = since
    for i in range(5):
        shelf.add(branch=md.DEFAULT_BRANCH if i == 0 else "loop/topic-%d" % i, kept=kept)
    assert shelf.evidence(since=_iso(since)) == rc
    out = capsys.readouterr().out
    assert ("and a report is kept %.1f days" % kept in out) is (rc == 2)


def test_the_shortest_retention_listed_decides_the_window(shelf, capsys):
    _five(shelf)
    shelf.add(kept=19)
    assert shelf.evidence() == 2
    assert "the window opened 20.0 days ago and a report is kept 19.0 days" in (
        capsys.readouterr().out)


def test_every_page_of_the_listing_is_read(shelf, capsys):
    _five(shelf)
    pages = shelf.pages(size=2)
    assert len(pages) == 3
    assert shelf.evidence(pages=pages) == 0
    capsys.readouterr()
    assert shelf.evidence(pages=pages[:2]) == 2
    assert "evidence: listing: the pages list 4 of 5 artifacts: fetch every page" in (
        capsys.readouterr().out)
    assert shelf.evidence(pages=shelf.pages(total=6)) == 2
    assert "list 5 of 6 artifacts" in capsys.readouterr().out


def test_pages_from_two_listings_are_refused(shelf, capsys):
    _five(shelf)
    pages = shelf.pages(size=3)
    page = json.loads(pages[0].read_text(encoding="utf-8")) | {"total_count": 4}
    pages[0].write_text(json.dumps(page), encoding="utf-8")
    assert shelf.evidence(pages=pages) == 2
    assert "the pages disagree on total_count (4, 5): list them again" in (
        capsys.readouterr().out)


@pytest.mark.parametrize("change", [
    lambda a: a.update(name="mutation-weights"),
    lambda a: a.pop("workflow_run"),
    lambda a: a["workflow_run"].update(id="41900000001"),
    lambda a: a["workflow_run"].update(head_sha="main"),
    lambda a: a["workflow_run"].update(head_branch=None),
    lambda a: a.update(expired="no"),
    lambda a: a.update(created_at="yesterday"),
    lambda a: a.update(id=True),
], ids=["name", "no-run", "run-id", "head-sha", "branch", "expired", "created", "id"])
def test_a_listing_entry_not_in_the_apis_shape_is_refused(shelf, capsys, change):
    _five(shelf)
    change(shelf.artifacts[-1])
    assert shelf.evidence() == 2
    assert "evidence: listing: " in capsys.readouterr().out


@pytest.mark.parametrize("body", ["{", "[]", json.dumps({"artifacts": []}),
                                  json.dumps({"total_count": "5", "artifacts": []})])
def test_a_page_that_is_not_the_listing_is_refused(shelf, capsys, body):
    _five(shelf)
    page = shelf.root / "page.json"
    page.write_text(body, encoding="utf-8")
    assert shelf.evidence(pages=[*shelf.pages(), page]) == 2
    assert "evidence: listing: %s: " % page in capsys.readouterr().out


@pytest.mark.parametrize("status, rc", [("AGREE", 3), ("DISAGREE", 1)])
def test_the_probe_is_read_and_never_counted(shelf, capsys, status, rc):
    for i in range(4):
        shelf.add(branch=md.DEFAULT_BRANCH if i == 0 else "loop/topic-%d" % i)
    _, probe = shelf.add(branch="probe/diff-gate-negative", status=status)
    assert shelf.evidence("--probe-run", str(probe)) == rc
    out = capsys.readouterr().out
    assert "4 of 5 AGREE" in _summary(out)
    assert ("the Step 7 probe -- never counted" in out) is (status == "AGREE")


@pytest.mark.parametrize("status, rc", [("AGREE", 3), ("DISAGREE", 1)])
def test_a_merge_queue_run_is_read_and_never_counted(shelf, capsys, status, rc):
    for i in range(4):
        shelf.add(branch=md.DEFAULT_BRANCH if i == 0 else "loop/topic-%d" % i)
    shelf.add(branch="gh-readonly-queue/main/pr-1288-" + "f" * 40, status=status,
              event="merge_group")
    assert shelf.evidence() == rc
    out = capsys.readouterr().out
    assert "4 of 5 AGREE" in _summary(out)
    assert ("merge_group run of merge queue -- a merge-queue run -- never counted" in out) is (
        status == "AGREE")


@pytest.mark.parametrize("over", [
    {"status": "VACUOUS"}, {"status": "INCOMPLETE"},
    # A stored AGREE under today's constants does not count: thresholds only rise.
    {"compared_mutants": 199}, {"compared_functions": 2},
    {"full_scoped": "FAIL"}, {"full_scoped": None, "diff_scoped": None},
], ids=["vacuous", "incomplete", "199", "two-functions", "split-verdicts", "no-verdicts"])
def test_a_report_that_does_not_meet_todays_bar_is_not_counted(shelf, capsys, over):
    for i in range(4):
        shelf.add(branch=md.DEFAULT_BRANCH if i == 0 else "loop/topic-%d" % i)
    shelf.add(branch="loop/weak", **over)
    assert shelf.evidence() == 3
    out = capsys.readouterr().out
    assert "evidence: 4 of 5 AGREE" in out
    assert "does not count" in out


@pytest.mark.parametrize("status", ["DISAGREE", "ALARM"])
def test_a_disagreement_or_alarm_anywhere_stops_the_plan(shelf, capsys, status):
    _five(shelf)
    shelf.add(branch="loop/bad", status=status, compared_mutants=3)
    junk, _ = shelf.add(branch="loop/junk")
    shelf.write(junk, "{")
    assert shelf.evidence() == 1
    assert "1 DISAGREE or ALARM" in _summary(capsys.readouterr().out)


@pytest.mark.parametrize("body", ["{", '"x"', "[]", json.dumps({"schema": True}),
                                  json.dumps({"schema": 1}), "\udc80"])
def test_an_unreadable_report_is_named_and_exits_2(shelf, capsys, body):
    _five(shelf)
    artifact_id, run_id = shelf.add(branch="loop/odd")
    path = shelf.root / str(artifact_id) / md.EVIDENCE_FILE
    if body == "\udc80":
        path.write_bytes(b"\xff")
    else:
        path.write_text(body, encoding="utf-8")
    assert shelf.evidence() == 2
    assert "evidence: artifact %d (run %d): " % (artifact_id, run_id) in (
        capsys.readouterr().out)


@pytest.mark.parametrize("over", [{"sha": "main"}, {"sha": None}, {"head_sha": ""},
                                  {"agree": True}, {"disagree": -1}, {"status": "agree"},
                                  {"full_scoped": "pass"}, {"event": 7}, {"run_id": 7},
                                  {"run_id": "١"}, {"run_id": ""}, {"scope": "x"},
                                  {"scope": "A" * 64}, {"scope": None}])
def test_every_field_is_checked_before_a_report_is_read(shelf, over):
    artifact_id, _ = shelf.add(**over)
    rec = json.loads((shelf.root / str(artifact_id) / md.EVIDENCE_FILE).read_text(
        encoding="utf-8"))
    assert md._evidence_problems(rec) != []


def test_the_reports_the_shelf_writes_are_well_formed(shelf):
    artifact_id, _ = shelf.add()
    rec = json.loads((shelf.root / str(artifact_id) / md.EVIDENCE_FILE).read_text(
        encoding="utf-8"))
    assert md._evidence_problems(rec) == []


def test_a_shortfall_or_no_nightly_exits_3(shelf, capsys):
    _five(shelf, nightly=0)
    assert shelf.evidence() == 3
    assert "(0 of 1 from schedule)" in capsys.readouterr().out
    assert shelf.evidence("--need-schedule", "0") == 0
    assert shelf.evidence("--need", "6", "--need-schedule", "0") == 3


def test_no_reports_no_directory_or_no_time(shelf, tmp_path, capsys):
    assert shelf.evidence() == 3
    assert md.main(["evidence", "--reports", str(tmp_path / "absent"), "--since", _SINCE,
                    "--listing", str(shelf.pages()[0])]) == 2
    assert shelf.evidence(since="last week") == 2
    assert "evidence: --since last week is not an ISO 8601 time" in capsys.readouterr().out


def test_the_listing_and_the_window_start_are_required(shelf):
    for drop in ("--listing", "--since"):
        argv = shelf.argv()
        i = argv.index(drop)
        with pytest.raises(SystemExit) as exc:
            md.main(argv[:i] + argv[i + 2:])
        assert exc.value.code == 2


def test_a_naive_window_start_is_utc():
    assert md._when("2026-11-05T00:00:00") == _T0
    assert md._when("2026-11-05") == _T0
    assert md._when(5) is None


def test_a_hostile_report_or_branch_cannot_start_a_workflow_command(shelf, capsys):
    shelf.add(event="x\n::error::pwned", status="VACUOUS")
    shelf.add(branch="loop/x\n::error::branch")
    shelf.evidence()
    out = capsys.readouterr().out
    assert all(line.startswith("evidence: ") for line in out.splitlines()), out
    assert "%0A::error::pwned" in out
    assert "%0A::error::branch" in out


def test_the_scope_is_the_set_of_names_compared():
    assert md.scope_digest(["b", "a", "a"]) == md.scope_digest(["a", "b"])
    assert md.scope_digest(["a"]) != md.scope_digest(["a", "b"])
    assert md._DIGEST.fullmatch(md.scope_digest([]))


def test_evidence_runs_as_a_script(tmp_path):
    now = datetime.now(UTC)
    shelf = _Shelf(tmp_path, t0=now - timedelta(days=1))
    _five(shelf)
    proc = subprocess.run([sys.executable, str(_P),
                           *shelf.argv(since=_iso(now - timedelta(days=2)))],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


_PLAN_DOC = _P.parents[1] / "docs" / "superpowers" / "plans" / "2026-10-31-ci-speed.md"


def test_the_plan_states_the_bar_the_code_applies():
    # The plan is what a reviewer reads before binding the gate; a number
    # changed in one place and not the other would be a bar nobody applies.
    if not _PLAN_DOC.exists():
        pytest.skip("docs/ not reachable (e.g. the mutants/ copy)")
    text = _PLAN_DOC.read_text(encoding="utf-8")
    for name in ("EVIDENCE_MIN_MUTANTS", "EVIDENCE_MIN_FUNCTIONS", "EVIDENCE_NEED",
                 "EVIDENCE_NEED_SCHEDULE"):
        assert "`%s = %d`" % (name, getattr(md, name)) in text, name
    for status in ("AGREE", "VACUOUS", "ALARM"):
        assert "**%s** (exit %d)" % (status, md.COMPARE_EXIT[status]) in text, status
    assert "**DISAGREE** (exit %d) and **INCOMPLETE** (exit %d)" % (
        md.COMPARE_EXIT["DISAGREE"], md.COMPARE_EXIT["INCOMPLETE"]) in text


def test_task_8_keeps_the_comparison_the_nightly_shadow_needs():
    # Once the diff gate binds, only a full nightly's plan carries both sets,
    # and its advisory diff legs are compared in `mutation`'s shadow step. A
    # checklist that said "remove compare step" would leave up to MAX_SHARDS
    # legs a night that nothing compares, with nothing going red.
    if not _PLAN_DOC.exists():
        pytest.skip("docs/ not reachable (e.g. the mutants/ copy)")
    text = _PLAN_DOC.read_text(encoding="utf-8")
    task8 = text[text.index("### Task 8:"):text.index("### Task 9:")]
    assert "remove compare step" not in task8
    assert "Keep the `diff-gate shadow` step (`mutation_diff.py compare`)" in task8
    assert ("still runs `mutation_diff.py compare` in the `diff-gate shadow` step guarded "
            "on `shadow == 'true'`") in task8
    assert "Keep `diff_plan`'s `shadow` parameter" in task8


def test_the_plan_collects_evidence_the_way_the_cli_counts_it():
    if not _PLAN_DOC.exists():
        pytest.skip("docs/ not reachable (e.g. the mutants/ copy)")
    text = _PLAN_DOC.read_text(encoding="utf-8")
    assert "from distinct commits" not in text
    assert "AGREE reports from distinct comparisons" in text
    assert "evidence/<artifact id>/" in text
    for flag in ("--listing", "--since", "--probe-run"):
        assert flag in text, flag
