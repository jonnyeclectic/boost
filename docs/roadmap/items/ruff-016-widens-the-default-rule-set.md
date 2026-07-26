---
id: ruff-016-widens-the-default-rule-set
board: code
section: health
status: planned
category: Toolchain
complexity: M
impact: Med
wow: 2
note: 83 errors, 43 auto-fixable
order: 15
owner:
pr: 236
title: ruff 0.16 widens the default rule set — 83 new errors on a version bump
---
Dependabot #236 bumps ruff <code>0.15.22 &rarr; 0.16.0</code> and the <code>ruff</code> step
fails with <b>83 errors</b>. None of them are new code — 0.16 <b>widened the default
selection</b>, and because <code>pyproject.toml</code> uses <code>extend-select</code>
(which adds to the defaults rather than replacing them), every newly-defaulted family
switched on at once. The project only ever opted into
<code>S, B, SIM, C4, PERF, RUF, UP</code>; what fires now is
<code>I001</code>&nbsp;(33), <code>PLW1510</code>&nbsp;(19), <code>BLE001</code>&nbsp;(9),
<code>ISC004</code>&nbsp;(4), plus <code>TRY</code>, <code>PLR</code>, <code>PIE</code>,
<code>DTZ</code>, <code>RET</code>, <code>PYI</code>, <code>FLY</code> and — awkwardly —
<code>FURB167</code>, a family the config explicitly delegates to refurb via
<code>external = ["FURB"]</code>.
So this is a <b>policy decision, not a lint fix</b>, and there are two honest answers.
Pin the policy: switch <code>extend-select</code> to a full <code>select = [...]</code> so
the rule set is stated outright and a future ruff release can never widen it again — the
bump then lands with zero code changes. Or adopt some of them: <code>I001</code> (import
sorting) and the 43 auto-fixable errors are cheap and arguably worth having, while
<code>PLW1510</code> (<code>subprocess.run</code> without <code>check=</code>) is 19 real
call sites that each need a judgement about whether a non-zero exit should raise.
<code>DTZ005/006</code> (naive <code>datetime.now()</code>) is worth a look on its own
merits given <a href="#rel-time-tests-race-the-wall-clock">the clock-racing test</a>.
Recommended: pin <code>select</code> first so the bump is unblocked and the gate stops
depending on an upstream default, then adopt families deliberately in follow-ups. Until
then #236 must not be merged — it reddens <code>ci / lint</code> on every branch.
