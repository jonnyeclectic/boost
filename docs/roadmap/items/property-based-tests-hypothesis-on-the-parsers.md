---
id: property-based-tests-hypothesis-on-the-parsers
board: code
section: health
status: inflight
category: Testing · Bug
complexity: M
impact: High
wow: 4
note: finds edge cases
order: 7
owner: loop/property-parsers
pr:
title: Property-based tests — <code>hypothesis</code> on the parsers
---
Generate adversarial inputs against <code>core/frontmatter</code> and
           <code>core/catalog.scan_dir</code> to surface crashes and round-trip
           failures the example-based unit tests never think to try — a
           <code>dump</code>→<code>parse</code> must round-trip; a scan must never
           raise on arbitrary bytes. Complements the gate: mutmut proves the tests
           are strict, Hypothesis proves the inputs are wide.
