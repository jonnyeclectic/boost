---
id: info-deps-materialize-a-dir-they-then-reject
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: cmd_info (info.py:482-486) and _skill_dir_for_deps (info.py:1058-1066) call store.sou…
order: 215
owner:
pr:
title: <code>boost info</code>/<code>deps</code> on a not-installed rule or workflow widens the tap's sparse cone for a directory <code>source_dir_for</code> immediately rejects
---
<b>Measured.</b> Across all 20 taps of the eval corpus, 0 of the 188 distinct (tap, rel_dir) directories that hold a rule or workflow contains a SKILL.md, and 0 of them have rel_dir == "." — so the existence check at store.py:179 rejects every single one of the 1,493 rule/workflow entries (14.71% of 10,152), and it does so only after store.py:178 has already written a new pattern into the tap's .git/info/sparse-checkout. Two read-only commands, <code>boost info</code> and <code>boost deps</code>, each provably widen a tap's sparse cone and then discard the directory they widened it for.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>S=$TMPDIR/eval-home; D=$TMPDIR/verify-f3; rm -rf $D; mkdir -p $D/.boost/repos $D/.boost/cache</code><br>
<code>cp -R "$S/repos/Aaronontheweb__dotnet-cursor-rules" $D/.boost/repos/</code><br>
<code>cp "$S/cache/Aaronontheweb__dotnet-cursor-rules.json" $D/.boost/cache/</code><br>
<code>python3 -c "import json;s=json.load(open('$S/config.json'));s['taps']=[t for t in s['taps'] if t['name']=='Aaronontheweb/dotnet-cursor-rules'];json.dump(s,open('$D/.boost/config.json','w'))"</code><br>
<code>export HOME=$D BOOST_HOME=$D/.boost BOOST_NO_AI=1</code><br>
<code>git -C $BOOST_HOME/repos/Aaronontheweb__dotnet-cursor-rules sparse-checkout list</code><br>
<code>./boost info meta</code><br>
<code>git -C $BOOST_HOME/repos/Aaronontheweb__dotnet-cursor-rules sparse-checkout list</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The defect is real and both repros land, but four statements in the finding are wrong and must not ship in a card:

1. TIMING — "~0.3s, roughly half the command" (runs 0.701 / 0.400 / 0.325s) is wrong by ~7x. The finder measured three consecutive runs against ONE copy, which conflates Python/page-cache warm-up with the git write: their own run2-&gt;run3 drops 0.075s with no write occurring at all. My controlled A/B (5 FRESH copies per arm, same tap, same entry) measures 0.166s mean with the widening vs 0.122s mean pre-widened. The correct figure is a delta of 0.044s, ~27% of the command — not 0.3s and not "roughly half".

2. "mutate the tap clone on EVERY invocation" is wrong. It is once per (tap, rel_dir). <code>gitutil._sparse_list</code> (gitutil.py:292-304) is a plain file read, and <code>materialize</code> returns at gitutil.py:341-342 once the pattern is present — so after the first run there is no git subprocess and no write. <code>source_dir_for</code> is still called and the raise still swallowed on every invocation, but nothing is written. (The finder's own why_it_matters says "per first-look", so it is the claim field that overstates.)

3. "silently re-inflates exactly what <code>boost compact</code> exists to shrink (177 MB -&gt; 93 MB)" is not supported.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Not carded — I re-did the check independently rather than trusting the finder's. I grepped all <code>^title:</code> lines and all bodies for <code>source_dir_for|materialize|sparse-checkout|sparse cone</code> (22 cards) and read the four plausible ones. <code>taps-check-out-freight-they-never-index.md</code> documents <code>source_dir_for</code> materializing as the deliberate chokepoint for consumers of a tap's real files and says nothing about a consumer that discards the result. <code>audit-info-stats-explain-render-a-different-smaller-shape-for-rule.md</code> (status: shipped, PR 789) is the nearest miss and is worth naming in the card: its shipped fix folded the <code>kind != skill</code> branch of <code>cmd_info</code> INTO the skill path, which is what routes a not-installed rule/workflow into this <code>source_dir_for</code> call in the first place — so this is a side effect of that fix, not an independent old bug. Its <code>source</code> line fix also shipped (my run prints <code>.cursor/rules/meta.mdc</code>, not <code>.cursor/rules</code>). Neither <code>audit-deps-findings.md</code> nor <code>audit-dry-runs-disagree-...</code> touches the materialize call.

SCOPE LIMITS of my repro, all of which a card author must respect: - The 188/3/46 and 14.71% figures are measured against the 20-tap, 10,152-entry eval corpus ONLY. They are not the shipped default/starter registry set and not the user's real ~445-tap install. The RATIO could differ on a registry that ships scripts or JSON beside its commands; the direction (the check is guaranteed to fail) will not, since it follows from the classifier. - I could NOT exercise the network path.

<b>Why it is worth doing.</b> An information command performs a git write (and, on a tap that has not fetched those blobs, a network fetch) for 14.7% of the catalogue, gains nothing from it, and silently re-inflates exactly what <code>boost compact</code> exists to shrink (CLAUDE.md records compact as 177 MB -&gt; 93 MB). Browsing the catalogue therefore costs disk, ~0.3s per first-look, and — offline or behind a proxy — can fail or hang a command that only needed a cache read. CLAUDE.md's own rule is that <code>source_dir_for</code> is the chokepoint for "anything reading a tap's real files"; here nothing reads them.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
