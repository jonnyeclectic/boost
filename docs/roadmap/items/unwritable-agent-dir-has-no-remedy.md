---
id: unwritable-agent-dir-has-no-remedy
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: Every other issue doctor raises names a command (boost heal, boost sync, boost update…
order: 240
owner:
pr:
title: "! agent dir ~/.cursor/skills is not writable" is the one doctor issue with no next action — heal has no path for it and the next install crashes at exit 70
---
<b>Measured.</b> With <code>chmod 500 ~/.cursor/skills</code>, doctor prints the bare line <code>! agent dir ~/.cursor/skills is not writable</code> and exits 1, <code>boost heal</code> answers <code>✓ nothing to heal</code> and exits 0, and the very next <code>boost install tdd-workflow</code> exits 70 with a crash report from the unguarded <code>link.symlink_to(target)</code> at boost_cli/core/store.py:209 — leaving a store dir and two live agent links (claude-code, windsurf) that the lock file does not record, after which doctor's only prescription is <code>boost sync</code>, which deletes both links with no confirmation prompt.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt; || exit 1</code><br>
<code>export HOME=$TMPDIR/audit-doctor-verify4; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/audit-doctor-fix4 &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/audit-doctor-fix4 &gt;/dev/null 2&gt;&amp;1</code><br>
<code>BOOST_ASSUME_YES=1 ./boost install brainstorming &gt;/dev/null 2&gt;&amp;1</code><br>
<code>chmod 500 "$HOME/.cursor/skills"</code><br>
<code>./boost doctor | grep 'agent dir'          # bare symptom, no next action</code><br>
<code>./boost heal; echo "HEAL_EXIT=$?"          # "✓ nothing to heal", 0</code><br>
<code>BOOST_ASSUME_YES=1 ./boost install tdd-workflow; echo "INSTALL_EXIT=$?"   # 70</code><br>
<code>ls -1 "$HOME/.agents/skills"; ls -1 "$HOME/.claude/skills"</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. THE HEADLINE CLAIM IS FALSE. "the one doctor issue with no next action" / "Every other issue doctor raises names a command ... or a concrete action" is wrong. <code>bad("lockfile", "lock file schema is v%s, expected v%d")</code> at boost_cli/commands/quality.py:459-460 is also a bare symptom with no command and no action. I produced it live: <code>! lock file schema is v2, expected v3</code>. Correct figure: cmd_doctor (HEAD lines 394-811) has 21 <code>bad()</code> call sites; 2 of the 21 carry no remedy — agent-dir (662) and lockfile-schema (459-460). The title must say "one of the two doctor issues with no next action", not "the one".

2. "silently removes the two live tdd-workflow links" overstates. <code>boost sync</code> prints <code>✓ removed stale link ~/.claude/skills/tdd-workflow</code> and the same for windsurf — it names each deletion. What is true is narrower and I verified it with stdin closed and no BOOST_ASSUME_YES: sync deletes with NO confirmation prompt, and doctor's <code>run \</code>boost sync\`<code> line does not say deletion is what will happen. Reword to that; the sync behaviour itself belongs to the separate </code>doctor-prescribes-sync-that-deletes-live-links<code> finding, as the finder noted.

3. FILE PATH. The finding writes "quality.py:661-662" and "quality.py:695-697" bare. The file is </code>boost_cli/commands/quality.py<code>. There is no </code>boost_cli/core/quality.py` — I looked there first and it does not exist.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMITS OF MY REPRO — things a card author must not get wrong:

- THE DOCTOR CHECK AND THE CRASH ITERATE DIFFERENT AGENT SETS. quality.py:660 walks <code>agents.enabled_agents()</code> (5 dirs here: claude-code, windsurf, cursor, gemini, antigravity); store.link_agents walks <code>agents.linking_agents()</code> (4 — gemini is a native-store agent boost never links into). So an unwritable <code>~/.gemini/skills</code> raises the doctor line but can NEVER crash install. "The next install crashes" holds for 4 of the 5 dirs doctor can flag, not all 5.

- "TWO LINKS" IS NOT A FIXED NUMBER. <code>linking_agents()</code> iterates claude-code, windsurf, cursor, antigravity in that order. Cursor is third, so claude-code and windsurf land first and antigravity never does — I confirmed <code>~/.gemini/antigravity-cli/skills</code> holds only <code>brainstorming</code>. An unwritable <code>~/.claude/skills</code> (first in the order) would leave the store dir and ZERO links. Card the shape ("every link before the bad dir survives, none after"), not the count.

- MY POST-CRASH <code>ls</code>/lock measurement was taken after two consecutive crashed installs, not one (I re-ran to capture the exit code cleanly). I then ran a third crash after sync and got the identical shape — store dir stays, the two links are recreated, lock still <code>['brainstorming']</code> — so the state is idempotent across repeats. Say that rather than let the card imply one run was measured.

- NOT CARDED, and I checked properly.

<b>Why it is worth doing.</b> The lens question for doctor is whether each issue names one concrete next action; this is the line that fails it, and it fails while sitting on top of a real, reachable exit-70 crash — the exact shape a stuck new user hits after copying a dotfiles tree or restoring a backup with wrong ownership. One <code>chmod u+w ~/.cursor/skills</code> clause on the line, matching the log-file line eight lines above it in the same function, converts a dead end into a fix; guarding the symlink call would additionally turn the install crash into the <code>res.conflicts</code> message store.py already has for the neighbouring 'something is in the way' case.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
