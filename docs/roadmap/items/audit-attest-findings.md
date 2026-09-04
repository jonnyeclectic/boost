---
id: audit-attest-findings
board: code
section: trust
status: inflight
category: Trust · UX
complexity: S
impact: Low
wow: 1
note: a deleted store dir is reported as a sha mismatch; drift names the same state correctly
order: 248
owner: loop/attest-verify-reason
pr: 765
title: "boost attest: CLI audit findings (2026-08)"
---
<b><code>attest --verify</code> misdiagnoses a missing artifact as a content change.</b> After
deleting <code>~/.agents/skills/brainstorming</code>, <code>boost attest --verify brainstorming</code>
prints <em>&ldquo;! brainstorming: store content no longer matches the lock sha&rdquo;</em> (exit 1)
&mdash; while <code>boost drift</code> on the same state correctly says <em>store-missing &middot;
boost heal</em>. <code>safety.py:556-557</code> collapses <code>sdir.is_dir()</code> and the sha
comparison into one boolean and <code>:584-586</code> words every failure as a sha mismatch; the
verify pass found a second site &mdash; the rule/workflow branch (<code>:560-563</code>) folds
STATUS_MISSING into the same &ldquo;materialized content no longer matches&rdquo; wording, and the
no-name all-skills invocation collapses identically.

<br><br>Low stakes &mdash; the failure <em>is</em> detected and exit is 1 &mdash; but the message
sends the user hunting for tampering when the remedy is <code>boost heal</code>. Fix: record a reason
alongside <code>sha_ok</code> in both branches (skill: <em>&ldquo;store directory missing (boost
heal)&rdquo;</em>; non-skill: <em>&ldquo;materialized file missing&rdquo;</em>), keep the sha-mismatch
wording for the genuinely modified case, and in <code>--json</code> add a <code>reason</code> field
(<code>missing</code>/<code>modified</code>) rather than repurposing the boolean. No doc changes.

<br><br>Found by the 2026-08 CLI audit (cluster <code>attest-missing-store-dir</code>); repro in the
audit log.

<br><br><b>Status.</b> Fix and tests are up in <a href="https://github.com/jonnyeclectic/boost/pull/765">PR
#765</a>, verified with pytest/ruff/mypy and <code>smoke.sh</code> — but the session that wrote it ran
in a sandboxed environment with no PyPI/npm egress, so <code>make check</code> (mutation gate
included) could not be run locally. Staying <code>inflight</code> until CI confirms the full gate.
