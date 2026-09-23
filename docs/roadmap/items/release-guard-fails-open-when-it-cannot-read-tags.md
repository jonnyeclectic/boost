---
id: release-guard-fails-open-when-it-cannot-read-tags
board: code
section: planned
status: shipped
category: Release · Bug
complexity: S
impact: Medium
wow: 3
note: The one check that stops a publish reads an unreadable tag list as "no tags, go ahead" — against its own docstring…
order: 336
owner: loop/release-guard-fails-closed
pr: 955
title: The release guard fails open when it cannot read the commit's tags
---
<b>Found by the audit of the repo's own automation.</b> <code>scripts/release_guard.py</code>'s
<code>git_tags_at()</code> swallows every <code>OSError</code> and <code>CalledProcessError</code>
from <code>git tag --points-at &lt;ref&gt;</code> and returns an empty list, which
<code>decide()</code> then reads as "this commit carries no tag, so publishing is fine". Its own
docstring says the opposite: <i>an unreadable tag list must not be mistaken for "no tags, go
ahead"</i>, and promises <code>decide</code> is told separately when the lookup itself failed. It is
not.
<br><br>
<code>publish.yml</code> is a fully automated PyPI publisher — guard, then release-drafter (which
publishes a GitHub Release and its tag), then build, then Trusted Publishing upload — and this guard
is the only thing between two triggers resolving to the same <code>main</code> tip and shipping the
same version twice.
<br><br>
<b>Fix.</b> Return the failure as a distinct value (or raise), and make <code>decide</code> refuse
on it, with a test that a git invocation which exits non-zero blocks rather than clears.
