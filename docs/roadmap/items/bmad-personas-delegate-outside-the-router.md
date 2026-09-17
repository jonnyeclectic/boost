---
id: bmad-personas-delegate-outside-the-router
board: code
section: dx
status: next
category: "Agents · BMAD"
complexity: S
impact: Med
wow: 3
note: router silence is banner-only, and nobody has counted
order: 325
owner:
pr:
title: "Persona descriptions say <code>Use PROACTIVELY</code>, so the router's silence governs only the banner"
---
<code>boost bmad on</code> gives Claude Code two routes to a persona, and only one goes through the router.
The banner is gated: <code>classify</code> returns <code>trivial</code> for slash commands and
<code>no bmad</code> (<code>boost_cli/core/bmad.py:402</code>), short informational questions (<code>:407</code>)
and thin keyword evidence (<code>:415</code>). The other route is the <code>description:</code> line of the
seven persona files written into <code>~/.claude/agents/</code> (<code>boost_cli/commands/bmad.py:258</code>),
which <code>persona_description</code> renders as <code>&lt;Name&gt;, &lt;Title&gt; (BMAD &lt;module&gt;). Use
PROACTIVELY for &lt;triggers&gt;.</code> (<code>boost_cli/core/bmad.py:594</code>). Neither that line nor the
persona body (<code>:642</code>) ties spawning to the router; the body's one mention has Amelia read the gate
command off its banner (<code>:91</code>).

<b>Claude Code reads that line as a delegation rule.</b> The sub-agents docs define <code>description</code>
as &ldquo;When Claude should delegate to this subagent&rdquo;, name it alongside the request and current
context as what automatic delegation is based on, and advise: &ldquo;To encourage proactive delegation,
include phrases like &lsquo;use proactively&rsquo; in your subagent's description field.&rdquo; So the
router's tuned silence and the <code>no bmad</code> opt-out decide whether a banner is added, not whether a
persona gets spawned.

<b>The repo's own silent-prompt fixtures read like the triggers.</b> <code>what does scan_dir do?</code>,
<code>fix the flaky test in test_catalog, no bmad</code> and <code>/code-review fix the failing tests in the
catalog scanner</code> (<code>tests/unit/test_bmad_core.py:48</code>, <code>:68</code>, <code>:86</code>) all
classify <code>trivial</code> with a 0-char banner on origin/main, yet Paige covers &ldquo;explaining a system
to the next person who touches it&rdquo;, Murat &ldquo;flaky suites&rdquo; and Amelia &ldquo;fixing a bug
&hellip; or any change that ends in edited source files&rdquo; (<code>boost_cli/core/bmad.py:183</code>&ndash;<code>218</code>).
Replayed over one real Claude Code profile's history (318 unique non-slash prompts up to 2,000 chars, 6 active
days), <b>60.7%</b> classify trivial and <b>55.7%</b> match no keyword. Little pushes back. The
<code>SessionStart</code> briefing says &ldquo;Trivial asks get no banner &mdash; answer those directly&rdquo;
(<code>:576</code>), but also that personas &ldquo;are delegated to with the Agent tool&rdquo; (<code>:570</code>),
and its hook does not fire on compaction (matcher <code>startup|resume|clear</code>,
<code>boost_cli/commands/bmad.py:84</code>). A <code>no bmad</code> prompt carries its own words, but nothing
says they cover the personas.

<b>Unmeasured, and the measurement could close this item.</b> Nobody has counted delegations on silent
prompts. Banner cost is countable (mean ~650 chars, ~163 tokens on that profile), while a description-triggered
spawn would be a whole subagent run that no banner count sees. That is inference, but it limits the claim that
the router &ldquo;costs a question nothing&rdquo; (<code>docs/bmad.md:76</code>,
<code>boost_cli/commands/bmad.py:14</code>) to the banner. Measure from a HOME with no persona files or boost
hooks: run each router-trivial prompt (the fixtures plus the trivial slice of a real history) as
<code>claude -p &lt;prompt&gt; --output-format stream-json --verbose</code> with the briefing via
<code>--append-system-prompt</code>, in three arms that differ only in the session-only <code>--agents</code>
flag (no personas, shipped descriptions, fixed descriptions). Count <code>Agent</code> <code>tool_use</code>
blocks whose <code>subagent_type</code> starts with <code>bmad-</code>, in messages with a null
<code>parent_tool_use_id</code>. Cost is on the stream's last line. A fourth arm runs routed prompts with the
real hook via <code>--settings</code>, to check that the fix still delegates when the slug arrives in hook-added
context rather than typed by the user. If the shipped arm spawns no more <code>bmad-*</code> subagents than the
no-persona arm, record that here and close the item.

<b>Proposed fix: make the banner the trigger.</b> Drop <code>Use PROACTIVELY</code> and have
<code>persona_description</code> say when the persona applies, e.g. <code>Amelia, Senior Software Engineer
(BMAD bmm). Use when a [BMAD autopilot] routing banner names bmad-dev, or the user asks for it by name.
Covers implementing a feature, fixing a bug, &hellip;</code>. The banner already names lead and support by
slug, and the docs say that when you name a subagent in your prompt &ldquo;Claude typically delegates&rdquo;.
Silent prompts would then leave only the briefing's roster pointing at a persona. If the conditional wording
fails the measurement, fall back to plain scope descriptions with no imperative. Until the fix lands,
<code>permissions.deny</code> on <code>Agent(bmad-dev)</code> and the rest stops the spawns but blocks
banner-led delegation too. <code>docs/bmad.md:76</code>&ndash;<code>78</code> should say that the opt-out and
the silence apply only to the banner. That doc change needs no measurement and can land now.

<b>Tests.</b> Extend <code>tests/unit/test_bmad_core.py</code>.
<code>TestPersonaFiles.test_the_frontmatter_block_is_exactly_this</code> (<code>:485</code>) pins Sally's
description byte for byte and must take the new text. <code>test_persona_descriptions_are_delegation_triggers</code>
(<code>:694</code>) checks only length and that there is no newline. It should also assert that every
description lacks <code>proactively</code> in any case and contains its persona's slug.
<code>test_explicit_opt_out_is_honored</code> (<code>:71</code>) proves only that the classifier stays silent,
and no unit test can observe delegation, so the headless run is the acceptance check. Only re-running
<code>boost bmad on</code> rewrites unedited persona files (<code>boost_cli/core/bmad.py:672</code>), so the
release note must tell users to re-run it.
