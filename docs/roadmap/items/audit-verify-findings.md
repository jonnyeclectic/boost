---
id: audit-verify-findings
board: code
section: health
status: inflight
category: Safety · Bug
complexity: S
impact: Low
wow: 1
note: fix landed and passes locally; make check's coverage/mutation/full lint tiers unverified — no PyPI egress in this sandbox
order: 302
owner: loop/verify-status-token
pr:
title: "<code>boost verify</code>: CLI audit findings (2026-08)"
---
<b>verify prints a green <code>ok</code> on a row it counts as failed.</b> With a lock rule entry stripped of <code>version</code> and given an empty <code>installed_at</code>, <code>verify</code> renders <em>&ldquo;dotnet-build&nbsp;&nbsp;ok&nbsp;&nbsp;rule &middot; missing lock fields: version, installed_at&rdquo;</em> and then <em>&ldquo;! 1 of 2 items failed verification&rdquo;</em> (exit 1) &mdash; the same row wears the pass token and lands in the failure count. <code>verify --json</code> is no better: <code>status: "ok"</code> beside a non-empty <code>missing_fields</code> and a top-level <code>failed</code>, with no per-row pass/fail signal. Verified mechanism: <code>cmd_verify</code> computes <code>bad</code> from status OR missing fields OR <code>commit_pin == MODIFIED</code> (<code>safety.py:391-393</code>), but the text renderer colors strictly on <code>r['status']</code> via <code>status_role</code> (<code>safety.py:418</code>) without checking membership in <code>bad</code>. Fix (verified recommendation): derive a per-row <code>passed = status in ('ok','quarantined') and not missing_fields and commit_pin != MODIFIED</code>, key the status token's role on it, and add <code>passed</code> to the JSON row. No doc changes needed. Found by the 2026-08 CLI audit (cluster <code>verify-ok-on-failure</code>); repro in the audit log.
