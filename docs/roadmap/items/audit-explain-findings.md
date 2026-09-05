---
id: audit-explain-findings
board: code
section: dx
status: shipped
category: Safety · Bug
complexity: M
impact: Med
wow: 2
note: fabricated Kubernetes/Flyway summary scores faithfulness 1.0 and prints verbatim
order: 267
owner: loop/explain-faithfulness-scope
pr:
title: "<code>boost explain</code>: CLI audit findings (2026-08)"
---
<b>The faithfulness guardrail scores a fully fabricated summary 1.0 when the fabrications are proper
nouns.</b> With a canned <code>claude</code> replying <em>&ldquo;This skill provisions Kubernetes
clusters with Terraform and migrates PostgreSQL schemas through Flyway. It triggers whenever the
agent sees a Dockerfile&rdquo;</em> &mdash; none of it in brainstorming's SKILL.md &mdash;
<code>explain brainstorming</code> printed the reply verbatim with no caveat, exit 0:
<code>faithfulness.score()</code> returned 1.0 because <code>salient_terms()</code> came back empty.
Only backtick spans, code-punctuated/digit tokens, <code>--flags</code> and ALL-CAPS acronyms count
(<code>faithfulness.py:37-42</code>, <code>50-67</code>), so Kubernetes, Terraform, Flyway and
Dockerfile pass as general English &mdash; although the module's own docstring
(<code>faithfulness.py:14-16</code>) says the failure worth catching is a model that <em>&ldquo;names
a command, flag, tool, or file the SKILL.md does not contain&rdquo;</em>. Verification found it
broader than reported: one grounded backtick term (<code>brainstorming</code>) in the reply also
scores 1.0, so a single real term whitelists any amount of proper-noun fabrication.

<br><br><b>Fix</b>: extend <code>salient_terms()</code> with capitalised non-sentence-initial tokens
absent from a small stop-list, and pin a test that the Kubernetes/Terraform reply scores below the
0.5 threshold &mdash; or always print a one-line <em>AI summary</em> caveat so a shown explanation is
never mistaken for source text. Update
<code>docs/roadmap/items/runtime-explain-faithfulness-guardrail.md</code> (the shipped guardrail this
follows up) to record the scope limit. Found by the 2026-08 CLI audit (cluster
explain-faithfulness-gap); repro in the audit log.
