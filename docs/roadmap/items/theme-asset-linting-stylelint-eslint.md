---
id: theme-asset-linting-stylelint-eslint
board: code
section: docsite
status: shipped
category: Quality · Style
complexity: S
impact: Med
wow: 2
note: shared blast radius
order: 8
owner: loop/themelint
pr: 203
title: Theme-asset linting — <code>stylelint</code> + <code>eslint</code>
---
The shared <code>style/boost.css</code> and <code>boost.js</code> theme
           the guide, roadmap and demo together, so a bug there recolours or breaks
           everything at once. <code>stylelint</code> guards the CSS tokens and
           <code>eslint</code> the reveal/interaction JS — the one place a small
           mistake has system-wide blast radius.
