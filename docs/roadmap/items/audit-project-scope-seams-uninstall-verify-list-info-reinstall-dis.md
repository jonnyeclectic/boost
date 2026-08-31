---
id: audit-project-scope-seams-uninstall-verify-list-info-reinstall-dis
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: install --local writes a lock that uninstall, verify, doctor and list then cannot find
order: 235
owner:
pr:
title: "Project scope seams: <code>uninstall</code>/<code>verify</code>/<code>list</code>/<code>info</code>/<code>reinstall</code> disagree with what <code>install --local</code> wrote"
---
The project-scope-across-every-command item shipped, and the 2026-08 CLI audit found its seams: the
writers and readers resolve "the project" differently. <code>install --local</code> uses
<code>scopes.resolve_base</code>, which falls back to the cwd
(<code>scopes.py:83-104</code>), while <code>uninstall</code>'s project fallback
(<code>store.py:1249</code>) and <code>verify</code>/<code>doctor</code>/<code>list</code> all go
through <code>scopes.project_root</code>, which requires a VCS marker (<code>scopes.py:45</code>).
So from a plain directory, <code>install anthropics/skills:pdf --local</code> writes
<code>.boost/skill-lock.json</code> and <code>.claude/skills/pdf</code> and reports success &mdash;
then <code>verify pdf</code> answers <em>&ldquo;Error: not installed: pdf&rdquo;</em>, plain
<code>uninstall</code> answers <em>&ldquo;brainstorming is not installed&rdquo;</em>, and
<code>doctor</code>/<code>list</code> show no project row. After <code>mkdir .git</code> the same
commands find everything. All six findings reproduced.

Four more seams, each confirmed in source. The already-installed error hints
<em>&ldquo;<code>boost reinstall brainstorming --local</code> to force&rdquo;</em> &mdash; a flag
<code>reinstall</code> does not have; following the hint exits 2 with
<em>&ldquo;unrecognized arguments: --local&rdquo;</em> (<code>store.py:615-617</code>).
<code>verify &lt;project-only name&gt;</code> ignores the filter and grades every user-scope item
&mdash; <code>cmd_verify</code> already passes <code>[]</code> for project-only names
(<code>safety.py:355-356</code>) but <code>_iter_installed_all</code> treats <code>[]</code> as
&ldquo;everything&rdquo; (<code>_common.py:66</code>, <code>if names:</code>), so the run can
<em>fail</em> on a rule the user never named. <code>list --local --kind rule</code> prints
<em>&ldquo;&#9675; no rules installed&rdquo;</em> although project scope holds skills only. And
<code>info</code> on a project-scoped skill shows the not-installed card &mdash; no version,
installed date, commit or agents rows &mdash; though the project lock records them all and
<code>--json</code> returns them under <code>project</code>.

The verified fix, one follow-up card: make <code>_iter_installed_all</code> treat <code>[]</code>
as nothing (<code>_common.py:66</code>) &middot; change the hint to
<code>boost install NAME --local --force</code> (matching README ~328) or add
<code>--local</code> to <code>reinstall</code> &middot; unify the uninstall fallback on
<code>resolve_base</code> or hint <code>--local</code> (<code>store.py:1249</code>) &middot; have
<code>install --local</code> warn outside a VCS root, or teach <code>project_root</code> to accept
<code>.boost/skill-lock.json</code> as a marker &middot; refuse
<code>list --local --kind rule|workflow</code> the way the existing <code>--tag</code> guard does
(<code>info.py:274-281</code>) &middot; render the plock identity rows in <code>cmd_info</code>.
Docs: README ~304&ndash;328 (uninstall/reinstall routes), a follow-up note on
<code>docs/roadmap/items/project-scope-across-every-command.md</code>, and regenerate
docs/commands.html if <code>reinstall</code> gains <code>--local</code>. Found by the 2026-08 CLI
audit (cluster <code>project-scope-readers</code>); repro in the audit log.
