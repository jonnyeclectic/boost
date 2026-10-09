---
id: scopes-contains-is-case-sensitive-on-a-case-insensitive-disk
board: code
section: trust
status: planned
category: Core · Bug
complexity: S
impact: Low
wow: 1
note: Path.resolve keeps the caller's spelling on macOS, so /users/x and /Users/x compare as different trees
order: 370
owner:
pr:
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
