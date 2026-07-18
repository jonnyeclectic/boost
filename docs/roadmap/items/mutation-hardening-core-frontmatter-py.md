---
id: mutation-hardening-core-frontmatter-py
board: code
section: shipped
status: shipped
category: Testing
complexity: M
impact: Med
wow: 3
note: PR #22 · 23 killed
order: 3
owner:
pr:
title: Mutation hardening — <code>core/frontmatter.py</code>
---
34&nbsp;→&nbsp;11 survivors with exact-equality tests, replacing
           substring <code>in</code> checks a mutated string literal still
           satisfied (e.g. <code>dump()</code>'s <code>XX%s:XX</code> still
           <em>contains</em> <code>tags:</code>).
