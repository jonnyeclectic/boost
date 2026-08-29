---
id: cli-command-audit
board: code
section: shipped
status: shipped
category: Quality · CLI
complexity: M
impact: Med
wow: 3
note: audited all 80 COMMANDS entries against a disposable HOME; 4 real defects fixed with tests
order: 128
owner: loop/verify
pr:
title: All 80 <code>boost</code> commands audited against a disposable HOME &mdash; four defects fixed
---
Every command in <code>boost_cli/cli.py</code>'s <code>COMMANDS</code> table (not memory of
what the CLI does) was exercised for real: <code>--help</code> against its actual
<code>argparse</code> definition, the happy path against its one-line summary and
<code>docs/commands.html</code>, exit codes on success/error/empty-store/nonexistent-name,
and &mdash; for anything that mutates state &mdash; the real lock file, symlinks and cache on
disk, not just stdout. Four parallel audits split the ~80 commands by
<code>COMMANDS</code>'s own groups (pkg+find, info+tap+ai, quality/safety, cfg+team) so
every command got adversarial testing (tampered store content, corrupted lock JSON,
deleted store dirs, real signed/tampered minisign manifests) rather than a clean-state
smoke pass.

The known failure modes this codebase has shipped before were hunted deliberately: a
command reporting success without doing the thing, a raw read that misses a tap's sparse
checkout, <code>Path.resolve(strict=True)</code>'s <code>RuntimeError</code>/<code>OSError</code>
split between Python 3.12 and 3.13+, and a dry-run that silently no-ops or over-reports.
<code>boost trust add</code> &mdash; the one command with a documented history of exactly the
first failure mode (a merged autofix once deleted its fingerprint line) &mdash; was
re-verified against real Ed25519 signatures and tampering and held up.

Four real defects, each fixed with a failing-then-passing test. <code>boost conflict</code>
and <code>boost audit --skills</code> kept reporting a MED conflict finding against a skill
after it was quarantined &mdash; quarantine's own documented purpose ("isolate a problematic
skill") gave no relief from the one command whose entire job is to report that condition;
both now exclude quarantined skills from conflict pairing. <code>boost catalog
--import</code> tells the receiver "<code>boost install</code> clones just the one registry
it needs", but <code>install</code> performed no lazy clone &mdash; the one end-to-end path the
command advertises (import &rarr; search &rarr; install) failed with a misleading "source
vanished from tap" error; <code>store.source_dir_for</code> now clones a
registered-but-uncloned tap on demand, the single choke point every consumer of tap content
already goes through. <code>boost onboard</code>'s own docstring promises a byte-for-byte
no-op on an unchanged re-run, but <code>.boost/telemetry.json</code> stamped a fresh
timestamp on every invocation, so the comparison could only pass by wall-clock luck &mdash; a
scripted <code>boost onboard --pr</code> on an already-onboarded repo would open a PR
containing only a timestamp bump, forever; it now preserves the existing file's
<code>created</code> field. <code>boost heal --dry-run</code> double-reported the same
broken symlink under two different messages ("would remove broken link" and "would remove
stale link") because the real run unlinks before computing <code>sync_plan()</code> while
dry-run never unlinks anything &mdash; a preview overstating what running <code>heal</code> for
real actually does.

A fifth, latent-only finding was fixed alongside them: <code>quality.py</code>'s
<code>_resolve_as_far_as_it_exists</code> caught only <code>OSError</code> around a
non-strict <code>Path.resolve()</code>, the same symlink-loop gap
<code>store.resolves_into_store</code> had already been fixed for. Verified empirically
(not just read) on both interpreters: <code>Path.resolve(strict=False)</code> on a
symlink-loop path returns silently on 3.14 and raises <code>RuntimeError</code> on 3.12 &mdash;
confirmed with a live symlink cycle on both, and the full affected test suite reran green
on a real Python 3.12 venv.

Two findings were investigated and deliberately left alone after checking the existing
test suite rather than trusting the audit's framing: <code>boost drift</code> always
exiting 0 is pinned as intentional by <code>tests/functional/test_cli_quality.py</code>'s
own comment ("rc stays 0: drift only reports"), and <code>boost who</code>'s aggregate view
counting every journal subject (not just install/edit/evolve/distill/tag actions) toward
"skill expertise" is pinned the same way by an existing test asserting a tap name in the
skills set. Flipping either would contradict a deliberately written existing test, not fix
an oversight.
