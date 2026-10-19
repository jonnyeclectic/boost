---
id: workflow-files
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: a workflow install overwrote the user's own slash command and uninstall deleted it; a slot move orphaned old files; edited files were deleted; Gemini kept $ARGUMENTS literal
order: 375
owner:
pr:
title: A workflow's agent files are boost's only while boost wrote them
---
<b>Installing a workflow could destroy a slash command the user wrote.</b>
If <code>~/.claude/commands/&lt;name&gt;.md</code> already held the user's own command,
<code>boost install</code> wrote over it with no warning, and the lock then recorded the
path, so <code>boost uninstall</code> deleted what was left. The install now refuses a path
the lock does not record unless it already holds the exact text boost would write, and says
<i>not written: … exists and is not managed by boost</i>. <code>--force</code> does not
override this, because <code>update</code> and <code>reinstall</code> always pass it.
<br><br>
Three related fixes. When the source moved from <code>commands/</code> to <code>agents/</code>,
the rebuilt lock dropped the old rows and left four live slash commands that no command could
remove. An update now deletes an old file it no longer writes while that file is still what
boost wrote, and keeps the row of an edited one. Uninstall now runs the sha check on an
agent's file that it already ran on the skill copy: an edited file is left in place and named.
Gemini TOML now maps Claude's <code>$ARGUMENTS</code> to <code>{{args}}</code>, following the
<code>custom-commands.md</code> shipped in Gemini CLI 0.61.0. <code>$1</code> and <code>$2</code>
have no Gemini counterpart and are left as written.
