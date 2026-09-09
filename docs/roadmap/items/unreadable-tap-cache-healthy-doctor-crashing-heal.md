---
id: unreadable-tap-cache-healthy-doctor-crashing-heal
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: Doctor's tap check is elif not tap.cache_file.exists(): (quality.py:420) — existence …
order: 239
owner:
pr:
title: An unreadable tap cache is invisible to doctor ("✓ 1 tap cloned &amp; cached", exit 0) while search, browse and heal all exit 70 with a crash report
---
<b>Measured.</b> A tap cache file that is fully READABLE but not writable (mode 400 — exactly what one <code>sudo boost</code> run leaves behind) turns the next routine <code>CACHE_FORMAT</code> bump into exit 70 on <code>search</code>, <code>browse</code>, <code>info</code>, <code>update</code> and <code>heal</code>, while <code>boost doctor</code> prints "✓ 1 tap cloned &amp; cached" and verdicts "● healthy" at exit 0 — and no boost command repairs it, because <code>boost update &lt;tap&gt;</code>, the remedy doctor would name, crashes with the same PermissionError at exit 70.

<b>Reproduce it.</b>

<code># run as a normal (non-root) user; root ignores mode bits</code><br>
<code>cd &lt;repo&gt; || exit 1</code><br>
<code>export HOME=$TMPDIR/audit-doctor-verify2; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/audit-doctor-fix2 &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/audit-doctor-fix2 &gt;/dev/null 2&gt;&amp;1</code><br>
<code>BOOST_ASSUME_YES=1 ./boost install brainstorming &gt;/dev/null 2&gt;&amp;1</code><br>
<code>chmod 000 "$BOOST_HOME/cache/audit-doctor-fix2.json"</code><br>
<code>./boost doctor; echo "DOCTOR_EXIT=$?"      # "✓ 1 tap cloned &amp; cached" ... "● healthy", 0</code><br>
<code>./boost heal; echo "HEAL_EXIT=$?"          # PermissionError, crash report, 70</code><br>
<code>./boost search brainstorm &gt;/dev/null 2&gt;&amp;1; echo "SEARCH_EXIT=$?"   # 70</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three corrections; the first two make the finding STRONGER, so the card must not repeat its own understatement.

1. WRONG REMEDY. The finding says "The real fix is one line (<code>boost update &lt;tap&gt;</code>, or deleting the cache file)". <code>boost update &lt;tap&gt;</code> does NOT fix it — it crashes with the identical PermissionError, UPDATE_EXIT=70 (measured unpiped; the finder's own piped run would have shown tail's status). <code>boost clean</code> exits 0 and leaves the file in place (cache/*.json whose stem IS a configured tap is deliberately kept). So there is NO CLI command that repairs this state: the only remedy is manually deleting or chmod-ing the file, which no boost surface names.

2. BLAST RADIUS UNDERSTATED. The finding lists search, browse, heal. <code>boost info &lt;skill&gt;</code> also exits 70 (INFO_EXIT=70). Unaffected: <code>list</code> (0), <code>clean</code> (0), <code>heal --dry-run</code> (0).

3. TWO LINE NUMBERS WRONG (secondary refs only). <code>complete.refresh_names()</code> is at quality.py:1152, NOT :1157. Journal rotation is quality.py:1154-1160, NOT :1159-1165. All four PRIMARY line numbers are exact: quality.py:420, quality.py:1140, quality.py:1146, catalog.py:253. The claim they encode — that both post-rebuild steps sit after the crash point — is correct.

4. TRIGGER IS WIDER THAN <code>chmod 000</code> (in the finding's favour, and this is the number the card should lead with). The file need only be NON-WRITABLE, not unreadable.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMITS OF MY REPRO — a card author must not overstate these:

- A read-only cache DIRECTORY does NOT trip this. I measured <code>chmod 500</code> on ~/.boost/cache with a stale format: search exited 0. POSIX only needs directory write permission to create or unlink, not to rewrite an existing file, and <code>rebuild_tap</code> overwrites in place. Do NOT describe the trigger as "a read-only ~/.boost" or "a read-only mount" — the trigger is specifically the cache FILE being non-writable by the process. - I could not test the root-owned-file case (no sudo in this sandbox). The <code>sudo boost</code> provenance story is the plausible real-world cause of a non-writable cache file, but it is reasoning from the mode bits I set by hand, not a measured provenance. State it as "what a root-owned cache file looks like", not as an observed user report. - Disk-full (ENOSPC) would hit the same unguarded <code>write_text</code> and is the other realistic trigger, but I could not simulate it. Do not put a number on it. - All exit codes in <code>reproduced_output</code> are unpiped. My first contrast run piped through <code>tail</code>, so those exit codes measured <code>tail</code>; I re-ran every one of them bare. The finder's evidence has the same piping hazard, which is how the <code>boost update</code> remedy claim survived unchecked. - Python here is 3.14.7 (Homebrew).

<b>Why it is worth doing.</b> A user whose search has stopped working runs the two commands the CLI offers for exactly that: doctor tells them the machine is healthy, and heal — the self-repair command that owns cache rebuilding — crashes with a stack-trace-shaped error and an invitation to file a GitHub issue. The real fix is one line (<code>boost update &lt;tap&gt;</code>, or deleting the cache file) and nothing names it. Because <code>rebuild_tap</code> runs unconditionally for every tap, one bad cache file among hundreds takes the whole <code>heal</code> run down and silently skips journal rotation and completion refresh.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
