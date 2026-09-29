---
id: audit-project-scope-seams-uninstall-verify-list-info-reinstall-dis
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: install --local wrote a lock that uninstall, verify, doctor and list then could not find
order: 235
owner: loop/project-scope-seams
pr:
title: "Project scope seams: <code>uninstall</code>/<code>verify</code>/<code>list</code>/<code>info</code> disagreed with what <code>install --local</code> wrote"
---
The project-scope-across-every-command item shipped, and the 2026-08 CLI audit found its seams: the
writers and readers resolved &ldquo;the project&rdquo; differently. <code>install --local</code>
uses <code>scopes.resolve_base</code>, which falls back to the cwd, while
<code>uninstall</code>'s project fallback and <code>verify</code>/<code>doctor</code>/<code>list</code>/<code>info</code>
all went through <code>scopes.project_root</code>, which requires a VCS marker. So from a plain
directory, <code>install anthropics/skills:pdf --local</code> wrote
<code>.boost/skill-lock.json</code> and <code>.claude/skills/pdf</code> and reported success
&mdash; then <code>verify pdf</code> answered <em>&ldquo;Error: not installed: pdf&rdquo;</em>,
plain <code>uninstall</code> answered <em>&ldquo;is not installed&rdquo;</em>, and
<code>doctor</code>/<code>list</code> showed no project row, while <code>sync</code> could still
see it and offered to re-materialize what <code>doctor</code> said was absent. After
<code>mkdir .git</code> the same commands found everything. All six findings reproduced.

Every read site now resolves its base the way install writes one, and <code>project_root</code>
is documented as the marker walk rather than the answer &mdash; it has one caller left,
<code>resolve_base</code>. <code>$HOME</code> is still never a project and deletion is still
gated by <code>scopes.resolve_in_base</code>, both re-asserted. Because bare <code>uninstall</code>
can now act in an unmarked directory that carries a committed <code>.boost/</code>, its TTY
confirmation names the directory it is about to delete from.

Three of the remaining seams were as the audit described and one was not.
<code>_iter_installed_all</code> now treats <code>[]</code> as nothing rather than everything, so
<code>verify &lt;project-only name&gt;</code> stops grading &mdash; and failing on &mdash; items
the user never named; the signature already declared <code>None</code> as
&ldquo;all&rdquo;, and the only caller that ever passed <code>[]</code> meant &ldquo;none&rdquo;.
The already-installed error hints <code>boost install NAME --local --force</code>, the one route
that works: <code>reinstall --local</code> exits 2 and bare <code>reinstall</code> reads the user
lock only, so it answers &ldquo;not installed&rdquo; for the very skill the error is about. And
<code>info</code> on a project-scoped skill now renders the identity rows off
<code>lock or plock</code> &mdash; version, tap, source, commit, sha256, dates, agents and a
<code>scope</code> row &mdash; while omitting rather than blanking <code>store</code>,
<code>pinned</code> and <code>quarantined</code>, which a project entry has no keys for.

<b>The audit was wrong about <code>list --local --kind rule</code>.</b> Project scope is not
skills-only: <code>store.install</code> passes <code>scope</code> to <code>_install_rule</code>
and <code>_install_workflow</code>, both write into the repo, and both stamp
<code>scope</code>+<code>base</code> into the <em>user</em> lock, because a project lock has a
<code>skills</code> key and nothing else. So the proposed <code>--tag</code>-style refusal would
have hardened a falsehood into an error message. <code>--local</code> now filters those two
dicts by <code>scopes.owned_by</code> (resolved paths on both sides) instead of discarding them.
Found by the 2026-08 CLI audit (cluster <code>project-scope-readers</code>).
