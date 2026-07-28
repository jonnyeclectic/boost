---
id: github-community-health-files
board: code
section: dx
status: shipped
category: Developer Experience
complexity: S
impact: Med
wow: 2
note:
order: 11
owner: loop/community-health-files
pr: 290
title: No issue/PR templates or a code of conduct
---
The repo has <code>SECURITY.md</code>, <code>CONTRIBUTING.md</code>, and
<code>dependabot.yml</code>, but no <code>.github/ISSUE_TEMPLATE/</code>, no
<code>.github/PULL_REQUEST_TEMPLATE.md</code>, and no <code>CODE_OF_CONDUCT.md</code>. For a project
that explicitly expects parallel external contributors (per the worktree-coordination rules in
<code>CONTRIBUTING.md</code>), a bug-report template built around <code>boost doctor</code>/crash-log
output and a PR checklist would cut triage friction more cheaply than most engine work.
