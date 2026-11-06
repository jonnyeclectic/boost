---
id: fix-tap-name-identity
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: on a case-insensitive filesystem, untapping a case variant deleted the clone of the tap that stayed configured
order: 374
owner:
pr:
title: Tap names are case-blind, untap keeps what it does not own, and <code>--at</code> hints honestly
---
<b><code>boost tap $H/FIX</code> after <code>boost tap $H/fix</code> added a second tap that
shared the first one's clone.</b> The "already tapped" checks in <code>registry.add</code>,
<code>add_many</code> and the <code>tap</code> command compared names case-sensitively. Clone and
cache paths come from the name, so on APFS and NTFS both config rows pointed at one directory and
one cache file. <code>untap FIX</code> then deleted the clone that <code>fix</code> still used.
<code>boost outdated</code> went on to report its installed skills as "removed upstream" and told
the user to uninstall them. Every identity check now compares <code>registry.name_key</code>
(<code>str.casefold</code>) on every platform, so a config written on Linux stays valid on a Mac.
The same repository under a different case is "already tapped". For a local path that
includes two spellings of one directory: <code>Path.resolve()</code> keeps the case it is given,
so <code>registry.same_source</code> asks the filesystem (<code>os.path.samefile</code>) when the
strings differ, instead of reporting the directory as a different repository. A different repository is
refused with the name it collides with. <code>get()</code> gains a case-folded lookup tier that
runs last, so the exact spelling still wins. A config written before this change can still
hold both rows. For that case, <code>remove()</code> asks the filesystem
(<code>os.path.samefile</code>) before deleting a clone or cache that another configured tap
resolves to.

<b><code>boost untap</code> crashed with <code>KeyError: 'name'</code> when config.json held a
row without a name.</b> <code>list_taps</code> already treats such a row as no tap, but
<code>remove()</code> indexed <code>t["name"]</code> on every row. It now drops only the row it
is removing and leaves every other row as it was, malformed ones included.

<b><code>boost tap SPEC --at SHA</code> on a tapped registry told the user to run
<code>boost update</code>.</b> That command skips a pinned tap, and <code>--force</code> moves to
branch HEAD and drops the pin. Neither reaches the requested commit. The hint now names the
sequence that does: <code>boost untap NAME</code>, then <code>boost tap SPEC --at SHA</code>.
