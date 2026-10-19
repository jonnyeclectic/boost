---
id: tap-spec-names-the-wrong-repo
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Medium
wow: 2
note: Three ways `boost tap` answered for a different repo than the one asked for — a same-basename repo "already tapped", file:// cloned from GitHub, an empty repo tapped as 0 items…
order: 373
owner: fix/tap-spec-identity
pr:
title: "boost tap answers for a different repo than the one it was given"
---
<b>Three defects, one shape: the spec named one repository and boost acted on another.</b>
<b>Same basename, different repo.</b> With <code>~/a/fixture-tap</code> tapped,
<code>boost tap ~/b/fixture-tap</code> printed <em>fixture-tap already tapped</em> and exited 0
having tapped nothing — the check compared names only, and a name is just the last path parts
(a GitHub and a GitLab <code>owner/repo</code> collide the same way). Now
<code>registry.same_source</code> compares the URLs: a different repo under a taken name is a
<code>BoostError</code> naming the URL that holds it (exit 1, and a per-spec failure in a
multi-spec or catalogue tap; two specs of one run that claim a name are reported as
<em>two specs in this batch both name X</em>), while re-tapping the same repo by another spelling
(<code>owner/repo</code>, <code>….git</code>, <code>git@host:owner/repo</code>, userinfo) stays the muted
skip. Hosts compare case-blind, paths only on github.com, so a self-hosted
<code>Team/Repo</code> or a local <code>/srv/A</code> is not its lowercase twin. &middot;
<b>Any <code>scheme://</code> is a URL.</b> <code>file://…/fixture-tap</code> and
<code>git://example.com/x/y.git</code> were rewritten to <code>https://github.com/file:///…</code>, and
<code>.replace(".git", "")</code> named <code>foo/my.github.io</code> as <code>foo/myhub.io</code>. Both are
cloned as given now, with only a trailing <code>.git</code> dropped from the name; a live
<code>boost tap file://…</code> taps 5 items in a sandbox. A <code>file://</code> URL of a directory on
this machine is that directory — same name, same resolved path — so
<code>boost tap &lt;dir&gt;</code> then <code>boost tap file://&lt;dir&gt;</code> is the already-tapped skip,
not a second tap of one repo. Unsafe transports are still refused by
<code>gitutil.clone_shallow</code>. &middot;
<b>A repo with no commits.</b> A freshly <code>git init</code>ed directory tapped as
<em>0 items</em> over skills sitting uncommitted, and <code>boost update</code> then died on git's
<em>ambiguous argument 'FETCH_HEAD'</em>. <code>clone_shallow</code> now removes an empty clone
and says <em>has no commits — commit your skills first</em>; <code>gitutil.pull</code> says the
same for an upstream that is still empty, and names a first commit as
<code>(no commits) → abc1234</code> rather than <code> → abc1234</code>. &middot;
Pinned by <code>tests/unit/test_tap_spec_identity.py</code>.
