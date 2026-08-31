---
id: tool-call-eval-tier
board: code
section: planned
status: planned
category: Quality · Eval
complexity: L
impact: High
wow: 4
note: Claude Code arm shipped in #616; the second host arm is unwritten and the card stays open for it
owner:
order: 96
title: a Tier 3 eval for tool-call behaviour, floored in <b>both</b> directions
---
boost's required gate floors <b>four</b> retrieval metrics — recall@k &ge; 0.78, hit@1 &ge; 0.40,
MRR &ge; 0.52, nDCG@k &ge; 0.58 — over a 91-query golden set and a 10,152-entry corpus, every
row pinned to a commit SHA. All of it measures what boost returns <i>once it is asked</i>. Nothing
measures whether an agent asks. **The call itself is unmeasured**, and it is the step everything
downstream depends on.

<b>The miss that exposed it.</b> A Gemini CLI session was asked to "create a new, simplified app
demonstrating RAG implementation in Python3 using langGraph, langChain, and langSmith" — a new
project, an architecture decision and a dependency choice, which is three of the triggers
<code>boost_search</code>'s description names explicitly. It activated two already-installed
skills, built the app, and never called boost. Asked why, it paraphrased boost's own lock-in
trigger list back verbatim, so the text was read and was not persuasive. A gate that floors
recall@k at 0.78 reported nothing, because retrieval was never invoked.

<b>Every claim in the MCP surface is argued, not measured.</b> The triggers, the 10-15s stated
cost, the skip list, the three-kind framing, the "already covered is not already checked" defeater
— each survived a careful review and none has a number behind it. That is a
high-variance lever tuned blind: <i>Tool Preferences in Agentic LLMs are Unreliable</i>
(EMNLP 2025, <code>arxiv 2505.18135</code>) measures description-only edits swinging call rate by
more than <b>10&times;</b>. boost currently ships those edits on reasoning alone.

<b>The design constraint that decides whether this is worth building: floor both directions.</b>
A tier that measures call rate alone rewards making boost maximally assertive, which is precisely
the capture the surface is written to avoid — and boost has already learned this exact lesson one
tier down. Flooring recall alone was <i>a hole rather than a simplification</i>: a ranker that
finds the right answer every time and never ranks it first scores recall@10 1.000 with hit@1
0.000, and passed. So the prompt set needs two halves — a <b>should-call</b> set (multi-file work,
a new subsystem, a config or CI job that outlives the session) and a <b>should-not-call</b> set
drawn from the shipped skip list (a question, a one-line edit, a command the user just handed
over) — with a false-call ceiling as binding as the call-rate floor. One number without the other
is an incentive to ship the thing boost refuses to be.

<b>Per host, never averaged.</b> The two registered hosts do not see the same boost text. Claude
Code puts server <code>instructions</code> in the system prompt; Gemini CLI never delivers them in
interactive mode at all — <code>Config.initialize()</code> does not await
<code>mcpInitializationPromise</code>, so <code>getMcpInstructions()</code> returns <code>""</code>,
<code>startChat</code> stamps the context entry once with a stable id, and the later
<code>refreshMcpContext()</code> re-renders Tier 1 only. A single averaged score would hide a host
where 1,786 characters of guidance are simply absent, and would credit or blame wording for a
delivery failure.

<b>Shape.</b> An opt-in <code>make eval-tools</code> beside <code>eval-ai</code> /
<code>eval-rec</code> / <code>eval-explain</code> — real hosts and real LLM calls, so it is
non-deterministic and key-gated and must <b>not</b> join the required <code>check</code> gate;
same degrade-cleanly contract as the other Tier 2 evals. Because the outcome is stochastic, report
N runs per prompt with an interval rather than a single pass/fail, the way
<code>golden-set-statistical-power</code> established for retrieval — a one-shot replay cannot tell
a wording regression from a sampling wobble.

<b>Where this stands (2026-08-30).</b> The Claude Code arm shipped in #616:
<code>scripts/eval_tools.py</code>, a 16-prompt set halved into should-call and should-NOT-call,
Wilson intervals over N runs, and a verdict that floors call rate <em>and</em> ceilings false
calls. Its first real run measured <b>3/3 false calls</b> &mdash; boost's tools fired on "What is
the difference between a Python list and a tuple?", which the shipped skip list excuses by name.
Call rate alone would have scored that a perfect 1.00, which is the whole argument for flooring
both directions, now with a number behind it.

<b>The card stays open because "per host, never averaged" is the binding requirement and only one
host has been driven.</b> Gemini CLI is not installed on the machine this was built on, and its
successor Antigravity CLI (<code>agy</code>, which boost already supports as its fifth agent
target and which has boost registered) cannot be driven from a sandbox: it starts a local
language server and dies on <code>listen tcp 127.0.0.1:0: bind: operation not permitted</code>.
Shipping an arm for a host nobody drove would put a number next to a measurement that never
happened &mdash; the exact unfalsifiable claim this tier exists to retire. The <code>owner</code>
is cleared rather than left on a merged branch, so the second arm is claimable.

<b>What it unlocks.</b> The first honest answer to "did that description edit help", a baseline the
next surface change can regress against, and a way to retire claims that survive only because
nobody can check them.
