---
id: hash-pinned-reproducible-toolchain-uv-lock
board: code
section: compat
status: planned
category: Security · Repro
complexity: M
impact: Med
wow: 3
note: supply-chain repro
order: 7
owner:
pr:
title: Hash-pinned, reproducible toolchain — <code>uv.lock</code>
---
Pin the dev and CI toolchain with a hash-locked <code>uv.lock</code> (or
           a hashed constraints file) so a yanked or compromised transitive
           dependency can't silently change a build. The reproducibility layer that
           complements Dependabot and <code>pip-audit</code> — same inputs, same
           bytes, every run.
