---
id: langchain-integration-explainer-page
board: code
section: docsite
status: shipped
owner: loop/langchain-docs
pr: 467
category: Docs · Interop
complexity: M
impact: Med
wow: 4
note: the eval.html genre, pointed at the LangChain stack — and it can only document what has shipped
order: 89
title: an explainer page for the LangChain / LangGraph / LangSmith integration
---
A companion to <b>production-ready LangChain / LangGraph / LangSmith integration</b>: one
<code>docs/langchain.html</code> that shows what the integration <i>is</i> — architecture and
sequence diagrams, annotated code you can paste, and the reasoning behind each seam — rather than
an API list. The audience is a Python engineer deciding whether boost's catalogue is worth wiring
into their agent, and that decision is made from a diagram and a twenty-line snippet, not from
a reference table.

<b>The genre already exists here.</b> <code>docs/eval.html</code> does exactly this job for the
evaluation system — architecture plus sequence diagrams plus a simple-vs-technical cheat sheet — and
it is the template to follow rather than reinvent. So are its mechanics: a page-specific
<code>&lt;style&gt;</code> block built <i>only</i> on <code>style/boost.css</code>
<code>:root</code> tokens, so the Aurora palette stays recolourable from one file, and diagrams as
<b>inline SVG on those same tokens</b> rather than a diagram library. A hardcoded hex in a diagram
silently opts that diagram out of every future theme change, and an external script opts the page
out of loading at all on a strict CSP.

<b>What the page has to cover</b>, one section per seam, each with a diagram and a runnable snippet:
retrieval (<code>BoostRetriever</code> over the BM25 + dense fusion, with the measured recall@k /
hit@1 / MRR / nDCG@k shown as numbers because they exist); a <code>SKILL.md</code> loaded as prompt
content with its frontmatter surviving as metadata; a LangGraph graph that pulls a procedure
<i>mid-run</i> instead of pre-loading every one into the system prompt; and a LangSmith trace of
that graph, next to a plain statement that the required gate stays offline, deterministic and
key-free.

<b>Three constraints that are specific to this repo</b>, all of them cheap to satisfy if known up
front and expensive to retrofit:

<b>No page ships unlinked.</b> <code>tests/unit/test_docsite_chrome.py</code> holds a
<code>_PAGES</code> tuple and asserts every page carries the footer and is reachable from all the
others. Adding the tenth page therefore means touching the nav and footer of the nine that exist —
it is a small edit, but it is not optional and it is not automatic.

<b>The budget already fits — measured, so nobody has to guess.</b>
<code>scripts/page_budget.py</code> allows a hand-written page 150 kB / 2,000 elements / depth 20.
Today <code>eval.html</code> is 35.5 kB / 528 elements / depth 10 and <code>mcp-hub.html</code>, the
largest hand-written page, is 50.0 kB / 607. A diagram-and-snippet page of this shape lands in the
same range, so it needs <b>no</b> new <code>BUDGETS</code> entry — and if it ever does, the entry
carries a <code>why</code> string rather than raising the default for every page.

<b>Accessibility is enforced with numbers, not vibes.</b> The axe-core sweep and
<code>scripts/a11y_check.py</code> gate WCAG 2.1 AA, and this genre trips it in a predictable place:
a diagram that encodes meaning in colour alone, or a link distinguished only by hue. The precedent
is already commented in <code>eval.html</code> — <code>--sky</code> on <code>--text-3</code> is
2.47:1 against the 3:1 that WCAG 1.4.1 requires, so its links carry an underline as the non-colour
cue. Diagram legends need the same treatment: shape or label, never colour by itself.

<b>Sequencing, and the one rule that keeps it honest.</b> The page cannot precede the code — a
demonstration of an unbuilt integration is fiction, and a snippet nobody ran is a bug with syntax
highlighting. So each section ships with the phase it documents (retrieval with phase 1, the graph
with phase 2, the trace with phase 3), and every snippet on the page should be extracted and
executed by a test rather than pasted in and trusted. That last part is a new discipline for this
docsite, not an existing one; it is worth adopting here first precisely because this page's whole
value is that its code runs.
