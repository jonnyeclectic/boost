# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The [langchain] extra's packaging contract.

boost_langchain ships INSIDE the boost-skill-cli wheel — a second top-level
package — while its langchain-core dependency rides the opt-in [langchain]
extra, so the zero-dependency default install gains files but no imports.
These tests pin the seams that keep that true: the extra's pins, package
discovery, the wheel-contents allowlist, the sdist manifest, the lint gate's
coverage of the new tree, and the import guard that turns a missing
langchain_core into the one actionable install hint. Everything here runs in
the base venv on purpose — no langchain required.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_langchain_extra_pins_core_to_the_v1_major():
    extras = _pyproject()["project"]["optional-dependencies"]
    assert "langchain" in extras, "the [langchain] extra is missing"
    reqs = extras["langchain"]
    core = [r for r in reqs if r.startswith("langchain-core")]
    assert core, "the extra must carry langchain-core"
    # BaseRetriever's contract moves on majors: >=1 for the API this package
    # implements against, <2 so a breaking major cannot arrive as a patch.
    assert ">=1" in core[0] and "<2" in core[0], core[0]
    # The retriever imports pydantic DIRECTLY (Field), so the extra must
    # declare it — not lean on langchain-core happening to pull it in.
    assert any(r.startswith("pydantic") for r in reqs), reqs


def test_default_install_stays_zero_dependency():
    # The whole premise of shipping the integration as an extra: the base
    # wheel gains files, never imports. A [project] dependencies key
    # appearing at all means that invariant broke.
    assert "dependencies" not in _pyproject()["project"]


def test_wheel_ships_both_top_level_packages():
    tool = _pyproject()["tool"]
    include = tool["setuptools"]["packages"]["find"]["include"]
    assert "boost_cli*" in include and "boost_langchain*" in include, include
    # check-wheel-contents flags a second top-level package as W009 unless the
    # allowlist names it — and the allowlist doubles as the statement of
    # intent that exactly these two trees, no more, ship in the wheel.
    assert tool["check-wheel-contents"]["toplevel"] == [
        "boost_cli", "boost_langchain"]
    # The package is annotated and ships its py.typed marker so consumers'
    # type checkers see through it.
    assert "py.typed" in tool["setuptools"]["package-data"]["boost_langchain"]


def test_sdist_manifest_carries_the_package():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "boost_langchain" in manifest, (
        "MANIFEST.in never mentions boost_langchain — the sdist would build "
        "a wheel missing the package")


def test_lint_gate_covers_the_package_in_make_and_ci():
    # Mirror of test_eval_corpus's rule: a gate that exists in one of
    # {Makefile, ci.yml} but not the other is how "make lint passes for you
    # and fails in CI" happens.
    for path in (ROOT / "Makefile", ROOT / ".github" / "workflows" / "ci.yml"):
        ruff_lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                      if "ruff check" in ln]
        assert ruff_lines, "no ruff invocation found in %s" % path.name
        assert all("boost_langchain" in ln for ln in ruff_lines), (
            "%s runs ruff without boost_langchain: %r" % (path.name, ruff_lines))


@pytest.mark.skipif(importlib.util.find_spec("langchain_core") is not None,
                    reason="langchain_core installed — the guard cannot fire")
def test_import_without_the_extra_names_the_fix():
    # The module files are always present now, so `import boost_langchain`
    # FINDS the package and then fails on langchain_core — the guard must
    # turn that into the one actionable message rather than a bare
    # ModuleNotFoundError pointing at an internal import.
    sys.modules.pop("boost_langchain", None)
    with pytest.raises(ModuleNotFoundError,
                       match=r"boost-skill-cli\[langchain\]") as excinfo:
        import boost_langchain  # noqa: F401
    # The replacement error keeps the ModuleNotFoundError contract: .name
    # carries the missing root, not None.
    assert excinfo.value.name == "langchain_core"


def test_version_floor_matches_the_extra_pin():
    # The guard's second half: langchain-core 0.3 (exactly the [eval]
    # extra's pin) satisfies every import this package makes and then fails
    # subtly at runtime — BaseMessage.text is a method in 0.3, a property
    # from 1.0 — so __init__ enforces the declared >=1,<2 major at import
    # time via this pure, base-venv-testable rule.
    from boost_langchain._compat import supported_langchain_core
    assert supported_langchain_core("1.0.0")
    assert supported_langchain_core("1.5.3")
    assert not supported_langchain_core("0.3.79")   # the [eval] stack
    assert not supported_langchain_core("2.0.0")    # contract moves on majors
    assert not supported_langchain_core("")
    assert not supported_langchain_core("garbage")
