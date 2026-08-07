---
id: efficiency-registries-ponytail-caveman
board: code
section: internals
status: shipped
category: Catalog · Curation
complexity: S
impact: Med
wow: 3
note: two ~97k-star repos the catalog was missing; both advertise savings their own benchmarks contradict
order: 103
owner: loop/tap-design-batch
pr:
title: The catalog was missing the two most-starred token-efficiency registries
---
<code>DietrichGebert/ponytail</code> (98.1k&nbsp;&#9733;) and
<code>JuliusBrussee/caveman</code> (96.7k&nbsp;&#9733;) are among the most-starred agent-skill
repos in existence, both MIT, both pushed within the last month &mdash; and neither was in
<code>registries.json</code>. They are now, under a new <code>efficiency</code> category:
items whose reason to exist is making an agent emit <em>less</em>, either less code
(<code>ponytail-audit</code>, <code>ponytail-debt</code>, <code>ponytail-gain</code>) or fewer
output tokens (<code>caveman-compress</code>, <code>caveman-stats</code>).

<b>Filed by item name, not README &mdash; the rule that already caught
<code>ai-design-skills</code>.</b> Both repos open with prose that reads like general-purpose
coding advice, and <code>general</code> is where a keyword scorer drops them. That would have
scattered the one axis they share across the catalog's largest and least useful bucket.
<code>tests/unit/test_registry_categories.py::TestEfficiencyDomain</code> pins both directions,
the same way <code>TestDesignDomain</code> pins <code>ui</code>.

<b>The counts are measured, and the raw walk is wrong for both.</b>
<code>scan_dir</code> finds 13 items in ponytail and 28 in caveman; the real figures are
<b>7</b> (6 skills, 1 rule) and <b>21</b> (7 skills, 14 workflows). Both ship one render per
agent &mdash; ponytail carries the same rule into <code>.cursor/rules</code>,
<code>.windsurf/rules</code>, <code>.clinerules</code>, <code>.kiro/steering</code> and
<code>.github/copilot-instructions.md</code>. Two near-misses are worth recording, because both
look like overcounting and neither is: caveman's <code>commands/*.toml</code> twins never enter
the count at all (<code>scan_dir</code> indexes Markdown, so the Gemini renders are invisible),
and its <code>commands/*.md</code> vs <code>src/plugins/opencode/commands/*.md</code> pairs
share names but are <em>separately authored prose</em>, not mirrors &mdash; the documented
"counts are floors" case. Both repos are now in <code>measure_registry.py</code>'s
<code>SELF_CHECK</code>, which reproduces 7 and 21 from real clones.

<b>The focus strings deliberately omit both headline numbers.</b> Ponytail advertises
&minus;54% code / &minus;20% cost; JetBrains' 80-task paired benchmark on SkillsBench measured
<b>&minus;15.4% code (p=0.088) and &minus;10.3% cost (p=0.004)</b>. Caveman advertises
&minus;65% output tokens; the same lab's 86-task, ~240-trial run measured <b>&minus;8.5%</b>,
because agent work is dominated by code, diffs and tool calls that the skill preserves by
design. Neither showed quality degradation (65/9/6 and 64/8/10 win/loss/tie), so the effects
are real &mdash; just a fifth of what is printed on the tin. A catalog that repeated the
advertised figure would be a megaphone for a number the source's own benchmark contradicts, so
a test asserts no <code>54|65|75|94%</code> ever appears in either <code>focus</code>.

<b>Catalogued, not installed.</b> Ponytail self-activated <em>zero times across ten passive
sessions</em> &mdash; it needs a <code>SessionStart</code> hook injection to fire at all, which
is the detail most write-ups omit. And installing ponytail's artefact is installing a
<em>rule</em>, which materialises into every agent's context file: more invasive than a skill,
not less. Cataloguing makes both discoverable through <code>boost search</code> and installable
on demand; it does not put either into anyone's standing instructions.

<b>Cataloguing them exposed a gap that made every item in both uninstallable</b> &mdash; see
<code>install-path-disambiguation</code>, fixed in the same change.
