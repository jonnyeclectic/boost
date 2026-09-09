---
id: quickstart-drops-incompatible-shard-status
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: shards.sync() returns status: "incompatible" with a fully-formed reason when the publ…
order: 220
owner:
pr:
title: quickstart silently discards the <code>incompatible</code> shard status, so a user with any API key is never told why zero vectors arrived
---
<b>Measured.</b> On one machine with <code>VOYAGE_API_KEY</code> set, <code>shards.sync</code> returned 7 rows all reading <code>status: "incompatible", detail: "published shards are local, this machine embeds with voyage"</code> and <code>boost quickstart</code> rendered zero of them — while <code>boost quickstart --dry-run</code> on that same machine promised "would build the keyword index, then import 5 shard(s)".

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>curl -sSL -o $TMPDIR/mf.json https://github.com/jonnyeclectic/boost/releases/download/shards-latest/manifest.json</code><br>
<code>export HOME=$TMPDIR/audit-qs-f1 ; export BOOST_HOME=$HOME/.boost ; mkdir -p "$HOME"</code><br>
<code>env -u OPENAI_API_KEY VOYAGE_API_KEY=x HOME="$HOME" BOOST_HOME="$BOOST_HOME" \</code><br>
<code>  BOOST_SHARD_MANIFEST="file://$TMPDIR/mf.json" \</code><br>
<code>  .venv/bin/python -c "import sys;sys.path.insert(0,'.');from boost_cli.cli import main;sys.exit(main(sys.argv[1:]))" quickstart</code><br>
<code># -&gt; no line mentions 'voyage', 'incompatible', or 'embedding space'.</code><br>
<code># Now show what sync actually returned and quickstart threw away:</code><br>
<code>env -u OPENAI_API_KEY VOYAGE_API_KEY=x HOME="$HOME" BOOST_HOME="$BOOST_HOME" \</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three details are wrong or understated; the defect itself is real and reproduced verbatim.

1. "17.1 MB for the seven defaults" — 17.1 MB (16.3 MiB) is the total across the <b>5 of 7</b> defaults that have a manifest row. <code>expo/skills</code> and <code>K-Dense-AI/scientific-agent-skills</code> have no published shard at all (which is also why they tapped without an <code>@ sha</code>). Per-row: qdhenry/Claude-Command-Suite 7.9 MB, trailofbits/skills 4.5 MB, PatrickJS/awesome-cursorrules 3.6 MB, anthropics/skills 0.7 MB, obra/superpowers 0.4 MB. The claim "all seven come back <code>incompatible</code>" is still exactly right, because <code>incompatible()</code> short-circuits before the row lookup. (459 rows and 1,604.8 MB total re-derive correctly.)

2. "points at hours of CPU" — wrong mechanism. For the affected user (a Voyage/OpenAI key is exported, which is *why* the shards are refused), <code>boost reindex --dense</code> embeds through the <b>paid API</b>, not the local model: the cost is money plus network time, not local CPU hours. Same conclusion, different bill.

3. "The fix is one tuple entry plus adding <code>incompatible</code> to the status comment" — understated, because there is a second defect on the same path that the finding does not name.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Verified against current source, not the finder's text: <code>_report</code> (<code>quickstart.py:105-135</code>) renders <code>imported</code>/<code>current</code> then loops exactly <code>("unpublished","refused","failed")</code>; <code>incompatible</code> is produced at <code>shards.py:357-360</code> and is absent from the status-vocabulary comment at <code>shards.py:326-330</code>. <code>_report</code> has exactly one caller (<code>quickstart.py:211</code>) — the sibling surfaces <code>commands/discovery.py:401-403</code> (<code>reindex --fetch-shards</code>) and <code>commands/pkg.py:984-986</code> (<code>update --shards</code>) both raise <code>BoostError("published shards cannot serve this machine — %s")</code> and exit 1, so quickstart is the only surface that swallows it. Test claim confirmed: <code>tests/functional/test_cli_quickstart.py:254</code> lives in <code>class TestFetchShards</code>, and the quickstart class's <code>test_shard_commits_are_passed_as_pins</code> (line 227) stubs <code>shards.sync</code> to <code>[]</code>.

CARD-AUTHOR WARNINGS: - Do NOT fix this by appending <code>("incompatible", …)</code> to the existing tuple as-is: <code>sync</code> stamps the *same machine-level* <code>detail</code> on every tap, so that emits seven identical muted lines. Render it <b>once</b>, and name both remedies — unset the key to take the free ~17 MB download, or keep the key and pay for <code>reindex --dense</code> through the API. - Affected population is narrower than "any machine with a key": it is key-exported <b>AND</b> the <code>[rag]</code> extra installed.

<b>Why it is worth doing.</b> A Voyage or OpenAI key is a configuration boost explicitly supports ("a key is a quality upgrade rather than the entry fee" — CLAUDE.md), and it is exactly what a serious first user is most likely to have already exported. For that user the headline feature of <code>quickstart</code> — 1,604.8 MB of published vectors across 459 rows, or 17.1 MB for the seven defaults — is declined with no reason given, and the one line they do get (<code>embed the rest locally when you want to: boost reindex --dense</code>) points at hours of CPU without mentioning that unsetting one env var would make the free download work instead. The fix is one tuple entry plus adding <code>incompatible</code> to the status comment at shards.py:327.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
