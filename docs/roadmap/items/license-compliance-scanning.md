---
id: license-compliance-scanning
board: code
section: pipeline
status: shipped
category: Supply chain
complexity: S
impact: Med
wow: 2
note:
order: 12
owner: loop/license-compliance
pr: 310
title: License-compliance scanning of the dependency closure
---
Nothing in CI checks SPDX license compatibility of resolved dependencies — <code>pip-audit</code>
gates known CVEs, not license terms, and the <code>[eval]</code>/<code>[rag]</code> extras pull in a
nontrivial transitive closure (the langchain stack, ragas, sqlite-vec) whose licenses are never
verified against boost's own. Add a <code>pip-licenses --fail-on</code> (or <code>reuse lint</code>)
step to <code>package-metadata.yml</code> to catch an incompatible transitive dependency before an
extra ships it.
