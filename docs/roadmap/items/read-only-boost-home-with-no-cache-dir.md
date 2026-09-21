---
id: read-only-boost-home-with-no-cache-dir
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Low
wow: 2
note: "fixed: paths.refuses_writes names the directory that stops a write, including the parent of a dir a refused mkdir left missing; doctor and heal create what they can and name ~/.boost (70 → 1), heal --dry-run agrees (0 → 1); journal.log creates only its own dir, so update, compact and install finish (70 → 0); an install checks the store and its target dirs before its first write and a refused lock-history snapshot is a warning, so nothing lands on disk unrecorded; a skill install skips an agent dir with a file or dangling link in the way, records the install and says to move it aside (70 → 0), and sync, doctor and heal name it too; untap names ~/.boost (70 → 1)"
order: 330
owner: loop/readonly-boost-home
pr:
title: Under a read-only <code>~/.boost</code> with no cache dir, <code>update</code>, <code>heal</code> and <code>doctor</code> crash at exit 70, and <code>heal --dry-run</code> says 0 for a run that crashes
---
<b>Measured</b> on the second release train and on <code>a316c6b</code>, where it behaves the same. Setup: tap the fixture, then <code>rm -rf ~/.boost/cache; chmod 500 ~/.boost</code>. <code>search</code>, <code>info</code> and <code>browse</code> now exit 0 (<code>cache-writers-that-still-crash-on-a-read-only-cache</code>), and <code>reindex</code> exits 1 naming <code>~/.boost</code>. But <code>update</code>, <code>heal</code> and <code>doctor</code> exit 70 with crash reports. <code>update</code> dies in <code>journal.log</code>'s <code>ensure_dirs</code>. The command whose job is to name the problem, <code>doctor</code>, is one that crashes.

<code>heal --dry-run</code> exits 0 in that state ("would rebuild catalog cache …") while <code>heal</code> exits 70. The cache-dir check heal and doctor gained in the first release train asks whether an <i>existing</i> directory refuses writes, deliberately, so that a missing one is not called unwritable. A missing cache dir under a parent that refuses the mkdir is a third case that neither branch names.

Likely fix: <code>paths.ensure_dirs</code> callers on the doctor, heal, update and journal paths tolerate a refused mkdir, like <code>rebuild_tap</code> now does. Doctor and heal then name the nearest existing directory that refuses writes, which is what <code>rag._unsaved</code> already does. The preview and the run must agree.
