---
id: fix-self-update-version-detection-dead-branch
board: code
section: internals
status: next
category: Correctness
complexity: S
impact: High
wow: 3
note: 
order: 2
owner:
pr:
title: Fix <code>self-update</code> version detection (dead branch)
---
<code>cmd_self_update</code> greps <code>__init__.py</code> for a <code>__version__ = "…"</code> literal (<code>commands/configuration.py:1090</code>), but the constant is <code>_detect_version()</code> (setuptools-scm — no literal). The regex never matches, so it reports <b>"already up to date"</b> even after a pull brings a newer tag. The success path is unreachable.
