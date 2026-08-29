#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Coverage-guided fuzz target: the SKILL.md frontmatter parser.

    python3 -m pip install atheris
    python3 tests/fuzz/fuzz_frontmatter.py -atheris_runs=100000
    python3 tests/fuzz/fuzz_frontmatter.py tests/fuzz/corpus/frontmatter/

Why this parser first: every skill, rule and workflow boost indexes goes through
it, and its input is *untrusted by definition* — a tapped repository is a third
party's Markdown. It is also hand-rolled (a stdlib-only YAML subset, no PyYAML),
so nobody else's fuzzing covers it.

The properties asserted below are the ones the rest of the engine relies on:

* ``parse`` never raises. Callers treat unreadable frontmatter as "no metadata"
  and keep going; an exception here aborts a whole tap scan over one bad file.
* The return shape is always ``(dict, str)``.
* **Coercion is lossless** — ``str()`` of any scalar gives back exactly what the
  author wrote. This is the property that caught the real bug: ``version: 1.10``
  became the float ``1.1``, so a skill published at 1.10 read as 1.1, compared
  as older than 1.9, and was never offered as an update. See
  ``test_frontmatter.py::test_scalar_preserves_lossy_version_strings``.

Run it as a plain script (no atheris) for a quick smoke pass over the seed
corpus — that path is what ``tests/unit/test_fuzz_targets.py`` exercises in the
normal suite, so the harness itself can never silently rot.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from boost_cli.core import frontmatter  # noqa: E402  (after sys.path shim)


def check(text: str) -> None:
    """Assert every invariant the engine relies on, for one input."""
    meta, body = frontmatter.parse(text)
    if not isinstance(meta, dict):
        raise AssertionError("parse() returned %r, not a dict" % type(meta))
    if not isinstance(body, str):
        raise AssertionError("body was %r, not a str" % type(body))

    for key, value in meta.items():
        if not isinstance(key, str):
            raise AssertionError("non-string key %r" % (key,))
        check_lossless(key, value, text)

    # parse() must be deterministic: the same bytes always give the same meta.
    again, _ = frontmatter.parse(text)
    if again != meta:
        raise AssertionError("parse() is not deterministic for %r" % text[:120])


def _source_scalar(key: str, text: str):
    """The raw text the author wrote after ``key:``, or None if not a simple line.

    Only plain ``key: value`` lines are checked. Block lists, flow lists and
    multi-line blocks legitimately do not render back to one scalar, so they are
    out of scope here rather than a false alarm.
    """
    prefix = "%s:" % key
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()[len(prefix):].strip()
    return None


def check_lossless(key, value, text: str) -> None:
    """A coerced scalar must render back to exactly the text the author wrote.

    This is the invariant that catches the ``version: 1.10`` bug, and it can
    only be checked against the SOURCE — comparing the parsed value to itself,
    or round-tripping it through ``dump``, is stable under the bug and proves
    nothing. (The first draft of this harness made that mistake.)
    """
    if isinstance(value, list):
        return          # a list never came from a single scalar
    # bool/None are the YAML 1.2 core-schema keywords: the document says "true"
    # and Python renders "True". That mapping is deliberate, so they are exempt.
    if isinstance(value, bool) or value is None:
        return
    if not isinstance(value, (int, float)):
        return          # already a string — nothing was coerced

    raw = _source_scalar(key, text)
    if raw is None or raw.startswith(("[", "{", '"', "'")):
        return
    if str(value) != raw:
        raise AssertionError(
            "lossy coercion: %s was written %r but parsed to %r (renders as %r)"
            % (key, raw, value, str(value)))


def fuzz_one_input(data: bytes) -> None:
    """libFuzzer entry point."""
    check(data.decode("utf-8", errors="replace"))


def _corpus_smoke() -> int:
    """Run every seed through `check` — the no-atheris fallback path."""
    corpus = Path(__file__).parent / "corpus" / "frontmatter"
    seeds = sorted(corpus.glob("*")) if corpus.is_dir() else []
    for seed in seeds:
        check(seed.read_text(encoding="utf-8", errors="replace"))
    print("fuzz_frontmatter: %d seed(s) OK" % len(seeds))
    return 0


def main() -> int:
    try:
        import atheris
    except ImportError:
        # atheris ships manylinux wheels only; on any other platform the seed
        # smoke pass is still meaningful and keeps this file honest.
        print("atheris not installed — running the seed corpus instead")
        return _corpus_smoke()
    atheris.Setup(sys.argv, fuzz_one_input, enable_python_coverage=True)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
