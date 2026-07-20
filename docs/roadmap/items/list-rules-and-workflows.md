---
id: list-rules-and-workflows
board: code
section: internals
status: shipped
category: Install engine · UX
complexity: S
impact: Med
wow: 2
note: list was skill-only after rule/workflow install landed
order: 23
owner: loop/list-all-kinds
pr: 154
title: <code>boost list</code> shows installed rules and workflows
---
Rule (<code>#141</code>) and workflow (<code>#150</code>) install landed, but
           <code>boost list</code> still read only the lock file's
           <code>skills</code> section — so a rule or workflow installed from
           <code>browse</code> showed up nowhere, and worse, the empty-state
           (<em>"no skills installed"</em>) fired whenever no <em>skill</em> was
           present even if rules/workflows were, hiding them entirely. Extend
           <code>list</code> to render an <em>installed rules</em> and
           <em>installed workflows</em> table (agents drawn from each item's
           recorded materializations, workflows also showing their slot), gate
           the empty state on all three kinds being empty, and move
           <code>--json</code> to a <code>{skills, rules, workflows}</code> shape.
           <code>--tag</code> stays skill-only.
