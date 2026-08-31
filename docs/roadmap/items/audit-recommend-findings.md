---
id: audit-recommend-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: curated picks repeat one name 6 of 8 rows; --json returns [] while text prints them
order: 286
owner:
pr:
title: "boost recommend: CLI audit findings (2026-08)"
---
<b>The curated fallback repeats one name, JSON omits it entirely, and sibling commands disagree on whose entry wins.</b> With curated taps and an unrecognised project, <code>recommend</code> prints <em>&ldquo;no stack-specific matches &mdash; curated picks instead:&rdquo;</em> followed by 8 rows carrying only 2 distinct names (python-patterns &times;6 &mdash; its es/ja/tr/zh mirrors from one tap &mdash; react-patterns &times;2): the fallback list-comps raw entries with no dedup (<code>boost_cli/commands/discovery.py:899-906</code>) while the keyword path dedups by name at <code>:876</code> and trending at <code>:1707</code>. In the same directory <code>recommend --json</code> returns <code>"recommendations": []</code> because the <code>as_json</code> branch (<code>:885-889</code>) returns before the fallback runs. And for one name shipped by several taps, trending shows the <em>last</em> tap's description (dict comprehension) where recommend keeps the <em>first</em> (<code>agg.setdefault</code>) &mdash; verified with python-patterns showing two different descriptions. Fix: dedup the curated fallback by name or content digest before slicing to <code>--limit</code>; compute the shown set (curated included) before the JSON/text split so both modes carry the same list, tagged <code>because: ["curated"]</code>; in <code>cmd_trending</code> prefer the lock's tap (or <code>catalog.find(name)[0]</code>) over last-entry-wins.

<b><code>recommend --json</code> and <code>search --json</code> dump raw catalog entries including the internal <code>search_blob</code> &mdash; ~36% of the payload.</b> Measured: 15 search items = 22,855 B with <code>search_blob</code> in all 15 (mean 401 / max 881 B per item); 8 recommend rows = 10,559 B, 36.1% blob. The codebase already classifies it as internal: <code>serve.public_row()</code> (<code>boost_cli/core/serve.py:335-337</code>) strips it with the comment &ldquo;index fuel and not display data&rdquo;. Fix: move that projection into core (<code>catalog.public_entry()</code>) and apply it in both <code>--json</code> branches (<code>discovery.py:135</code>, <code>:886</code>); keep <code>content</code>, <code>tap</code>, <code>skill_md</code>; pin with a unit test asserting no <code>search_blob</code> key.

<b>The stack line omits keywords the <code>because:</code> column then cites.</b> In the boost worktree: <code>stack: javascript, python &middot; frameworks: pytest</code> followed by <code>because: ci, python</code> &mdash; <code>ci</code> is matched at <code>discovery.py:874</code> but the line at <code>:890-892</code> only prints languages and frameworks. Fix: append the extra keywords, e.g. <code>&middot; also: ci</code>.

Found by the 2026-08 CLI audit (clusters <code>recommend-trending-provenance</code>, <code>json-internal-blob</code>, <code>recommend-stack-line</code>); repro in the audit log.
