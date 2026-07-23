---
id: project-scope-across-every-command
board: code
section: internals
status: shipped
category: Install engine · Scope
complexity: M
impact: Med
wow: 2
note: update/audit/doctor are user-scope only
order: 23
owner: loop/scopewide
pr: 217
title: Teach the rest of the CLI about project scope
---
Workspace scope shipped in <a href="https://github.com/jonnyeclectic/boost/pull/212">#212</a>
           — <code>install --local</code>, <code>list --local</code>,
           <code>uninstall --local</code>, <code>info</code> and
           <code>sync</code> all understand the per-repo lock. The other ~70
           commands still read the user lock alone, and an adversarial review
           of that PR named the consequences: <code>boost update</code> and
           <code>outdated</code> can't see a vendored skill (the workaround is
           <code>install --local --force</code>), and the governance
           commands — <code>audit</code>, <code>verify</code>,
           <code>drift</code>, <code>doctor</code>, <code>health</code>,
           <code>fingerprint</code>, <code>attest</code> — report a clean bill
           of health while N third-party skills sit in the repo being loaded by
           every agent on the team. That last one is the real prize: vendored
           skills are exactly the ones a security review should be looking at,
           because they arrive by PR and run on everyone's machine. Shipped the governance slice — the real prize — via a shared
           integrity.project_skills() / project_status() pair: verify and
           doctor now check project-scoped skills' committed digests the same
           way they do user-scope ones, so a drifted vendored skill is flagged
           instead of silently trusted.
