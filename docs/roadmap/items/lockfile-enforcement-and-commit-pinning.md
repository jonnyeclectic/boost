---
id: lockfile-enforcement-and-commit-pinning
board: code
section: trust
status: planned
category: Security · Integrity
complexity: S
impact: Med
wow: 3
note: pin to commit
order: 7
owner:
pr:
title: Lockfile enforcement &amp; commit pinning
---
Promote the recorded <code>sha256</code> from a note to a rule: refuse to
           load a skill whose content has drifted from the lockfile, and let users
           pin a skill to an exact commit. The enforcement layer that makes the
           <code>verify</code> digest binding rather than advisory.
