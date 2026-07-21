---
id: secret-scanning-gitleaks-push-protection
board: code
section: health
status: shipped
category: Security · Secrets
complexity: S
impact: Med
wow: 3
note: pre-commit-able
order: 4
owner: loop/gitleaks
pr: 180
title: Secret scanning — <code>gitleaks</code> + push protection
---
Scan the full history and every PR diff for leaked tokens, keys and
           PyPI credentials with the free <code>gitleaks</code> action, paired
           with GitHub push-protection (free on public repos) so a secret is
           blocked <em>before</em> it lands. Cheap insurance for a project whose
           release automation trades on trusted identity.
