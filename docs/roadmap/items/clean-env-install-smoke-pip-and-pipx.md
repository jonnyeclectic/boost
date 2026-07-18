---
id: clean-env-install-smoke-pip-and-pipx
board: code
section: compat
status: planned
category: Testing · Install
complexity: S
impact: High
wow: 4
note: tests the real artifact
order: 2
owner:
pr:
title: Clean-env install smoke — pip &amp; <code>pipx</code>
---
Every gate runs against an editable <code>pip install -e .</code>, which
           hides missing package-data, a broken entry point or an undeclared
           dependency. A job that <code>pip install</code>s the built wheel into a
           <em>fresh</em> venv (and <code>pipx install</code>s it) then runs
           <code>boost --version</code> proves the artifact a user actually gets
           works.
