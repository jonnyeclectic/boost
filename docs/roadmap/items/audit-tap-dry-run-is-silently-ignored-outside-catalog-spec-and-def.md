---
id: audit-tap-dry-run-is-silently-ignored-outside-catalog-spec-and-def
board: code
section: dx
status: inflight
category: Safety · Bug
complexity: S
impact: High
wow: 2
note: tap --dry-run expo/skills clones for real; --defaults --dry-run taps five registries
order: 220
owner: loop/tap-dry-run
pr:
title: "<code>tap --dry-run</code> is silently ignored outside <code>--catalog</code>: SPEC and <code>--defaults</code> clone for real"
---
On a pristine HOME, <code>boost tap --dry-run expo/skills</code> printed <code>&#10003; Tapped expo/skills (26 items)</code>, exit 0 in 1.56&nbsp;s &mdash; and the clone exists and <code>config.json</code> gained the row. <code>tap --defaults --dry-run</code> cloned five registries (<code>&#10003; tapped trailofbits/skills (124 items) &hellip;</code>) and grew the config from 21 to 26 taps. The multi-spec path is the same: <code>tap --dry-run expo/skills anthropics/skills</code> answered with <code>already tapped</code> lines, proving registry code ran. Help does say <em>&ldquo;with --catalog: print what would be tapped, tap nothing&rdquo;</em> &mdash; documented-narrow, but a flag literally named <code>--dry-run</code> that clones repos and writes config is a safety hole regardless of wording.

The source confirms the shape: <code>taps.py</code> consults <code>args.dry_run</code> only inside <code>_tap_catalog</code> (<code>boost_cli/commands/taps.py:38</code>); <code>cmd_tap</code>'s defaults, single-spec and multi-spec branches (<code>taps.py:144-166</code>) never read it. Not a duplicate of the roadmap's <em>dry-run-promised-a-link-nobody-makes</em>, which is about <code>install --dry-run</code>.

Fix, per the verified recommendation: in <code>cmd_tap</code>, when <code>args.dry_run</code> and (<code>args.spec</code> or <code>args.defaults</code>), print the parsed <code>(name, url)</code> per spec &mdash; or the <code>DEFAULT_TAPS</code> list &mdash; and return 0 <em>before</em> <code>registry.add</code>/<code>_tap_all</code>; update the <code>--dry-run</code> help text; add a unit test that <code>--dry-run SPEC</code> writes nothing. Docs: regenerate <code>docs/commands.html</code> after the help-text change.

Found by the 2026-08 CLI audit (cluster <code>tap-dry-run-ignored</code>); repro in the audit log. Verified against source 2026-08-31.
