---
id: secret-and-pii-scanning-of-installed-skills
board: code
section: trust
status: shipped
category: Security · Secrets
complexity: S
impact: Med
wow: 3
note: installed content
order: 6
owner: loop/secret-scan
pr: 138
title: Secret &amp; PII scanning of installed skills
---
Point the round-2 secret scanners (<code>gitleaks</code>/<code>trufflehog</code>)
           at <em>third-party</em> skill content, not just boost's own repo — catching
           a skill that ships embedded credentials or, worse, one whose prompt
           coaxes the agent into harvesting the user's. Same free tools, a different
           and higher-stakes target.
