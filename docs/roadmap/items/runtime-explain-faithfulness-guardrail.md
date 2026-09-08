---
id: runtime-explain-faithfulness-guardrail
board: code
section: trust
status: shipped
category: Trust · Hallucination guard
complexity: M
impact: Med
wow: 4
note: faithfulness → extractive fallback
order: 4
owner: loop/faithful
pr: 218
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

<br><br><b>Scope limit found and closed (2026-09, <code>audit-explain-findings</code>).</b>
The shipped <code>salient_terms()</code> only recognized backtick spans, code-shaped
tokens, and ALL-CAPS acronyms as checkable — a fabrication stated as plain,
grammatical English (<em>"provisions Kubernetes clusters with Terraform"</em>) had
nothing for it to catch and scored 1.0. It now also treats a capitalized word that
is not the first word of its sentence as salient, which is the shape a fabricated
technology or product name actually takes. See <code>boost_cli/core/faithfulness.py</code>
and <code>tests/unit/test_faithfulness.py</code>.
