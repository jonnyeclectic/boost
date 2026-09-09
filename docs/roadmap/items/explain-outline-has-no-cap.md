---
id: explain-outline-has-no-cap
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: cmd_explain asks the model for "4-6 sentences, no markdown" (info.py:800-803), but th…
order: 212
owner:
pr:
title: <code>boost explain</code>'s heuristic fallback prints every heading in the file — 541 lines for one skill — while the sibling list in the same function caps at 12
---
<b>Measured.</b> <code>BOOST_NO_AI=1 boost explain fpf-agent</code> prints 541 lines / 27,699 bytes, 521 of them an uncapped outline emitted by the unsliced <code>for hashes, title in headings</code> at info.py:844, while <code>for rule in rules[:12]</code> nineteen lines below at info.py:859 caps the sibling list in the same function — and 2,861 of 10,152 eval-corpus entries (28.2%) exceed 25 outline lines.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home BOOST_NO_AI=1</code><br>
<code>./boost explain fpf-agent | wc -l           # 541</code><br>
<code>./boost explain fpf-agent | wc -c           # 27699</code><br>
<code>./boost explain fpf-agent | awk 'length&gt;80' | wc -l   # 42</code><br>
<code>grep -n 'rules\[:12\]\|headings = re.findall' boost_cli/commands/info.py   # 840 vs 859</code><br>
<code>python3 - &lt;&lt;'PY'</code><br>
<code>import json,glob,os,re</code><br>
<code>home=os.environ["BOOST_HOME"]; counts=[]</code><br>
<code>for f in glob.glob(home+"/cache/*.json"):</code><br>
<code>    if os.path.basename(f)=="rag_index.json": continue</code><br>
<code>    d=json.load(open(f)); td=os.path.join(home,"repos",d["tap"].replace("/","__"))</code><br>
<code>    for e in d.get("skills",[]):</code><br>
<code>        try: t=open(os.path.join(td,e["skill_md"]),encoding="utf-8",errors="replace").read()</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Two stated details are wrong; every number in the finding is right.

1. "541 lines for one skill" (title) — fpf-agent is a WORKFLOW, not a skill: <code>boost info fpf-agent</code> reports <code>kind workflow</code>, source <code>plugins/fpf/agents/fpf-agent.md</code>. The card must not say "skill" while citing 541. The worst real SKILL is <code>git-worktrees</code>: 237 headings -&gt; 248 output lines. Use both, or say "one catalog entry".

2. The <code>--json</code> rider's "the only name-taking reporting command in the info group with no --json" is contradicted by the finding's own parenthetical. Measured across the <code>info</code> group: list/info/log/deps/tag HAVE --json; cat, edit, preview, home AND explain all take a name and LACK it — explain is one of five, not the only one. (The six commands the finding lists as having --json — search/discover/recommend/trending/stats/count — do have it, but they are in the <code>find</code> group, not <code>info</code>.) Reword to "there is no structured form of the outline either", or drop the rider.

Everything else re-derived and exact: 541 / 27,699 bytes / 42 lines &gt;80 cols / longest 147; info.py lines 801, 840, 844, 859; p50 16, p75 27, p90 47, p95 64, p99 106, max 521, mean 22.0; 2,861 of 10,152 (28.2%) &gt;25; 120 &gt;100; 432 roadmap items. The finder's approximation regex agrees with the real code path exactly.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Independently confirmed not carded. 432 items; the three nearest cards are all different defects: audit-explain-findings (shipped, PR 774) is the AI path's faithfulness scoring; audit-info-stats-explain-render-a-different-smaller-shape-for-rule (shipped, PR 789) is where the outline STARTS for rules, not its length; BOOST-D27 (proposed) is the wrap-law rollout and names three gaps, none of them this. Also checked single-imperative-rule-extractor (the card about the sibling rule extractor) — it does not mention a cap.

SCOPE LIMIT — the prevalence numbers are corpus-specific. p50/p75/p90/p95/p99 and the 28.2% figure describe the 20-tap, 10,152-entry shared eval corpus at $TMPDIR/eval-home. They are NOT measurements of the ~71,700-item live catalogue or of any default/starter tap set, and the card must attribute them. The code defect itself (a missing slice) is corpus-independent and needs no corpus.

This is a TAIL defect, which is what justifies Med rather than High: at p50 (16 headings) output is fine — <code>brainstorming</code> prints 29 lines — and it only becomes unscannable in the upper quartile.

<b>Why it is worth doing.</b> <code>explain</code> exists to answer "what does this do?" without reading the file, and the AI path is opt-in — the heuristic is the default answer for anyone without <code>claude</code> on PATH or an API key. On 28% of the catalogue it returns something no one can scan, and at the tail it returns a 541-line, 27 KB wall for a single item, which is not a summary of the file so much as a reformatting of it. The 12-cap on the rules list shows the ceiling was already understood to be necessary here.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
