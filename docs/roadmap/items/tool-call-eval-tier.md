---
id: tool-call-eval-tier
board: code
section: planned
status: inflight
category: Quality · Eval
complexity: L
impact: High
wow: 4
note: probe fixed; --strict-mcp-config shipped for the surface confound; second host (Gemini CLI) still unwritten
owner: loop/eval-tools-strict-mcp
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

<b>Where this stands (2026-08-31), and a correction.</b> The Claude Code arm shipped in #616:
<code>scripts/eval_tools.py</code>, a 16-prompt set halved into should-call and should-NOT-call,
Wilson intervals over N runs, and a verdict that floors call rate <em>and</em> ceilings false calls.

<b>Its probe was broken, and the finding this card recorded was an artifact of it.</b> An earlier
revision of this card reported &ldquo;3/3 false calls &mdash; boost's tools fired on <em>What is the
difference between a Python list and a tuple?</em>&rdquo;. They did not fire. <code>called_boost()</code>
substring-scanned the raw event stream, and <code>claude -p --output-format stream-json --verbose</code>
opens with a <code>system</code>/<code>init</code> event enumerating <em>every tool available to the
session</em> &mdash; which on any machine where boost is registered contains
<code>mcp__boost__boost_search</code> and the other three CONSULT names. So the check returned
<code>true</code> on every run, including runs with no tool call at all. Measured directly:
<code>Say OK and nothing else.</code> produced zero <code>tool_use</code> blocks and scored as a
boost consult.

Two consequences shipped with it. <code>make eval-tools</code> could never pass &mdash; eight
no-call rows &times; three runs is 24 forced trues, so the false-call rate's lower bound sat at
1.00 against a 0.20 ceiling, red on every machine forever. And the tier built to retire
unfalsifiable claims had produced one. <b>The lesson is the tier's own:</b> the existing tests
passed because they fed hand-written one-line fragments with no <code>init</code> event &mdash; a
fixture the author invented could not catch the author's wrong model of the input. The probe now
parses the NDJSON and counts only <code>tool_use</code> blocks inside <code>assistant</code>
events, and the regression test drives a <b>captured real stream</b>.

<b>The second host arm is still unwritten, and should stay that way until the fixed probe is
re-run.</b> Building arm two on a probe that cannot tell an offer from a call would produce two
hosts scoring an identical, meaningless 1.00. When it is built, the candidate is <b>Gemini CLI
proper</b>, not Antigravity CLI: the delivery claim below is about Gemini's Node bundle, and
<code>agy</code> is a third mode again &mdash; it receives boost's <code>instructions</code> and
writes them to <code>~/.gemini/antigravity-cli/mcp/boost/instructions.md</code>, pointing the agent
at the file rather than inlining it. Substituting it would measure a different mechanism than the
one this card argues about.

<b>Cost, now measured.</b> Two trivial runs on a real host reported <code>$0.657</code> and
<code>$0.682</code> of <code>total_cost_usd</code>, so 16 prompts &times; 3 runs is roughly
<b>$30&ndash;50 per host per invocation</b> on a machine with a crowded tool surface.
<code>--strict-mcp-config</code> with a boost-only config cuts that sharply and controls the
surface confound in the same move.

<b>2026-08-31: <code>--strict-mcp-config</code> shipped.</b> <code>eval_tools.py</code> now takes
a <code>--strict-mcp-config</code> flag: it writes a boost-only <code>mcpServers</code> config
(the same <code>&lt;launcher&gt; mcp --stdio</code> invocation and fork-safety <code>env</code>
<code>core.mcphost.register_argv</code> uses for a real registration — confirmed against an actual
<code>claude mcp add-json</code> write, not guessed at the schema) to a temp file and passes
<code>--strict-mcp-config --mcp-config &lt;path&gt;</code> to every <code>claude -p</code> call,
cleaning the file up afterward. This session's sandbox had no network path to PyPI, so the pinned
toolchain (<code>pytest</code>, <code>ruff</code>, <code>mypy</code>, …) could not be installed and
<code>make check</code> could not be run here; the change was verified by hand instead — direct
<code>python3.12</code> import of the module, the new unit tests executed by eye against the
interpreter, <code>py_compile</code>, a manual line-length check against ruff's 88-column default,
and an end-to-end dry run with <code>subprocess.run</code> mocked that confirms the flags land on
the argv and the temp file is created and removed. CI runs the real gate on the PR.

<b>Still unwritten: the second host arm (Gemini CLI).</b> No <code>gemini</code> CLI was reachable
in this sandbox to capture a real stream from, and building that arm on an invented model of
Gemini's non-interactive output format is the exact mistake this card's own probe fix (2026-08-30)
already paid for once — "a fixture the author invented cannot catch the author's wrong model of the
input." That arm stays a placeholder until it can be built against a captured real stream, on a
machine with the <code>gemini</code> CLI installed.

<b>What it unlocks.</b> The first honest answer to "did that description edit help", a baseline the
next surface change can regress against, and a way to retire claims that survive only because
nobody can check them.
