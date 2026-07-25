---
id: bring-commands-under-mutation-testing
board: code
section: planned
status: planned
category: Testing · Gap
complexity: XL
impact: High
wow: 3
note: 
order: 2
owner:
pr:
title: Bring <code>commands/</code> under mutation testing
---
The ~8,100-line command layer has <strong>zero</strong> mutation coverage: mutmut is
           scoped to <code>core/</code> only. Measurements taken before attempting it, so the
           next attempt starts from data rather than re-deriving it:
           <code>commands/</code> is 8,122 lines against <code>core/</code>'s 8,289, and
           <code>core/</code> generates <strong>9,909</strong> mutants — so expect ~10,000
           more, roughly <em>doubling</em> the ~18-minute mutation job that is already the
           long pole before every release. Three constraints found the hard way:
           mutmut's <code>pytest_add_cli_args_test_selection</code> is <em>single-valued</em>
           (<code>tests/unit/ tests/functional/</code> is passed as one path and errors — it
           has to be <code>tests/</code>); <code>commands/</code> is covered by
           <code>tests/functional</code> (61s) not <code>tests/unit</code> (12s), so
           per-mutant cost rises about 5&#215;; and mutmut must run that suite <em>inside</em>
           <code>mutants/</code>, which needs <code>docs/</code>, <code>style/</code>,
           <code>README.md</code> and the root redirect added to <code>also_copy</code> —
           a missing tree fails baseline <em>collection</em> and surfaces as "mutmut run
           failed to execute", pointing nowhere near the cause. Deliberately not shipped as a
           blocking gate until the baseline kill rate has actually been measured: this gate
           runs on every release, and setting a floor without ever seeing the number is how
           you red-line main.
