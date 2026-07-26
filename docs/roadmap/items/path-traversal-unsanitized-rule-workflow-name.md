---
id: path-traversal-unsanitized-rule-workflow-name
board: code
section: trust
status: shipped
category: Security · Bug
complexity: M
impact: High
wow: 3
note: live-reproduced
order: 10
owner: loop/rule-name-traversal
pr:
title: Path traversal via unsanitized rule/workflow name
---
<code>catalog._make_entry</code> only slugifies a catalog name when it contains a space, so a tap's
rule/workflow frontmatter carrying <code>name: ../../../../.ssh/authorized_keys</code> sails straight
through into <code>rule_target</code>/<code>workflow_target</code>, which build the destination as
<code>root / "rules" / (name + ext)</code> with zero traversal guard — unlike
<code>skill_store_dir()</code>'s <code>[A-Za-z0-9._-]+</code> regex. A malicious tap can write an
arbitrary file outside <code>.cursor/rules/</code> or <code>.claude/</code>, and it is worse under
<code>--scope project</code> since <code>base</code> is the victim's own repo. Apply the same
name-validation regex used by <code>skill_store_dir()</code> before any rule/workflow install path
is built.
