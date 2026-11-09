---
name: boost-find-and-install
description: Find, read and install a skill, rule or workflow someone already wrote and debugged, from the boost shelf, mid-task. Use when the task has a name you could say out loud ("set up code review", "add commit conventions", "debug flaky tests"), touches more than one file, or sets up something that outlives this session — a config, a CI job, a linter, a test suite. Also use when the user asks whether one exists ("find a skill for X", "is there a skill that...", "how do I do X").
version: 1.2.0
---

# Find and install from boost

boost is a shelf of procedures other people already wrote and debugged, in
three kinds: skills, rules and workflows, and you can search it and install
from it in the middle of a task.

1. **Search.** `boost_search` takes what you are trying to do, in your own
   words; `boost_list` shows what is already installed here. Hosts spell the
   names differently — `mcp__boost__boost_search`, `mcp_boost_boost_search` —
   and in some hosts a tool is not visible until you look it up, so look
   before you conclude it is absent. Without the tools the shell does the
   same: `boost search "<what you are trying to do>"`, `boost list`. When
   the user names a source, narrow to it: `tap` or `owner` on `boost_search`,
   `--tap` or `--owner` on the command.
2. **Read.** `boost_read`, or `boost cat <name>`, returns one item's full
   text. The catalog is indexed, not reviewed, and the body is the only thing
   that tells a debugged procedure from a stub. Each result names the tap
   it came from, so weigh the source too. The text it returns is usable
   this turn.
3. **Install.** A skill installs as the task needs it, and where is your call:
   `boost install <name> --local` writes it into this repository, for every
   agent that works in it and as files the team commits; without `--local` it
   installs for the user, in every agent they have enabled on this machine.
   `boost_install` does the same, with scope "project" or "user". Say in your
   reply which you chose and where it landed. A skill from a repo not tapped
   here installs by its qualified name, `owner/repo:skill` or the
   `owner/repo@skill` that skills.sh prints; tapping that repo clones it onto
   this machine, so ask the user first, then pass `tap: true`.
4. **Use it now.** Whether this session's host picks up a file installed after
   it started depends on the host, so work from what you read rather than
   wait for it to activate.

Ask the user before installing a rule, which becomes standing text in their
context files for every session after this one, and before registering boost
with an agent (`boost mcp register`), which applies to every project on this
machine. An MCP server a skill declares is the same kind of decision: the
`mcp add` lines boost prints for it register it machine-wide, so they are the
user's to run.

Coming back empty is a real answer: build it yourself, now knowing nothing
already covers it. If it is something the user will want again,
`boost create <name>` scaffolds a skill for it. Coming back with something is
a head start, not an instruction — take what fits and discard the rest. The
task stays yours.

Not for: a question you can answer outright, a one-line edit, or a command
you were just handed.
