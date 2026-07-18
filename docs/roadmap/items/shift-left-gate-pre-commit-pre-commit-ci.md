---
id: shift-left-gate-pre-commit-pre-commit-ci
board: code
section: dx
status: planned
category: DX · Infra
complexity: S
impact: High
wow: 4
note: auto-fix PRs
order: 2
owner:
pr:
title: Shift-left gate — <code>pre-commit</code> + pre-commit.ci
---
A <code>.pre-commit-config.yaml</code> runs ruff, mypy, codespell and the
           whitespace fixers <em>before</em> code ever reaches CI, and the free-for-OSS
           <strong>pre-commit.ci</strong> auto-fixes and auto-updates hooks right on the
           PR. The foundation the rest of this section plugs into — one config,
           many checks, faster feedback.
