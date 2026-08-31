---
id: audit-reindex-findings
board: code
section: internals
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 2
note: 3 of 6 manifest fetches read 131,072 of 166,210 bytes and blame the JSON
order: 287
owner:
pr:
title: "boost reindex: CLI audit findings (2026-08)"
---
<b>A truncated manifest download is reported as a broken manifest.</b> 3 of 6 <code>reindex --fetch-shards</code> runs (and the same fraction of <code>update --shards</code>) failed with <code>Error: shard manifest at &hellip;/shards-latest/manifest.json is not valid JSON: Unterminated string starting at: &hellip; (char 113774)</code> &mdash; the offset differing per run. The published file is fine: curl fetches all 166,210 bytes. <code>shards.fetch_manifest</code> does one <code>resp.read(MAX_MANIFEST_BYTES + 1)</code> (<code>boost_cli/core/shards.py:97-114</code>) and feeds whatever arrived to <code>json.loads</code>; a probe against the same URL showed Content-Length 166,210 with the single read returning exactly 131,072 bytes (128 KiB). Fix: read in a loop until EOF or Content-Length is satisfied (or catch <code>http.client.IncompleteRead</code>), and on a short read raise a BoostError naming the truncation &mdash; <code>download cut short (131,072 of 166,210 bytes) &mdash; retry</code> &mdash; retrying once; keep the JSON error only for a genuinely malformed body. Mention the transient-failure/retry behaviour in README.md's <code>--shards</code> cron section (~lines 158-185).

<b><code>reindex --json</code> names taps two ways in one object.</b> <code>"reused"</code> holds cache stems &mdash; <code>0xfurai__claude-code-subagents</code> (<code>rag.py:293-298</code>, <code>:313</code>) &mdash; while <code>"reindexed"</code> holds tap names &mdash; <code>0xfurai/claude-code-subagents</code> (<code>rag.py:307</code>), so a script that set-differences the two lists sees every tap as changed. Fix: in <code>rag.build</code> map reused safe names back to tap names via <code>registry.list_taps()</code>, and add a unit test asserting <code>set(reindexed) | set(reused)</code> equals the tap-name set from <code>taps --json</code>. No flag text changes, so docs/commands.html needs no regeneration.

Found by the 2026-08 CLI audit (clusters <code>manifest-truncated-read</code>, <code>reindex-json-tap-names</code>); repro in the audit log.
