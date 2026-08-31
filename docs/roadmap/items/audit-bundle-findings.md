---
id: audit-bundle-findings
board: code
section: dx
status: planned
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: mismatched tap/version lines count "already present" — the Boostfile stops being reproducible
order: 252
owner:
pr:
title: "boost bundle: CLI audit findings (2026-08)"
---
<b>Local skills vanish into comments with no console notice</b> (cluster
<code>bundle-dump-local-notice</code>, med). With 2 imported (tap=local) skills plus one tap skill
installed, <code>bundle dump</code> prints <em>&ldquo;&#10003; wrote Boostfile.local (1 tap, 1
skill)&rdquo;</em> and warns about rules/workflows &mdash; but says nothing about the local skills,
which appear only as <code># local skill (no tap source): ab-testing</code> comments in the file.
Fires on any dump with local skills, not just the all-local edge. Fix in <code>_bundle_dump</code>
(<code>boost_cli/commands/pkg.py:1211-1234</code>): count the local entries and
<code>out.warn</code> &ldquo;N local skills have no tap source and were written as comments&rdquo; on
both paths, parallel to the existing rules/workflows notice.

<br><br><b>The present check ignores tap and version</b> (cluster <code>bundle-present-check</code>,
med). With brainstorming installed from <code>sickn33/antigravity-awesome-skills</code> v0.0.0, the
lines <code>skill nosuch/tap:brainstorming</code> and
<code>skill sickn33/&hellip;:brainstorming@9.9.9</code> both yield exactly <em>&ldquo;Installed 0
skills, 2 already present&rdquo;</em>, exit 0, no warning &mdash; presence is
<code>have_installed.get(sname)</code> on the bare name and <code>tapq</code>/<code>sver</code> are
parsed then discarded (<code>pkg.py:1281-1290</code>). The code's own comment says a Boostfile is
&ldquo;meant to be reproducible&rdquo; (<code>:1298</code>), and the &ldquo;Boostfile wants @X, tap
has Y&rdquo; warning already exists on the fresh-install path (<code>:1306-1308</code>). Fix: compare
the lock entry's tap/version against the Boostfile line before counting present; warn on mismatch,
don't reinstall.

<br><br><b>The dump omission notice is styled differently on the two paths</b> (cluster
<code>bundle-dump-warn-style</code>, low). TTY <code>bundle dump</code> prints the notice as a bare
uncoloured print (<code>pkg.py:1219</code>) while <code>bundle dump Boostfile</code> sends the same
text through <code>out.warn</code>, yellow (<code>:1233</code>). One-line fix:
<code>out.warn(msg, stream=sys.stderr)</code> on both, keeping stdout a clean artifact.

<br><br><b>Two small install-message gaps</b> (cluster <code>bundle-install-messages</code>, low).
<code>bundle install</code> with no Boostfile reports the tautology <em>&ldquo;Error: no Boostfile at
Boostfile&rdquo;</em> &mdash; pathlib normalises <code>./Boostfile</code> to the bare name
(<code>pkg.py:1241-1244</code>), and <code>./nosuch/Boostfile</code> likewise loses its
<code>./</code>. And <code>bundle install - &lt; /dev/null</code> (or a comment-only file) reports
<em>&ldquo;Installed 0 skills&rdquo;</em>, exit 0, with no hint that nothing was parsed. Fix: display
the resolved path through the existing <code>_tilde()</code>, and warn when zero tap/skill lines were
read (keeping exit 0).

<br><br>Found by the 2026-08 CLI audit; repro in the audit log. All behaviour-only &mdash; regenerate
<code>docs/commands.html</code> only if the <code>bundle</code> summary in <code>cli.py</code>
COMMANDS changes.
