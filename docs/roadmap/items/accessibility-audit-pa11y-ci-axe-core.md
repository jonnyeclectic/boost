---
id: accessibility-audit-pa11y-ci-axe-core
board: code
section: docsite
status: shipped
category: Quality · A11y
complexity: M
impact: Med
wow: 4
note: WCAG AA
order: 3
owner: loop/a11y-audit
pr: 243
title: Accessibility audit — <code>pa11y-ci</code> / axe-core
---
WCAG 2.1 AA over every docs page, in two halves. <code>scripts/a11y_check.py</code>
           is the always-on gate: pure stdlib, so it runs in the lint job beside the other
           <code>--check</code> scripts with no Node, Chrome or network. It covers what the
           markup alone decides — <code>lang</code>, <code>alt</code>, accessible names for
           links and buttons, duplicate ids, heading order — plus the 1.4.3 contrast ratios
           computed from the Aurora tokens for the ink/ground pairs the CSS actually puts
           together (listing the real pairs, not the cross-product, so a pair that never
           renders can't cry wolf). The axe-core sweep in <code>tests/visual/</code> is the
           other half: contrast as <em>rendered</em> over glass and gradient, ARIA validity
           against the computed tree, landmarks, focusable-but-hidden elements — everything
           that needs a live DOM and therefore can't be a cheap always-on gate. The audit
           found one real failure, a skipped heading level on the design board, fixed by
           promoting the section headings with their class-scoped selectors in lockstep so
           the rendering is unchanged. Contrast came back clean: the muted tokens the card
           suspected were already fixed (<code>--text-3</code> had been raised from a 3.9:1
           value), and this gate is what keeps them that way.
