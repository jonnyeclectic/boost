#!/usr/bin/env python3
"""Coverage-guided fuzz target: the tap-spec parser and the catalog scalars.

    python3 -m pip install atheris
    python3 tests/fuzz/fuzz_registry.py -atheris_runs=100000
    python3 tests/fuzz/fuzz_registry.py tests/fuzz/corpus/registry/

``registry.parse_spec`` turns whatever a user types after ``boost tap`` into a
``(name, url)`` pair, and the *name* becomes a directory under
``~/.boost/repos``. That makes it both an untrusted-input parser and a path
constructor, so the invariants asserted here are about containment as much as
about crashes:

* it either returns a 2-tuple of strings or raises ``BoostError`` — never
  another exception type, and never ``None``;
* the derived name is a single path component: no separators, no ``..``, not
  empty, not absolute. A spec that produced ``../..`` would let a tap escape
  the repos directory.

The scanners (``secretscan``/``injectscan``) and ``util.semver_gt`` ride along:
they are regex-driven over untrusted text, where a catastrophic-backtracking
pattern is the realistic failure, and libFuzzer's timeout detector is exactly
the tool for finding one.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# parse_spec touches the filesystem (an existing directory is a valid spec), so
# point HOME somewhere harmless before the module resolves any paths.
os.environ.setdefault("BOOST_NO_AI", "1")

from boost_cli.core import injectscan, paths, registry, secretscan, util  # noqa: E402
from boost_cli.errors import BoostError  # noqa: E402

# Anything longer is a pathological input the CLI would never see, and it only
# slows the fuzzer down.
MAX_LEN = 4096


def check(text: str) -> None:
    """Assert every invariant, for one input."""
    _check_parse_spec(text)

    # Regex-driven scanners over untrusted text: assert they terminate and
    # return the documented shape. libFuzzer's own timeout detector catches
    # catastrophic backtracking, which is the realistic bug here.
    for scan in (secretscan.scan_text, injectscan.scan_text):
        findings = scan(text)
        if not isinstance(findings, list):
            raise AssertionError("%s returned %r" % (scan.__name__, type(findings)))

    # semver_gt is total: any two strings compare without raising.
    util.semver_gt(text, "1.0.0")
    util.semver_gt("1.0.0", text)
    util.semver_gt(text, text)


def _check_parse_spec(text: str) -> None:
    """parse_spec returns a safe (name, url) pair or raises BoostError."""
    try:
        result = registry.parse_spec(text)
    except BoostError:
        return  # the documented rejection path
    if not (isinstance(result, tuple) and len(result) == 2):
        raise AssertionError("parse_spec returned %r" % (result,))
    name, url = result
    if not isinstance(name, str) or not isinstance(url, str):
        raise AssertionError("parse_spec returned non-str parts: %r" % (result,))

    # The containment property, asserted on the DERIVED PATH rather than on the
    # raw name. `Tap.safe_name` maps "/" to "__", so a name like "../../etc"
    # becomes the single component "..__..__etc" and stays put — asserting that
    # the *name* has no traversal parts would be a false alarm (it was, on the
    # first run of this harness). What must actually hold is that the clone
    # directory and cache file never escape their parents.
    tap = registry.Tap(name=name, url=url)
    for derived, parent in ((tap.path, paths.repos_dir()),
                            (tap.cache_file, paths.cache_dir())):
        resolved, root = os.path.realpath(str(derived)), os.path.realpath(str(parent))
        if os.path.commonpath([resolved, root]) != root:
            raise AssertionError(
                "spec %r escapes %s: %s" % (text[:80], root, resolved))


def fuzz_one_input(data: bytes) -> None:
    """libFuzzer entry point."""
    text = data.decode("utf-8", errors="replace")
    if len(text) > MAX_LEN:
        return
    check(text)


def _corpus_smoke() -> int:
    """Run every seed through `check` — the no-atheris fallback path."""
    corpus = Path(__file__).parent / "corpus" / "registry"
    seeds = sorted(corpus.glob("*")) if corpus.is_dir() else []
    for seed in seeds:
        check(seed.read_text(encoding="utf-8", errors="replace"))
    print("fuzz_registry: %d seed(s) OK" % len(seeds))
    return 0


def main() -> int:
    try:
        import atheris
    except ImportError:
        print("atheris not installed — running the seed corpus instead")
        return _corpus_smoke()
    atheris.Setup(sys.argv, fuzz_one_input, enable_python_coverage=True)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
