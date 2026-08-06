---
id: est-items-counts-agent-mirrors-as-items
board: code
section: internals
status: shipped
category: Catalog · Correctness
complexity: S
impact: Med
wow: 3
note: registries now ship one rendered copy per agent, so a raw walk credits pbakaus/impeccable with 40 items for the 9 it has
order: 102
owner: loop/tap-design-batch
title: est_items counted one skill fourteen times once registries went multi-agent
---
<code>est_items</code> is the catalog's honest number — the README sells it as
<i>measured from the repo's file tree, not estimated</i>, and <code>tap --catalog --limit</code>
ranks by it. The measurement was <code>len(catalog.scan_dir(repo))</code>, which was right when a
registry was a directory of <code>SKILL.md</code> files and stopped being right when registries
started shipping <b>one rendered copy per agent</b>. <code>pbakaus/impeccable</code> vendors its
skill into fourteen dotdirs — <code>.claude/</code>, <code>.cursor/</code>, <code>.gemini/</code>,
<code>.github/</code>, <code>.grok/</code>, <code>.kiro/</code>, <code>.opencode/</code>,
<code>.pi/</code>, <code>.qoder/</code>, <code>.rovodev/</code>, <code>.trae/</code>,
<code>.trae-cn/</code>, <code>.vibe/</code>, <code>plugin/</code> — so a raw walk finds <b>40</b>
items for the <b>9</b> it has. Nothing was wrong with the walk; it is the same code
<code>boost tap</code> runs. What was wrong was calling its output a count of items.

<b>Neither name nor bytes is the identity.</b> Keying on the name over-collapses:
<code>Owl-Listener/designer-skills</code> ships
<code>design-research/commands/test-plan.md</code> and
<code>prototyping-testing/commands/test-plan.md</code>, two different items that share a name, and
a <code>design-review</code> subagent and a <code>/design-review</code> command are genuinely two.
Keying on the raw bytes under-collapses, because the mirrors are <i>rendered</i>, not copied:
impeccable's fourteen <code>SKILL.md</code> copies differ only in the dotdir baked into their prose
(<code>node .cursor/skills/...</code>) and in per-agent frontmatter — the same
one-render-per-agent shape boost itself emits from <code>rules.CONTEXT_FILES</code> and
<code>workflows.render_gemini_command</code>. So
<code>scripts/measure_registry.py</code> hashes the body with the frontmatter dropped and agent
dotdir tokens normalized, and <code>--self-check ~/.boost/repos</code> re-derives already-committed
counts from local clones so the rule stays falsifiable rather than folkloric.

It found a row that had been wrong in the shipped data: <code>Owl-Listener/ai-design-skills</code>
advertised <b>80</b> items because <code>claude-plugin/&lt;pack&gt;/commands/x.md</code> and
<code>commands/&lt;pack&gt;/x.md</code> were read as two commands each. It is 62.

<b>The same batch fixed three categories, and the fix is why the rule is "item names, never the
README".</b> <code>bergside/awesome-design-skills</code> is named like an index and sat in
<code>meta</code>; its 67 items are called <code>brutalism</code>, <code>claymorphism</code>,
<code>bento</code>, <code>editorial</code> — a visual-style corpus, so <code>ui</code>.
<code>thedaviddias/Front-End-Checklist</code> reads like a checklist repo and ships 390
<code>aria-*</code>/<code>accessible-*</code> checks, so <code>ui</code>. And the counter-example
that keeps a name-based rule honest: <code>Owl-Listener/ai-design-skills</code> has "design" in its
name and ships <code>chain-of-thought-design</code>, <code>guardrail-design</code>,
<code>trust-calibration</code> — prompt and agent design, so <code>ai</code>, not <code>ui</code>.
<code>TestDesignDomain</code> pins all four directions.

Landed alongside four new registries — <code>pbakaus/impeccable</code>,
<code>Leonxlnx/taste-skill</code>, <code>alchaincyf/huashu-design</code> and
<code>microsoft/playwright</code>, whose framework repo ships agent skills under
<code>packages/playwright-core</code> next to the product.
