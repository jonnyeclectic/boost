---
id: cache-writers-that-still-crash-on-a-read-only-cache
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Med
wow: 2
note: "fixed: refresh_names replaces _names.txt through atomic_write_text and warns once when it cannot write at all (heal/update/untap/tap 70 → 0 on a 444 file); reindex in a 500 cache dir prints one error naming the dir and `chmod u+w ~/.boost/cache` (70 → 1)"
order: 328
owner: loop/cache-writers
pr:
title: Two cache writers still crash on what one <code>sudo boost</code> leaves behind. A read-only <code>_names.txt</code> fails <code>heal</code>, <code>update</code> and <code>untap</code> at exit 70 while <code>doctor</code> says healthy.
---
<b>Measured</b> on <code>a316c6b</code>, a sandbox HOME with one fixture tap and <code>brainstorming</code> installed. The same results on <code>16de514</code> show this predates #889.

<b><code>_names.txt</code>.</b> <code>chmod 444 ~/.boost/cache/_names.txt</code>, which is what a root-owned file looks like to the user. Then <code>doctor</code> prints "● healthy" and exits 0, and <code>heal --dry-run</code> says "nothing to heal" at 0. But <code>heal</code>, <code>update</code>, <code>untap</code> and a repeat <code>tap</code> all exit 70 with a crash report ending at <code>complete.py:76</code> (<code>names_file().write_text</code>). <code>clean</code> keeps the file. <code>complete.refresh_names</code> writes in place, which is exactly what #889 stopped <code>rebuild_tap</code> doing. The remedy <code>doctor</code> would name for anything else, <code>heal</code>, is one of the commands that crashes.

<b><code>reindex</code> in a read-only cache directory.</b> Under <code>chmod 500 ~/.boost/cache</code>, <code>search</code>, <code>browse</code>, <code>info</code> and <code>update</code> warn and serve a fresh scan at exit 0 (#889). <code>reindex</code> exits 70 instead, with a <code>PermissionError</code> creating <code>.rag_postings.sqlite.*.tmp</code>. <code>doctor</code> does flag the directory, so nothing contradicts it here. It is still a crash where every sibling command degrades.

Likely fix: <code>refresh_names</code> writes through <code>util.atomic_write_text</code>, and it tolerates an <code>OSError</code> the way <code>rebuild_tap</code> does (the completion list is a convenience, not a catalogue). <code>reindex</code> turns a cache it cannot write into one error line naming the directory, the same remedy <code>doctor</code> and <code>heal</code> print. Found by the verifier of <code>unreadable-tap-cache-healthy-doctor-crashing-heal</code>.

<b>Shipped.</b> <code>refresh_names</code> now writes like <code>rebuild_tap</code>: replace, then the in-place write, then one warning per run. <code>rag._save</code> turns a refused write into a <code>BoostError</code> that names the directory, and offers <code>chmod</code> only for a permission error. <code>rag.ensure</code> still catches it, so search keeps degrading. <code>doctor</code> gains no <code>_names.txt</code> check. In a writable dir the next refresh replaces the file, and a read-only dir is already flagged.
