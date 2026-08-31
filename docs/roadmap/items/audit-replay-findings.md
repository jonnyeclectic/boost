---
id: audit-replay-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: rollback says "complete" (exit 0) with a skill unrestored, and replans it forever
order: 288
owner:
pr:
title: "boost replay: CLI audit findings (2026-08)"
---
<b><code>replay list</code>'s ID and WHEN describe two different instants on one row.</b> <code>replay list --json</code> after two installs 4 s apart: <code>{"id": "20260831T140213Z", "updated": "2026-08-31T14:02:09Z"}</code>. <code>lockfile.write()</code> (<code>boost_cli/core/lockfile.py:78-99</code>) stamps the history filename with <em>now</em> &mdash; the moment the outgoing lock becomes historical &mdash; but that snapshot's own <code>updated</code> field was stamped by the <em>previous</em> write, and <code>cmd_replay list</code> (<code>boost_cli/commands/team.py:592</code>) prints the two side by side as if they were one instant; <code>replay show</code> reuses the earlier one. Fix: stamp the history filename with the lock's own <code>updated</code> so the id equals the state time, or relabel the column (e.g. STATE FROM) and note the distinction in <code>replay show</code>'s heading.

<b><code>replay rollback</code> reports success it did not deliver, and never converges.</b> Rolling back to a snapshot naming a skill no tap carries prints <code>! vanished-skill-zzz is gone from every tap &mdash; cannot restore</code> and then <code>&#10003; rollback to 20200101T000000Z complete</code>, exit 0 &mdash; and a second run replans <em>install 1</em>, warns again, and says complete again, indefinitely. In <code>cmd_replay</code> rollback (<code>team.py:650-687</code>) an unresolvable name gets <code>out.warn</code> + <code>continue</code> with no tracking, and the function unconditionally reaches the journal log and <code>return 0</code>. Fix: track names that failed <code>_resolve_entry</code>; when any exist, say <em>finished with N skill(s) not restored</em> and return non-zero; treat unrestorable-only differences as already-at-snapshot on subsequent runs.

Found by the 2026-08 CLI audit (clusters <code>replay-id-time-semantics</code>, <code>replay-partial-rollback</code>); repro in the audit log.
