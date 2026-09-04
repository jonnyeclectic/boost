---
id: audit-verify-findings
board: code
section: health
status: inflight
category: Safety · Bug
complexity: S
impact: Low
wow: 1
note: a row counted among the N failed still renders the green ok token
order: 302
owner: loop/verify-passed-flag
pr: 766
title: "<code>boost verify</code>: CLI audit findings (2026-08)"
---
<b>verify prints a green <code>ok</code> on a row it counts as failed.</b> With a lock rule entry stripped of <code>version</code> and given an empty <code>installed_at</code>, <code>verify</code> renders <em>&ldquo;dotnet-build&nbsp;&nbsp;ok&nbsp;&nbsp;rule &middot; missing lock fields: version, installed_at&rdquo;</em> and then <em>&ldquo;! 1 of 2 items failed verification&rdquo;</em> (exit 1) &mdash; the same row wears the pass token and lands in the failure count. <code>verify --json</code> is no better: <code>status: "ok"</code> beside a non-empty <code>missing_fields</code> and a top-level <code>failed</code>, with no per-row pass/fail signal. Verified mechanism: <code>cmd_verify</code> computes <code>bad</code> from status OR missing fields OR <code>commit_pin == MODIFIED</code> (<code>safety.py:391-393</code>), but the text renderer colors strictly on <code>r['status']</code> via <code>status_role</code> (<code>safety.py:418</code>) without checking membership in <code>bad</code>. Fix (verified recommendation): derive a per-row <code>passed = status in ('ok','quarantined') and not missing_fields and commit_pin != MODIFIED</code>, key the status token's role on it, and add <code>passed</code> to the JSON row. No doc changes needed. Found by the 2026-08 CLI audit (cluster <code>verify-ok-on-failure</code>); repro in the audit log.

<br><br><b>Status (2026-09-04, PR open).</b> Implemented as <code>integrity.verification_passed()</code> in <code>core/integrity.py</code>, consumed by <code>cmd_verify</code> for the failure tally, the JSON row's new <code>passed</code> field, and the row's color token (danger, not the status-keyed role, on any unpassed row). Manually reproduced the exact audit scenario (stripped <code>version</code>, blanked <code>installed_at</code>) end to end through the built CLI, with and without <code>BOOST_COLOR=always</code> forcing ANSI: the row now renders red and <code>passed: false</code> where it previously rendered green. Unit coverage added for every branch of the new predicate; functional coverage added for the missing-fields and drifted-commit-pin cases via <code>--json</code>. <b>Not yet run:</b> this session's sandbox has no PyPI egress (org policy denies <code>pypi.org</code>), so <code>make check</code> — lint/mypy, the eval floors, pytest at 90% coverage, smoke, and the mutation gate — could not be executed here; CI must be green on the PR before this ships.
