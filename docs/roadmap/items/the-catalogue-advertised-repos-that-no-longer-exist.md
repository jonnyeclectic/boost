---
id: the-catalogue-advertised-repos-that-no-longer-exist
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: a scheduled gate had never once passed, and the reason was one deleted upstream in its pinned corpus
order: 117
owner: fix/retire-dead-registries
pr: 527
title: a convention that said "verify the repo is real" verified nothing
---
<b>The <code>eval-scale</code> workflow has run once and failed once.</b> Not a retrieval
regression &mdash; the gate refused to score, correctly, because it could not materialise its
corpus: <code>pcliangx/AppGenesisForge</code> returns 404, so the clone falls through to
<code>could not read Username for 'https://github.com'</code> and the whole 183-repo corpus is
unavailable. The gate exits 75 rather than scoring the 182 that <em>are</em> reachable, and it is
right to: measured, dropping the largest repo alone moves recall@10 from 0.852 to 0.885 and hit@1
from 0.473 to 0.593, so a partial corpus clears the floors <em>more</em> easily than the real one.

<b>The dead repo was not only in the corpus &mdash; it was in the shipped catalogue.</b> Auditing all
<b>470</b> registries in <code>registries.json</code> against GitHub found <b>two</b> that no longer
exist. The other one, <code>MikroJit-Technologies/claude-skills</code>, is already famous here: it is
the tap that broke <code>boost update</code> for every other tap on the maintainer's machine. That
bug was fixed by making the update loop survive a dead tap &mdash; and the catalogue went on
recommending the repo to everyone else.

<b>Deleting the rows is not the fix.</b> The catalogue is assembled from research batches, and a
batch written before a repo vanished still names it, so the next sweep re-adds it from the same
stale source. <code>RETIRED</code> is the record that survives the sweep: name plus the reason, with
a test that fails if any of them reappears in a source tuple, in <code>LIST_ONLY</code>, or in the
generated payload.

<b>And the convention that should have caught this is now runnable.</b> CLAUDE.md has said
&ldquo;verify a repo is real before adding it&rdquo; for a long time; six stale rows are what a
convention with no command behind it is worth. <code>build_registries.py --verify-live</code> asks
GitHub about every shipped registry and prints what it finds. It is deliberately <em>not</em> a gate:
a required check over 470 third-party repos goes red the day any one of them is deleted, which is a
fact about GitHub and not about the commit under test &mdash; the same reasoning that pins every row
of <code>taps.txt</code> to a SHA.

<b>Archived is not gone.</b> Four registries are archived upstream and stay: they still clone and
still ship their items, and frozen is a different thing from deleted. The audit reports them
separately for the same reason.
