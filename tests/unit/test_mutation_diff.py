# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import sys
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[2] / "scripts" / "mutation_diff.py"
_spec = importlib.util.spec_from_file_location("mutation_diff", _P)
md = importlib.util.module_from_spec(_spec)
sys.modules["mutation_diff"] = md
_spec.loader.exec_module(md)


def test_body_edit_is_a_change():
    assert md.changed_functions(
        "def a():\n    return 1\n", "def a():\n    return 2\n"
    ) == {"x_a"}


def test_new_function_counts_and_deleted_one_does_not():
    assert md.changed_functions(
        "def a(): pass\ndef b(): pass\n", "def a(): pass\ndef c(): pass\n"
    ) == {"x_c"}


def test_new_file_everything_is_new():
    assert md.changed_functions(None, "def a(): pass\n") == {"x_a"}


def test_method_edit_uses_mutmuts_mangled_name():
    base = "class K:\n    def m(self):\n        return 1\n"
    assert md.changed_functions(base, base.replace("1", "2")) == {"xǁKǁm"}


def test_deleted_file_has_no_scope():
    assert md.changed_functions("def a(): pass\n", None) == set()


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
