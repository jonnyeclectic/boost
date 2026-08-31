---
id: audit-profile-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: declined --prune leaves extras fully linked yet still prints "✓ switched"
order: 281
owner:
pr:
title: "<code>boost profile use</code>: CLI audit findings (2026-08)"
---
<b><code>profile use</code> omits the version-drift warning <code>diff</code> reports, and a declined <code>--prune</code> still reports a clean switch with extras fully linked.</b> Reproduced: <code>profile diff daily</code> prints <code>~ brainstorming  (version differs)</code> but <code>profile use daily</code> says only <code>✓ switched to profile daily</code> — <code>team.py:335</code> discards the <code>_changed</code> tuple element that <code>diff</code> prints at <code>team.py:315-316</code>. Worse, with an extra skill installed and the <code>--prune</code> confirm declined via EOF, the output is <code>kept extras installed</code> then the same unconditional <code>✓ switched to profile daily</code>, and the extra's symlink was confirmed still present in <code>.claude/skills/</code> — the non-prune path would have sidelined it, so the checkmark claims a state the machine is not in.<br><br>Verified fix (<code>boost_cli/commands/team.py:333-367</code>): print a warn line per entry in <code>_changed</code>, mirroring diff's "~ NAME (version differs)" wording; and after a declined <code>--prune</code> confirm either fall through to the sideline/unlink branch or drop the trailing checkmark and say the switch was partial. No flag changes, so no docs regeneration needed.<br><br>Found by the 2026-08 CLI audit (cluster <code>profile-use-drift-prune</code>); repro in the audit log.
