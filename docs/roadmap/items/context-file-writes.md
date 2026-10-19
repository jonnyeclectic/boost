---
id: context-file-writes
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: installing a rule replaced a symlinked CLAUDE.md or GEMINI.md with a private copy, and uninstall left the copy behind
order: 374
owner:
pr:
title: A rule writes through a symlinked context file and keeps its mode
---
<b>Installing a rule broke a symlinked context file, and uninstalling it did not repair the damage.</b>
Rule install, uninstall, quarantine and release wrote <code>CLAUDE.md</code>, <code>GEMINI.md</code>
and <code>AGENTS.md</code> with <code>util.atomic_write_text</code>. That writer is meant for
boost's own files: it writes a <code>mkstemp</code> temp file, which is always 0600, then calls
<code>os.replace</code> on the path. A <code>~/.claude/CLAUDE.md</code> that linked into a
dotfiles checkout became a detached regular 0600 file. The rule never reached the file the user
edits, and the link was still gone after uninstall. In a repo where <code>GEMINI.md</code> links
to <code>AGENTS.md</code>, git showed a typechange on <code>GEMINI.md</code>, and a 0644
<code>AGENTS.md</code> became private.

<b>A new writer for those files, <code>util.write_user_file</code>.</b> It follows a symlink
through every hop and writes the target, so the link stays a link. It keeps the target's
existing permission bits, and a new file gets <code>0o666 &amp; ~umask</code>. At project scope
it runs <code>scopes.ensure_in_base</code> on the <i>resolved</i> target, so boost refuses to
write through a committed link that points outside the repo. A linked file that held only
boost's block is emptied, not unlinked. Uninstall now de-duplicates on the resolved file, so
<code>GEMINI.md -&gt; AGENTS.md</code> counts as one file. <code>atomic_write_text</code> is
unchanged, because the lock and config files depend on its private, replace-the-path behaviour.

<b>A link out of the repo is refused before the first change, not part-way through.</b> The
containment check first ran inside the write, so it fired mid-loop. A project uninstall whose
<code>GEMINI.md</code> had been re-pointed outside the repo deleted <code>CLAUDE.local.md</code>
and the Cursor and Windsurf rule files, then raised at <code>GEMINI.md</code>, leaving
<code>AGENTS.md</code> holding the block and the lock row in place. Quarantine and release had
the same mid-loop refusal. The new <code>util.user_file_target</code> resolves and checks a path
without writing it. Uninstall, quarantine and release now call it on every file they will
write through, before they change any file or persist the quarantine stash.
