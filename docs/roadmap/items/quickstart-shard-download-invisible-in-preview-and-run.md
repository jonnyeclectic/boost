---
id: quickstart-shard-download-invisible-in-preview-and-run
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: shards.sync() takes an on_event progress callback and both other callers pass one; qu…
order: 223
owner:
pr:
title: The shard download is invisible both before and during: <code>--catalog --dry-run</code> never names the 1,604.8 MB, and the live fetch passes no progress callback and has no spinner
---
<b>Measured.</b> On a virgin HOME, <code>boost quickstart --catalog --dry-run</code> prints exactly two lines — "would tap 464 registries (459 pinned to a published shard's commit)" and "would build the keyword index, then import 459 shard(s)" — and never names the 1,604.8 MB (1,604,753,775 bytes) those same 459 manifest rows sum to, although the dry-run has already read the manifest that carries every row's <code>bytes</code> and <code>shards._size_label()</code> exists to format it.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>grep -n 'on_event' boost_cli/commands/quickstart.py            # -&gt; no matches</code><br>
<code>grep -n 'on_event' boost_cli/commands/discovery.py boost_cli/commands/pkg.py</code><br>
<code>sed -n '195,215p' boost_cli/commands/quickstart.py             # Spinner at 195, bare sync at 209</code><br>
<code>curl -sSL -o $TMPDIR/mf.json https://github.com/jonnyeclectic/boost/releases/download/shards-latest/manifest.json</code><br>
<code>python3 -c "import json;d=json.load(open('$TMPDIR/mf.json'));print(len(d['shards']),'rows', '%.1f MB' % (sum(r.get('bytes',0) for r in d['shards'])/1e6))"</code><br>
<code>export HOME=$TMPDIR/audit-qs-f3 ; export BOOST_HOME=$HOME/.boost ; mkdir -p "$HOME"</code><br>
<code>env HOME="$HOME" BOOST_HOME="$BOOST_HOME" BOOST_SHARD_MANIFEST="file://$TMPDIR/mf.json" \</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

One stated detail is wrong: "<code>shards.sync()</code> … both other callers pass one."

<code>shards.sync</code> has THREE call sites, and only ONE passes <code>on_event</code>: - <code>boost_cli/commands/discovery.py:409</code> (sync) — passes <code>on_event=None if args.as_json else _shard_event</code> at :414. ✓ - <code>boost_cli/commands/quickstart.py:209</code> (sync) — passes none, no Spinner. ✗ - <code>boost_cli/commands/pkg.py:941</code> (<code>_resync_vectors</code>) — <code>shards.sync(list(by_name), by_name, manifest=manifest)</code>, passes NO <code>on_event</code> and is inside no Spinner either. ✗

The finding's second citation, <code>pkg.py:997</code>, is the <code>on_event=</code> line of a <code>shards.ingest(</code> call that starts at <code>pkg.py:993</code> — not a <code>sync</code> caller. Both quoted line numbers (414, 997) are accurate as lines; the framing "both other [sync] callers pass one" is not, and so is the implied "quickstart is the lone outlier".

Everything else re-derived and correct to the digit: 459 manifest rows; 1,604,753,775 bytes = 1604.8 MB (1530.4 MiB); the five per-default byte counts and chunk counts verbatim; expo/skills and K-Dense-AI/scientific-agent-skills have NO ROW; 17,088,844 = 17.1 MB for the seven defaults; the two dry-run lines verbatim including "464 registries" / "459 shard(s)"; the <code>--catalog</code> help text verbatim.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMITS OF MY REPRO — a card must not overstate these: 1. The live silence was measured on the SEVEN DEFAULTS only, and the sandbox proxy truncates response bodies (every shard ended "failed verification" — bytes were received and hashed, then rejected). My 2.19 s gap ([3.93s] "indexed 962 items" -&gt; [6.12s] first shard line) is a LOWER BOUND; a complete 17.1 MB fetch takes longer. The finder measured 2.53 s and 1.98 s — same shape. 2. <code>--catalog</code> was NEVER exercised live by me (it would pull 1.6 GB, and the proxy truncates). 1,604.8 MB is manifest arithmetic — the sum of <code>bytes</code> over all 459 rows — not a stopwatched transfer. It is the right number for a virgin HOME, where no row is "current" and all 459 download, but write it as a sum, not as a measurement. 3. The dry-run repro requires <code>dense.have_backend()</code> True (the repo <code>.venv</code> has <code>[rag]</code>). Without the extra the manifest is never fetched and the dry-run prints a different "0 because …" line — a different defect, already carded in audit-quickstart-findings.md. 4. The live run needs the REAL manifest URL. With <code>BOOST_SHARD_MANIFEST=file://…</code> the host check refuses every shard ("shard URL … is not on the manifest's own host") and no download is attempted, so that override is fine for the dry-run repro but useless for timing the live path.

FIX SCOPE IS WIDER THAN THE FINDING SAYS: because <code>pkg.py:941</code> (<code>_resync_vectors</code>) is also a silent <code>shards.sync</code> caller, a fix that only touches quickstart leaves two of three sync sites inconsistent.

<b>Why it is worth doing.</b> <code>--catalog</code> is the one expensive, mostly-irreversible decision quickstart offers a brand-new user, and both surfaces that exist to describe it — <code>--help</code> and <code>--dry-run</code> — omit its dominant cost. A user on a laptop tether or a metered link is asked to approve "459 shard(s)" with no way to learn that means 1.6 GB, and once it starts there is no spinner, no per-shard line and no byte counter to tell them how far along it is or that anything is happening at all. Every ingredient of the fix is already in the file: pass <code>_shard_event</code>-style <code>on_event</code>, and sum <code>row['bytes']</code> through the existing <code>_size_label</code> in the dry-run line.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
