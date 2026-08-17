# Catalogue content identity

**Date:** 2026-08-16
**Status:** approved, implementing

## Problem

boost indexes 60,047 items across 460 taps on a real install. Most of them are
not distinct things: registries mirror each other, and a single registry
frequently ships one skill rendered once per agent dotdir. Measured on that
install, only 41,051 of the 60,047 entries (68.4%) are distinct content.

boost already collapses those copies at the two places a user *sees* them —
`rag.dedupe_by_content` for search results, `catalog.resolve_one` for install
resolution. Nothing collapses them at the places boost *pays* for them:

| Store | Size | Redundancy |
|-------|------|------------|
| `rag_vectors.sqlite` | 3.2 GB | 42.9% of 750,416 chunks are duplicates |
| `rag_postings.sqlite` | 653 MB | — |
| `rag_index.json` | 44 MB | — |

`dense._embed_and_store` embeds every chunk of every entry with no content
check; one chunk was embedded 1,464 times. Those embeddings cost API credits,
and they buy nothing: `retrieve_any` applies `dedupe_by_content` on every
retrieval path — dense-only, BM25-only, and fused — so each redundant vector is
computed, stored, billed, and then discarded before it can reach the user.

The root cause is that a catalog entry carries no content identity. It carries
`(tap, skill_md)` — *row* identity, which is deliberately strict and correct —
but nothing that says "this is the same thing as that". Every consumer that
needs content identity therefore derives it independently, and they disagree.

## Which key is correct

Three keys are in use or were considered. Measured over all 60,047 entries:

| Key | Clusters kept | Clusters merging *different* names |
|-----|---------------|------------------------------------|
| A — name + description + body | 41,051 (68.4%) | **0** |
| B — body only | 40,372 (67.2%) | 259 |
| C — name + description | 37,668 (62.7%) | 2 |

**A is correct**, and A is what `rag` already hashes: `_make_docs` hashes
`read_body()`, and `read_body` prepends name and description to the body.

`rag.dedupe_by_content`'s docstring says clustering is "on the body, never the
name", and offers as proof that no cluster spans more than one name. Both the
claim and the proof are artefacts: the name is *inside* the hash, so zero
name-spanning clusters is guaranteed rather than measured. Key B — the one the
docstring describes — would merge 259 clusters spanning different names, which
is exactly the `admin-interface-rule` failure #366 fixed. The code was right and
the comment was wrong.

`browse.dedupe` uses key C, which over-collapses: 3,383 clusters that A keeps
distinct. Those are items sharing a name and description but carrying different
bodies, and collapsing them makes one of them unreachable in the browser.

## Design

### 1. Entries carry the digest

`catalog._make_entry` gains a `content` field: the first 16 hex chars of the
sha256 of `f"{name}\n{description}\n{body}".strip()`, byte-identical to what
`rag.read_body()` produces for the same entry.

This is free. `_make_entry` already receives `body` — the file is read, parsed,
and thrown away. Measured marginal cost over the full corpus: **2.04 µs/entry,
122 ms for all 60,047**.

It also *removes* work. `rag._make_docs` currently re-reads every item's file at
index-build time solely to recompute this value (~14 s and 60k file opens on a
real install). With the digest on the entry it reads it instead, and falls back
to computing it when absent so a stale cache still indexes correctly.

### 2. Tap caches are versioned

`rebuild_tap` writes `{tap, url, generated, commit, skills}` with no format
field, so there is no way to invalidate 460 caches on read. Add
`CACHE_FORMAT = 1`, written by `rebuild_tap` and checked by `_cached_tap`; a
cache with a missing or older format is treated as stale and rescanned.

Precedent: `catalogbundle.BUNDLE_FORMAT` and `rag.INDEX_VERSION` both
self-version for exactly this reason. This is what makes the backfill automatic
rather than a 460-repo re-tap.

### 3. `browse` uses the digest

