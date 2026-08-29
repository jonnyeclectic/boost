# Agent hooks and the BMAD Method

Two related features: `boost hooks`, which manages agent hooks for you, and
`boost bmad`, which uses them to put the [BMAD Method](https://bmadcode.com/)'s
personas in charge of every task.

## boost hooks

`boost hooks` manages hooks in `settings.json` at either scope: `--scope
project` writes `./.claude/settings.json`, `--scope global` writes
`~/.claude/settings.json`. boost only touches hooks it created, tagged with a
`# boost:<name>` marker in the command, and snapshots the prior file before
each write.

```bash
boost hooks add SessionStart -c 'echo hello' -n greet --scope project
boost hooks list
boost hooks remove -n greet --scope project
```

### Gemini CLI

Gemini has hooks too, behind `--host gemini` (`~/.gemini/settings.json`). The
file shape is the same, but two details differ, and boost handles both:

Its `timeout` is in milliseconds where Claude's is in seconds. `--timeout 10`
means ten seconds on either host.

Most event names differ. Pass whichever vocabulary you know and boost
translates, telling you which name it wrote:

```bash
boost hooks add PreToolUse --host gemini -c 'boost check' -n guard
#   Claude's 'PreToolUse' is Gemini's 'BeforeTool' — using that
boost hooks list          # both hosts, with a host column
```

`SubagentStop` and `SubagentStart` have no Gemini counterpart, because it has no
sub-agents. boost refuses those rather than writing a hook that could never
fire.

## BMAD autopilot

`boost bmad on` is a one-time global switch. No Node, no network, one command:

```bash
boost bmad on
```

It writes seven BMAD persona subagents into `~/.claude/agents/` and installs two
hooks on every host it finds. A `SessionStart` hook briefs the session on the
roster. A `UserPromptSubmit` hook classifies each incoming prompt and prefixes
it with a short routing banner:

```text
[BMAD autopilot] track: build
Lead: `bmad-dev` subagent — Amelia, Senior Software Engineer. Ship it complete and verified.
Support: `bmad-tea` (Murat), `bmad-scribe` (Paige) — spawn them with the Agent tool…
BMAD skill: `bmad-build` — invoke it if it is installed; otherwise the persona's own playbook stands.
Done means: tests: add or update coverage under `tests/`, and run them · docs: update
`README.md` / `docs/` wherever the change shows · roadmap: create or claim the item under
`docs/roadmap/items/` · gate: `make check` green, with real output · `CLAUDE.md` is binding
Work autonomously through to a finished, verified change; stop to ask only when a choice
would change what gets delivered.
```

Nine tracks (`build`, `quality`, `docs`, `planning`, `product`, `architecture`,
`ux`, `discovery`, `review`) each name a lead persona, the support personas to
spawn alongside it, and the canonical BMAD v6 skill for that kind of work.

That last line is the point. The definition of done is read off the repository
in front of you: your test directory, your docs, your roadmap items, your gate
command. Documentation, testing and roadmap bookkeeping travel with the task
instead of being remembered afterwards.

The router costs a question nothing. Acknowledgements, slash commands, short
informational questions ("what does `scan_dir` do?") and anything containing
`no bmad` produce no banner at all. Because a `UserPromptSubmit` hook that exits
non-zero would erase your prompt, it degrades every failure to silence and
always exits 0.

```bash
boost bmad personas                            # the roster, and whether it's installed
boost bmad route "add tests for the scanner" --plain   # what would this route to?
boost bmad doctor                              # autopilot + workflow state, both scopes
boost bmad off                                 # remove the hooks and the personas
boost bmad on --scope project                  # or keep it to one repo
```

Every persona file carries an ownership stamp containing a digest of its own
contents, so the moment you edit one it stops being boost's. `boost bmad on`
reports it as kept rather than overwriting it, and `boost bmad off` leaves it
alone. Delete the file if you want the stock version back.

### Which hosts get the hooks

`boost bmad on` writes its two hooks into every host it has evidence you use,
and re-running it changes nothing that is already correct.

- **Claude always.** It is boost's primary host, and the check deliberately is
  not "is the `claude` binary on `PATH`" — `bmad on` only writes a
  settings.json, so someone running inside Claude Code whose launcher is not on
  boost's `PATH` would otherwise silently get no hooks. (`boost mcp register`
  does gate on the binary, because it shells out to `claude mcp add` and
  genuinely cannot work without it.)
- **Any other host on evidence of use** — its CLI on `PATH`, or its dotdir
  already there. Writing into `~/.gemini/settings.json` for someone who has
  never run Gemini is litter in a file boost does not own. Install that agent
  later and the next `boost bmad on` picks it up.

boost translates on the way in. `UserPromptSubmit` is written as Gemini's
`BeforeAgent`, and `--timeout 10` means ten seconds on both hosts even though
Gemini's field is milliseconds. Matchers are **not** translated — they pass
through host-native — so Claude's `startup|resume|clear` source matcher is
applied only on Claude, where that vocabulary exists.

**The personas stay Claude-only.** A subagent definition is a Claude Code
contract, and Gemini's `agents/` slot validates its input, so a Claude-dialect
persona would be rejected. What a second host gets is prompt shaping: the
routing banner arrives and names a lead persona, but Gemini cannot spawn it.

## The full BMAD method

The method itself is a separate, heavier install. `boost bmad install` delegates
to the canonical `npx bmad-method install` (needs Node.js 20.12+) for the
`bmad-*` workflow skills and the per-project `_bmad/` runtime they read on
activation:

```bash
boost bmad install --scope project   # skills + per-project _bmad/ runtime
boost bmad install --scope global    # skills into ~/.claude/skills for every session
boost bmad init                      # add the _bmad/ runtime to the current repo
boost bmad startup on|off            # just the SessionStart briefing
boost bmad disable / enable          # quarantine / restore skills (recoverable)
boost bmad uninstall                 # delete skills + _bmad/ for a scope
```

The two compose. The autopilot routes at `bmad-build`, `bmad-prd` and friends
whether or not they are installed, and says which case you are in. With the
skills present you get BMAD's full workflow; without them, the persona's own
playbook. Global installs stage the installer in a temp directory and copy only
the `bmad-*` skills, so `$HOME` never gets a stray `_bmad/`. The workflow runtime
stays per-project.
