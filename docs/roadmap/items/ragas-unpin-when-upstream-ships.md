---
id: ragas-unpin-when-upstream-ships
board: code
section: planned
status: planned
category: Tech-debt
complexity: S
impact: Low
wow: 1
note: blocked on ragas shipping a release after 0.4.3 — check before starting
order: 97
title: unpin the <code>[eval]</code> langchain stack when ragas ships its fix
---
The <code>[eval]</code> extra pins <code>langchain-core&lt;0.4</code>,
<code>langchain-community&lt;0.4</code> and <code>langchain-openai&lt;1</code> because ragas hard-imports
<code>langchain_community.chat_models.vertexai.ChatVertexAI</code> — a path langchain-community
0.4.x deleted. The LangChain integration card originally made this unpin its phase 0 and was
corrected in place: <b>ragas 0.4.3 still carries the import</b> (measured 2026-08-04 — declared
bounds are open, but <code>import ragas</code> crashes beside langchain 1.x), while upstream main
already has the removal merged. So the unpin is one release of someone else's package away.

<b>What to do when it lands.</b> Check <code>pip index versions ragas</code> (or the PyPI JSON) for
a release after 0.4.3; verify in a throwaway venv that <code>import ragas</code> succeeds beside
<code>langchain&gt;=1</code>; then move <code>[eval]</code> to that floor, delete the three langchain
pins, and adapt <code>scripts/eval_explain.py</code> if the 0.4 scoring API moved (its
<code>evaluate</code>/<code>to_pandas</code> surface is what
<code>tests/unit/test_eval_faithfulness.py</code> stubs). The <code>eval-explain</code> workflow is
the live proof — it must stay green with real keys.

<b>Why it stays its own card.</b> The shipped integration card documents the block but will not be
re-read; an unpin nobody remembers is how a workaround pin outlives its reason by years. This card
is the reminder, and it is deliberately not claimable until the upstream release exists.
