---
id: doctor-prescribes-sync-that-deletes-live-links
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: L
impact: High
wow: 4
note: store.sync_plan decides staleness with link.name not in lock where lock = lockfile.in…
order: 206
owner:
pr:
title: A missing or corrupt lock file makes doctor prescribe <code>boost sync</code>/<code>boost heal</code>, and both delete every live agent symlink of an intact install
---
<b>Measured.</b> With the lock file deleted from an otherwise intact install, <code>boost doctor</code> exits 1 and prescribes <code>boost sync</code> on two separate lines; running that prescription removes 4 of 4 live, boost-owned, store-resolving agent symlinks (claude-code, windsurf, cursor, antigravity) with four green ✓ marks, no confirmation prompt of any kind, and exit code 0 — because <code>store.sync_plan</code> (store.py:1785-1787) tests <code>link.name not in lock</code> against <code>lockfile.installed()</code>, which collapses a missing lock into an empty skeleton (lockfile.py:44-45), and <code>sync_apply</code>'s unlink loop (store.py:1895) has no confirm while cmd_sync's only two confirms (pkg.py:694, 704) are both <code>--prune</code>-gated.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt; || exit 1</code><br>
<code>export HOME=$TMPDIR/audit-doctor-verify1; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/audit-doctor-fix1 &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/audit-doctor-fix1 &gt;/dev/null 2&gt;&amp;1</code><br>
<code>BOOST_ASSUME_YES=1 ./boost install brainstorming &gt;/dev/null 2&gt;&amp;1</code><br>
<code>ls -l $HOME/.claude/skills/          # link present and resolving</code><br>
<code>rm $HOME/.agents/skills/.skill-lock.json</code><br>
<code>./boost doctor; echo "DOCTOR_EXIT=$?"  # prescribes `boost sync` twice</code><br>
<code>./boost sync; echo "SYNC_EXIT=$?"      # removes all 4 live links, exit 0, no prompt</code><br>
<code>ls -A $HOME/.claude/skills/ $HOME/.cursor/skills/ $HOME/.windsurf/skills/ $HOME/.gemini/antigravity-cli/skills/</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The defect is real and the mechanism is exactly as described. Five corrections, two of them citation drift and three substantive enough that a card must not inherit them:

1. CITATION (minor). <code>store.py:1784-1787</code> — line 1784 is a comment (<code># keep in ~/.claude/skills was swept up by \</code>boost sync\<code>.</code>). The predicate is at <b>1785-1786</b> and <code>plan["stale_links"].append(str(link))</code> at <b>1787</b>. Cite <b>store.py:1785-1787</b>. (store.py:1684 docstring, store.py:1895, lockfile.py:44-45, lockfile.py:226-228, pkg.py:694 and pkg.py:704 are all EXACT as stated.)

2. CITATION (minor). <code>read()</code> returns the skeleton for corrupt at <b>lockfile.py:54</b>, not 53. Line 52 is a comment, line 53 is <code>_preserve_corrupt(p)</code>, line 54 is <code>return _skeleton()</code>. Cite <b>lockfile.py:53-54</b> (or 50-54 for the whole except block).

3. SUBSTANTIVE — the root-cause story in <code>why_it_matters</code> is wrong. It claims the lock file is "the one file with no atomic-write protection story ... (an interrupted install, a full disk, a bad restore)". The lock file <b>is</b> written atomically: <code>lockfile.write</code> ends at <code>lockfile.py:160</code> with <code>util.atomic_write_text(...)</code>, which writes to a same-directory temp file, flushes, fsyncs and <code>os.replace</code>s (util.py:123-135, docstring names the lock file explicitly), and the roadmap card <code>docs/roadmap/items/atomic-corruption-safe-lock-file-writes.md</code> is <code>status: shipped</code>, <code>pr: 65</code>.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

NOT A DUPLICATE — I re-checked all 432 items independently rather than trusting the finder's list. - <code>audit-verify-drift-say-nothing-installed-exit-0-and-doctor-says-lo.md</code> (shipped, PR #674) is the closest and is the direct predecessor, not a duplicate: read in full, it is explicitly scoped to REPORTING in <code>cmd_verify</code>/<code>cmd_drift</code>/<code>cmd_doctor</code>, and it is the card that INTRODUCED the exact wording measured here ("! lock file missing — N store dirs unrecorded, run <code>boost sync</code>"). Grep confirms <code>lockfile.check()</code>/<code>store.has_content()</code> appear ONLY in <code>quality.py:442,447</code> and <code>_common.py:57,61</code> — never in <code>store.py</code>. The repair engine was never converted. - <code>sync-deletes-unowned-broken-symlinks.md</code> (PR #273) and <code>heal-deleted-links-it-never-made.md</code> (PR #459) both concern ownership of BROKEN/foreign links; the links here are live, owned, and resolve. Sharpest near-miss evidence: the heal card's own body says ownership must be read from the link "because the two moments a dangling link is most likely to exist — a skill uninstalled mid-sweep, <b>a lock file that has gone missing</b> — are exactly the moments the lock cannot answer", then applies that reasoning only to the <code>points_into_store</code> half of the predicate, leaving <code>link.name not in lock</code> still consulting the lock. - <code>audit-focus-profile-sideline-...md</code> (PR #741) is the inverse direction — sync RELINKS via <code>missing_links</code>, undoing a sideline.

<b>Why it is worth doing.</b> This is the recovery surface behaving as a destroyer at the exact moment a user reaches for it. The lock file is the one file with no atomic-write protection story a new user knows about (an interrupted install, a full disk, a bad restore), the skill on disk and its four agent links are all still correct, and the single command doctor prints — twice — silently uninstalls it from Claude Code, Cursor, Windsurf and Antigravity, exits 0, and calls the result healthy two commands later. The one command that actually recovers (<code>boost install &lt;name&gt;</code>) is never mentioned, and the corrupt-lock alternative (<code>boost replay</code>) is empty on any machine with a single install — i.e.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
