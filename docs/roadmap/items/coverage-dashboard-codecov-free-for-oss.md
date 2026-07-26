---
id: coverage-dashboard-codecov-free-for-oss
board: code
section: dx
status: shipped
category: Testing · Platform
complexity: S
impact: Med
wow: 3
note: PR decoration
order: 8
owner: loop/quality-dashboards
pr: 246
title: Coverage dashboard — Codecov (free for OSS)
---
The self-contained <code>diff-cover</code> gate enforces patch coverage in CI; this is
           its hosted counterpart — the same <code>coverage.xml</code> the gate already
           reads, turned into PR diff-coverage comments, a file sunburst and a trend line
           over time. Wired into the existing <code>patch-coverage</code> job (no second
           test run) and <em>deliberately non-blocking</em>: <code>codecov.yml</code> marks
           every status <code>informational</code>, because boost already enforces coverage
           twice offline and a merge should never hinge on a third party's uptime. Inert
           until a <code>CODECOV_TOKEN</code> secret exists — the step's <code>if</code>
           reads the token through <code>env</code> (a secret cannot be referenced directly
           in an <code>if</code>), so with no secret it skips rather than fails.
