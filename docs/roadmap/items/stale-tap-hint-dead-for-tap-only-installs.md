---
id: stale-tap-hint-dead-for-tap-only-installs
board: code
section: planned
status: planned
category: Tech-debt
complexity: M
impact: Med
wow: 3
note: CLAUDE.md's rule is that "search must never refresh taps in the background: _hint_sta…
order: 244
owner:
pr:
title: The "taps last refreshed N days ago" hint can never fire on a machine that tapped and never ran <code>boost update</code> — the only writer of the marker is <code>update</code> itself
---
<b>Measured.</b> The maintainer's own production install has 458 taps configured and no marker: <code>~/.boost/state/</code> is fully populated (pulse.jsonl 95k, lock-history/, snapshots/, and <code>last-shard-sync</code> stamped 8 Sep) while <code>last-tap-refresh</code> is absent — so the directory was not wiped, the file was simply never written across 458 taps, and the stale-tap hint CLAUDE.md describes as search's drift-reporting mechanism has never been able to fire there. The 20-tap eval corpus is the same: no marker. Two real installs, zero markers.

<b>Reproduce it.</b>

<code>export HOME=$TMPDIR/lens2-du2 ; export BOOST_HOME=$HOME/.boost ; mkdir -p "$HOME"</code><br>
<code>cd &lt;repo&gt;</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/lens2-fix2</code><br>
<code>./boost tap $TMPDIR/lens2-fix2</code><br>
<code>python3 -c "from boost_cli.core import paths, registry; m=paths.tap_refresh_marker(); print('marker:',m); print('exists:',m.exists()); print('refresh_age_days():',registry.refresh_age_days()); print('STALE_TAPS_DAYS:',registry.STALE_TAPS_DAYS)"</code><br>
<code># now prove update is the only writer:</code><br>
<code>grep -rn 'mark_refreshed()' boost_cli | grep -v 'def mark_refreshed'</code><br>
<code>./boost update</code><br>
<code>ls -la $BOOST_HOME/state/last-tap-refresh</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The mechanism reproduces exactly, but three of the claim's supporting statements are wrong:

1. "the open card audit-audit-findings.md:36" — that card is <code>status: shipped</code> (docs/roadmap/items/audit-audit-findings.md, frontmatter line 5), not open. Its proposal is not pending; it landed.

2. "would make two more surfaces silent for the same population" — false for <code>boost health</code>, which has ALREADY moved onto this marker and does NOT go silent. boost_cli/commands/quality.py:1417-1425 reads <code>registry.last_refresh_at()</code> and I measured the tap-only install printing <code>last tap sync never</code>. That is an honest degradation, visible to the user — the opposite of the silent failure the claim predicts.

3. "would make two more surfaces silent" — also false for <code>boost audit --skills</code>, which never moved onto the marker. boost_cli/commands/safety.py:233 <code>_tap_age_days</code> still shells out to <code>git log -1 --format=%ct</code> on the clone, so it is unaffected by the marker either way. Zero additional surfaces are made silent, not two.

4. "unreachable for the entire population it is aimed at" — over-broad. The hint is aimed at users whose taps are stale, and the long-ago-updated half of that population IS served correctly (my control run B proves it fires at 200 days).

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope limits of my repro:

- My A/B used a 5-item <code>tests/make_fixture.py</code> tap, not the real default set. The population claim about <code>boost tap --defaults</code> and <code>boost quickstart</code> is settled by code inspection, not by running them: quickstart.py touches only <code>registry.list_taps</code> and <code>registry.add_many</code>, and <code>pkg.py:1077</code> is the sole <code>registry.update</code> call in all of boost_cli/commands/. No command other than <code>update</code> can reach <code>mark_refreshed</code>. - I aged install A by backdating every file under BOOST_HOME and install B by backdating the marker; neither is a genuinely 200-day-old machine, but the marker's mtime is the only input <code>refresh_age_days</code> reads (registry.py:435-440), so the emulation is exact. - The real install was inspected read-only with <code>ls</code> and a <code>json.load</code> of config.json. I did NOT run <code>boost health</code> there — it writes caches — so the "last tap sync never" line is measured on my disposable HOME, and the real machine's marker absence is measured directly. - I did not weigh the mitigation heavily: <code>boost health</code> does report "never", but it reaches the wrong population — the hint lives in <code>search</code> precisely because that is the command a never-update user runs, and nothing routes them to <code>health</code>. - Noticed but out of scope, not chased: the <code>if results:</code> guard at registry.py:680 means an <code>update</code> sweep where every tap FAILED also skips the stamp, and <code>test_a_sweep_with_no_taps_stamps_nothing</code> pins the no-taps case deliberately. - Not carded: <code>grep -h '^title:' docs/roadmap/items/*.md</code> plus body greps for mark_refreshed / tap_refresh_marker / refresh_age_days / "never …

<b>Why it is worth doing.</b> Tap clones are load-bearing for both BM25 freshness and dense vector validity, and boost deliberately refuses to refresh them in the background — which makes this one muted line the entire mechanism by which a user learns their catalogue has drifted. It is switched off for precisely the users who need it (onboard via quickstart or <code>tap --defaults</code>, search for months, never update), and switched on only for users who already demonstrated they run <code>boost update</code>. Stamping the marker on a successful tap would cost one <code>write_text</code> and make the hint reachable.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
