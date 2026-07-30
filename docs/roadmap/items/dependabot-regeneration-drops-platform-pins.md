---
id: dependabot-regeneration-drops-platform-pins
board: code
section: internals
status: shipped
category: Build · Bug
complexity: M
impact: High
wow: 3
note: every pip bump PR is unmergeable — 2 of 2 observed, both red on the install step
order: 36
owner: loop/dependabot-lock-guard
pr: 342
title: Dependabot cannot regenerate the hash-pinned locks
---
<b>Every Dependabot PR that touches <code>requirements/*.txt</code> is unmergeable</b>, and the
failure is not in the bumped package. Dependabot re-resolves the lock on Linux and writes that
resolution back, which silently <b>drops entries whose environment marker excludes them on the
resolving platform</b> — but the lock is installed with <code>--require-hashes</code> on Windows and
macOS too, so the dropped pins become install failures on the platforms that need them.

Two of two observed in one scheduled run. The hypothesis bump (<code>#300</code>/<code>#303</code>)
deleted <code>colorama==0.4.6 ; sys_platform == 'win32'</code> — pytest's Windows terminal
dependency — from <b>all three</b> of <code>test-tools</code>, <code>coverage-tools</code> and
<code>mutation-tools</code>, so <code>tests (windows-latest, 3.12)</code> and
<code>(windows-latest, 3.14)</code> both died in the <code>install test deps</code> step with the
suite never running. The twine bump (<code>#301</code>/<code>#302</code>) deleted
<code>colorama</code> and <code>pywin32-ctypes</code> (keyring's Windows backend, and keyring is
twine's own dependency) plus <code>pip</code> and <code>setuptools</code> from
<code>release-tools.txt</code>, failing the <code>metadata</code> job in <code>Install build +
validation tools</code>. The GitHub-Actions bumps in the same run were all fine: they are pure SHA
pins in workflow YAML and involve no resolution.

<code>scripts/lock_toolchain.py</code> is the source of truth precisely because it resolves for
every supported platform and keeps the conditional pins. Dependabot has no equivalent. The same run
also rewrote the provenance comments from <code>-r requirements/test-tools.in</code> to
<code>-r test-tools.in</code>, i.e. it compiled from a different working directory — the
machine-independence that <code>test_header_is_machine_independent</code> already guards.

The cheapest honest fix is to stop asking Dependabot to do this: drop the version-update side of the
pip entries (or set <code>open-pull-requests-limit: 0</code>, which leaves <b>security</b> updates
firing, since those are what the entries are actually worth) and regenerate the locks on a schedule
with <code>lock_toolchain.py</code> instead. Whatever is chosen, it needs a guard: a lock that
<i>loses</i> a platform-markered pin should fail its own gate rather than fail three Windows jobs
two steps later, because the current failure names the install step and never mentions the missing
package. Related: [[dependabot-root-pip-entry-duplicates-requirements]].
<b>Progress:</b> <code>lock_toolchain.py</code> now takes <code>-P/--upgrade-package</code>, so a
Dependabot bump can be <i>reproduced</i> rather than merged — take the version it proposes,
re-resolve that one package universally, and every other pin (markers included) stays as committed.
Both open bumps were landed that way: <code>hypothesis</code> 6.161.6 to 6.163.0 and
<code>twine</code> 6.2.0 to 7.0.0, four changed lines across five locks, with
<code>colorama</code> and <code>pywin32-ctypes</code> intact.
<b>Shipped:</b> both remaining halves. The <code>/requirements</code> entry now carries
<code>open-pull-requests-limit: 0</code>, which switches off <i>version</i> updates — the ones that
regenerate the lock — while <b>security</b> updates ignore the limit and keep firing, so the entry
still earns its place. The <code>/</code> entry is untouched; narrowing that one is
[[dependabot-root-pip-entry-duplicates-requirements]].
And the guard the card asked for exists: <code>requirements/platform-pins.lock</code> records every
marker-gated pin <b>by name and marker but not version</b>, so a routine bump leaves it untouched
and only a change in the <i>shape</i> of a resolution moves a line.
<code>lock_toolchain.py --audit</code> diffs the locks against it and <b>runs first inside
<code>--check</code></b>, before uv is invoked at all — it reads only committed files, so it also
runs in the unit suite and on a runner that could not resolve. A lost pin now fails naming the
package, the group and the marker it lost, and prints the <code>-P</code> command that reproduces
the bump properly. A <i>lost</i> pin and a <i>new</i> pin are reported differently on purpose: the
same textual drift, but one is a broken install on a platform CI never resolves on and the other is
routine — collapsing them into one "stale" message is how this stayed invisible the first time.
