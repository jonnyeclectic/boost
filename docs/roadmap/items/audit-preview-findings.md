---
id: audit-preview-findings
board: code
section: dx
status: planned
category: CLI · UX
complexity: S
impact: Med
wow: 1
note: piped preview strips ** with no substitute; at 60 cols 10 lines leak raw markers
order: 280
owner:
pr:
title: "<code>boost preview</code>: CLI audit findings (2026-08)"
---
<b>Preview strips markdown markers with no substitute when piped, and leaks raw <code>**</code> when a bold span straddles a wrap boundary.</b> Piped <code>preview brainstorming</code> shows 0 lines containing <code>**</code> where piped <code>cat</code> shows the raw 22 — the markers are removed and no colour replaces them, <code>---</code> prints literally, and a wrapped <code>&gt; quote</code> continuation loses its <code>&gt;</code>; neither raw Markdown nor a faithful render. On a TTY at <code>COLUMNS=60</code> the reverse bug: <b>10 lines leak literal <code>**</code></b> (0 at 120 columns) because <code>_render_markdown</code> wraps first and runs <code>_inline</code> per chunk, and <code>out.wrap</code>'s atomic-span protection (<code>output.py:369-390</code>, <code>_CODE_SPAN_RE</code>) covers only backtick spans. Fix per the verified recommendation: in <code>cmd_preview</code> (<code>boost_cli/commands/info.py:614-677</code>) emit the raw body when <code>not sys.stdout.isatty()</code>, mirroring <code>boost cat</code>; and extend the atomic-token handling in <code>out.wrap</code> to treat <code>**…**</code> like a backtick span (or apply <code>_inline</code> before wrapping with bold state carried across chunks). Regenerate <code>docs/commands.html</code>.<br><br><b>The title bar shows <code>v?</code> where <code>info</code>/<code>list</code>/<code>search</code> show 0.0.0 for the same skill.</b> Observed: <code>● ● ●  brainstorming · v? · sickn33/antigravity-awesome-skills</code> while <code>info</code> prints <code>version 0.0.0</code> — and verification found it broader than filed: <em>every</em> skill whose SKILL.md omits <code>version:</code> disagrees, installed or not, because <code>cmd_preview</code> reads raw frontmatter while <code>catalog.scan_dir</code> normalises a missing version to "0.0.0" (<code>core/catalog.py:117</code>). The same titlebar line already falls back to the lock/catalog for the <em>tap</em>; version simply missed the pattern. One-line fix at <code>info.py:673</code>: <code>meta.get("version") or (lock or cat or {}).get("version") or "?"</code>, plus a unit test asserting preview and info agree.<br><br>Found by the 2026-08 CLI audit (clusters <code>preview-markdown-render</code>, <code>preview-version-placeholder</code>); repro in the audit log.
