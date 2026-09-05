---
id: audit-browse-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: curses init failure = exit-70 crash + hosed terminal; piped fallback dumps 765 KB
order: 251
owner: loop/browse-curses-fallback
pr: 782
title: "boost browse: CLI audit findings (2026-08)"
---
<b>A curses init failure crashes with a report instead of falling back</b> (cluster
<code>browse-curses-fallback</code>, med). On fds that claim <code>isatty</code> but are not a pty
(IDE run consoles, <code>script</code>, <code>TERM=dumb</code>), <code>browse</code> emits raw
alternate-screen escapes (<code>[?1049h[1;40r&hellip;</code>) and then <em>&ldquo;Error: boost hit an
unexpected error: error: nocbreak() returned ERR / hint: a crash report was written to
&hellip;&rdquo;</em>, exit 70, terminal never restored. <code>discovery.py:1663-1666</code> catches
only <code>ImportError</code> for the <code>_browse_plain</code> route; the <code>_browse_tui</code>
call at <code>:1667</code> has no <code>curses.error</code> handler. Fix: wrap it in
<code>except curses.error as e: return _browse_plain(entries, 'the terminal does not support curses
(%s)' % e)</code> &mdash; <code>curses.wrapper</code> already calls <code>endwin()</code>, so the
fallback prints on a restored screen. README's browse section should mention the plain fallback.

<br><br><b>The non-TTY fallback is a 765 KB dump that misdescribes itself</b> (cluster
<code>browse-plain-dump</code>, med). <code>browse &lt; /dev/null</code> piped emits 10,157 lines:
<code>00-andruia-consultant</code> appears 3&times; (per-agent mirrors, nothing distinguishing them),
rules and workflows carry no kind marker, the curated-&#9733; column is an empty header with a
trailing <code>&#9474;</code>, and the footer says <em>&ldquo;10152 skills &middot; install with
<code>boost install &lt;name&gt;</code>&rdquo;</em> over a catalog that is skills+rules+workflows. The
TUI itself already dedupes (<code>browse.dedupe</code>, <code>discovery.py:1179</code>) and renders
kind badges (<code>:952-965</code>), so the fallback lags browse's own intended presentation. Fix in
<code>_browse_plain</code> (<code>discovery.py:926-933</code>): reuse <code>browse.dedupe</code>, add
a kind column, drop the curated column when nothing is curated, and word the footer
<em>&ldquo;N items: N skills &middot; N rules &middot; N workflows&rdquo;</em> with a hint toward
<code>boost search</code>.

<br><br>Found by the 2026-08 CLI audit (clusters <code>browse-curses-fallback</code>,
<code>browse-plain-dump</code>); repro in the audit log. Docs: <code>README.md</code> browse section
(~line 343); <code>docs/commands.html</code> regenerates only if the summary changes.
