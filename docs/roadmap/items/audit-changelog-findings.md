---
id: audit-changelog-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: fetch --unshallow advised on complete clones; rules/workflows logged at directory granularity
order: 254
owner:
pr:
title: "boost changelog: CLI audit findings (2026-08)"
---
<b>The shallow-clone hint fires on complete clones</b> (cluster <code>changelog-shallow-hint</code>,
med). <code>changelog cowboy-coding</code> on a full local fixture clone prints its one commit and
then <em>&ldquo;(shallow clone: run <code>git -C ~/.boost/repos/fixture-tap fetch --unshallow</code>
for full history)&rdquo;</em> &mdash; but the clone has no <code>.git/shallow</code> file, and that
command fails on a complete clone. <code>boost_cli/commands/quality.py:1159</code> gates the hint on
<code>len(lines) &lt; 3</code> &mdash; output length, not clone shape &mdash; so any short history
triggers it; it is only accidentally true for default remote taps, which really are shallow. Fix:
gate on <code>(tap.path/'.git'/'shallow').exists()</code> as well, plus a unit test with a full
fixture clone.

<br><br><b>Rules and workflows are addressed by their directory, and changelog ignores the lock
entry</b> (cluster <code>rule-file-vs-directory</code>, med; also hits <code>home</code>).
<code>changelog csharp-reviewer</code> &mdash; an <em>installed</em> workflow &mdash; fails with
<em>&ldquo;Error: 'csharp-reviewer' matches 3 different skills in affaan-m/ECC&rdquo;</em>, because
<code>quality.py:1140-1153</code> resolves via <code>lockfile.get_skill</code> (skills only) then
catalog ambiguity, although the lock already records <code>"source_file":
"ci-cd/dotnet-build.mdc"</code>-style entries and <code>lockfile.find_any</code>
(<code>lockfile.py:195</code>, whose docstring names this exact failure class) sits unused. When
resolution does succeed, the log runs over <code>rel_dir</code> &mdash; the containing directory
(<code>catalog.py:121-122</code>) &mdash; so <code>git log -- ci-cd</code> covers every sibling rule,
masked today only by the depth-1 clone; following the command's own unshallow hint would surface it.
<code>home --print dependency-management</code> has the same shape: it links
<code>&hellip;/tree/HEAD/dotnet-sdk</code> (a folder of 11 rules) and <code>actix-expert</code> links
a folder of 138 workflows (<code>info.py:865-891</code>). One fix covers all three findings: resolve
installed names with <code>lockfile.find_any</code>, and for <code>kind != skill</code> pass
<code>entry['source_file']</code> (catalog: <code>entry['skill_md']</code>) to
<code>log_for_path</code> and build <code>/blob/HEAD/&lt;file&gt;</code> URLs in <code>cmd_home</code>,
keeping <code>rel_dir</code> for skills; add a unit test with a two-commit repo touching two rules in
one directory.

<br><br>Found by the 2026-08 CLI audit (clusters <code>changelog-shallow-hint</code>,
<code>rule-file-vs-directory</code>); repro in the audit log. Regenerate
<code>docs/commands.html</code> only if the <code>home</code>/<code>changelog</code> summaries change.
