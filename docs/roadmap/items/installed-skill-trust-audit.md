---
id: installed-skill-trust-audit
board: code
section: trust
status: planned
category: Trust · Health
complexity: M
impact: Med
wow: 3
note: audit what you run
order: 47
owner:
pr:
title: <code>boost audit --skills</code> — a trust/staleness report for installed skills
---
<code>boost audit</code> today gates CVEs in boost's <em>own</em> Python dependencies,
           and <code>boost outdated</code> compares an installed skill's version against
           its tap — but nothing gives a single trust-health report for the set of skills
           you actually run. The catalog's large supply-chain / dependency-audit cluster
           is the tell: users want to know what they're trusting. Add
           <code>boost audit --skills</code> — flag each installed skill that is unsigned,
           came from an untrusted or now-stale tap, is behind its tap, or newly conflicts
           with another installed skill. Composes with the provenance work already shipped
           (signing, trusted keys, <code>verify</code>) and the <code>requires:</code>/<code>conflicts:</code>
           graph, turning scattered signals into one "is my installed set healthy?" answer.
