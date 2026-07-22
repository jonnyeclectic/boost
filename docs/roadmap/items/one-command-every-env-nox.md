---
id: one-command-every-env-nox
board: code
section: compat
status: shipped
category: Testing · Infra
complexity: S
impact: Med
wow: 2
note: local == CI
order: 8
owner: loop/nox
pr: 184
title: One command, every env — <code>nox</code>
---
A <code>noxfile.py</code> makes the full lint / test / smoke / mutation
           gate reproducible across 3.9&nbsp;→&nbsp;3.14 in isolated environments,
           locally and in CI alike — so "green on my machine" and "green in CI"
           finally mean the same thing, and a contributor can run the exact gate
           before pushing.
