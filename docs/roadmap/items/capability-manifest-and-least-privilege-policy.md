---
id: capability-manifest-and-least-privilege-policy
board: code
section: trust
status: shipped
category: Security · Policy
complexity: L
impact: Med
wow: 4
note: builds on policy.py
order: 8
owner: loop/caps
pr: 219
title: Capability manifest &amp; least-privilege policy
---
Extend the existing <code>policy.py</code> so a skill declares the
           capabilities it expects — network, shell, file scope — and the user's
           policy allows or denies them. Turns install-time governance into
           least-privilege for the instructions an agent is about to run, the
           natural next step for a tool that already blocks installs by policy.
