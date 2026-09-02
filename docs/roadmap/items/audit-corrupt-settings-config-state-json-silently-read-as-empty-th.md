---
id: audit-corrupt-settings-config-state-json-silently-read-as-empty-th
board: code
section: dx
status: shipped
category: Safety · Bug
complexity: M
impact: High
wow: 2
note: a trailing comma in settings.json costs the permissions/model block on the next hooks add
order: 203
owner: loop/corrupt-json-state
pr: 714
title: "Corrupt settings/config/state JSON silently read as empty, then clobbered on the next write"
---
One shared load pattern across four surfaces: a JSON file that exists but does not parse is read as <code>{}</code> (<code>except (JSONDecodeError, OSError)</code> at <code>boost_cli/core/claude_settings.py:74-75</code> and <code>boost_cli/core/config.py:129</code>/<code>196-203</code>/<code>246-250</code>), and the next write replaces it. Verified worst case: with a trailing comma in <code>~/.claude/settings.json</code>, <code>hooks add SessionStart &hellip;</code> prints <em>&ldquo;&#10003; added SessionStart hook&rdquo;</em> exit 0 and the file afterwards holds <em>only</em> <code>{"hooks": &hellip;}</code> &mdash; the user's <code>permissions</code> and <code>model</code> keys are gone, no warning. With a corrupt <code>~/.boost/config.json</code>, <code>config list</code> silently prints the defaults, and <code>config set ai.enabled true</code> rewrites the file to defaults-plus-that-key &mdash; a 20-tap list unrecoverable, <b>no backup</b>. <code>context status</code>/<code>context map</code> and <code>focus --status</code> do the same to <code>state/context.json</code>/<code>focus.json</code>; a corrupt profile is invisible to <code>profile list</code> yet <code>profile delete broken</code> <em>refuses</em> with exit 1, because the existence check parses the file before deleting.

Verification narrowed the hooks half: <code>claude_settings.save</code> already snapshots the prior file into <code>~/.boost/state/claude-settings-history/</code> before every write (confirmed byte-for-byte), so that path is recoverable &mdash; but silently, and nothing tells the user. <code>config.json</code> has no such net: that loss is real. Degrading a corrupt file to defaults on <em>read</em> is arguably deliberate (the <code>config.py</code> comment says so); silently <em>overwriting</em> it on the next write is documented nowhere and destroys user data. The roadmap's atomic-lock-file-writes item covers the lock file only &mdash; related pattern, not a duplicate.

Fix centrally, per the verified recommendation: when a JSON state file exists but fails to parse, warn on read naming the file and the JSON error, and before any save either refuse with a BoostError and a fix-it hint or move the bad file to <code>&lt;name&gt;.corrupt</code> and say so. <code>hooks add</code> should print the claude-settings-history snapshot path it already writes; <code>profile delete</code> should check <code>_profile_path(name).exists()</code> instead of parsing; <code>profile list</code> should show an <em>(unreadable)</em> marker. Docs: note the corrupt-file behaviour in <code>docs/DEBUGGING.md</code> (config/logging section).

Found by the 2026-08 CLI audit (cluster <code>corrupt-json-clobbered</code>); repro in the audit log. Verified 2026-08-31: all four surfaces reproduced.

<b>2026-09-02, PR open.</b> New <code>core/jsonstate.py</code> (<code>read_object</code>/<code>is_corrupt</code>/<code>quarantine</code>) centralizes the read-vs-corrupt distinction; <code>config.py</code>, <code>claude_settings.py</code> and <code>commands/intelligence.py</code>'s <code>_load_state</code>/<code>_save_state</code> (context/focus) all warn on a corrupt read and quarantine to <code>&lt;name&gt;.corrupt</code> (or reuse the existing history snapshot, for hooks) before the next write. <code>hooks add</code> prints the snapshot path; <code>profile delete</code> checks existence instead of parsing; <code>profile list</code> marks a corrupt profile <em>(unreadable)</em>. <code>docs/DEBUGGING.md</code> has a new section. All four surfaces from the audit are covered. Held <code>inflight</code> at PR-open time because this session's sandbox has no PyPI egress, so the mutation/lint toolchain (mutmut, vulture, xenon, interrogate, refurb, codespell, actionlint, zizmor) could not be installed to run <code>make check</code> locally &mdash; ruff, mypy, pyright and pytest (unit+functional, no coverage) were run directly against the changed files and passed clean.

<b>Shipped.</b> PR #714's branch was briefly behind <code>main</code> (a train of 8 other PRs landed while CI ran); merged <code>main</code> in, re-verified locally, and CI ran clean end to end on the merged head: <code>lint</code>, <code>check</code>, the full OS&times;Python test matrix, <code>evals</code>, all six <code>mutation-shard</code> jobs plus the <code>mutation</code> gate, <code>smoke</code>/<code>install-smoke</code>, <code>dco</code>, <code>vale</code>, <code>lighthouse</code>, CodeQL and the security scanners &mdash; 41/41 checks green, no merge conflict.
