---
id: broken-link-and-anchor-checking-lychee
board: code
section: docsite
status: shipped
category: Quality · Docs
complexity: S
impact: Med
wow: 3
note: 8 dead links found
order: 5
owner: loop/lychee
pr: 210
title: Broken-link &amp; anchor checking — <code>lychee</code>
---
Fast, free link checker over the README and <code>docs/*.html</code>:
           verifies external URLs (GitHub, PyPI), asset paths
           (<code>../style/boost.css</code>) and in-page anchors
           (<code>#next</code>, <code>#health</code>) still resolve. A dead link in
           the landing page is the first broken promise a visitor sees. Red on
           its first run: eight were already broken — four <code>../adapters.html</code>
           at the wrong depth, two dangling anchors, one link to an item file as
           though it were a page, and a README pointing at
           <code>docs/overview.html</code>, renamed to <code>index.html</code>
           and never updated.
