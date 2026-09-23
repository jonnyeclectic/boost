---
id: manifest-in-prunes-only-the-root-copy
board: code
section: planned
status: planned
category: Packaging · Bug
complexity: S
impact: Low
wow: 2
note: A maintainer's local agent-permission file ships to PyPI under a directive written to prevent exactly that…
order: 341
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
<b>Fix.</b> Use recursive patterns (<code>global-exclude</code> / <code>prune</code> per path), and
add a test that builds an sdist and fails on any <code>.claude</code> or <code>node_modules</code>
member, so the rule is enforced rather than stated.
