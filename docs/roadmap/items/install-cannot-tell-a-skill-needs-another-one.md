---
id: install-cannot-tell-a-skill-needs-another-one
board: code
section: shipped
status: shipped
category: Install · Research
complexity: M
impact: Med
wow: 3
note: The premise was wrong — boost has always followed <code>requires:</code>. It is the narrowest spelling in the ecosystem (101 values); <code>skills:</code> and <code>dependencies:</code> carry 2,388 more and were invisible.
order: 348
owner: loop/install-prerequisites
pr: 987
title: "Research: how <code>boost install</code> could tell that a skill needs something else installed first"
---
<b>Shipped as a measurement note plus a report-only warning. The card's premise was wrong, and
the correction is the finding.</b> <code>boost install</code> has read prerequisites since the
dependency resolver landed: <code>pkg._expand_dependencies</code> walks
<code>deps.requirement_names(entry["meta"])</code> transitively and installs the closure unless
<code>--no-deps</code>. What it reads is <code>requires:</code> — and a census of the real catalog
says that is the <i>narrowest</i> spelling anyone uses.
<br><br>
<b>The census.</b> 461 tapped registries, 62,310 entries, every value read out of
<code>entry["meta"]</code> in <code>~/.boost/cache/*.json</code> (<code>catalog.scan_dir</code>
keeps the full parsed frontmatter, so this needed no re-tap). <b>14 dependency-ish spellings are
present; 1,099 entries across 52 taps carry a non-empty value.</b> By key:
<code>skills</code> 1,323 values / 18 taps &middot; <code>dependencies</code> 1,065 / 17 &middot;
<code>requires</code> <b>101 / 6</b> &middot; <code>prerequisites</code> 57 &middot;
<code>uses</code> &middot; <code>depends-on</code> &middot; <code>depends_on</code>.
So a user installing <code>athola/claude-night-market</code>'s
<code>architecture-paradigms</code> got no hint that it names five siblings it cannot run
without — it spells them <code>dependencies:</code>.
<br><br>
<b>Q1 — is a declaration a declaration?</b> Not by key name. Two lookalikes had to be excluded
<i>by name</i>: <code>required:</code> is an argument-schema field (130 entries, booleans and
parameter lists — reading it would invent 130 prerequisites), and <code>tools_required:</code>
names Claude tool permissions (<code>Bash</code>, <code>Read</code>), not installables. Both are
in <code>deps.NON_PREREQUISITE_KEYS</code> with the count that justifies them.
<br><br>
<b>Q2 — what is the value?</b> Classification is <b>per value, not per key</b>:
<code>dependencies:</code> is pip packages in <code>Galaxy-Dawn/claude-scholar</code> and sibling
skills in <code>athola/claude-night-market</code>. Of 2,658 values,
<b>1,944 (73%) resolve to a catalogued item</b>; 413 are bare tokens matching nothing
(<code>chromadb</code>, <code>litgpt</code>), 193 are package specs
(<code>torch&gt;=2.0.0</code>, <code>dspy[mcp]</code>), 62 are prose
(<code>GitHub CLI (gh) installed and authenticated</code>), 42 are file paths. Per-key
resolvability: <code>skills</code> 98% &middot; <code>depends-on</code>/<code>depends_on</code>
100% &middot; <code>uses</code> 81% &middot; <code>prerequisites</code> 65% &middot;
<code>dependencies</code> 45% &middot; <code>requires</code> 30%.
<br><br>
<b>Q3 — ambiguity.</b> 422 values name something carried by more than one tap, and
<b>preferring the declaring tap disambiguates 326 of them (77%)</b>. The remainder are dropped
rather than guessed; a name in exactly one other tap is reported qualified
(<code>tap:name</code>), because boost refuses an unqualified name carried by two.
<br><br>
<b>Q4 — report, offer, or install? <i>Report.</i></b> Three measurements decide it. Fan-out
reaches <b>19</b> direct prerequisites (<code>nWave-ai/nWave</code>'s
<code>nw-functional-software-crafter</code>) and the transitive closure reaches <b>35</b> items
over a 553-node / 1,411-edge graph nine levels deep, so "install what it needs" quietly becomes a
35-item install. The graph has <b>two cycles</b> (<code>pr-review</code> ⇄
<code>review-chamber</code>, <code>code-refinement</code> ⇄
<code>safety-critical-patterns</code>). And <code>sparesparrow/cursor-rules</code> lists
<b>rules</b> under <code>dependencies:</code> — installing a rule edits a file the user reads
every session, which is the most invasive thing boost can do, off the least reliable input it
has. So the widened keys are surfaced as a line; the <code>requires:</code> auto-install closure
is unchanged.
<br><br>
<b>Shipped.</b> <code>core/deps.py</code> gains the classifier
(<code>classify_token</code> → item / package / prose / file) and the pure rules
(<code>declared_prerequisites</code>, <code>unmet_prerequisites</code>);
<code>core/prereq.py</code> composes them against the catalog and the lock file.
<code>boost install</code> — and <code>--dry-run</code> — name what an item declares that is not
installed, with the one <code>boost install …</code> that meets it; <code>boost doctor</code>
reports the same across everything installed as an INFO check, <b>not</b> an issue, because no
boost command clears it on the user's behalf. Siblings installed in one command satisfy each
other. The read goes through a new <code>catalog.cached_entries()</code> that never writes:
<code>load_tap</code> rescans and saves a missing cache, so an advisory check hung off
<code>doctor</code> rebuilt the very cache doctor was about to report missing, turning
<code>heal</code>'s "rebuilt catalog cache" into "nothing to heal".
<br><br>
<b>A bug fell out of Q2.</b> <code>deps.requirement_names</code> returned every
<code>requires:</code> value verbatim, so <code>boost deps</code> rendered
<code>torch&gt;=2.0.0 ✗ not installed</code> and <code>boost install</code> reported prose "in no
tap". It now filters through the classifier.
<br><br>
<b>The floor held: wrong less often than silence.</b> Unresolvable tokens are dropped
<i>silently</i> — those 413 bare tokens would otherwise be 413 false "in no tap" lines.
<b>733 rows in 32 taps</b> have at least one resolvable prerequisite, which is the true size of
the thing that was invisible. <b>Follow-up:</b> a <code>shutil.which()</code> classifier could
turn some of the 413 into an honest "needs the <code>gh</code> binary" line, and the prose half
(Q6 — "requires the brainstorming skill" in a body) stays unmeasured.
