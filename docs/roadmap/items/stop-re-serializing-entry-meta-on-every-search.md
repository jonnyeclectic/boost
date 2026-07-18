---
id: stop-re-serializing-entry-meta-on-every-search
board: code
section: internals
status: shipped
category: Performance
complexity: S
impact: Med
wow: 2
note: 
order: 11
owner: loop/precompute-search-blob
pr: 93
title: Stop re-serializing entry meta on every search
---
<code>catalog.search</code> computes <code>json.dumps(meta).lower()</code> for <b>every entry on every query</b> just to substring-match (<code>catalog.py:222</code>). Precompute a lowercased search blob at index time, or match structured fields directly.
