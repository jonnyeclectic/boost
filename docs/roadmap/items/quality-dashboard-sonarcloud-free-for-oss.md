---
id: quality-dashboard-sonarcloud-free-for-oss
board: code
section: health
status: shipped
category: Quality · Platform
complexity: M
impact: High
wow: 5
note: PR quality gate
order: 6
owner: loop/quality-dashboards
pr: 246
title: Quality dashboard — SonarCloud (free for OSS)
---
One external surface over everything the offline gates measure separately: bugs, code
           smells, security hotspots, duplication and a coverage overlay, decorating each PR
           with a quality gate. Free for public repos. Settings live in
           <code>sonar-project.properties</code> — <code>boost_cli</code> as sources with
           <code>tests</code> declared separately (so the suite's asserts do not score as
           duplication), the generated version stub and boards excluded, coverage read from
           the Cobertura report CI already emits rather than re-running the suite.
           Non-blocking and inert until onboarded: without <code>SONAR_TOKEN</code> the job
           skips and writes what to do into the run summary, so a skipped run explains
           itself instead of looking broken. Not added to required checks — boost's own
           gates stay authoritative because they run offline and a contributor can
           reproduce them.
