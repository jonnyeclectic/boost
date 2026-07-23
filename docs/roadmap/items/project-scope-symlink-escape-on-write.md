---
id: project-scope-symlink-escape-on-write
board: code
section: trust
status: shipped
category: Security · Integrity
complexity: S
impact: High
wow: 4
note: hostile repo could write outside itself
order: 6
owner: loop/writeguard
pr: 213
title: Project scope — refuse to write through an escaping symlink
---
Workspace scope (<a href="https://github.com/jonnyeclectic/boost/pull/212">#212</a>)
           guarded the delete side — <code>uninstall --local</code> re-derives every
           recorded path and refuses one that resolves outside the repo — but not
           the <em>write</em> side. A project install builds its destination from
           agent-dir names committed in the repo
           (<code>.claude/skills</code> and its per-agent siblings), and a hostile
           clone can ship one of those as a <strong>symlink pointing outside the
           tree</strong> — at <code>~/.ssh</code>, say. Cloning that repo and
           running <code>boost install &lt;skill&gt; --local</code> then writes on the
           far side: confirmed by reproduction, a skill directory landed in a
           sibling of the repo instead of inside it. The squatter check does not
           stop it (a brand-new leaf name like <code>authorized_keys</code>
           collides with nothing, and <code>--force</code> waives it anyway).
           <code>scopes.ensure_in_base</code> is the write-side mirror of the
           delete guard: it re-derives containment through symlinks for every
           target up front, so one escaping directory aborts the whole install
           before anything is written. Covers all three project-scope kinds —
           skill, rule and workflow.
