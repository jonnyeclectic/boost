---
id: audit-distill-s-heuristic-merge-drops-repeated-fences-braces-writi
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: merged SKILL.md keeps 4 fence lines where one source alone had 56 — blocks never close
order: 205
owner: loop/distill-merge-fence-corruption
pr:
title: "distill's heuristic merge drops repeated <code>```</code> fences/braces, writing a structurally corrupt SKILL.md"
---
<code>_distill_merge</code> keeps a global <code>seen</code> set of every stripped non-blank line
and drops all repeats — so structural lines (closing <code>```</code> fences, <code>}</code>,
<code>});</code>, <code>---</code> rules, table separators) vanish after their first occurrence.
Verified: <code>distill brainstorming test-driven-development</code> on the heuristic path wrote a
SKILL.md with <b>4</b> fence lines (one bare <code>```</code>, then unclosed <code>```dot</code> /
<code>```typescript</code> / <code>```bash</code>) where the TDD source alone has <b>56</b>; the
"NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST" block never closes and the rest of the skill
renders inside an unterminated code block. Exit 0 — and the CLI then offers the corrupt output to
<code>boost import</code>.

The docstring says "dedupe exact-duplicate body lines"; the intent is dedupe, but corrupting
Markdown structure is not a defensible reading of it. A guard exists only for the degenerate case:
<code>distill X X</code> refuses ("needs at least two distinct skills"), so the corruption hits
exactly the normal two-distinct-skills invocation.

Fix, localized to <code>boost_cli/commands/intelligence.py:225-237</code>: track fenced-block state
and never dedupe inside a fence, and whitelist pure-syntax lines (<code>```</code>,
<code>---</code>, <code>}</code>, <code>);</code>, table rules) from the seen-set. Add a unit test
asserting the merged body has balanced fences. Docs: refresh
<code>docs/carousel/tapes/distill.tape</code> if the demo output changes; no
<code>docs/commands.html</code> summary/flag change.

Found by the 2026-08 CLI audit (cluster <code>distill-merge-corruption</code>); repro in the audit
log.
