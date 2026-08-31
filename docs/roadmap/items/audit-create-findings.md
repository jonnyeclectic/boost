---
id: audit-create-findings
board: code
section: internals
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: parse(dump(meta)) != meta — evolve rewrites untouched lines, create writes broken YAML
order: 260
owner:
pr:
title: "boost create: CLI audit findings (2026-08)"
---
<b>The frontmatter dump/parse round-trip is lossy, and one asymmetric pair is the root cause:</b>
<code>frontmatter.dump</code> (<code>frontmatter.py:161-178</code>) quotes only on <code>:</code> or
surrounding whitespace and escapes <code>"</code> as <code>\"</code>, while <code>_scalar</code>
(<code>frontmatter.py:34-39</code>) strips surrounding quotes and never unescapes — so
<code>parse(dump(meta)) != meta</code>. Three verified symptoms. <em>evolve</em>'s heuristic
parse&rarr;dump rewrites lines the feedback never touched: the diff shows
<code>-description: "Use before &hellip;"</code> &rarr; <code>+description: Use before &hellip;</code>
and <code>-date_added: "2026-02-27"</code> &rarr; <code>+date_added: 2026-02-27</code> (a bare
<code>2026-02-27</code> is a YAML timestamp, not the string the author wrote), and
<code>--apply</code> writes that into the store's SKILL.md.
<br><br>
<em>create</em> with a multi-line description writes an invalid block:
<code>create multi-desc --description $'first line\nsecond line'</code> emits
<code>description: first line</code> followed by a bare <code>second line</code> inside the
<code>---</code> fences; boost's own parser then reads only <code>first line</code> and drops the
rest — exit 0, no warning. And <em>create</em>'s valid escaping is never unescaped by boost's own
reader: <code>description: "has: colon and \"quotes\" and #hash"</code> comes back from
<code>boost info</code> as <code>has: colon and \"quotes\" and #hash</code>, backslashes carried
into the catalog, lint and search text.
<br><br>
<b>Fix</b> (verified recommendation): in <code>core/frontmatter.py</code>, quote any scalar
containing <code>\n</code>, <code>#</code> or leading YAML-specials in <code>dump</code> (escaping
<code>\n</code>), unescape <code>\"</code> and <code>\\</code> in <code>_scalar</code> for
double-quoted values, and pin <code>parse(dump(meta)) == meta</code> in <code>tests/unit</code>.
For evolve (<code>intelligence.py:663</code>), splice the version line and appended section into
the original frontmatter text instead of parse+dump, so untouched lines stay byte-identical. The
shipped <em>frontmatter-scalar-over-coercion</em> item covered type coercion only — this is not a
duplicate. No flag changes, so <code>docs/commands.html</code> is untouched. Found by the 2026-08
CLI audit (cluster <code>frontmatter-roundtrip</code>); repro in the audit log.
