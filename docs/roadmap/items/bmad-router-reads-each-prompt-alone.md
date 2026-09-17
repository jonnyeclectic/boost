---
id: bmad-router-reads-each-prompt-alone
board: code
section: dx
status: next
category: "Agents · BMAD"
complexity: M
impact: High
wow: 3
note: pastes, follow-up replies and yes/no questions get delegation banners
order: 320
owner:
pr:
title: "The BMAD router reads each prompt alone, so a pasted log, an &ldquo;ok update both and rerun&rdquo; and a yes/no question all get a banner"
---
<b>The hook is handed the conversation and drops it.</b> <code>_route</code> (<code>commands/bmad.py:340</code>&ndash;<code>342</code>)
reads <code>prompt</code> and <code>cwd</code> from a <code>UserPromptSubmit</code> payload that also carries
<code>session_id</code>, <code>transcript_path</code> and (v2.1.196+) <code>prompt_id</code>, per Claude Code's hooks reference;
Gemini's <code>BeforeAgent</code> input has the first two. So <code>classify()</code> (<code>core/bmad.py:392</code>) judges
every message as if it opened a session, and one keyword buys a ~650-char banner whose last line opens &ldquo;Work autonomously
through to a finished, verified change&rdquo; (<code>core/bmad.py:551</code>). A misrouted question becomes an invitation to edit.

<b>Measured on one real prompt history, in aggregate.</b> Replaying origin/main's classifier over 669 history records
from 6 active days: of 417 regular prompts, <b>147 (35%) get a banner</b> &mdash; 109 if the hook's <code>prompt</code>
excludes pasted-text expansion, which is <em>unverified</em>. Of 318 unique prompts up to 2,000 chars, 60.7% classify
trivial but 55.7% match no keyword at all, so the gates silence only 5.0 points of prompts that do hit one. And
89 of the 143 routed unique prompts were decided by exactly one keyword. A <b>single judge</b> (an agent without prior
turns) labelled 41 banners stratified by track: warranted 20, track or lead clearly wrong 21, <b>any clear failure 29</b>
(~74% weighted by track size), fully right 3, &ldquo;Done means&rdquo; fit 5 (11 with partial). About half that history
is the author's own tooling repos.

<b>Four shapes, reproduced on origin/main</b> with synthetic prompts in a throwaway repo (banners 648&ndash;666 chars).
<i>(a) Pasted output</i>, 4 of 5 routed: a 25-word pytest failure &rarr; <code>quality</code>; a <code>git status</code> paste
&rarr; <code>build</code> on git's own words (<code>Changes not staged</code>, <code>use "git add &lt;file&gt;..." to update</code>);
an 80-word npm log &rarr; <code>build</code>, clearing <code>LONG_PROMPT_WORDS</code> (<code>core/bmad.py:374</code>) on two hits,
the word <code>build</code> and the <code>fix</code> of <code>npm audit fix</code>. The silent one, a Python traceback, just had
no keyword. <i>(b) Replies</i>, 7 of 10: &ldquo;ok update both and rerun&rdquo; &rarr; <code>build</code>; &ldquo;sure, add a
test for that too&rdquo; &rarr; <code>quality</code>, handing the lead to Murat mid-task. <i>(c) Yes/no questions</i>, 11 of 11:
<code>_INFO_QUESTION</code> (<code>core/bmad.py:342</code>) knows only wh-words, so &ldquo;are there any tests for the
parser?&rdquo; routes and &ldquo;what tests cover the parser?&rdquo; does not. <i>(d) Read-and-tell</i>, 4 of 5, the track
picked by words inside the URL (<code>/changelog</code>, <code>docs.example.com/guide</code>, <code>api-schema-design</code>).

<b>Fix, stateless, in <code>classify()</code>.</b> (1) An auxiliary opener (<code>is|are|do|does|did|has|have|should|can|could|would|will</code>)
on a prompt ending in <code>?</code> is a question, except <code>can|could|would|will</code> + <code>you|we</code>, which is a
request unless the verb is <code>explain|tell|describe|summarize</code>. That exception keeps
<code>test_a_modal_request_is_not_trivial</code> (<code>tests/unit/test_bmad_core.py:74</code>) green: it pins &ldquo;can you
fix the crash in store.install?&rdquo; as <code>build</code>. (2) <code>read|skim|look at</code> &hellip; <code>tell me|summarize</code>
is a question unless a <code>then</code> clause follows; strip URLs before scoring. (3) Paste shape: 3+ lines, at least half
machine-shaped (<code>$ </code>, <code>Traceback</code>, <code>File "&hellip;", line N</code>, <code>at</code> frames,
<code>npm ERR!</code>, <code>path:line</code>, timestamps, indented lines); score only the rest and require two hits, the
argument <code>LONG_PROMPT_WORDS</code> already makes.

<b>Fix, per session, in the hook.</b> Record the last banner per <code>session_id</code> under <code>paths.state_dir()</code>,
like <code>_state_path</code> (<code>commands/bmad.py:670</code>). A banner is a function of track and root alone, and Claude
Code inserts <code>additionalContext</code> into the conversation where the hook fired, so a same-track banner in the same
<code>cwd</code> repeats context the model already holds &mdash; skip it (Gemini's reference appends it &ldquo;for this turn
only&rdquo;, so there that is unverified). A short reply (<code>yes|ok|sure|no|go ahead</code>, &le;12 words) gets none once
the session has one. Clear the record on <code>SessionStart</code> <code>clear</code>/<code>compact</code> (the matcher at
<code>commands/bmad.py:84</code> lacks <code>compact</code>). Reading <code>transcript_path</code> is best-effort: it is written
asynchronously and may lag.

<b>Prototyped in a scratch copy, not merged.</b> Stateless gates plus a stateless reply gate: all 109 tests in
<code>test_bmad_core.py</code> pass, the repros route 0/5, 0/10, 0/11, 0/5, and 10 of 12 genuine-task controls still route.
A first cut that called any auxiliary opener not followed by <code>you</code> a question routed only 4 of 12 further request
probes (&ldquo;do the migration for the orders table&rdquo; went silent) and still bannered &ldquo;did you update the
docs?&rdquo;; the rules above route 10 of 12 and silence all 4 question probes. Both lose &ldquo;fix this:&rdquo; over a pytest
paste (accepted under &ldquo;rather under-route than talk over someone&rdquo;, <code>core/bmad.py:387</code>&ndash;<code>388</code>)
and, to the reply gate, short replies that carry a task (&ldquo;ok, now implement the export command and add tests for it&rdquo;).
Behind the session check that loss is mid-session only, where a lead and done-contract stand even if the reply changes the
track &mdash; an accepted cost, not a solved one.

<b>How to test.</b> A class in <code>tests/unit/test_bmad_core.py</code> beside <code>TestEvidenceScalesWithLength</code>
(line 110): silence cases for all four shapes, the controls and request probes as must-route cases, the golden banner
(line 396) unchanged; keep the session decision a pure function in <code>core/bmad.py</code> so this file covers it. The hook
side extends <code>TestRoute</code> in <code>tests/functional/test_cli_bmad.py</code> (line 473), which already pipes JSON to
<code>boost bmad route</code> under the <code>sandbox</code> fixture's fake HOME: same <code>session_id</code> twice &rarr; one
banner, a new id &rarr; banner, corrupt state &rarr; exit 0.
