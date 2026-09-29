# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`catalog.content_unique` / `distinct_content`: counting items, not rows.

The one subtle rule is what happens to an entry with no recorded digest, and
it is the rule the obvious implementation gets wrong. ``len({e["content"] for
e in entries})`` collapses every absence into a single ``None`` — so a tap
whose cache predates ``CACHE_FORMAT`` reports one item where it has hundreds,
and does it silently. Each test below fails against that implementation or
against a plausible mutation of this one.
"""
import pytest

from boost_cli.core import catalog


def entry(name, digest=None, **extra):
    e = {"name": name, "description": "", "kind": catalog.KIND_SKILL}
    if digest is not None:
        e["content"] = digest
    e.update(extra)
    return e


class TestDistinctContent:
    def test_an_empty_scan_is_zero(self):
        assert catalog.distinct_content([]) == 0

    def test_three_copies_of_one_digest_count_as_one(self):
        rows = [entry("a", "d1"), entry("b", "d1"), entry("c", "d1")]
        assert catalog.distinct_content(rows) == 1

    def test_different_digests_are_not_merged(self):
        rows = [entry("a", "d1"), entry("a", "d2")]
        assert catalog.distinct_content(rows) == 2

    def test_two_absent_digests_count_as_two(self):
        """The set-comprehension bug, stated directly."""
        assert catalog.distinct_content([entry("a"), entry("b")]) == 2

    def test_an_empty_string_digest_counts_as_absent(self):
        """`_content_digest` never returns "", so "" is a missing field."""
        assert catalog.distinct_content([entry("a", ""), entry("b", "")]) == 2

    def test_present_and_absent_are_summed_not_maxed(self):
        rows = [entry("a", "d1"), entry("b", "d1"), entry("c"), entry("d")]
        assert catalog.distinct_content(rows) == 3

    def test_a_missing_digest_beside_a_known_one_is_not_absorbed(self):
        assert catalog.distinct_content([entry("a", "d1"), entry("a")]) == 2

    def test_the_count_is_the_length_of_the_unique_list(self):
        rows = [entry("a", "d1"), entry("b"), entry("c", "d1")]
        assert catalog.distinct_content(rows) == len(catalog.content_unique(rows))


class TestContentUnique:
    def test_it_keeps_the_first_copy_of_each_digest(self):
        rows = [entry("first", "d1"), entry("second", "d1")]
        assert [e["name"] for e in catalog.content_unique(rows)] == ["first"]

    def test_it_keeps_every_entry_that_carries_no_digest(self):
        rows = [entry("a"), entry("b"), entry("c")]
        assert [e["name"] for e in catalog.content_unique(rows)] == ["a", "b", "c"]

    def test_it_preserves_scan_order(self):
        rows = [entry("a", "d1"), entry("b", "d2"), entry("c", "d1"),
                entry("d", "d3")]
        assert [e["name"] for e in catalog.content_unique(rows)] == ["a", "b", "d"]

    def test_it_returns_the_entries_themselves(self):
        row = entry("a", "d1")
        assert catalog.content_unique([row])[0] is row

    def test_it_consumes_an_iterator(self):
        rows = iter([entry("a", "d1"), entry("b", "d1")])
        assert len(catalog.content_unique(rows)) == 1


def test_a_real_scan_collapses_a_vendored_mirror(tmp_path):
    """The card's case, end to end through `scan_dir`.

    A registry that vendors a byte-identical copy of its own skill scans into
    two rows and one item. This is the shape `tests/eval/taps.txt`'s two
    counts describe, reproduced small.
    """
    body = "---\nname: alpha\ndescription: the one skill\n---\n\nBody text.\n"
    for rel in ("skills/alpha/SKILL.md", "plugins/pack/skills/alpha/SKILL.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    entries = catalog.scan_dir(tmp_path, "fixture")
    assert len(entries) == 2
    assert catalog.distinct_content(entries) == 1


def test_every_scanned_entry_carries_a_digest(tmp_path):
    """`_make_entry` stamps `content` unconditionally.

    Pinned because the distinct count's absence branch is defensive on this
    path: if a scan ever stopped stamping the field, the count would quietly
    become the row count again.
    """
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: d\n---\n\nBody.\n", encoding="utf-8")
    entries = catalog.scan_dir(tmp_path, "fixture")
    assert entries
    assert all(e.get("content") for e in entries)


@pytest.mark.parametrize("fn", [catalog.content_unique, catalog.distinct_content])
def test_neither_helper_mutates_its_input(fn):
    rows = [entry("a", "d1"), entry("b", "d1")]
    before = [dict(e) for e in rows]
    fn(rows)
    assert rows == before
