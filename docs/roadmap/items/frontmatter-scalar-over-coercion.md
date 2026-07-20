---
id: frontmatter-scalar-over-coercion
board: code
section: internals
status: shipped
category: Correctness
complexity: S
impact: Low
wow: 2
note: 
order: 18
owner: loop/reconcile-stale-cards
pr:
title: Frontmatter scalar over-coercion
---
Already shipped: <code>core/frontmatter._scalar</code> coerces only the YAML 1.2
           core keywords (<code>true</code>/<code>false</code>/<code>null</code>/<code>~</code>);
           the 1.1 aliases <code>yes/no/on/off/none</code> stay strings, so a skill
           named <code>none</code> or tagged <code>on</code> keeps the right type.
           Guarded by <code>test_scalar_leaves_yaml11_aliases_as_strings</code>.
