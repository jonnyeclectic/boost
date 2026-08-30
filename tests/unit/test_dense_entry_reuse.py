# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Reuse is decided per ENTRY, not per tap — a moved commit is not a changed skill.

Dense reuse was keyed on a tap's git commit alone, and `_delete_taps` is
``DELETE FROM chunks WHERE tap = ?``, so anything below tap granularity was
redone from scratch. A tap's commit moving says *something* in that clone
changed. It does not say anything boost indexes did.

Measured on a real 464-tap / 63,003-entry / 657,587-chunk install:

- 19 taps drifted in 6.85 h — 4.1% of taps, but **17.0% of chunks**, costing
  61-68 min against a 5 h 28 m cold build.
- Those 19 held 967 changed files, of which **39** map to an indexed entry
  owning **659** chunks. Boost re-embedded **112,081** — **170x** the change.
- **10 of the 19 changed nothing boost indexes at all** (badge JSON,
  star-history SVGs, CI YAML, e2e TypeScript) and cost **44,866 chunks =
  40.0%** of the incremental bill. `davila7/claude-code-templates` re-embedded
  all 18,566 of its chunks over four dashboard JSON files.

The fix needs no new identity machinery. `catalog._content_digest` already
stamps each entry with a hash of exactly what `rag.read_body` assembles, and
`tests/unit/test_content_identity.py` pins that parity byte-for-byte — so an
entry whose stored digest matches its catalog digest is one whose embedded text
is unchanged.

What must NOT regress, and each has a test below: an entry deleted upstream has
to stop answering queries (whole-tap deletion used to sweep it for free), a
changed entry has to be replaced rather than doubled, and an entry with no
digest must never be reused — two absences are not a match.
"""
from __future__ import annotations

import math

import pytest

from boost_cli.core import dense, embed, rag

TAP = "acme/skills"


def _toy_embed(texts, input_type=None, timeout=60):
    """8-d so `_quantizable` holds, deterministic so reuse is observable."""
    out = []
    for t in texts:
        v = [float(sum(t.encode()[i::8]) % 97) for i in range(8)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def _e(name, body, *, tap=TAP, digest=None):
    """A catalog entry whose `content` is a stand-in for _content_digest.

    The real digest hashes ``name + description + body``; what matters to
    reuse is only that it changes when the body does, so the tests set it
    explicitly and a test that means to omit it passes ``digest=""``.
    """
    entry = {"name": name, "tap": tap, "kind": "skill",
             "skill_md": "skills/%s/SKILL.md" % name, "_body": body}
    if digest is None:
        digest = "d-%s" % abs(hash(body))
    if digest:
        entry["content"] = digest
    return entry


@pytest.fixture()
def counting_env(sandbox, monkeypatch):
    """dense wired to a toy embedder that records every text it is asked for."""
    asked: list[list[str]] = []
    commit = {"v": "c1"}

    def recording(texts, input_type=None, timeout=60):
        asked.append(list(texts))
        return _toy_embed(texts, input_type, timeout)

    monkeypatch.setattr(embed, "embed", recording)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {TAP: "/x"})
    monkeypatch.setattr(rag, "_tap_commits",
                        lambda: {TAP.replace("/", "__"): commit["v"]})
    monkeypatch.setattr(dense, "read_body",
                        lambda e, tp=None: e.get("_body", ""))
    asked.commit = commit          # type: ignore[attr-defined]
    return asked


def _flat(asked):
    return [t for batch in asked for t in batch]


def _build(entries):
    res = dense.build(entries)
    if res is None:
        pytest.skip("sqlite-vec backend unavailable")
    return res


def _move_commit(env, to):
    """Advance the tap's commit — what makes the tap look changed."""
    env.commit["v"] = to


def _chunk_paths(con):
    return sorted(r[0] for r in con.execute("SELECT path FROM chunks"))


