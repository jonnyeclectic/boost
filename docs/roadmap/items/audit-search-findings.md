---
id: audit-search-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: "CJK rows 72 cells in a 60 pane; --json drops --smart; '60 matches' is the cap, not the count"
order: 291
owner: loop/search-audit-cjk-json-footer
pr:
title: "boost search: CLI audit findings (2026-08)"
---
<b>Truncation counts code points, so CJK rows overflow the pane.</b> At <code>COLUMNS=60</code>, 14 search rows measure exactly 60 cells but <code>prompt-optimizer [skill] 分析原始提示，识别意图和…</code> measures <b>72 cells</b> (60 codepoints, East-Asian-width W/F = 2). <code>out.truncate</code> (<code>core/output.py:313-329</code>) clips with <code>len()</code> and slicing while the same module already owns <code>_char_width</code>/<code>visible_len</code> (<code>output.py:341-364</code>) — and the defect is wider than search: <code>truncate</code> also budgets columns in list/preview/browse (<code>discovery.py:202,913,1572,1590,1716,1727</code>) and <code>search_layout</code> sizes the name column with <code>len(n)</code> (<code>output.py:576-616</code>). Fix once in <code>truncate</code> — walk chars accumulating cell width, reserve the ellipsis — and size columns with <code>visible_len</code>; pin with a W-width fixture at <code>COLUMNS=60</code>.

<b><code>search --json</code> silently ignores <code>--smart</code>.</b> <code>search code review --json</code> and <code>search code review --json --smart</code> are byte-identical, with nothing on stderr either — a script cannot even detect the dropped flag. The cause is ordering: <code>cmd_search</code>'s <code>if args.as_json: print(...); return 0</code> (<code>discovery.py:134-136</code>) sits above the <code>if args.smart:</code> rerank branch (<code>discovery.py:152-159</code>). Move the rerank (and its ai-unavailable fallback warn, on stderr) above the JSON branch and add a <code>ranker</code> field to the JSON; test that <code>--json --smart</code> under <code>BOOST_NO_AI=1</code> warns on stderr with stdout still valid JSON.

<b>The 'N matches' footer reports the retrieval cap, not the match count.</b> One query, three limits: <code>--limit 1</code> → <em>"60 matches"</em>, <code>--limit 16</code> → <em>"64 matches"</em>, <code>--limit 1000</code> → <em>"2648 matches"</em> — exactly <code>max(60, limit*4)</code>, because <code>cmd_search</code> retrieves with <code>k=max(60, args.limit*4)</code> (<code>discovery.py:130</code>) and prints <code>len(scored)</code> (<code>discovery.py:181-182</code>), which <code>rag.py:903-910</code> caps at k. Word the footer from what is known: below k it is the true count; at the cap say <em>"top N of K+ retrieved"</em> (or have retrieve return the total hit count). Keep the ranker label unchanged — the eval baseline pins it. No flag changes, so <code>docs/commands.html</code> needs no regeneration.

Found by the 2026-08 CLI audit (clusters <code>cjk-cell-width</code>, <code>search-json-smart</code>, <code>search-match-count</code>); repro in the audit log.
