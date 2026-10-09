---
id: scopes-contains-is-case-sensitive-on-a-case-insensitive-disk
board: code
section: trust
status: shipped
category: Core · Bug
complexity: S
impact: Low
wow: 1
note: Path.resolve keeps the caller's spelling on macOS, so /users/x and /Users/x compare as different trees
order: 370
owner: loop/scopes-case
pr: 1048
title: "<code>scopes.contains</code> calls the same directory two different trees when only the case differs"
---
<code>scopes.contains</code> compares <code>Path.resolve()</code> output with
<code>os.path.commonpath</code>. On macOS's default case-insensitive APFS, <code>resolve()</code> does
not canonicalize case. Measured: <code>Path('/users/jonny/code').resolve()</code> returns
<code>/users/jonny/code</code>, not <code>/Users/jonny/Code</code>.

Its callers include <code>mcphost.escapes_home</code> and <code>claude_settings.escaping_path</code>. So
<code>CLAUDE_CONFIG_DIR=/users/jonny/.claude</code> with <code>HOME=/Users/jonny</code> counts as escaping
home, and boost refuses an MCP registration or a hooks write into a directory that is inside home.

The error fails closed, so it is safe, but it is false. The fix has to keep failing closed. Compare
with <code>os.path.normcase</code> only where the filesystem actually folds case, or compare
<code>os.stat</code> identity (<code>st_dev</code>, <code>st_ino</code>) for paths that exist. Don't
case-fold blindly: on a case-sensitive Linux disk, <code>/home/A</code> and <code>/home/a</code> really
are different directories.

<b>Shipped.</b> Reproduced first, through a caller: with <code>&lt;tmp&gt;/Home</code> as home,
<code>mcphost.escapes_home("claude", {"CLAUDE_CONFIG_DIR": "&lt;tmp&gt;/home/.claude"}, …)</code>
returned the config path, a false escape, on this APFS disk. <code>os.path.normcase</code> was not
an option because it does nothing on posix. So <code>contains</code> keeps the string test as its
fast path. Only when that test answers "outside" does it ask each existing proper ancestor of
<code>path</code> whether it <em>is</em> <code>base</code> by <code>(st_dev, st_ino)</code>.
That answer comes from the disk, so it folds case only where the disk folds case. The same call
now returns <code>None</code>, and a real escape still returns its path. Four rules keep it fail-closed. The base is never inside itself under any
spelling. A <code>commonpath</code> <code>ValueError</code> still means outside. A base that cannot
be stat'ed, or that reports inode 0, matches nothing. A sibling, a <code>..</code> climb and a
symlink out of a case-variant base are all still refused. Every caller is covered:
<code>resolve_in_base</code>, <code>ensure_in_base</code>, <code>mcphost.escapes_home</code> and
<code>claude_settings.escaping_path</code>, which between them guard store install/uninstall,
<code>integrity</code>, <code>info</code>, <code>bmad</code>, <code>configuration</code> and
<code>pkg</code>. Tests probe the filesystem rather than <code>sys.platform</code>. The
case-sensitive direction runs for real on Linux CI and is simulated here by stat identity; the walk's True half is also simulated by stat aliasing, so it is exercised on every OS. Eight new
tests fail on the old code. <code>scopes.py</code> has 100% line and branch coverage. Not
covered here: <code>store.points_into_store</code> has the same weakness (it uses
<code>normcase</code> on posix), but it does not call <code>contains</code>.
