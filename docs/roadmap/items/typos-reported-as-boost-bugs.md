---
id: typos-reported-as-boost-bugs
board: code
section: dx
status: shipped
category: Bug
complexity: S
impact: Med
wow: 4
note: `boost create --dir` answered a mistyped path with "file it at github.com/.../issues"
order: 318
owner: fix/land-claims-fixes
pr:
title: The last command that blamed boost for the user's typo
---
Naming a bad path to <code>boost create --dir</code> produced this:

<code>Error: boost hit an unexpected error: NotADirectoryError: [Errno 20] Not a
directory</code><br>
<code>&nbsp;&nbsp;hint: a crash report was written to … or file it at
https://github.com/jonnyeclectic/boost/issues</code>

Exit 70, a crash report on disk, and an invitation to open a bug — for naming a file where a
directory was wanted, or a directory boost cannot write.

<b>boost already owned the right answer.</b> <code>boost import ./nope</code> replies
<code>Error: no such directory: ./nope</code> with a hint and exit 1;
<code>boost infer --path ./nope</code> replies <code>~/nope is not a directory</code>;
<code>infer -o</code> and <code>tap</code> were brought to the same house style earlier. This
was one command missing a house style, not a house style missing.

One test in the first draft overreached and had to be corrected rather than the code:
<code>create --dir</code> builds missing parent directories on purpose
(<code>parents=True</code>), which is useful, not a defect. The bad-input cases are a
<i>file</i> standing in the parent's place, and a parent that is not writable.