`browse.dedupe` keys on `entry["content"]` when present, falling back to the
current name+description signature when it is absent, so a browser run against a
not-yet-rebuilt cache still works. The fuzzy near-duplicate pass is retained for
the fallback path only.

### 4. Install resolves identical content across taps

`resolve_one` collapses indistinguishable copies *within* one tap today, and
raises `"exists in multiple taps"` across taps regardless of whether the copies
are identical. With a content digest, the cross-tap case can make the same
judgement the within-tap case already makes: if every candidate shares one
digest, there is nothing for the user to choose between, so choose — ranking by
`rag.source_rank` (curated first, then registry confidence), which exists for
precisely this decision.

This narrows a real dead-end (a mirrored skill cannot be installed unqualified
today) without weakening the genuine ambiguity error, which still raises when
the digests differ.

### 5. Embedding dedup (separate change)

`_embed_and_store` dedupes its batch by chunk text before calling the embedding
provider, then fans each returned vector back out to every row sharing that
text. Embeddings are deterministic, so the stored result is byte-identical to
today's; the saving is 42.9% of embedding calls and build time. The schema and
per-entry `chunks` rows are unchanged, so tap deletion keeps working untouched.

Ships alongside the rest rather than separately. It depends on nothing above —
it keys on the chunk text directly, not on the catalogue digest — but it is the
same finding acted on at the last layer that still paid for duplicates, and
`main` requires every PR to be rebuilt on current `main` before merging, so
splitting a 40-line change into its own serial CI cycle buys review clarity that
the shared theme already provides.

Measured on the live store: 750,416 chunks collapse to 428,436 distinct texts,
so **321,980 embedding calls (42.9%)** are saved on the next rebuild. Disk is
unchanged, because one `chunks` row and one vector per entry is what keeps tap
deletion correct. Cutting the 3.2 GB itself needs a schema that lets several
entries share a stored vector; that is a real migration with a measurable risk
to retrieval, and it is deliberately not attempted here.

## What is deliberately NOT done

**Rows are not dropped from `all_entries()`.** Every duplicate row stays in the
catalogue. Dropping them would look like the biggest win available (37.5% of the
corpus) and would break, in order: `--path` disambiguation, typosquat detection
(`pkg.py`), `sync_apply`'s tap-scoped repair (`store.py`), the eval harness's
exemplar resolution (`prepare_row` raises `SystemExit` when a `tap::skill_md`
stops resolving), `retrieve`'s `live` filter, and the `source_rank` quality
prior that needs to see every candidate to pick the best-sourced one.

The mark is the digest, carried per entry. Nothing is destroyed and the change
is reversible by rebuilding caches.

**The BM25 index is not deduplicated in this change.** It would take postings
from 18.6M rows to roughly 12.7M, but it moves the four floored eval metrics and
must be measured against the eval gate on key A before it ships. Deferred.

## Testing

- Digest parity: `catalog._make_entry`'s `content` equals
  `sha256(rag.read_body(entry))[:16]` for a scanned fixture tap. This is the
  invariant the whole design rests on, so it is pinned directly rather than
  inferred from behaviour.
- Cache format: a cache written without `format`, or with an older one, is
  rescanned rather than trusted.
- `rag._make_docs` uses a present digest and recomputes an absent one, producing
  the same index either way.
- `browse.dedupe` collapses same-digest entries, keeps different-digest entries
  that share a name and description (the key-C regression), and still works on
  entries with no digest.
- `resolve_one` returns the best-sourced copy when cross-tap candidates share a
  digest, and still raises when they do not.
- Embedding dedup embeds one text once and stores a row per entry.

## Risks

- **Digest/`read_body` drift.** If either side changes its text assembly the
  digest stops matching and dedup silently degrades. Mitigated by the parity
  test above, which fails on any divergence.
- **Untap orphaning a vector.** Not applicable as designed: embedding dedup
  keeps one `chunks` row per entry, so removing a tap deletes only its own rows.
- **Corpus figures in `CLAUDE.md` and `tests/eval/taps.txt`.** Untouched,
  because no rows are dropped.
