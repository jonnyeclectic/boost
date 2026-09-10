---
id: reclone-leaves-a-clone-on-head-when-it-cannot-reach-the-pin
board: code
section: internals
status: shipped
category: Safety · Bug
complexity: S
impact: High
wow: 3
note: the last unfixed path of the pin-integrity item, left behind when three PRs claimed it and one won
order: 310
owner: loop/reclone-pin-integrity
pr: 0
title: "<code>compact --reclone</code> left a clone on HEAD when it could not reach the pin"
---
The residual of <code>audit-pinned-taps-silently-moved-to-head-by-update-re-clone-and-co</code>,
and it survived for a reason worth recording: <b>three PRs claimed that item, all
22/22 green, and none was a strict superset.</b> <code>#725</code> guarded the
unresolvable pin in <code>registry.update</code> and won on the older claim;
<code>#738</code> guarded it in <code>compact --reclone</code> and was closed. The
closing comment named the gap and asked for it back as its own item &mdash; this is
that item, and the fix is <code>#738</code>'s, applied to current <code>main</code>.

What was left: <code>--reclone</code> deletes the clone <em>before</em> it makes a new
one, so by the time <code>gitutil.checkout_commit</code> raises on a pin it cannot
resolve, the pinned tree is already gone. The <code>except BoostError</code> below
warned and carried on, leaving a clone sitting on HEAD with the old pin still recorded
beside it in <code>config.json</code>. The next <code>update</code> then reads
<code>is_cloned</code> true <em>plus</em> a pin and answers
<em>&ldquo;pinned at &lt;sha&gt; (skipped)&rdquo;</em> &mdash; permanently, for a tree
that is not on that commit. Prebuilt shard vectors are keyed to that pin, so the tap
carries stale vectors that are still present and raise no error: the failure that looks
like nothing at all.

The fix removes the half-made clone and re-raises, which is exactly what
<code>registry.update</code> already does on the same failure &mdash; this is simply the
path that gets there first. Not-cloned is a state <code>doctor</code> names
(<em>&ldquo;! tap &lt;x&gt; not cloned&rdquo;</em>, exit 1) and one <code>update</code>
repairs, landing the tap back on its pin. Cloned-but-lying is neither. The pin itself is
kept, because it is the target <code>update</code> needs; dropping it would be the
silent move by another route.
