---
id: audit-adapt-renders-every-sibling-of-a-flat-agents-dir-workflow-as
board: code
section: internals
status: inflight
category: CLI · Bug
complexity: S
impact: High
wow: 2
note: one flat agents/x.md adapts into a 383 KB crew of 138 Agent()s — including itself, twice
order: 200
owner: loop/adapt-flat-agents-subagent-scope
pr:
title: "<code>adapt</code> renders every sibling of a flat <code>agents/</code>-dir workflow as a 138-agent crew"
---
<code>adapt actix-expert --to crewai -o x.py</code> prints <em>&ldquo;&#10003; adapted actix-expert &rarr; x.py (crew of 138 &middot; claude-haiku-4-5-20251001)&rdquo;</em> and writes a <b>383 KB</b> render containing <b>138 <code>Agent()</code> + 138 <code>Task()</code></b> &mdash; <code>actix_expert</code>, then <code>actix_expert_1</code> (the item itself, again), then android-expert, angular-expert, &hellip; every sibling in the registry's <code>agents/</code> directory. <code>--to agents-sdk</code> announces <em>&ldquo;note: actix-expert declares 137 subagent(s)&rdquo;</em>. The item is one flat frontmatter file declaring nothing.

The mechanism: <code>cmd_adapt</code> (<code>boost_cli/commands/pkg.py:1737</code>) passes <code>skill_md.parent</code> to <code>discover_subagents</code> (<code>boost_cli/core/adapters.py:157-186</code>). For a SKILL.md-rooted skill that parent is the skill's own directory and the feature works as shipped (<code>adapt brainstorming --to crewai</code> renders a single agent). For a flat <code>agents/&lt;x&gt;.md</code> workflow the parent <em>is</em> the registry-wide <code>agents/</code> dir, so all 137 siblings become a fabricated crew &mdash; and since the exclusion at <code>adapters.py:170-173</code> skips only <code>SKILL.md</code>, the adapted item is re-included as one of its own subagents.

Fix per the verified recommendation: run <code>discover_subagents</code> only when the resolved item is SKILL.md-rooted (<code>skill_md.name == 'SKILL.md'</code>), and harden <code>discover_subagents</code> to skip the entry's own file and require the <code>agents/</code>/<code>subagents/</code> dir to be strictly beneath <code>skill_dir</code>. Add a unit test adapting a bare <code>agents/&lt;x&gt;.md</code> item that asserts a single-<code>Agent()</code> render. Update <code>docs/adapters.html</code> (subagent-discovery wording).

Found by the 2026-08 CLI audit (cluster <code>adapt-subagent-misdetect</code>); repro in the audit log. Verified 2026-08-31: reproduced, defect in the shipped multi-agent adapter feature (whose design intended skill-declared subagents only), not a duplicate of it.
