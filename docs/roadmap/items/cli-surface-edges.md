---
id: cli-surface-edges
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: the tap fix for an over-long name covered one command, and four others still crashed on the same input
order: 373
owner: fix/cli-surface-edges
pr:
title: Long names, <code>--help &lt;command&gt;</code> and TAB after a global flag
---
<b>Four commands crashed on a 300-character name, and the crash happened on macOS too.</b>
<code>boost create</code>, <code>profile save</code>, <code>export -o</code> and
<code>infer -o</code> each printed <code>OSError: [Errno 63] File name too long</code>, wrote a
crash report and exited 70. The cause is the same one
<a href="#pathlib-exists-is-not-total">pathlib-exists-is-not-total</a> fixed for <code>tap</code>:
<code>Path.exists()</code> raises ENAMETOOLONG instead of returning False. That fix covered only
<code>parse_spec</code>. <code>util.check_path_length</code> now rejects any path component over
<b>255 bytes</b> as a framed <code>BoostError</code> (exit 1) before the first stat.
<code>resolve_slug</code> applies the same limit to every user-typed slug. The check is pure string
work, so it gives the same answer on every OS. <code>profile save</code> checks the whole
<code>&lt;slug&gt;.json</code> file name, not the slug alone, because a 252-byte slug is legal until
the suffix pushes the name past the limit.

<b><code>boost --help install</code> printed the 81-command index and silently dropped
<code>install</code>.</b> <code>-h</code>/<code>--help</code> followed by a command now behaves like
<code>boost help &lt;command&gt;</code>, which is how git and brew handle it.

<b>TAB completion went silent after a leading global flag.</b> <code>boost --debug ins&lt;TAB&gt;</code>
treated <code>--debug</code> as the command name. Completion now strips the same leading flags
<code>cli.main</code> strips (passed in as data, because <code>core</code> cannot import
<code>cli</code>), and it never strips the word being typed. <code>boost help &lt;TAB&gt;</code>
now offers command names, since the usage line advertises <code>boost help &lt;command&gt;</code>.
