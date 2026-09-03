---
id: audit-out-table-clips-data-columns-to-an-assumed-80-columns-when-s
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: boost list | grep NAME matches nothing — piped tables clip to an assumed 80 columns
order: 239
owner: loop/table-pipe-clip
pr:
title: "<code>out.table</code> clips data columns to an assumed 80 columns when stdout is a pipe; narrow TTYs clip IDs/hashes"
---
One root cause, twelve findings across ten commands: <code>out.table</code> always fits rows
through <code>_fit_widths(term_width())</code>, and <code>term_width()</code> answers 80 when
stdout is detached &mdash; so a pipe, where there is no pane to fit, gets data columns ellipsised.
Piped <code>list</code>: <em>&ldquo;test-driven-develop&hellip;&nbsp; 0.0.0&nbsp;&nbsp;
NeoLabHQ/context-en&hellip;&nbsp; claude&middot;windsurf&middot;cur&hellip;&rdquo;</em>; piped
<code>taps</code>: <em>&ldquo;NeoLabHQ/context-engineering&hellip;&nbsp; 92&nbsp;
@555b952&nbsp; https://github.com/NeoLabHQ/&hellip;&rdquo;</em> &mdash; so
<code>boost list | grep test-driven-development</code> matches nothing, and the clipped NAME is
exactly the identifier <code>untap</code>/<code>update</code> need. With <code>COLUMNS=200</code>
the same pipes print full names. The same mechanism clips <code>fingerprint --verbose</code>
sha256s to 38 chars, <code>drift</code>'s remedy hint
(<em>&ldquo;boost reinstall brainstorming to discard loc&hellip;&rdquo;</em>),
<code>trust verify</code>'s only explanation of an invalid status, <code>attest</code> names,
<code>hooks list</code> commands and <code>discover</code> URLs.

Narrow TTYs hit the second half: at <code>COLUMNS=60</code>, <code>snapshot list</code> renders
every ID as the identical stub <em>&ldquo;snap-20260831-&hellip;&rdquo;</em> &mdash; and the id is
the only argument <code>snapshot restore</code> accepts &mdash; while <code>taps</code> spends
half the pane on identical <em>&ldquo;https://github.c&hellip;&rdquo;</em> cells and clips NAME.
This contradicts both the CLAUDE.md rule that only chrome may be wrapped and
<code>out.table</code>'s own docstring (&ldquo;scripts that parse table output never see the
ornament&rdquo;). The shipped width-aware-table items covered TTY fitting, not pipe clipping.
Scope is broader than one call site: 11 of 12 findings share
<code>out.table&rarr;_fit_widths</code> with no isatty gate
(<code>output.py:308-310</code>, <code>726-743</code>, <code>773</code>), and piped
<code>boost --help</code> is a second emit site &mdash; <code>cli.py:169,199-209</code> uses
<code>out.truncate</code>/<code>term_width</code> directly, truncating command summaries in
<code>--help | grep</code> too.

Verified fix: in <code>out.table</code> skip <code>_fit_widths</code> when stdout is not a TTY and
<code>COLUMNS</code> is unset &middot; add a per-column no-clip marker for data columns (snapshot
ID, digests, hook commands) so narrow TTYs shrink chrome (WHO/WHEN/URL) first &middot; give
<code>cli.print_help</code> its own not-a-TTY branch emitting full summaries &middot; unit-test a
60-column render asserting full IDs survive. Found by the 2026-08 CLI audit (cluster
<code>tables-clip-data-columns</code>); repro in the audit log.
