---
id: audit-simulate-findings
board: code
section: dx
status: planned
category: CLI · UX
complexity: S
impact: Low
wow: 1
note: "norm_rule turns NEVER into 'nEVER'; trigger desc clipped mid-word at char 100"
order: 292
owner:
pr:
title: "boost simulate: CLI audit findings (2026-08)"
---
<b>The rule list prints 'nEVER'.</b> <code>simulate test-driven-development --task "fix a flaky test"</code> renders <em>"&bull; nEVER test mock behavior"</em>, <em>"&bull; nEVER add test-only methods to production classes"</em>, <em>"&bull; nEVER mock without understanding dependencies"</em> — <code>norm_rule</code> (<code>boost_cli/core/imperative.py:40-47</code>) lowercases only <code>t[:1]</code> of an all-caps NEVER, against its own docstring's goal of a "stable, comparable rule string". Fix at <code>imperative.py:47</code>: lowercase the whole leading modal token (never/always/must/do not/don't) — safe for dedup (it can only merge more duplicates), and since <code>norm_rule</code> is the shared extractor consumed by <code>explain</code> and <code>conflict</code> too, the fix reaches them for free. Optional: reword the <em>"Claude would:"</em> lead-in so <em>"&bull; do not treat the output as a substitute…"</em> bullets read grammatically.

<b>The trigger description clips mid-word at 100 chars with no ellipsis.</b> <em>likely triggers when the task involves: "Use when implementing any feature or bugfix, before writing implementation code - write the test fir"</em> — verification showed the clip is width-independent (at <code>COLUMNS=200</code> the line fits yet still ends at char 100 with a trailing space before the closing quote) and shows piped and TTY alike. <code>core/chat.py:184</code> already truncates on a word boundary with <code>" …"</code>; replace <code>desc[:100]</code> at <code>boost_cli/commands/intelligence.py:287</code> with the same <code>desc[:100].rsplit(' ', 1)[0] + ' …'</code> pattern. No doc changes for either fix.

Found by the 2026-08 CLI audit (cluster <code>simulate-text-polish</code>); repro in the audit log.
