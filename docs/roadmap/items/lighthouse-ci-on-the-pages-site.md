---
id: lighthouse-ci-on-the-pages-site
board: code
section: docsite
status: shipped
category: Docs · Perf
complexity: M
impact: High
wow: 5
note: 4 score budgets
order: 2
owner: loop/lighthouse
pr: 214
title: Lighthouse CI on the Pages site
---
<code>treosh/lighthouse-ci-action</code> scores <code>index.html</code>
           and <code>roadmap.html</code> on performance, accessibility,
           best-practices and SEO on every deploy, and fails the build against
           budgets. Turns the marketing surface's quality into four numbers that can't
           silently regress as the Aurora theme evolves — budgets calibrated
           from the first CI run and floored with margin, the same way
           <code>perf_gate</code> sets its thresholds. Also filled the one real
           gap the audit named up front: <code>index.html</code> was missing a
           <code>meta description</code>.
