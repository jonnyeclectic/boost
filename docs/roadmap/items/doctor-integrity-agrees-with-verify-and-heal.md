---
id: doctor-integrity-agrees-with-verify-and-heal
board: code
section: health
status: shipped
category: Diagnostics · Bug
complexity: S
impact: Med
wow: 2
note: doctor said healthy over hand-edited rules/workflows, and prescribed a heal that declines for a pinned skill
order: 355
owner: fix/doctor-integrity
pr:
title: <code>boost doctor</code> agrees with <code>verify</code> on rule/workflow edits, and stops prescribing a <code>heal</code> that declines
---
<b>Rule and workflow drift.</b> Appending one line to an installed
<code>.cursor/rules/*.mdc</code> and to a <code>.claude/commands/*.md</code>
made <code>boost verify</code> exit 1 with both <code>modified</code> and
<code>boost drift</code> report two local edits, while <code>boost doctor</code>
said <code>1 rule and 1 workflow fully materialized … healthy</code>, rc 0:
its rule and workflow loops checked only that each file existed. They now ask
<code>integrity.materialized_status</code>, the function <code>verify</code>
uses, and name <code>X modified since install — run `boost verify`</code>.
A <code>CLAUDE.md</code> block with a start marker and no end marker counted as
present; it is now named as malformed with the hand edit that fixes it
(<code>rules.unclosed_block</code>, a new helper; the merge logic is unchanged).

<b>Pinned skill, store dir gone, tap moved.</b> <code>boost heal</code> printed
<code>✓ … repair declined</code> and exited 0, and <code>boost doctor</code> kept
saying <code>run `boost heal`</code>, a loop with no exit.
<code>store.is_unrepaired</code> now recognises a declined repair (a pin, or a
URL import sync cannot re-clone), so heal and sync print it as a warning and
heal exits 1 in both the real and <code>--dry-run</code> runs. Doctor asks
<code>store.plan_missing_store</code> for a pinned entry and prints its answer:
unpin, or <code>boost reinstall</code>.
