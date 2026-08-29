# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`(tap, name)` is not a unique key, and both engines used it as one.

Measured on the pinned 6-tap eval corpus: 743 entries collapse to 694 distinct
`(name, tap)` pairs, so **49 entries (6.6%) are shadowed**. On a real 83-tap
install the roadmap item measures 1,557 of 11,147 (14.0%), worst case
`('survivorforge/cursor-rules', 'rule')` x47.

The failure is not a ranking annoyance, it is mis-binding. `rag.retrieve` and
`dense.retrieve` both build `live = {(name, tap): entry}` as a dict
comprehension, so the last entry silently wins and every earlier one becomes
unreachable. A query that matches the shadowed entry's *body* is then reported
with the surviving entry's name, description and path. A concrete pair from that
corpus, same tap and same name:

    docs/rules/backend/nodejs/express-mongodb/admin-interface-rule.mdc
    docs/rules/backend/nodejs/fullstack-mern-guide/admin-interface-rule.mdc

Two different rules about two different stacks. One of them cannot be found.

`(tap, skill_md)` is 743/743 distinct on that corpus and 11,147/11,147 on the
83-tap install, which is why it is the key used here.
"""
from __future__ import annotations

from boost_cli.core import rag


def _entry(name, tap, skill_md, description=""):
    return {"name": name, "tap": tap, "skill_md": skill_md, "kind": "rule",
            "description": description, "rel_dir": "", "version": "",
            "curated": False, "meta": {}, "search_blob": description}


# The real collision, reduced: same tap, same name, different files.
SHADOWED = _entry("admin-interface-rule", "LessUp/awesome-cursorrules-zh",
                  "docs/rules/backend/nodejs/express-mongodb/"
                  "admin-interface-rule.mdc", "express mongodb admin")
SURVIVOR = _entry("admin-interface-rule", "LessUp/awesome-cursorrules-zh",
                  "docs/rules/backend/nodejs/fullstack-mern-guide/"
                  "admin-interface-rule.mdc", "mern fullstack admin")


class TestEntryKey:
    """The identity function both engines and the fuser share."""

    def test_distinguishes_two_files_with_one_name_in_one_tap(self):
        assert rag.entry_key(SHADOWED) != rag.entry_key(SURVIVOR)

    def test_is_stable_for_the_same_entry(self):
        assert rag.entry_key(SHADOWED) == rag.entry_key(dict(SHADOWED))

    def test_separates_the_same_file_path_in_different_taps(self):
        # A path alone is not unique either — two registries commonly ship
        # `skills/commit/SKILL.md`. The tap has to stay in the key.
        other = dict(SHADOWED, tap="someone/else")
        assert rag.entry_key(SHADOWED) != rag.entry_key(other)

    def test_no_entry_is_shadowed_in_a_live_map(self):
        # The actual defect: a dict comprehension over a non-unique key.
        entries = [SHADOWED, SURVIVOR]
        live = {rag.entry_key(e): e for e in entries}
        assert len(live) == 2, "one entry was silently overwritten by the other"


class TestFusionKeepsThemApart:
    """`rrf_fuse` must not merge two entries that only look alike."""

    def _hit(self, entry, score):
        return {"entry": entry, "score": score, "snippet": ""}

    def test_two_shadowed_entries_stay_two_results(self):
        bm25 = [self._hit(SHADOWED, 3.0), self._hit(SURVIVOR, 2.0)]
        fused = rag.rrf_fuse([bm25], limit=10)
        paths = {h["entry"]["skill_md"] for h in fused}
        assert len(fused) == 2 and len(paths) == 2, (
            "fusion collapsed two distinct rules into one result")

    def test_the_same_entry_from_two_engines_still_fuses_to_one(self):
        # The inverse must keep holding: agreement between engines is the whole
        # point of RRF, so a genuinely identical entry must not become two rows.
        bm25 = [self._hit(SHADOWED, 3.0)]
        dense = [self._hit(dict(SHADOWED), 1.0)]
        fused = rag.rrf_fuse([bm25, dense], limit=10)
        assert len(fused) == 1

    def test_agreement_still_outranks_a_single_engine_hit(self):
        # Guards the ordering contract rather than just the count.
        bm25 = [self._hit(SHADOWED, 3.0), self._hit(SURVIVOR, 2.0)]
        dense = [self._hit(dict(SURVIVOR), 9.0)]
        fused = rag.rrf_fuse([bm25, dense], limit=10)
        assert fused[0]["entry"]["skill_md"] == SURVIVOR["skill_md"]


class TestIndexVersionWasBumped:
    """An index built under the old key must not be reused under the new one.

    The stored docs carry the key's components, so an index written before this
    change cannot answer with the new identity — it has to be rebuilt, and the
    version constant is what forces that instead of serving mis-bound results.
    """

    def test_bm25_index_version_is_past_the_colliding_key(self):
        assert rag.INDEX_VERSION >= 3
