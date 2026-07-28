---
id: wire-bdd-suite-into-ci
board: code
section: dx
status: shipped
category: Test infra
complexity: S
impact: Med
wow: 2
note:
order: 12
owner: loop/wire-bdd-into-ci
pr: 292
title: New BDD suite has zero CI wiring
---
The behave suite added under <code>tests/bdd/</code> (11 features, 47 scenarios) passes cleanly
today, but <code>make bdd</code> is invoked nowhere in <code>.github/workflows/</code> — only
<code>lint</code>, <code>test</code>, <code>smoke</code>, and <code>mutation</code> run in
<code>ci.yml</code>. Unlike the eval/mutation gates, which degrade cleanly but still execute, this
suite only runs if a human remembers to run it locally, so a CLI change that breaks the step glue
(output-string matching, mocked <code>shutil.which</code>) can rot silently for any number of merges.
