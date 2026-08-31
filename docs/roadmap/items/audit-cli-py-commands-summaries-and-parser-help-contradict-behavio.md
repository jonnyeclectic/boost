---
id: audit-cli-py-commands-summaries-and-parser-help-contradict-behavio
board: code
section: dx
status: planned
category: Docs · Drift
complexity: S
impact: Med
wow: 1
note: search says "(AI-ranked)" and every default run prints "ranked by full-content BM25"
order: 228
owner:
pr:
title: "cli.py COMMANDS summaries and parser help contradict behavior across ~11 commands"
---
The one-line summaries in <code>boost_cli/cli.py</code>'s <code>COMMANDS</code> table &mdash; the strings
<code>boost --help</code> shows and <code>docs/commands.html</code> is generated from &mdash; contradict what
the commands do, in four recurring ways. <b>Wrong default:</b> <code>search</code> says
<em>&ldquo;(AI-ranked)&rdquo;</em> while every default run prints <em>&ldquo;ranked by full-content
BM25&rdquo;</em>, and <code>--smart</code>'s prerequisites (a <code>claude</code>/<code>gemini</code> CLI or
<code>ANTHROPIC_API_KEY</code>) surface only as a runtime warning. <b>Overselling:</b>
<code>impact</code> claims <em>&ldquo;Measure a skill's influence on code quality&rdquo;</em>; the live output
is a COMMITS SINCE / EVENTS table captioned <em>&ldquo;correlation, not causation&rdquo;</em> &mdash; no quality
signal is computed. <code>onboard</code> promises <em>&ldquo;&amp; open a PR&rdquo;</em> that only
<code>--pr</code> opens. <b>Missing targets/hosts:</b> <code>adapt</code> says <em>&ldquo;(CrewAI, Agents
SDK)&rdquo;</em> while its own <code>--to</code> lists <code>langgraph</code> (also stale in
<code>docs/adapters.html:346</code>); <code>mcp</code> names two of its three hosts (<code>agy</code>
missing) and <code>--host</code> help omits the accepted <code>all</code> value
(<code>mcphost.resolve()</code> takes it, <code>configuration.py:1683</code>). <b>Wrong kind:</b>
<code>pin</code>/<code>unpin</code>/<code>quarantine</code>/<code>reinstall</code> say
&ldquo;skill&rdquo; though all three kinds apply, <code>tap</code> says &ldquo;GitHub repo&rdquo; though the spec
takes a git URL or local directory, <code>outdated</code> says &ldquo;skills&rdquo; yet lists
<code>code-signing (rule)</code>, <code>uninstall</code> names a phantom &ldquo;config&rdquo; kind
<code>store.uninstall</code> does not have, and <code>untap -f</code> promises to skip a confirmation that
per the audit log rarely fires. <code>reindex</code>'s summary and parser description are two different
sentences for no reason.

Help that lies is a defect, not polish: it is the only interface documentation most users read, and
three of these (search's default, impact's claim, onboard's PR) misstate what running the command does.
Verified live for <code>impact</code>/<code>mcp</code>/<code>adapt</code>; the rest confirmed verbatim
against the <code>COMMANDS</code> rows (<code>cli.py:57</code>, <code>:60-61</code>, <code>:64</code>,
<code>:67</code>, <code>:88-91</code>, <code>:102</code>, <code>:126</code>, <code>:130</code>) and documented
behavior.

Fix per the verified recommendation: one sweep of the <code>COMMANDS</code> rows plus matching parser
descriptions &mdash; impact &rarr; <em>&ldquo;Correlate a skill's install date with repo activity&rdquo;</em>;
search &rarr; <em>&ldquo;(BM25; --smart reranks with Claude)&rdquo;</em>; adapt &rarr; add LangGraph; mcp &rarr;
name all three hosts and document <code>--host all</code>; pin/unpin/reinstall/quarantine/tap/outdated
&rarr; &ldquo;skill, rule or workflow&rdquo; / &ldquo;items&rdquo;; onboard &rarr; <em>&ldquo;(optionally open a PR
with --pr)&rdquo;</em>. Then regenerate <code>docs/commands.html</code> (<code>make generate</code>) and
update <code>docs/adapters.html</code>, the <code>docs/index.html</code> command table, and README.md
(search example, mcp section). Found by the 2026-08 CLI audit (cluster help-claims-wrong); repro in
the audit log.
