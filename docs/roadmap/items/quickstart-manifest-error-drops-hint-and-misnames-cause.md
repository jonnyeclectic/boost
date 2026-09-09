---
id: quickstart-manifest-error-drops-hint-and-misnames-cause
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: cmd_quickstart catches every BoostError from shards.fetch_manifest() and prints exc.m…
order: 221
owner:
pr:
title: A local manifest read error is reported as "no published shards", and the BoostError's hint — the only actionable line — is discarded
---
<b>Measured.</b> 4 of the 9 <code>BoostError</code> raises reachable from <code>shards.fetch_manifest()</code> carry a <code>hint</code>, and all three transport-shaped failures are among them — scheme refusal, "cannot reach" (hint: "shards are optional — <code>boost reindex --dense</code> embeds locally instead"), and truncation (hint: "a proxy or a dropped connection cut the stream — retry") — so the one line quickstart.py:164 throws away is precisely the line that fires on the real-world failures, while a live run with an unreadable manifest still ends <code>✓ ready</code> at exit 0 with all seven taps unpinned and no word about vectors.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-qs-f4 ; export BOOST_HOME=$HOME/.boost ; mkdir -p "$HOME"</code><br>
<code># 1. the error object carries a hint:</code><br>
<code>env HOME="$HOME" BOOST_HOME="$BOOST_HOME" BOOST_SHARD_MANIFEST="file:///nonexistent-manifest.json" \</code><br>
<code>  .venv/bin/python -c "</code><br>
<code>import sys; sys.path.insert(0,'.')</code><br>
<code>from boost_cli.core import shards</code><br>
<code>from boost_cli.errors import BoostError</code><br>
<code>try: shards.fetch_manifest()</code><br>
<code>except BoostError as e: print('message:', e.message); print('hint   :', e.hint)"</code><br>
<code># 2. what quickstart prints instead (dry-run: no clones, no writes):</code><br>
<code>env HOME="$HOME" BOOST_HOME="$BOOST_HOME" BOOST_SHARD_MANIFEST="file:///nonexistent-manifest.json" \</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three stated details are wrong; the defect itself is real and reproduces exactly.

1. "<code>grep -n 'hint' boost_cli/commands/quickstart.py</code> returns only argparse <code>help=</code> strings" — it returns ZERO lines. No <code>help=</code> string in the file contains the substring "hint". The underlying claim (<code>exc.hint</code> is never read in quickstart.py) is correct.

2. "at quickstart.py:212-217 the chain is <code>if manifest is not None: … elif args.no_vectors: … elif not dense.have_backend():</code>" — the chain spans lines 200-217. <code>if manifest is not None:</code> is at line <b>200</b>; 212-217 covers only the two <code>elif</code> arms (212 <code>elif args.no_vectors:</code>, 214 <code>elif not dense.have_backend():</code>). Cite 200-217, not 212-217.

3. "Read all 318 <code>^title:</code> lines" — <code>grep -h '^title:' docs/roadmap/items/*.md | wc -l</code> returns <b>432</b> today (432 item files). Likely concurrent-loop growth since the finder ran, but the stated count is stale.

Every other figure re-derived and matched: quickstart.py:163-165 (the catch) exact; :173-176 (the "the live path already explains both cases" comment) exact; :186-189 (the dry-run explanatory branch) exact; the live manifest is 169,851 bytes and publishes 459 shards; <code>fetch_manifest</code> is one GET with no retry loop; live run exits 0 with 962 items and no <code>@ sha</code> pins.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope of my repro: I forced the failure with <code>BOOST_SHARD_MANIFEST=file:///nonexistent-manifest.json</code>, which takes the <code>_open</code> URLError branch (hint "shards are optional…"). The truncation hint at shards.py:152-155 is verified by reading source, NOT by reproducing a truncated download — the finder's <code>113778 of 169851 bytes</code> capture is theirs. I corroborated only that 169,851 is the real Content-Length today (curl, http=200).

Things a card author must not get wrong: - <code>_report()</code> (~quickstart.py:120) uses the SINGULAR "no published shard" per-tap, and that wording is correct in its context. The fix targets only the plural at line 164. Do not sweep both. - <code>shards.rows()</code> never raises (it skips malformed rows by design, shards.py:222-237), so <code>fetch_manifest</code> is the only BoostError source inside the try at 160-165. Every error that reaches the catch is a read/transport/format failure — "no published shards" is wrong in every reachable case, not merely usually. - 5 of the 9 raises carry NO hint (implausibly large, not-valid-JSON, not-an-object, missing provider/model/dim, no shards list), so "render <code>exc.hint</code>" improves a subset; the wording fix and the missing live-path else-branch are the parts that help universally. - The convention the catch bypasses is real: <code>boost_cli/cli.py:368</code> renders <code>out.err(e.message, hint=e.hint)</code> at top level. - No test pins the current wording — <code>grep -rn 'no published shards'</code> across the repo has exactly one hit, quickstart.py:164 itself.

<b>Why it is worth doing.</b> The manifest fetch is one 170 KB GET that decides whether the whole run pins taps and imports vectors, and it is attempted exactly once with no retry. When it fails for any reason — a proxy, a dropped connection, a <code>BOOST_SHARD_MANIFEST</code> typo, an air-gapped mirror path — the user is told the wrong thing ("no published shards", i.e. the project has none) and is not told the right thing (the hint boost already wrote for this case). On the live path they are then told nothing further, so a run that quietly skipped the entire vector step ends in a green tick.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
