---
id: quickstart-says-ready-exit-0-after-every-tap-failed
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: L
impact: High
wow: 4
note: cmd_quickstart warns per failed clone but never tracks failures: it unconditionally r…
order: 222
owner:
pr:
title: With every registry unreachable, quickstart prints "✓ indexed 0 items" and "✓ ready", exits 0 — and the command it recommends exits 1
---
<b>Measured.</b> On a machine that cannot reach any registry, <code>boost quickstart</code> fails 0-for-7 clones, prints "✓ indexed 0 items for keyword search" and "✓ ready — try <code>boost search brainstorming</code>", and exits 0 — while the very next line of README's own install snippet (README.md:22-23 is <code>boost quickstart</code> followed by <code>boost search</code>) exits 1 with "Error: no taps configured — nothing to search"; <code>cmd_quickstart</code> has no failure counter at all, so <code>out.ok</code> at quickstart.py:197 and :220 and <code>return 0</code> at :221 are unreachable-by-failure.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-qs-f2 ; export BOOST_HOME=$HOME/.boost ; mkdir -p "$HOME"</code><br>
<code>printf '[url "https://no-such-host.invalid/"]\n\tinsteadOf = https://github.com/\n' &gt; "$HOME/.gitconfig"</code><br>
<code>BOOST() { .venv/bin/python -c "import sys;sys.path.insert(0,'&lt;repo&gt;');from boost_cli.cli import main;sys.exit(main(sys.argv[1:]))" "$@"; }</code><br>
<code>BOOST quickstart ; echo "QUICKSTART_EXIT=$?"</code><br>
<code>BOOST search brainstorming ; echo "SEARCH_EXIT=$?"</code><br>
<code>BOOST doctor | tail -6</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Two process nits in the finding's own prose; neither is a defect number and neither belongs on a card.

1. <code>not_carded_check</code> says "Read all 318 <code>^title:</code> lines". The real count is 432: <code>ls docs/roadmap/items/*.md | wc -l</code> = 432 and <code>grep -h '^title:' docs/roadmap/items/*.md | wc -l</code> = 432. The conclusion still holds — I re-ran the dedupe check myself over all 432.

2. <code>evidence</code> says "lines 195-220 run unconditionally and end <code>return 0</code>". <code>return 0</code> is line <b>221</b>; the file is 221 lines long. Lines 195-220 are correct for the unconditional block; the return is one line past it.

Every defect-bearing figure is right: <code>quickstart.py:91</code> is the <code>out.warn("could not tap %s: %s"...)</code> + <code>continue</code>; <code>:197</code> is <code>out.ok("indexed %s items for keyword search")</code>; <code>:220</code> is <code>out.ok("ready — try \</code>boost search brainstorming\<code>")</code>; <code>:3</code> is the "one command from empty machine to working search" docstring; <code>config.DEFAULT_TAPS</code> is exactly 7 registries in the order printed; <code>tests/functional/test_cli_quickstart.py:217</code> is <code>test_it_reports_each_outcome_and_survives_a_bad_registry</code> with <code>assert both.count("tapped ") &gt;= 2</code> at :224 and <code>assert "ready" in both</code> at :225, and it passes today.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Dedupe check I ran myself: only 5 of the 432 item files mention quickstart. <code>audit-quickstart-findings.md</code> is unpinned-taps-without-[rag] plus the three <code>[rag]</code> hint wordings — no exit codes, no success lines. <code>shard-refresh-skips-processed-commits.md</code> is rerun re-downloads. <code>published-shards-have-no-consumer.md</code>, <code>publish-the-keyword-index.md</code> and the stale-prose card are the 463/464 count and shard reachability. I also read the exit-0 family (<code>audit-verify-drift-…exit-0</code>, <code>audit-clean-counts-failed-removals-…exits 0</code>, <code>audit-tap-findings</code>, <code>one-dead-tap-broke-every-update</code>) — all per-command, none quickstart. Not carded.

Two things a card author must not get wrong:

1. <b>The fix condition is "no taps configured afterwards", not "zero clones succeeded".</b> <code>registry.add_many</code> returns <code>skipped: True</code> for a registry already tapped, and <code>_tap_defaults</code> returns <code>names</code> (every selected registry, tapped here or not) — it discards outcomes entirely. So on a clean rerun where all 7 are already tapped, *zero* results carry <code>ok: True</code>. A naive <code>count(ok) == 0 -&gt; return 1</code> would make every successful rerun exit 1. Gate on <code>registry.list_taps()</code> being empty (or <code>stats["entries"] == 0</code>) instead. I ran <code>test_it_reports_each_outcome_and_survives_a_bad_registry</code> and it passes today; that test asserts <code>both.count("tapped ") &gt;= 2</code> and <code>"ready" in both</code>, so a fix that only fires at total failure keeps it green, as the finding says.

2.

<b>Why it is worth doing.</b> This is the first command a new user runs and the first one a Dockerfile, CI job or setup script runs. Exit 0 means every automated caller records a successful install of a boost that cannot search anything; a human sees seven warnings scroll past and two green ticks at the bottom, which is the shape that reads as success. The command's own docstring promises "working search" and delivers zero items while claiming ready. A fix is a failure counter: when 0 taps succeeded, say so and return non-zero — leaving the partial-failure behaviour (and its existing test) untouched.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
