---
id: audit-import-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: import turns a tap install into "local" silently; a URL import records a deleted temp path
order: 271
owner:
pr:
title: "<code>boost import</code>: CLI audit findings (2026-08)"
---
<b>import loses provenance, both ways</b> <em>(med)</em>. Importing over a tap-installed skill
prints the normal four &#10003; lines and rewrites the lock to <code>tap='local',
commit=''</code> with no notice that the skill just lost its update source. And a URL import records
the temp clone as <code>source_dir</code> &mdash; <code>cmd_import</code>
(<code>pkg.py:1350-1367</code>) clones to a <code>mkdtemp</code> and <code>rmtree</code>s it in
<code>finally</code> &mdash; so <code>boost info</code> shows a dead path and
<code>boost reinstall</code> fails: <em>&ldquo;local source &hellip; is gone &mdash; skipped /
Reinstalled 0 skills&rdquo;</em>, exit 1. The URL and cloned HEAD commit are known at import time and
simply dropped. Fix: pass them into <code>store.install_from_path</code>, teach reinstall's local
branch (<code>pkg.py:1154-1162</code>) to re-clone when <code>source_dir</code> is gone but a URL is
recorded, and warn when a non-local lock entry is replaced. Regenerate <code>docs/commands.html</code>
only if the import help changes. (Cluster <code>import-provenance-loss</code>.)

<br><br><b><code>--agent</code> narrows the declaration but leaves the links</b> <em>(low)</em>.
Re-importing an installed skill with <code>--agent cursor</code> prints <em>&#10003; linked &rarr;
cursor</em> and sets <code>only_agents=['cursor']</code>, but the other three symlinks stay; the very
next <code>sync --diff</code> reports <em>&ldquo;linked outside declared scope (3)&rdquo;</em>.
Emit one warn after <code>link_agents</code> naming the out-of-scope links and the
<code>boost sync</code> remedy &mdash; pruning can stay sync's job
(<code>pkg.py:1372-1376</code>). (Cluster <code>import-agent-scope-links</code>.)

<br><br><b>The multi-skill table pre-cuts descriptions at 60 chars</b> <em>(low)</em>. At
COLUMNS=200 rows end mid-word &mdash; <em>&ldquo;implement an A/B tes&rdquo;</em> &mdash; with ~120
spare columns unused, because <code>pkg.py:1413</code> slices
<code>(e["description"] or "")[:60]</code> before <code>out.table</code> gets to fit and ellipsise
the column (<code>output.py:746-777</code>). Drop the pre-slice; one line.
(Cluster <code>import-desc-truncation</code>.)

<br><br><b>Errors print above the tables they refer to</b> <em>(low, shared with
<code>policy check</code>)</em>. <code>out.err</code> (<code>output.py:240-244</code>) writes to
stderr without flushing block-buffered stdout, so any piped capture shows <em>&ldquo;Error: multiple
skills found&rdquo;</em> before the listing it refers to. One central fix:
<code>sys.stdout.flush()</code> at the top of <code>out.err</code>/<code>warn</code>, covering
<code>cli.py:317-321</code>, <code>configuration.py:497-503</code> and every future caller. Found by
the 2026-08 CLI audit (cluster <code>stderr-stdout-ordering</code>); repro in the audit log.
