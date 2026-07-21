---
id: widen-the-ruff-rule-surface-b-sim-c4-perf-ruf
board: code
section: pipeline
status: shipped
category: Quality · Smell
complexity: S
impact: Med
wow: 3
note: 0 new deps
order: 7
owner: loop/widen-ruff
pr: 178
title: Widen the ruff rule surface — <code>B·SIM·C4·PERF·RUF</code>
---
Beyond the <code>S</code> security family (round 1), enable
           flake8-bugbear (<code>B</code>), simplify (<code>SIM</code>),
           comprehensions (<code>C4</code>), perflint (<code>PERF</code>) and
           Ruff-native (<code>RUF</code>) rules — bug, readability and performance
           smells caught at zero new-tool cost since ruff already runs in the lint
           gate.
