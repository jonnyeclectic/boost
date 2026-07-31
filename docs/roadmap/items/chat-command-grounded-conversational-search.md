---
id: chat-command-grounded-conversational-search
board: code
section: pipeline
status: shipped
category: Search · Intelligence
complexity: M
impact: High
wow: 4
note: a chatbot that cannot name a skill you do not have
order: 77
owner:
pr:
title: <code>boost chat</code> — ask about skills in plain language, grounded in retrieval
---
Everything needed for conversational search already existed and had never been put together:
<code>rag.retrieve_any</code> finds candidates with whatever engine the machine has,
<code>ai.ask</code> writes prose, and <code>faithfulness.score</code> checks prose against its
source. <code>boost chat</code> is the seam &mdash; a question in, an answer that names specific
skills and says why, with citations.

<b>The design problem is not the chat loop, it is fabrication.</b> boost is a package manager. An
assistant that invents a plausible-sounding skill name sends the user hunting for
<code>docker-compose-expert</code>, finding nothing, and concluding either that the catalogue is
broken or &mdash; worse &mdash; that something adjacent from an unvetted tap is the thing they meant.
Typosquatting is a live hazard in this ecosystem; <code>core/typosquat.py</code> exists for it. So a
chatbot that manufactures names is <em>actively dangerous</em> rather than merely unhelpful, and the
whole command is built as a retrieval system that happens to speak rather than a model that happens
to search.

Two defences, in order. <b>Retrieval decides what may be discussed</b> &mdash; the model is never
asked &ldquo;what skill does X?&rdquo;, it is handed a numbered candidate set and asked to answer
from it, so nothing outside that set can be recommended because nothing outside it is in the prompt.
<b>The reply is then checked before it is shown</b>: every skill-shaped token must name something in
the retrieved set (<code>chat.ungrounded_names</code>), and the prose as a whole must clear the same
faithfulness threshold <code>boost explain</code> uses. A reply failing either is <em>discarded, not
patched</em> &mdash; there is no honest way to show prose pointing at a skill that does not exist.

<b>Degrading is the default, not the error path.</b> With <code>BOOST_NO_AI=1</code>, no key, or no
<code>claude</code> CLI, the answer is the retrieved matches themselves: names, descriptions, taps
and the command to install one. That is what every keyless install gets, so it is written to be
genuinely useful rather than an apology. The AI path improves the prose and is never load-bearing
for correctness.

<b>A downgraded answer says so.</b> Silently swapping a rejected reply for the extractive one makes
the two indistinguishable, so a rejection is reported &mdash; and <code>--json</code> carries
<code>grounded: false</code> as a field a caller can branch on rather than a string to parse.

<b>Shipped with:</b> <code>core/chat.py</code> (the engine, so the mutation gate covers it),
<code>cmd_chat</code> as thin CLI glue per the commands/core split, 21 unit tests weighted toward the
rejection paths, 13 functional tests on the CLI contract, and <code>docs/chat.html</code> walking
through what happens to a question. Verified against the real 6-tap corpus: the AI path returns
<code>source: ai, grounded: true</code> over hybrid RRF retrieval, and an injected reply naming
<code>docker-compose-expert</code> is caught and replaced.

<b>Deliberately not built.</b> No session persistence &mdash; a saved transcript is a second source
of truth about a catalogue that changes under it. No tool-calling or install-on-your-behalf: the
command answers questions, and <code>boost install</code> stays an explicit act. History is bounded
at four turns because a long transcript encourages answering from the conversation rather than from
what retrieval returned, which is the same failure the grounding checks exist to catch.
