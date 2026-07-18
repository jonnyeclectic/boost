---
id: accessibility-audit-pa11y-ci-axe-core
board: code
section: docsite
status: planned
category: Quality · A11y
complexity: M
impact: Med
wow: 4
note: WCAG AA
order: 3
owner:
pr:
title: Accessibility audit — <code>pa11y-ci</code> / axe-core
---
Run WCAG checks over the rendered pages: colour contrast, focus order,
           alt text and ARIA. The Aurora palette leans on muted
           <code>--text-2/--text-3</code> tokens against dark glass — exactly where
           contrast ratios slip below AA. Catches the a11y regressions a purely
           visual review misses.
