---
id: audit-fingerprint-findings
board: code
section: health
status: inflight
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: quarantine doesn't change the fingerprint; an uncloned tap hashes as empty, silently
order: 269
owner: loop/fingerprint-quarantine
pr:
title: "<code>boost fingerprint</code>: CLI audit findings (2026-08)"
---
<b>fingerprint ignores quarantine state and silently hashes uncloned taps as empty commits.</b>
Measured: the digest was <code>092c60d8b4324373</code> both before and after
<code>quarantine brainstorming</code> &mdash; although <code>_fingerprint</code>'s own comment
(<code>quality.py:294-296</code>) says a poisoned CLAUDE.md rule must change the fingerprint, and
quarantine (<code>store.py:948-975</code>) de-arms exactly that without touching the hash. And with
one tap's clone deleted, <code>fingerprint --json</code> exits 0 containing
<code>"0xfurai/claude-code-subagents:"</code> (an empty commit), the digest changes, and nothing on
stderr says a component is unknown &mdash; while <code>heal</code>/<code>doctor</code> warn
<em>&ldquo;tap &hellip; not cloned&rdquo;</em> on the same state. Verification found both the plain
TTY output and <code>--json</code> silent, so a changed hash cannot be told from real drift on
either path.

<br><br><b>Fix</b> (per the verified recommendation): in <code>_fingerprint</code>
(<code>quality.py:289-305</code>) append a <code>:q</code> suffix to component lines whose lock
entry has <code>quarantined</code> set &mdash; kind-prefixed, so an environment with nothing
quarantined keeps its current digest &mdash; and return the uncloned-tap names so
<code>cmd_fingerprint</code> can print <em>&ldquo;! tap X not cloned &mdash; fingerprint incomplete
(boost update)&rdquo;</em> on stderr and add <code>"incomplete": [...]</code> to the JSON. Exit
stays 0. Found by the 2026-08 CLI audit (cluster fingerprint-completeness); repro in the audit log.
