---
id: audit-catalog-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: --show says "22 taps" then tables exactly 20; --export ships sender-machine paths as URLs
order: 253
owner: loop/catalog-bundle-audit-fixes
pr: 652
title: "boost catalog: CLI audit findings (2026-08)"
---
<b><code>catalog --show</code> silently truncates the tap table at 20 rows</b> (cluster
<code>catalog-show-row-cap</code>, med). Reproduced offline with 22 taps: the heading says
<em>&ldquo;built &hellip; &middot; 22 taps &middot; 10,162 entries&rdquo;</em>, then a
TAP/ENTRIES/COMMIT table of exactly 20 rows and nothing after &mdash;
<code>boost_cli/commands/taps.py:392</code> slices <code>(manifest.get("taps") or [])[:20]</code>
with no remainder line, so the heading's own count contradicts the table. <code>--json</code>
already carries all rows. Fix: when <code>len(taps) &gt; 20</code> print
<code>out.dim("&hellip; and %d more (use --json for the full list)")</code>, or drop the cap &mdash;
<code>--show</code> is explicit and bundles are usually small.

<br><br><b><code>catalog --export</code> packs local-directory taps with sender-machine paths as
URLs</b> (cluster <code>export-local-tap-urls</code>, low). After tapping a local directory, the
bundle's manifest row carries <code>url: /private/tmp/&hellip;/minio-copy</code>; the receiver imports
it with no warning, and once the sender path is gone, <code>boost update minio-copy</code> fails with
<em>&ldquo;git clone failed: fatal: repository '/private/tmp/&hellip;' does not exist&rdquo;</em>
&mdash; leaking the sender's directory layout. <code>catalogbundle.py</code>'s own docstring
(<code>:24-27</code>) says the URL exists &ldquo;precisely so the receiving machine can clone&rdquo;,
so this breaks the module's stated contract. The imported catalogue itself still searches fine, which
is why the verified fix flags rather than skips: mark scheme-less URLs <code>local: true</code> in
<code>export_bundle</code> and have <code>import_bundle</code> warn that N taps point at directories
on the exporting machine. <code>README.md</code>'s bundle section (lines ~229-247) should note the
limitation.

<br><br>Found by the 2026-08 CLI audit (clusters <code>catalog-show-row-cap</code>,
<code>export-local-tap-urls</code>); repro in the audit log. No <code>docs/commands.html</code>
regeneration unless the summary changes.
