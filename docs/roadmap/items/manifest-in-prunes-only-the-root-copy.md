---
id: manifest-in-prunes-only-the-root-copy
board: code
section: planned
status: shipped
category: Packaging · Bug
complexity: S
impact: Low
wow: 2
note: A maintainer's local agent-permission file ships to PyPI under a directive written to prevent exactly that…
order: 341
owner: loop/manifest-prune-sdist
pr: "967"
title: MANIFEST.in prunes only the root copy, so dev-local files ship in the sdist
---
<b>Found by the audit of packaging, and confirmed against the artifact on PyPI.</b>
<code>MANIFEST.in</code> opens by saying everything below it is dev-only and should never ship, then
writes <code>prune .claude</code> and <code>exclude package.json package-lock.json</code>. Both
patterns are root-relative, so they match <code>./.claude/</code> and <code>./package.json</code>
and miss <code>docs/.claude/settings.local.json</code> and <code>tests/visual/package.json</code>,
which setuptools-scm's file finder adds because they are tracked. Both ship in every release:
<code>boost_skill_cli-1.2.138.tar.gz</code> off PyPI carries three such files, as four tar members
(one is the <code>docs/.claude/</code> directory entry).
<br><br>
Today's contents are harmless, which is the reason to fix it now rather than after someone adds a
machine-specific path or a tool allowlist to a checked-in agent-permission file.
<br><br>
<b>Fixed.</b> A MANIFEST.in glob never crosses a separator — setuptools rewrites every
<code>*</code> to <code>[^/]*</code> and <code>**</code> is not special — so no single line can be
depth-agnostic on both sides of the directory name, and the fix is a ladder. It goes on the
<i>prefix</i>: <code>prune &lt;dir&gt;</code> is already recursive below the directory it names, so
<code>prune .claude</code> · <code>*/.claude</code> · <code>*/*/.claude</code> ·
<code>*/*/*/.claude</code> covers every layout inside whatever its depth. The npm files keep a
single unanchored <code>global-exclude</code>, which matches the whole relative path and so needs no
ladder at all.
<br><br>
The rule is now enforced twice, because a pattern list and a member list are different claims.
<code>tests/unit/test_sdist_contents.py</code> runs setuptools' own matcher
(<code>_distutils.filelist.FileList</code>, the engine its <code>sdist</code> command uses) over
<code>git ls-files</code>, which is what setuptools-scm's file finder hands it — offline, in the unit
suite, with planted paths so the test measures the recursion rather than the repo happening to have
no offender there. Nine of its seventeen tests fail against the old manifest. The
<code>package-metadata</code> workflow then greps the tarball it already builds, so the thing that is
actually uploaded is checked before every release.
<br><br>
<b>Review found three more, two of them in this fix.</b> The first draft replaced the anchored
patterns with a <i>suffix</i> ladder, <code>global-exclude .claude/* .claude/*/* .claude/*/*/*</code>
— which still let a plugin's own
<code>docs/.claude/plugins/&lt;pack&gt;/commands/&lt;x&gt;.md</code> through, four levels down. That
is what moved the ladder to the prefix, and two planted paths now pin it. The second was in the
simulation rather than the packaging: distutils runs every pattern through
<code>convert_path</code>, so on Windows <code>.claude/*</code> becomes <code>.claude\*</code> and
cannot match the <code>/</code>-joined output of <code>git ls-files</code> — the three Windows legs
of the matrix would have failed against a correct manifest. Paths are now compared in the platform's
own separator. The third was the test toolchain: <code>python -m venv</code> stopped seeding
<code>setuptools</code> in 3.12 and the <code>tests</code> job does no editable install, so every leg
raised <code>ModuleNotFoundError</code> while the test passed locally, where <code>make venv</code>
also installs the release tools. It is declared in <code>requirements/test-tools.in</code> now.
