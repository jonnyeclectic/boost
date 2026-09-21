---
id: audit-bundle-findings
board: code
section: dx
status: shipped
category: CLI · UX
complexity: M
impact: Med
wow: 1
note: mismatched tap/version lines count "already present" — the Boostfile stops being reproducible
order: 252
owner: loop/bundle-audit
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

<br><br><b>Shipped (loop/bundle-audit).</b> All four reproduced on <code>a316c6b9</code> before
any change, with the fixture tap and two imported skills: the dump said <em>&ldquo;&#10003; wrote
Boostfile.local (1 tap, 1 skill)&rdquo;</em> and nothing else; <code>bf2</code> (the two lines
above) gave <em>&ldquo;Installed 0 skills, 2 already present&rdquo;</em>, exit 0, and its
<code>--dry-run</code> <em>&ldquo;would install 0 items, 2 already present&rdquo;</em>;
<code>bundle install</code> with no file said <em>&ldquo;no Boostfile at Boostfile&rdquo;</em>; an
empty stdin said <em>&ldquo;Installed 0 skills&rdquo;</em>. Now: the dump names <em>&ldquo;2 local
skills written as comments &mdash; no tap source to reinstall from&rdquo;</em> on both paths, through
<code>out.warn</code>; each mismatched line warns <em>&ldquo;installed from fixture-tap, Boostfile
wants nosuch/tap &mdash; kept as installed&rdquo;</em> (or the version form), rules and workflows
included, is not reinstalled, and
the summary says <em>&ldquo;2 differ from the Boostfile&rdquo;</em> instead of calling it present;
the missing-file error shows the absolute path; a file with no directives warns <em>&ldquo;nothing to
apply&rdquo;</em>. Exit codes unchanged. The tap/version test is <code>store.lock_drift</code>,
using the same <code>catalog.tap_matches</code> rule as <code>resolve_lock_entry</code>, so a
dump&rarr;install round trip still reads back as present.

<br><br><b>Two more found while fixing these.</b> (1) The one-line style fix was not enough:
<code>out.warn(msg, stream=sys.stderr)</code> chose colour by asking <em>stdout</em>, so
<code>bundle dump &gt; Boostfile</code> printed the notice plain on a terminal and
<code>bundle dump 2&gt;log</code> wrote escape codes into the log (measured with a fake TTY on each
stream). <code>warn</code> now asks the stream it writes to, which also fixes the other
<code>stream=sys.stderr</code> callers in discovery, info and intelligence. (2) The
<code>--dry-run</code> from #835 did not match the real run: with a <code>tap</code> line for a new
registry in the file, <code>skill fixture-tap:ghost</code> (a tap already present, without that
skill) printed <em>&ldquo;cannot resolve yet; its tap would be added by this same file&rdquo;</em> and
exited 0, where the real run says <em>&ldquo;ghost not found in tap fixture-tap &mdash;
skipped&rdquo;</em> and exits 1. The preview now defers only a line whose tap this file would add, by the
line&rsquo;s NAME or by the name the run derives from its URL (or an unqualified one while any
would be added), counts those as <em>&ldquo;N unresolved until
tapped&rdquo;</em>, says <em>&ldquo;would install that&rdquo;</em> instead of <em>&ldquo;installing
that&rdquo;</em> on a version mismatch, and uses the same kind-aware noun as the real summary
(<em>&ldquo;would install 1 skill&rdquo;</em>, not <em>&ldquo;1 item&rdquo;</em>).

<br><br>Found by the 2026-08 CLI audit; repro in the audit log. All behaviour-only &mdash; regenerate
<code>docs/commands.html</code> only if the <code>bundle</code> summary in <code>cli.py</code>
COMMANDS changes.
