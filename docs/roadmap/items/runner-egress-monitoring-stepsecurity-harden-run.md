---
id: runner-egress-monitoring-stepsecurity-harden-run
board: code
section: dx
status: planned
category: Security · CI/CD
complexity: S
impact: Med
wow: 4
note: runtime + static
order: 9
owner:
pr:
title: Runner egress monitoring — StepSecurity Harden-Runner
---
Free for public repos, Harden-Runner watches (and can block) unexpected
           network egress from CI runners — the runtime signal that catches a
           compromised action exfiltrating a token. The dynamic complement to
           <code>zizmor</code>'s static workflow analysis, guarding the release
           path from both sides.
