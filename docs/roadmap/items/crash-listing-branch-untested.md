---
id: crash-listing-branch-untested
board: code
section: internals
status: shipped
category: Testing · Bug
complexity: S
impact: Low
wow: 1
note:
order: 37
owner: loop/crash-listing-tests
pr: 291
title: <code>boost log --crashes</code> listing branch has no non-empty test
---
<code>_show_crashes</code> has an empty-state branch and a listing branch that reads each
<code>crash-*.log</code>, extracts its summary line, and swallows <code>OSError</code> on an
unreadable report — only the empty-state message is exercised by any test. A regression in the glob
sort, the summary-extraction regex, or the <code>OSError</code> fallback would ship undetected. Add
a test that seeds one or more crash logs and asserts on the rendered listing.
