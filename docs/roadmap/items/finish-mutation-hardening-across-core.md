---
id: finish-mutation-hardening-across-core
board: code
section: planned
status: shipped
category: Testing
complexity: L
impact: Med
wow: 2
note: behavioral gaps closed
order: 1
owner: loop/mutation-hardening
pr: 225
title: Finish mutation hardening across <code>core/</code>
---
Audited the surviving mutants across all ten listed modules — catalog, util,
           ai, registry, lockfile, policy, config, output, agents, paths — and
           killed every one that reflected a real behavioral coverage gap: the
           <code>search</code> desc-bonus accumulation and <code>classify_workflow</code>
           signature logic; <code>score_skill</code> signal detection and the
           <code>rel_time</code> bucket boundaries; <code>registry.remove</code> keeping
           other taps; a 3-level <code>config.unset</code> slicing bug; the untested
           <code>lockfile.remove_rule</code>/<code>remove_workflow</code> returns and
           corrupt-history skip; the entirely-untested <code>policy.check_capabilities</code>;
           and <code>confirm()</code>'s safe default. The residual survivors are
           <b>equivalent mutants</b> — encoding defaults, macOS case-folding (killed
           on CI's Linux runner), <code>+=</code> vs <code>=</code> on a zero-init score,
           <code>//</code> vs <code>/</code> under <code>%d</code>, dead defensive defaults
           carried by <code>DEFAULTS</code>, and test-double-stubbed plumbing kwargs —
           none of which represents a missing assertion. The required mutation gate
           stays green with margin.
