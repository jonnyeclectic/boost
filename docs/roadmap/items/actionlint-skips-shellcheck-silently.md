---
id: actionlint-skips-shellcheck-silently
board: code
section: dx
status: shipped
category: Testing · Bug
complexity: S
impact: Med
wow: 4
note: fixed — shellcheck is pinned in lint-tools and both gates now assert it is there
order: 69
owner: loop/lint-shellcheck
pr:
title: The second silent skip &mdash; <code>actionlint</code> runs, and checks no <code>run:</code> block at all
---
<code>make-lint-masks-actionlint-failures</code> fixed the layer everyone can see: <code>make
lint</code> discarded actionlint's exit status. There is a second layer underneath it, and the
first fix does not reach it. <b><code>actionlint</code> does not lint <code>run:</code> blocks
itself.</b> It shells out to <code>shellcheck</code>, and when shellcheck is not on
<code>PATH</code> it skips every one of them &mdash; no warning, no note, exit 0.

Same workflow file, same actionlint binary, only <code>PATH</code> differs:

<code>without shellcheck -&gt; (no output) exit=0</code><br>
<code>with shellcheck    -&gt; bad.yml:8:9: shellcheck reported issue in this script: SC2001 &hellip; exit=1</code>

So the honest description of the gate before this change was: <code>make lint</code> ran a workflow
linter that silently declined to look inside any script, and reported success. That is not
hypothetical either &mdash; it is exactly how an <code>SC2001</code> reached CI from a green local
gate, in the very change that fixed layer one.

<b>CI was not safe, only lucky.</b> Its actionlint step carried the comment "shellcheck is
preinstalled on the runner, so run: blocks are checked too" &mdash; true today, and an unpinned,
unversioned, silently revocable dependency on somebody else's base image. If GitHub ever drops it
from <code>ubuntu-latest</code>, CI degrades to the same hollow check with no signal that anything
changed. For a repository that hash-pins its entire lint toolchain precisely so an upstream release
cannot move a gate underneath it, an implicit dependency on a runner image is the same bug in a
different coat.

<b>Shipped.</b> <code>shellcheck-py==0.11.0.1</code> is declared in
<code>requirements/lint-tools.in</code> and hash-pinned into the generated
<code>lint-tools.txt</code> like every other tool, which puts it on both sides: CI installs it from
that lock, and <code>make venv</code> puts it in <code>.venv/bin</code>. <code>make lint</code> now
prepends <code>.venv/bin</code> to <code>PATH</code> so actionlint can find it, and <b>fails</b> if
it is missing rather than running a check it knows is hollow; CI asserts <code>command -v
shellcheck</code> before invoking actionlint. Verified in four states against the real recipe: the
tool absent (skip message, exit 0), shellcheck missing from the venv (exit 1 with a message naming
the fix), both present and workflows clean (exit 0), and both present with an <code>SC2001</code> in
a <code>run:</code> block (exit 1 &mdash; the case that used to pass). The old recipe on that same
file exits 0.

<b>What is deliberately still skipped.</b> If <code>actionlint</code> itself is absent,
<code>make lint</code> prints a message and continues. Closing that would mean pinning
<code>actionlint-py</code>, which is sdist-only and fetches the binary from the network at install
time, and which tracks a different actionlint version than the URL-pinned one CI uses. Trading a
pinned binary for a build-time download is a worse trade than the skip, so the skip stays and is
documented rather than quietly tolerated. The wider gap named by the earlier card is also still
open: <code>zizmor</code> and <code>gitleaks</code> run only in CI and have no Makefile equivalent.
