---
id: readme-hero-installs-a-name-no-starter-registry-ships
board: code
section: planned
status: planned
category: Quality · Docs
complexity: L
impact: High
wow: 4
note: The first code block in README.md (lines 21-26) is the four-command get-started seque…
order: 225
owner:
pr:
title: README's hero block ends in exit 1: <code>boost install tdd-workflow</code> names a skill no starter registry ships
---
<b>Measured.</b> In a virgin HOME after <code>boost tap --defaults</code> (the identical 7 registries <code>boost quickstart</code> taps, 962 items), the README's fourth hero line <code>boost install tdd-workflow</code> exits 1 with "no skill named 'tdd-workflow' in any tap" while <code>boost install test-driven-development</code> exits 0 from those same 7 taps — the README is wrong by one word, and its error's three close-match hints (eas-workflows, python-llm-ml-workflow-cursorrules-prompt-file, secure-workflow-guide) all steer away from the skill that would have worked.

<b>Reproduce it.</b>

<code>export HOME=$TMPDIR/audit-docs-onboarding &amp;&amp; export BOOST_HOME=$HOME/.boost &amp;&amp; mkdir -p "$HOME"</code><br>
<code>cd &lt;repo&gt;</code><br>
<code>./boost tap --defaults          # == the set boost quickstart taps (quickstart.py:44)</code><br>
<code>./boost taps | tail -2          # 7 taps · 962 items</code><br>
<code>./boost search tdd              # 11 matches, no tdd-workflow row</code><br>
<code>./boost install tdd-workflow ; echo "EXIT=$?"   # exit 1, "no skill named 'tdd-workflow' in any tap"</code><br>
<code># network-free confirmation that the name is not unique anywhere either:</code><br>
<code>BOOST_HOME=$TMPDIR/eval-home ./boost info tdd-workflow ; echo "EXIT=$?"</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Two stated details are wrong; the defect itself is not.

1. "The name comes from boost's own test fixture ..., not from any real registry" and "No tap set makes the line work" are both too strong, and the finding's own eval-corpus evidence contradicts them: two real registries ship a <code>tdd-workflow</code> (affaan-m/ECC and sickn33/antigravity-awesome-skills), so a tap set containing exactly one of them would make the bare line succeed. Accurate wording: no starter/default tap set resolves the name, and in a wider corpus the bare name is ambiguous (exit 1) rather than absent.

2. <code>docs/index.html:988-1002</code> is off. The step-3 block is <code>&lt;pre id="install-code"&gt;</code> at line 989 through <code>&lt;/pre&gt;</code> at line 1004; <code>boost search brainstorming</code> is line 995 and the "step 3" label is line 986. Use 989-1004.

Nothing else needed correcting: 7 starter registries, 962 items, 11 matches, the exact error string and its three close-match hints, and every cited file:line all reproduced verbatim.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

- Provenance is proven, not inferred. <code>git log -S 'boost install tdd-workflow' -- README.md</code> returns exactly one commit: 6ffbf14a, "docs(marketing): correct the front-page numbers, pin them, and automate the demo (#245)" — the shipped card docs/roadmap/items/refresh-the-marketing-surface.md, whose body says "The README hero now leads with ... a four-command block". That commit message also states every command in demo.tape was verified "against a fixture", and docs/demo.tape indeed runs <code>python3 tests/make_fixture.py</code> then <code>boost search tdd</code> / <code>boost install brainstorming</code>. The fixture is where <code>tdd-workflow</code> is defined (make_fixture.py:90). So refresh-the-marketing-surface is the ORIGIN of this defect, not a card covering it — duplicate_of stays empty. - Not carded. I read all 432 titles and grepped item bodies myself: <code>tdd-workflow</code> appears only in browse-could-not-search-two-words.md:31 and cli-output-ignored-the-terminal.md:21, both incidental. "hero" appears only in BOOST-D03.md:16 (terminal gradient) and docsite-chrome-and-content-audit.md:38 (roadmap.html header). audit-quickstart-findings.md is about unpinned taps + three [rag] hint wordings; prerequisites-and-semantic-search-setup.md (shipped, PR 364) is about README's semantic-search section, <code>search</code>'s engine note and MCP instructions. Neither names README.md:21-26. - ADDITION the finder missed: line 23's comment "loads prebuilt vectors" is false in the same block for the same reason as line 24 — <code>boost quickstart --dry-run</code> prints "would import 0 shard(s) / 0 because semantic search needs the extra".

<b>Why it is worth doing.</b> This is the very first thing a new user copies out of the README, immediately under <code>pipx install boost-skill-cli</code>. Three of the four lines work and the fourth prints an error with three irrelevant close-match suggestions, so the reader's first impression of boost is that install is broken or that the docs are untrustworthy. It is also self-inflicted: the name is a test-fixture identifier that leaked into the marketing surface, and index.html already demonstrates the correct pattern (<code>brainstorming</code>, which resolves against the same starter set).

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