class TestAMovedCommitIsNotAChangedSkill:
    """The 40% case: ten of nineteen drifted taps changed nothing indexed."""

    def test_identical_content_costs_no_embeddings(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == [], (
            "a moved commit re-embedded content that had not changed")

    def test_the_stats_say_what_was_reused(self, counting_env):
        # `reused` is tap-level and reports [] here — the tap DID move. Without
        # a separate counter the reply would say "reindexed everything" while
        # embedding nothing, which is the confusing half of the old behaviour.
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build(entries)
        assert res["reused_entries"] == 2
        assert res["embedded_entries"] == 0
        assert res["reindexed"] == [TAP]      # the tap genuinely moved

    def test_the_chunk_total_does_not_drift(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        first = _build(entries)
        _move_commit(counting_env, "c2")
        again = _build(entries)
        assert again["chunks"] == first["chunks"]


class TestOnlyTheChangedEntryIsReEmbedded:
    """The 170x case: 659 chunks of real change cost 112,081 re-embeds."""

    def test_one_changed_body_embeds_one_entry(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        changed = [entries[0], _e("beta", "two REWRITTEN"), entries[2]]
        res = _build(changed)
        assert _flat(counting_env) == ["two REWRITTEN"]
        assert res["embedded_entries"] == 1
        assert res["reused_entries"] == 2

    def test_the_changed_entry_is_replaced_not_doubled(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([entries[0], _e("beta", "two REWRITTEN")])
        con = dense._connect()
        rows = list(con.execute(
            "SELECT COUNT(*) FROM chunks WHERE name = 'beta'"))
        con.close()
        assert rows[0][0] == 1, "the old vectors survived alongside the new"
        assert res["chunks"] == 2

    def test_the_new_digest_is_what_gets_stored(self, counting_env):
        # Storing the old digest would reuse stale vectors forever — the
        # failure mode that looks right and is invisible.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        rewritten = _e("alpha", "one REWRITTEN")
        _build([rewritten])
        con = dense._connect()
        stored = {r[0] for r in con.execute(
            "SELECT digest FROM chunks WHERE name = 'alpha'")}
        con.close()
        assert stored == {rewritten["content"]}

    def test_a_second_rebuild_after_a_change_reuses_again(self, counting_env):
        # Proves the new digest was actually persisted, not merely computed.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        rewritten = [_e("alpha", "one REWRITTEN")]
        _build(rewritten)
        counting_env.clear()
        _move_commit(counting_env, "c3")
        _build(rewritten)
        assert _flat(counting_env) == []


class TestNothingStaleSurvivesReuse:
    """Whole-tap deletion swept deleted entries for free. Reuse must not lose that."""

    def test_an_entry_deleted_upstream_stops_answering(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([entries[0], entries[2]])
        con = dense._connect()
        paths = _chunk_paths(con)
        con.close()
        assert paths == ["skills/alpha/SKILL.md", "skills/gamma/SKILL.md"]
        assert res["chunks"] == 2

    def test_pruning_a_deleted_entry_costs_no_embeddings(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build([entries[0]])
        assert _flat(counting_env) == []

    def test_a_whole_tap_going_away_still_prunes(self, counting_env):
        # The tap-level sweep this sits under must keep working.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([_e("alpha", "one", tap="other/skills")])
        assert TAP in res["pruned"]


class TestAMissingDigestIsNeverAMatch:
    """CLAUDE.md: consumers degrade cleanly when `content` is absent, and must
    never treat two absences as a match. Two unknowns are not one thing."""

    def test_an_entry_without_a_digest_is_re_embedded(self, counting_env):
        entries = [_e("alpha", "one", digest="")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == ["one"], (
            "an entry with no digest was reused — two absences matched")

    def test_it_does_not_poison_its_neighbours(self, counting_env):
        entries = [_e("alpha", "one", digest=""), _e("beta", "two")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == ["one"]


class TestTheStoreFormatMovedWithIt:
    def test_index_version_was_bumped(self):
        # A v2 store has no `digest` column and `_ensure_schema` cannot add one
        # (CREATE TABLE IF NOT EXISTS), so the version bump IS the migration —
        # `build` wipes on a version change. Pinned because forgetting it makes
        # every existing store fail its next build on "no column named digest".
        assert dense.INDEX_VERSION >= 3

    def test_the_schema_carries_the_digest(self, sandbox):
        con = dense._connect()
        if con is None:
            pytest.skip("sqlite-vec backend unavailable")
        dense._ensure_schema(con, 8)
        cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
        con.close()
        assert "digest" in cols

    def test_a_shard_carries_the_digest_too(self, counting_env):
        # Without this an imported shard's entries have no digest, so the very
        # next build re-embeds them — paying in CPU exactly what downloading
        # the shard was meant to save.
        _build([_e("alpha", "one")])
        shard = dense.export_shard(TAP)
        assert shard["chunks"], "nothing exported"
        assert all("digest" in c for c in shard["chunks"])
        assert any(c["digest"] for c in shard["chunks"])
