---
id: dependabot-missing-pip-ecosystem
board: code
section: pipeline
status: planned
category: Supply chain
complexity: S
impact: Low
wow: 1
note: extras only — <code>/requirements</code> is covered
order: 11
owner:
pr:
title: Dependabot's <code>pip</code> entry misses <code>pyproject.toml</code>'s extras
---
<code>.github/dependabot.yml</code> declares <code>pip</code> for
<code>directory: /requirements</code>, so the hash-pinned dev/CI toolchain does get weekly
bump PRs. What it does <b>not</b> cover is <code>pyproject.toml</code> at the repo root:
Dependabot only scans manifests under the declared <code>directory</code>, so the optional
extras — <code>[rag]</code> (sqlite-vec), <code>[eval]</code> (ranx, ragas and the pinned
langchain 0.3 stack), <code>[bdd]</code> (behave), <code>[perf]</code> (pytest-benchmark) —
never get proactive version-bump PRs, only reactive <code>pip-audit</code> CVE flags.
Low impact by design: <code>[project].dependencies</code> is empty, so none of this reaches
anyone who installs <code>boost-skill-cli</code> — it is contributor-facing only. The fix is
a second <code>pip</code> entry with <code>directory: /</code>. Weigh it against the noise:
the <code>[eval]</code> stack is <b>deliberately</b> held at langchain 0.3 because ragas
0.2.x breaks against langchain &ge;1.0, so that one will raise PRs that must be closed
unmerged until ragas catches up.
