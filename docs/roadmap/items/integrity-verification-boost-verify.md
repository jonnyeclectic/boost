---
id: integrity-verification-boost-verify
board: code
section: trust
status: planned
category: Security · Integrity
complexity: S
impact: High
wow: 4
note: reuses sha256_dir
order: 2
owner:
pr:
title: Integrity verification — <code>boost verify</code>
---
The lockfile already records a <code>sha256</code> per install via
           <code>util.sha256_dir</code>, but nothing ever re-checks it. A
           <code>verify</code> command (and a <code>doctor</code> gate) that
           re-hashes installed skills and flags drift turns that stored digest into
           actual tamper-detection — cheap, and built on machinery that already
           exists.
