---
id: mutation-hardening-core-gitutil-py
board: code
section: shipped
status: shipped
category: Testing
complexity: M
impact: High
wow: 4
note: 34 mutants killed
order: 2
owner:
pr:
title: Mutation hardening — <code>core/gitutil.py</code>
---
35&nbsp;→&nbsp;1 survivor via argv-assertion tests that record the exact
           git command line — sidestepping the macOS case-insensitive filesystem
           that let <code>HEAD/head</code>, <code>.git/.GIT</code> and
           <code>git/GIT</code> mutants survive against a real repo.
