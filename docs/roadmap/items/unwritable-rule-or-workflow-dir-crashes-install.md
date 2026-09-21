---
id: unwritable-rule-or-workflow-dir-crashes-install
board: code
section: planned
status: shipped
category: Onboarding · Bug
complexity: M
impact: Med
wow: 2
note: an unwritable ~/.cursor/rules or ~/.cursor/commands still crashes a rule/workflow install at exit 70, leaving files the lock never records
order: 326
owner: loop/unwritable-rule-dir
pr: 931
title: An unwritable agent <code>rules/</code> or <code>commands/</code> dir still crashes a rule or workflow install at exit 70
---
<b>Found while verifying #890</b>, which fixed the <em>skills</em> half of this for
<code>unwritable-agent-dir-has-no-remedy</code>. <code>store.link_agents</code> now catches
<code>PermissionError</code> per agent, and the install names <code>chmod u+w</code> then
<code>boost sync</code>. Rules and workflows do not go through <code>link_agents</code>. They are
<em>materialized</em> per agent (<code>_install_rule</code> / <code>_install_workflow</code>), and
that write path has no guard.

<b>Measured on #890's branch</b>, in a disposable HOME: with <code>chmod 500
~/.cursor/rules</code> (or <code>~/.cursor/commands</code>), installing a rule (or workflow)
exits <b>70</b> with a crash report. The agents written before the failure keep their files,
including a rule block in <code>~/.claude/CLAUDE.md</code>, but the lock records none of it.
<code>boost uninstall</code> then says the rule "is not installed", and <code>boost doctor</code>
exits 0 because it never checks those directories. This is the same shape the skills fix
closed: a partial install nothing can see or undo.

<b>Also seen:</b> <code>boost reinstall</code> and <code>boost update</code> discarded the install
result. After #890 they name an unwritable skills dir, but they still say nothing about
<code>conflicts</code> (a real file squatting a link path), which was already true before #890.

<b>Fix direction.</b> Guard the per-agent materialization write the way <code>link_agents</code>
now does: skip the agent, record it on the result, and let the command layer name the remedy.
doctor should check the materializing agents' <code>rules/</code> and <code>commands/</code>
directories, as it checks the linking agents' <code>skills/</code> ones. The remedy has to be
checked before it is printed: whether <code>boost sync</code> re-materializes a rule or workflow
for an agent it skipped is not established here.
