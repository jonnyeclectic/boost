---
id: dependabot-missing-pip-ecosystem
board: code
section: pipeline
status: planned
category: Supply chain
complexity: S
impact: Med
wow: 2
note:
order: 11
owner:
pr:
title: Dependabot has no <code>pip</code> ecosystem entry
---
<code>.github/dependabot.yml</code> declares only <code>package-ecosystem: github-actions</code>,
reasoned as "the runtime is stdlib-only" — but the <code>[rag]</code>/<code>[eval]</code>/
<code>[bdd]</code>/<code>[perf]</code> extras in <code>pyproject.toml</code> (sqlite-vec, ranx,
ragas, the langchain stack, behave, pytest-benchmark) never get proactive version-bump PRs, only
reactive <code>pip-audit</code> CVE flags. Add a <code>pip</code> ecosystem entry targeting
<code>pyproject.toml</code> alongside the existing <code>github-actions</code> one.
