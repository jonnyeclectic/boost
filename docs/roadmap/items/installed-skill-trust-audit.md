---
id: installed-skill-trust-audit
board: code
section: trust
status: inflight
category: Trust · Health
complexity: M
impact: Med
wow: 3
note: audit what you run
order: 47
owner: loop/trust-audit
pr:
title: <code>boost audit --skills</code> — a trust/staleness report for installed skills
---
boost already computes every individual trust signal, each in its own command:
           <code>verify</code> checks lock-file integrity, <code>outdated</code> compares an
           installed skill against its tap, <code>trust</code> reports tap-level signing
           provenance, <code>deps</code> shows the <code>requires:</code>/<code>conflicts:</code>
           graph. What nothing answered is the aggregate question — <em>of the skills I
           actually run, which ones should I stop trusting?</em> <code>boost audit --skills</code>
           gathers all of it into one report: every installed skill that is unsigned, signed
           by an untrusted key, signed but failing verification, sitting on a tap nobody has
           synced in a month, behind its tap, or conflicting with another installed skill.
           The decision layer is <code>core/trustaudit.py</code> — pure and I/O-free like
           <code>core/staleness.py</code>, so every branch is unit-tested and reachable by
           the mutation gate. Only a malformed signature is HIGH; an unsigned tap is the norm
           for most of the catalog today and stays LOW, so the command never cries wolf on an
           ordinary install.
