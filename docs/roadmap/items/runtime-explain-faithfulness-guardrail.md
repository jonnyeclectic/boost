---
id: runtime-explain-faithfulness-guardrail
board: code
section: trust
status: planned
category: Trust · Hallucination guard
complexity: M
impact: Med
wow: 4
note: faithfulness → extractive fallback
order: 4
owner:
pr:
title: Runtime hallucination guardrail for <code>boost explain</code>
---
Today the ragas <b>faithfulness</b> check (Tier 2c, <code>scripts/eval_explain.py</code>)
is <em>eval-time only</em> — an offline monitor that flags when generated
explanations drift from their <code>SKILL.md</code>, but never intercepts a live
response. Promote it to a <b>runtime guardrail</b>: score the generated summary
against the source and, when it falls below a faithfulness threshold, fall back
to the deterministic extractive summary <code>cmd_explain</code> already ships
for the no-AI case (description + outline + key rules) — or append a
low-confidence caveat. Turns "a human notices the drift next week" into "the
tool refuses to show an ungrounded explanation," closing the gap between
detecting hallucinations and preventing them.
