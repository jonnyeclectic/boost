"""Property-based tests (Hypothesis) for the parsers.

These complement the example-based unit suite: mutmut proves the unit tests are
*strict*, Hypothesis proves the inputs are *wide*. They live under
``tests/functional`` on purpose — they run in the coverage gate but stay out of
mutmut's ``tests/unit`` selection, so random generation never slows or
destabilises the mutation gate.

Runs are derandomised and example counts bounded, so a failure is a real,
reproducible parser bug rather than a flaky seed.
"""
from __future__ import annotations

import string
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from boost_cli.core import catalog, frontmatter

# ── strategies ─────────────────────────────────────────────────────────────

# A char set with no quotes / '#' / '[' / '|' / '>' / newlines, so the only
# round-trip hazards left are whole-string ones we filter below.
_ALPHABET = string.ascii_letters + string.digits + " ._-/,;:()!?@"

_BLOCK_SCALARS = {"|", "|-", "|+", ">", ">-", ">+"}


def _is_clean_scalar(s: str) -> bool:
    """A string that survives ``dump`` → ``parse`` unchanged (see frontmatter)."""
    if s != s.strip():                       # we generate stripped values only
        return False
    if s.lower() in ("true", "false", "null") or s == "~":
        return False                         # would coerce to bool/None
    if s in _BLOCK_SCALARS:
        return False                         # would open a block scalar
    if s.startswith("- ") or s == "-":
        return False                         # would read as a list item
    for cast in (int, float):
        try:
            cast(s)
            return False                     # would coerce to a number
        except ValueError:
            pass
    return True


_clean_scalar = (st.text(alphabet=_ALPHABET, min_size=0, max_size=24)
                 .map(str.strip).filter(_is_clean_scalar))

_key = (st.text(alphabet=string.ascii_letters + string.digits + "_-",
                min_size=1, max_size=12)
        .filter(lambda k: k[0] in string.ascii_letters))

# Values that round-trip exactly: clean strings, bools, ints, and non-empty
# lists of clean strings.
_value = st.one_of(
    _clean_scalar,
    st.booleans(),
    st.integers(),
    st.lists(_clean_scalar, min_size=1, max_size=4),
)

_meta = st.dictionaries(_key, _value, max_size=6)

# Filenames for scan_dir: safe basenames, biased toward files the scanner
# actually classifies (SKILL.md, .md, .mdc, plain).
_base = st.text(alphabet=string.ascii_letters + string.digits + "._-",
                min_size=1, max_size=10).filter(lambda b: b not in (".", ".."))
_filename = st.one_of(
    st.just("SKILL.md"),
    _base.map(lambda b: b + ".md"),
    _base.map(lambda b: b + ".mdc"),
    _base.map(lambda b: b + ".txt"),
)


# ── frontmatter ────────────────────────────────────────────────────────────

@settings(derandomize=True, max_examples=200, deadline=None)
@given(_meta)
def test_frontmatter_dump_parse_round_trips(meta):
    """dump(meta) then parse must recover the same mapping (empty body)."""
    got, body = frontmatter.parse(frontmatter.dump(meta))
    assert got == meta
    assert body == ""


@settings(derandomize=True, max_examples=300, deadline=None)
@given(st.one_of(
    st.text(),
    # bias toward real frontmatter shapes so the block parser is exercised
    st.builds(lambda inner: "---\n" + inner + "\n---\n", st.text()),
))
def test_frontmatter_parse_never_raises(text):
    """Best-effort parser: any input yields a (dict, str), never an exception."""
    meta, body = frontmatter.parse(text)
    assert isinstance(meta, dict)
    assert isinstance(body, str)


@settings(derandomize=True, max_examples=150, deadline=None)
@given(_meta)
def test_frontmatter_parse_is_idempotent(meta):
    """Re-dumping a parsed block yields identical text the second time."""
    once = frontmatter.dump(meta)
    twice = frontmatter.dump(frontmatter.parse(once)[0])
    assert once == twice


# ── catalog.scan_dir ───────────────────────────────────────────────────────

@settings(derandomize=True, max_examples=100, deadline=None)
@given(st.lists(st.tuples(_filename, st.binary(max_size=80)), max_size=6))
def test_scan_dir_never_raises_on_arbitrary_bytes(files):
    """A scan over arbitrary file names and raw bytes returns a list, no crash."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name, content in files:
            (root / name).write_bytes(content)
        entries = catalog.scan_dir(root)
    assert isinstance(entries, list)
    assert all(isinstance(e, dict) for e in entries)
