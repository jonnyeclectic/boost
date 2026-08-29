# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: the fuzz harnesses in tests/fuzz/ stay wired to the code.

A fuzz target that stops importing, or whose invariants stop matching the
engine, fails *silently* — the scheduled job keeps going green while testing
nothing. These run each harness's `check()` over its committed seed corpus in
the normal suite, so a harness that rots breaks the required gate instead.

The seeds are cheap and deterministic; the coverage-guided run (which needs
atheris and a Linux wheel) is the scheduled `fuzz` workflow's job.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

FUZZ_DIR = Path(__file__).resolve().parent.parent / "fuzz"
TARGETS = ("fuzz_frontmatter", "fuzz_registry")


def _load(name):
    """Import a harness by path — tests/fuzz is not a package."""
    spec = importlib.util.spec_from_file_location(name, FUZZ_DIR / ("%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", TARGETS)
def test_harness_imports(name):
    mod = _load(name)
    assert callable(mod.check)
    assert callable(mod.fuzz_one_input)


@pytest.mark.parametrize("name", TARGETS)
def test_harness_has_seeds(name):
    kind = name.replace("fuzz_", "")
    seeds = list((FUZZ_DIR / "corpus" / kind).glob("*"))
    assert seeds, "no seed corpus for %s" % name


@pytest.mark.parametrize("name", TARGETS)
def test_every_seed_passes(name, sandbox):
    # sandbox: fuzz_registry derives paths from $HOME, and the containment
    # assertion must run against the throwaway one, never the developer's.
    mod = _load(name)
    kind = name.replace("fuzz_", "")
    for seed in sorted((FUZZ_DIR / "corpus" / kind).glob("*")):
        mod.check(seed.read_text(encoding="utf-8", errors="replace"))


@pytest.mark.parametrize("name", TARGETS)
def test_fuzz_one_input_accepts_bytes(name, sandbox):
    mod = _load(name)
    for raw in (b"", b"---\nname: x\n---\n", b"\xff\xfe\x00", b"owner/repo"):
        mod.fuzz_one_input(raw)          # must not raise on arbitrary bytes


def test_frontmatter_harness_catches_the_regression_it_was_written_for():
    """The lossy-coercion invariant must actually fail on the old behavior.

    `version: 1.10` parsed to the float 1.1, so a skill published at 1.10 read
    as 1.1 and never registered as newer than 1.9. If someone reintroduces the
    coercion, this proves the harness notices rather than shrugging.
    """
    from boost_cli.core import frontmatter
    meta, _ = frontmatter.parse("---\nversion: 1.10\n---\n\nbody\n")
    assert meta["version"] == "1.10"
    assert isinstance(meta["version"], str)

    # The harness must FAIL on the old behavior. Feeding it the value the buggy
    # parser produced, against the source the author actually wrote, is the
    # check that proves the invariant has teeth.
    mod = _load("fuzz_frontmatter")
    source = "---\nversion: 1.10\n---\n\nbody\n"
    mod.check_lossless("version", "1.10", source)        # the fixed behavior
    with pytest.raises(AssertionError, match="lossy coercion"):
        mod.check_lossless("version", float("1.10"), source)   # str() -> "1.1"

    # And the exempt cases must NOT trip it.
    mod.check_lossless("flag", True, "---\nflag: true\n---\n\nb\n")
    mod.check_lossless("nil", None, "---\nnil: null\n---\n\nb\n")
    mod.check_lossless("count", 3, "---\ncount: 3\n---\n\nb\n")
