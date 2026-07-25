---
id: hash-pinned-reproducible-toolchain-uv-lock
board: code
section: compat
status: shipped
category: Security · Repro
complexity: M
impact: Med
wow: 3
note: supply-chain repro
order: 7
owner: loop/hashed-toolchain
pr: 234
title: Hash-pinned, reproducible toolchain — <code>requirements/*.txt</code>
---
Every dev/CI tool was resolved at install time, so two runs of the same gate could
           install different bytes — and only <code>requirements/lint-tools.txt</code> pinned
           anything at all (added after ruff 0.16.0 reddened the gate with no code change).
           Now every tool comes from a generated, hash-pinned
           <code>requirements/*.txt</code>: exact versions <em>plus</em> a sha256 for every
           artifact in the transitive closure, which pip enforces on install, so a yanked or
           tampered dependency fails loudly instead of silently changing a build.
           <code>scripts/lock_toolchain.py</code> regenerates from the <code>.in</code>
           declarations and <code>--check</code> gates drift in <code>make lint</code>; a new
           Dependabot <code>pip</code> entry keeps the locks from rotting. One file per
           consumer, because pip enforces hashes across a whole resolution — and
           <code>test-tools</code> resolves <em>universally</em>, so one file covers the
           3 OS &#215; 3 Python matrix without dragging 3.12/3.14 back to the 3.9 floor's
           versions. The opt-in <code>[eval]</code> extra stays out on purpose: locking its
           deliberately-old langchain stack into a scannable file would re-expose the pin
           <code>osv-scanner.yml</code> is PR-diff-scoped to avoid.
