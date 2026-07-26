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
           scoped to <code>core/</code> only. A blocking 80% floor was attempted and the
           baseline has now actually been <em>measured</em> — it does not clear the bar, and
           two of the three constraints recorded here earlier were wrong. What a sample run
           of <code>commands/taps.py</code> (the <em>best</em>-covered module in the package,
           95.8% lines) against <code>tests/unit/</code> + <code>tests/functional/</code>
           reports through this repo's own gate:
           <strong>570/793 killed — 71.9%</strong>, under the 80% floor, with all 223
           survivors spread across every one of the module's 7 functions rather than
           concentrated in one testable gap. Mutant density is <strong>4.2 per
           statement</strong> in <code>taps.py</code> but <strong>2.46</strong> across
           <code>core/</code> (9,909 mutants over 4,033 statements), so
           <code>commands/</code>'s 5,314 statements imply somewhere between
           <strong>13,000 and 22,300 mutants</strong>; at the measured
           <strong>1.42 mutations/sec</strong> — roughly 6.5&#215; slower per mutant than the
           <code>core/</code> job, which matches the functional-vs-unit suite cost — that is
           <strong>2.5 to 4.5 hours</strong> on one runner, against an ~18-minute job today.
           The job sets no <code>timeout-minutes</code>, so it inherits GitHub's 360-minute
           cap rather than failing fast.
           Two blockers sit underneath that number. Selecting only <code>tests/unit/</code>,
           the way <code>core/</code> does, leaves <code>commands/</code> at
           <strong>17.9%</strong> line coverage versus 91.5% with functional included — and
           "no tests" mutants count against the score, so that route floors out near 18%.
           Selecting <code>tests/functional/</code> instead crashes the run: mutmut's
           <code>record_trampoline_hit</code> calls <code>p.resolve(strict=True)</code> on the
           <em>relative</em> source path, so any test that <code>chdir</code>s into a temp
           project dies with <code>FileNotFoundError: &lt;tmp&gt;/boost_cli</code> — confirmed
           on <code>test_verify_sees_a_project_skill</code>. Corrections to the earlier note:
           <code>pytest_add_cli_args_test_selection</code> is <em>not</em> single-valued, it
           is a list that configparser splits on newlines (a space-separated line is what
           errors), and a sibling <code>pytest_add_cli_args</code> takes extra pytest flags.
           One prerequisite is already fixed: <code>--no-mcp</code> leaked through
           <code>os.environ</code> and made the suite order-dependent, which mutmut exposes
           because it runs whichever test subset covers each mutant.
