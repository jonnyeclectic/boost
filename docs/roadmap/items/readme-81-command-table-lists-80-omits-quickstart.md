---
id: readme-81-command-table-lists-80-omits-quickstart
board: code
section: planned
status: planned
category: Quality · Docs
complexity: S
impact: Low
wow: 2
note: README.md:389 heads a table "## 81 commands, organized into 8 groups", but the eight …
order: 224
owner:
pr:
title: README's "81 commands" table enumerates only 80 — the missing one is <code>quickstart</code>, the README's own first command
---
<b>Measured.</b> Commit dd2fba07 (PR #594, "publish prebuilt vectors where a new user can reach them") added <code>("quickstart", "cfg", ...)</code> to cli.py's COMMANDS and changed README.md:389 from "## 80 commands" to "## 81 commands" — and left README.md:404's Configuration row at its 13 names, so the README has advertised 81 commands while listing 80 ever since, with the whole test suite green, because <code>test_marketing_counts.py</code> asserts the integer and <code>test_docsite_chrome.py:63-71</code> pins the enumeration only for <code>docs/index.html</code>.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import re, sys</code><br>
<code>sys.path.insert(0,'.')</code><br>
<code>from boost_cli.cli import COMMANDS</code><br>
<code>names = {n for n,_,_,_ in COMMANDS}</code><br>
<code>readme = open('README.md').read()</code><br>
<code>rows = re.findall(r'^\| ([A-Z][^|]*?) \| (.+?) \|$', readme, re.M)</code><br>
<code>tbl = {g.strip(): [c.strip() for c in cmds.split('·')] for g, cmds in rows if '·' in cmds}</code><br>
<code>listed = {c for v in tbl.values() for c in v}</code><br>
<code>print("README table total:", sum(len(v) for v in tbl.values()), "COMMANDS:", len(names))</code><br>
<code>print("missing from README table:", sorted(names - listed))</code><br>
<code>PY</code><br>
<code>grep -n '81 commands' README.md</code><br>
<code>./boost --help | grep -n 'quickstart'</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The defect itself reproduces exactly as stated — README.md:389 heads "81 commands", the eight rows at README.md:398-405 enumerate 80, and the set difference against <code>cli.py</code>'s COMMANDS is exactly <code>{'quickstart'}</code>. Two stated facts are wrong:

1. LOAD-BEARING — <code>why_it_matters</code> says "The README table is the only place a reader browses the command surface without running the CLI." False. <code>docs/commands.html</code> (4 quickstart hits) and <code>docs/index.html</code> (3 hits, including the pinned <code>["quickstart","cfg",...]</code> row) both enumerate the full surface, and README.md:391-393 links both of them two lines ABOVE the table. A card must not ship that sentence. The honest framing: the README table is the surface a reader browses in-file, and the one enumeration of the three that nothing pins.

2. SOFT — "the one <code>docs/semantic-search.md</code> points at three times". Three is only right if you count fenced-code invocations (lines 30, 63, 64). The string <code>boost quickstart</code> appears 4 times (30, 33, 63, 64) and <code>quickstart</code> appears on 7 lines (+1, 83, 89). Say "four <code>boost quickstart</code> references across seven mentions" or drop the number.

3.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO: entirely static — README.md, boost_cli/cli.py, docs/*.html, the two test files, and <code>./boost --help</code> from the repo checkout. No corpus, tap set or network was needed, so nothing here is contingent on the 20-tap eval corpus or on which registries ship by default. Fully settled.

WHY Low, not Med. The finder's Med overstates it. <code>quickstart</code> is named in README.md five other times (line 23 hero, 142, 145, 151, 176), in <code>./boost --help</code>, and in both generated doc pages that the README links immediately above the table. The user-visible cost is one missing name out of 81 in one browsable list; nothing breaks and no one is misinformed about whether the command exists. The finder's line "a user who reads the hero sees a command the table says does not exist" is rhetorical — the table omits, it does not deny.

WHY IT IS STILL WORTH A CARD. The value is structural, not the symptom: of the three enumerations of the command surface, <code>docs/index.html</code> is pinned name-by-name against COMMANDS (test_docsite_chrome.py:63-71), <code>docs/commands.html</code> is generated from COMMANDS and gated by <code>build_command_reference.py --check</code>, and README's table is hand-maintained with only its integer asserted. PR #594 is the proof that the gap is live rather than theoretical.

<b>Why it is worth doing.</b> The README table is the only place a reader browses the command surface without running the CLI, and the one command it drops is the one the same file's hero block makes step 2 of onboarding. A user who reads the table sees no quickstart, and a user who reads the hero sees a command the table says does not exist. The count and the list also contradict each other in the same heading, which is exactly the class of drift test_marketing_counts.py was written for — it just guards the integer and not the enumeration.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
