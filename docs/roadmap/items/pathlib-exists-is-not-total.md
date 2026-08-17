---
id: pathlib-exists-is-not-total
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 4
note: the weekly fuzzer has now found two crashes in one function, three weeks apart, and been ignored both times
order: 118
owner: fix/tap-spec-name-too-long
pr: 528
title: <code>Path.exists()</code> looks total, and is not
---
<b><code>boost tap &lt;anything long enough&gt;</code> died with a raw traceback on Linux.</b>
<code>parse_spec</code> probes whether the spec names an existing directory, and
<code>pathlib</code> swallows only <b>ENOENT, ENOTDIR, EBADF and ELOOP</b> &mdash;
<b>ENAMETOOLONG is not in that set</b>. So on any filesystem with a 255-byte component limit, which
is to say ext4 and therefore every Linux runner and most users, <code>os.stat</code> raises straight
out through <code>parse_spec</code> as a bare <code>OSError</code>. Not a <code>BoostError</code>,
so the CLI's error handling never got to frame it.

<b>macOS does not reproduce it.</b> That is the whole reason it shipped: the only thing that ever saw
it was the scheduled Linux fuzz job.

<b>Which had been reporting it for three weeks.</b> <code>fuzz.yml</code> runs libFuzzer over
<code>parse_spec</code> weekly and has now failed <b>four scheduled runs out of four</b>. The first
three were one bug &mdash; an embedded NUL &mdash; found on 2026-07-25, 08-01 and 08-08 and fixed
after the third. The fourth, on 08-15, is this one, minimised to 91 bytes: <code>0x38</code>
followed by ninety <code>0xff</code>, each un-decodable and so each becoming U+FFFD, which is
<b>three</b> UTF-8 bytes apiece &mdash; <b>271 bytes</b> from an input only 91 characters long.

<b>The limit is on bytes, and on the derived name.</b> Measuring characters would have let exactly
this input through. Measuring the <em>spec</em> would have turned away a legitimate deep local path
whose basename is short, so the rule applies to the name that is about to become one directory under
<code>~/.boost/repos</code>, caught at the parse boundary rather than at clone time where it
resurfaces as git's own ENAMETOOLONG on a path the user never typed.

<b>Rejecting is only half of it.</b> A path the OS refuses to <em>look at</em> is a &ldquo;no&rdquo;,
not a crash, so the probe is now total by construction &mdash; and pinned by a test on every
platform, not only the one where it fails, because a test that needs a real over-long path proves
nothing on the machine most of this is written on.

<b>Both reproducers are now seeds.</b> The NUL one was fixed and never added to the corpus, so
the fuzzer was free to spend runs rediscovering it. <code>tests/fuzz/corpus/registry/</code> carries
both, which means the no-atheris seed smoke &mdash; the path that runs without the fuzzer installed
&mdash; is now a regression test for both.
