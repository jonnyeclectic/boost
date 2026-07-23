---
id: lighthouse-ci-on-the-pages-site
board: code
section: docsite
status: shipped
category: Docs · Perf
complexity: M
impact: High
wow: 5
note: 4 budgets + 3 real a11y fixes
order: 2
owner: loop/lighthouse
pr: 214
title: Lighthouse CI on the Pages site
---
<code>treosh/lighthouse-ci-action</code> scores <code>index.html</code>
           and <code>roadmap.html</code> on performance, accessibility,
           best-practices and SEO on every deploy, and fails the build against
           budgets. Turns the marketing surface's quality into four numbers that can't
           silently regress as the Aurora theme evolves — four floors (a11y and
           SEO 0.95, best-practices 0.90, the noisier performance 0.85) asserted
           on the median of three runs, calibrated below the real scores with
           margin the same way <code>perf_gate</code> sets its thresholds. And,
           as every checker on this repo has, it found real defects on the
           storefront: muted text at <code>3.9:1</code> contrast (below WCAG AA),
           an <code>h2 → h4</code> heading skip, and colour-only footer links —
           all fixed, so both pages now score <code>100</code> on accessibility.
