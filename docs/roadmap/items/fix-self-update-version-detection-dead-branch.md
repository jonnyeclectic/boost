---
id: fix-self-update-version-detection-dead-branch
board: code
section: shipped
status: shipped
category: Correctness
complexity: S
impact: High
wow: 3
note: broken headline command, now works
order: 7
owner: loop/self-update-fix
pr:
title: Fix <code>self-update</code> version detection (dead branch)
---
<code>boost self-update</code> greped <code>__init__.py</code> for a
           <code>__version__ = "…"</code> literal that setuptools-scm never
           writes, so the regex never matched and it always reported
           <b>"already up to date"</b> — even after a pull brought a newer tag.
           The success path was <em>unreachable</em>. It now derives the pulled
           version straight from git (<code>describe --tags</code>, mirroring
           <code>_detect_version()</code>) and treats a moved <code>HEAD</code>
           as the "an update landed" signal, so the version-bump path finally
           fires. Regression tests cover both the up-to-date and update-landed
           branches.
