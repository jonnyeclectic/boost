---
id: fix-hooks-robustness
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: three ways a hooks command did the wrong thing to settings.json, one of them in the user-global file
order: 374
owner:
pr:
title: Padded hook names, foreign hook shapes and the project root for <code>boost hooks</code>
---
<b>A <code>--name</code> with a trailing space duplicated the hook on every re-add.</b> The name
was written raw and read back trimmed, so <code>hooks add -n 'my hook '</code> never matched its
own entry: a second add appended a copy (the hook then ran twice per event) and
<code>hooks remove -n 'my hook '</code> could not find what <code>hooks list</code> showed.
<code>claude_settings.clean_name</code> now trims the name once on the way in and refuses an
empty one, a line break (the name is a trailing shell comment, so a newline would run the rest as
a command) and the <code># boost:</code> marker itself. The removers trim too, so duplicates
already on disk go with the trimmed name.

<b>One malformed hook entry crashed <code>boost doctor</code>.</b> An inner entry that is not an
object, such as <code>{"hooks": ["echo hi"]}</code>, made doctor, <code>hooks list</code> and
<code>hooks remove</code> exit 70 with <code>AttributeError</code>, and a <code>"hooks": []</code>
key crashed <code>hooks add</code>. The readers now skip any block, event or entry of the wrong
shape and never rewrite it. <code>add</code> refuses a <code>hooks</code> key or event value of
the wrong type by name and leaves the file as it was.

<b>Project scope used the raw cwd.</b> Run from <code>proj/src/deep</code>, a project hook went
into <code>proj/src/deep/.claude/settings.json</code>, which <code>hooks list</code> at the repo
root never read. Run from <code>$HOME</code>, it went into <code>~/.claude/settings.json</code>,
the global file, while reporting "(project)", and the list then showed it twice. Project scope now
resolves through <code>scopes.resolve_base</code>, as <code>install --local</code> does. It walks
up to the repo root and refuses with "there is no project here" when <code>$HOME</code> is the
only candidate. A listing with no scope skips the project row in that case. A read of project scope with no project is empty rather than an
error, so <code>bmad doctor</code> and <code>bmad status</code>, which read it unasked, still exit 0
from <code>$HOME</code>, and <code>bmad on --scope project</code> there refuses before it writes a
persona. <code>bmad</code> puts its project personas and state at the same root as its hooks, so
<code>doctor</code> gives one answer from the root and from a subdirectory. BMAD's skills stay
where <code>npx bmad-method</code> installs them, the cwd. A project hook written into a
subdirectory before this change is no longer read: project scope now names one file per repo, as
it does for <code>install --local</code>, and reading a second location would bring back the
ambiguity this fixes.
