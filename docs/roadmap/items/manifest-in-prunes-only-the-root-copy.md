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
which setuptools-scm's file finder adds because they are tracked. Both ship in every release.
<br><br>
Today's contents are harmless, which is the reason to fix it now rather than after someone adds a
machine-specific path or a tool allowlist to a checked-in agent-permission file.
<br><br>
<b>Fixed.</b> The three root-anchored patterns became unanchored
<code>global-exclude</code> ones, which is what makes them recursive — one line per directory depth,
because a MANIFEST.in glob never crosses a separator (setuptools rewrites every <code>*</code> to
<code>[^/]*</code>, and <code>**</code> is not special). Measured on the real artifact: four members
before, none after.
<br><br>
The rule is now enforced twice, because a pattern list and a member list are different claims.
<code>tests/unit/test_sdist_contents.py</code> runs setuptools' own matcher
(<code>_distutils.filelist.FileList</code>, the engine its <code>sdist</code> command uses) over
<code>git ls-files</code>, which is what setuptools-scm's file finder hands it — offline, in the unit
suite, with planted paths three directories deep so the test measures the recursion rather than the
repo happening to have no offender there. It fails on the old manifest. The
<code>package-metadata</code> workflow then greps the tarball it already builds, so the thing that is
actually uploaded is checked before every release.
