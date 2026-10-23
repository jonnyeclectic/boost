---
id: windows-autocrlf-reads-project-copies-as-drifted
board: code
section: shipped
status: shipped
category: Robustness · Bug
complexity: M
impact: Medium
wow: 3
note: On Windows with core.autocrlf, a teammate's clone of a project's committed skill copies hashes differently from the lock…
order: 378
owner:
pr:
title: On Windows, a clone of a project's committed skill copies reads as drifted
---
<b>Found while fixing the Windows runs of the 2026-10-22 release train.</b>
Project-scope copies are checked against the lock with <code>util.sha256_dir</code>, which hashes raw
bytes. Git for Windows defaults to <code>core.autocrlf=true</code>, so a teammate's clone, or the
<code>git checkout</code> that <code>boost doctor</code> prints to restore them, writes the copies back with CRLF
line endings. Their hash no longer matches the one the lock recorded, so boost reports them as drifted.
<code>tests/functional/test_project_moved_tap_roundtrip.py</code> pins <code>core.autocrlf=false</code> in its fixture
for exactly this reason.

<b>Fix direction.</b> Choose between two options. One is to have boost write a <code>.gitattributes</code>
(<code>* -text</code>) beside the project copies it commits, so git leaves their bytes alone. The other is to
normalise line endings in the hash used for drift checks. The first keeps the hash what it means today and costs
one file in the user's repo. The second changes what every existing lock row describes, so it needs a lock-format
step.
