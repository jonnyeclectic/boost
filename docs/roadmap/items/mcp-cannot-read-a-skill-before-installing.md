---
id: mcp-cannot-read-a-skill-before-installing
board: code
section: dx
status: next
category: MCP · UX
complexity: S
impact: High
wow: 3
note: boost_info returns the same one line boost_search already gave
order: 127
owner:
pr:
---
<code>boost_info</code>'s MCP description promises &ldquo;<em>the whole picture of one skill, rule or
workflow by name &mdash; what it does, its kind, the tap it came from, its version, and whether it is
already installed</em>&rdquo;. Called on a real hit it returns five fields:

<code>name</code> &middot; <code>version</code> &middot; <code>tap</code> &middot;
<code>description</code> &middot; <code>installed</code>

&mdash; where <code>description</code> is <b>byte-identical to the one-liner
<code>boost_search</code> already returned</b>. There is no body, no excerpt, no first paragraph. So
&ldquo;what it does&rdquo; is the same sentence the agent already had, and the tool adds only
<code>installed: no</code>, which the search reply already marks.

<b>The consequence is that installing is the only way to read.</b> An agent deciding whether a skill
is worth adopting has exactly one sentence to go on, written by whoever published it, and its only
route to the actual procedure is to install it into the user's real
<code>~/.agents/skills</code> and read it off disk. That inverts the tool's own pitch: the point of
<code>boost_search</code> costing 10&ndash;15 s of LLM rerank is that the top result is
&ldquo;worth acting on rather than skimming&rdquo;, and then nothing lets the agent look before it acts.

<b>Why the one-liner is not enough, measured today.</b> A single search for embedding work returned ten
hits, two of which &mdash; <code>ai-cost-optimization</code> and <code>rag-patterns</code>, both from
<code>j4flmao/agent-skills</code> &mdash; carry the description &ldquo;<em>To optimize **Skill**, we
enforce the following foundational rules:</em>&rdquo;. That is an unfilled template. Separately,
<code>superpowers-lab</code> installs to an 868-byte <code>SKILL.md</code> whose entire Instructions
section reads &ldquo;<em>This skill provides guidance and patterns for lab environment for claude
superpowers.</em>&rdquo; &mdash; the name echoed back in every section. Both indexed, both ranked, both
returned looking exactly like real results. <b>The body is the only thing that separates a written
skill from a generated stub, and MCP cannot reach the body.</b> Note the eval gate cannot catch this
either: <code>golden.jsonl</code> grades by <em>name</em>, and a stub matches its own name perfectly.

<b>The fix is already written &mdash; it is just not exposed.</b> Two CLI commands already do this, both
in the <code>info</code> module: <code>boost cat</code> (&ldquo;Print a skill or rule's contents&rdquo;,
<code>cli.py:79</code>) and <code>boost explain</code> (&ldquo;Explain what a skill does in plain
English&rdquo;, <code>cli.py:82</code>). The MCP server exposes six tools and neither is among them. And
<code>core/mcp.py</code> is built for exactly this: tools self-register on a <code>Registry</code>, so
adding one is &ldquo;<em>one <code>register()</code> call &mdash; no dispatcher edits, no server
changes</em>&rdquo; (<code>mcp.py:7-10</code>).

<b>Three things to get right, none of them large.</b>
<b>(1) Prefer <code>cat</code> as the default.</b> It is offline, deterministic and free;
<code>explain</code> goes through <code>core/ai.py</code>, costs seconds plus a key, and degrades to
heuristics without one. The cheap answer must not sit behind the expensive one's latency &mdash; that is
the same mistake <code>boost_list</code> avoids by never reading the catalog.
<b>(2) Cap the bytes and say so when truncating.</b> A <code>SKILL.md</code> can be large and an MCP
reply lands directly in an agent's context; returning a whole file unbounded is how one lookup costs a
session. The <code>snip = text[:200]</code> convention exists for the same reason.
<b>(3) Keep it read-only.</b> This is the tool that exists so an agent does <em>not</em> have to install
to look; it must not become a second install path.

<b>And fix the description either way.</b> If <code>boost_info</code> keeps returning five fields, it
should stop claiming the whole picture &mdash; an overstated tool description costs an agent a wasted
call and teaches it to distrust the rest of the surface.
