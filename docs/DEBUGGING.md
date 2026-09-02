# Debugging, logging & observability

boost keeps three separate channels of information, so when something goes
sideways you always have a trail to follow. This page covers where that trail
lives, how to turn up the verbosity, and the free services that watch the
project itself.

---

## The three channels

| Channel | Module | Audience | Where it goes |
|---------|--------|----------|---------------|
| **Output** | `core.output` | you, right now | pretty stdout (`✓`, tables, headings) |
| **Activity** | `core.journal` | `boost pulse` / `trending` / `who` | `~/.boost/state/pulse.jsonl` |
| **Diagnostics** | `core.logs` | you, *after* something breaks | `~/.boost/logs/boost.log` |

The **diagnostic** channel is the one you reach for when debugging. It records
what boost did and why, at `DEBUG` granularity, to a rotating log file — even on
a run that looked completely normal.

---

## The diagnostic log

Every invocation appends to a rotating log file:

```text
~/.boost/logs/boost.log        # current file (rotates at ~1 MB)
~/.boost/logs/boost.log.1      # … up to 3 older files (~4 MB ceiling total)
```

Read the tail without hunting for the path:

```bash
boost log --diagnostics          # last 20 lines of the trail
boost log --diagnostics -n 200   # last 200 lines
```

The **file always records at `DEBUG`**, regardless of console verbosity, so a
plain run still leaves a complete trail. The *console* diagnostic channel
(stderr) is **off by default** — normal runs keep stderr clean because
user-facing messages already go through the output channel.

Every invocation is bookended by two lines — an `invoke:` at the start and a
`done:` at the end that carries the **exit code and wall-clock duration** — so
the trail doubles as a lightweight timing record. A failing run logs its `done:`
line at `WARNING`, so it stands out when you scan the log:

```text
… INFO    boost: invoke: boost install brainstorming
… INFO    boost: done: boost install brainstorming -> rc=0 in 214ms
… WARNING boost: done: boost install missing -> rc=1 in 48ms
```

### Turning up console verbosity

Global flags go **before** the command name (`boost --debug install foo`); a
flag after the command name belongs to that subcommand:

| Flag / env | Effect |
|------------|--------|
| `--debug` / `BOOST_DEBUG=1` | console shows `DEBUG`; **unexpected errors re-raise the full traceback** |
| `--verbose` / `-v` | console shows `INFO` (invocations, key steps) |
| `--quiet` / `-q` | console diagnostic channel stays silent |
| `BOOST_LOG_LEVEL=DEBUG\|INFO\|WARNING\|ERROR` | explicit console level |
| config `logging.level` (default `OFF`) | persistent console level — set it once instead of passing a flag |

```bash
boost --verbose update          # see each step on stderr
boost --debug install foo       # full detail + tracebacks on crash
BOOST_LOG_LEVEL=INFO boost sync # same, via env
boost config set logging.level INFO   # make it permanent
```

### Disabling the log file

```bash
BOOST_NO_LOG=1 boost install foo      # this run writes no file
boost config set logging.file false   # permanently
```

### Structured (JSON) log lines

The trail is plain text by default. `json` emits **one JSON object per line**
carrying the same fields, so the file pipes straight into `jq` or a log
collector instead of needing a regex:

```bash
BOOST_LOG_FORMAT=json boost install foo    # this run
boost config set logging.format json       # permanently

jq -r 'select(.level=="WARNING") | .msg' ~/.boost/logs/boost.log
```

| Field | Meaning |
|-------|---------|
| `ts` | UTC timestamp, `2026-07-27T14:03:11Z` |
| `level` | `DEBUG` … `CRITICAL` |
| `logger` | always `boost` today |
| `msg` | the formatted message, arguments already interpolated |
| `exc` | the traceback — present only on records logged with an exception |

The format applies to the console channel too, so `--debug` shows the same
shape the file is recording. `boost log --diagnostics` renders JSON lines back
as text, so switching format doesn't cost you the built-in viewer, and a file
whose format changed mid-life still reads end to end. An unrecognised value
falls back to `text` rather than failing the run.

---

## Crash reports

When an **unexpected** exception escapes (not a normal `BoostError` — those
print a clean one-line message and hint), boost:

1. writes a full **crash report** to `~/.boost/logs/crash-<timestamp>.log`,
2. records the crash in the rotating trail, and
3. prints a friendly message pointing at the report — *not* a raw traceback.

A crash report bundles everything needed to reproduce or file a bug:

```text
boost crash report
==================
time:     2026-07-18T05:23:14Z
version:  1.0.3
python:   3.14.5
platform: macOS-26.5.2-arm64
command:  boost install some-skill
environment:
  BOOST_HOME=/Users/you/.boost
traceback:
  Traceback (most recent call last):
  ...
```

Only boost-relevant env vars (`BOOST_*`, `NO_COLOR`, `CLICOLOR_FORCE`) are
captured — never your whole environment. The 20 most recent reports are kept;
older ones are pruned automatically.

```bash
boost log --crashes             # list recent crash reports
cat ~/.boost/logs/crash-*.log   # read one
boost --debug install foo       # reproduce with a live traceback
```

### Filing a bug

Re-run with `--debug`, then open an issue at
<https://github.com/jonnyeclectic/boost/issues> and attach the crash report
(scan it first — it's plain text you can read and redact).

---

## Health at a glance

```bash
boost doctor      # environment health; reports the log path + any crash reports
boost health      # skill-environment dashboard
boost heal        # self-diagnose & repair
```

`boost doctor` now surfaces the diagnostic log location and notes when crash
reports are present, so a stuck environment points you at its own evidence.
That note is informational, not a fault — a crash report is history, so it
does not count toward doctor's issue tally or its exit code.

---

## `boost self-update` didn't move

`boost self-update` drives whatever installed this copy — `pipx upgrade`,
`uv tool upgrade`, or `<this python> -m pip install --upgrade`. Use
`--dry-run` to see the exact command without running it:

```bash
boost self-update --dry-run
#   installed with: pipx
#   would run: /opt/homebrew/bin/pipx upgrade boost-skill-cli --pip-args=--no-cache-dir
```

**Why the no-cache flag is there.** PyPI serves its package index with
`Cache-Control: max-age=600` and pip honours it, so two upgrades inside ten
minutes are answered from pip's HTTP cache — and a release published in between
is invisible. pip then says `Requirement already satisfied` and exits 0. Every
manager is therefore told to refresh its index (`--refresh` for uv, which has an
index-only refresh; `--no-cache-dir` for pip and pipx, which don't).

**If the version still doesn't move**, boost does not report success. It asks
PyPI what the newest release is and says which of three things happened:

| What you see | What it means |
|--------------|---------------|
| `boost v1.0.422 → v1.0.423` | upgraded |
| `already up to date (v1.0.423)` | PyPI confirms this is the newest release |
| `boost is unchanged (v…); could not reach PyPI to confirm…` | nothing moved and the check couldn't run — no claim either way |
| `pipx exited 0 but boost is still v… — PyPI has v…` | the manager declined to upgrade; the hint gives you a pinned, forced install |

That last case is usually a stale index or an environment whose Python is too
old for the new wheel. The hint names the exact command to force it, because a
plain `upgrade` has already been tried and refused.

---

## A corrupt config/settings/state file

boost keeps several small JSON files — `~/.boost/config.json`, each agent's
`settings.json` (hooks), `~/.boost/state/context.json`/`focus.json`, and a
saved `boost profile`. If one of these exists but fails to parse (a truncated
write, a hand-edited trailing comma), the read that notices prints a warning
to stderr naming the file and the JSON error, then falls back to that file's
empty/default state for the current command — the bad bytes are left on disk,
untouched, by the read itself.

**The next write to that file is what matters.** Rather than silently
building a fresh file from the empty/default view and overwriting the corrupt
one — losing whatever was in it, with no way back — boost moves the corrupt
file aside first:

- `~/.claude/settings.json` (and `~/.gemini/settings.json`) already snapshot
  the *previous* version into `~/.boost/state/claude-settings-history/` on
  every write, corrupt or not, so a corrupt file is preserved there too.
  `boost hooks add` prints that snapshot's path (`backup: ...`) whenever one
  is written, so you don't have to know the history directory exists to use
  it.
- `~/.boost/config.json` and the `context.json`/`focus.json` state files have
  no such standing history, so the write itself quarantines a corrupt file to
  `<name>.json.corrupt` (or `.corrupt.2`, `.corrupt.3`, ... if that name is
  already taken by an earlier corruption) before writing the new one, and
  says so on stderr.
- `boost profile list` marks a corrupt profile `(unreadable)` instead of
  hiding it, and `boost profile delete <name>` only checks that the file
  exists — not that it parses — so a corrupt profile can still be deleted.

None of this recovers a corrupt file's *content* automatically — it recovers
the bytes so you can look at them (`<name>.json.corrupt`, or the newest file
under `claude-settings-history/`) and hand-merge anything worth keeping.

---

## Environment variables

Everything that changes boost's runtime behaviour, in one place:

| Variable | Purpose |
|----------|---------|
| `BOOST_HOME` | override `~/.boost` (state, cache, logs, repos) |
| `BOOST_AGENTS_STORE` | override `~/.agents/skills` (the canonical store) |
| `BOOST_DEBUG` | `=1` → console `DEBUG` + tracebacks |
| `BOOST_LOG_LEVEL` | explicit console diagnostic level |
| `BOOST_LOG_FORMAT` | `text` (default) or `json` — one JSON object per log line |
| `BOOST_NO_LOG` | `=1` → don't write the diagnostic log file |
| `BOOST_NO_AI` | `=1` → disable all AI calls (offline / deterministic) |
| `BOOST_NO_NET` | `=1` → skip the PyPI version check in `self-update` (air-gapped) |
| `BOOST_ASSUME_YES` | `=1` → auto-confirm prompts (also `--yes`/`-y`) |
| `NO_COLOR` / `CLICOLOR_FORCE` | force color off / on |

Tests sandbox the whole tool by pointing `HOME`/`BOOST_HOME`/`BOOST_AGENTS_STORE`
at a throwaway directory — the same mechanism you can use to try boost without
touching your real config.

---

## Project-level monitoring (free / freemium)

boost watches *itself* using only free tiers appropriate for an open-source
CLI — no paid observability stack:

| Concern | Service (free tier) | Where to look |
|---------|--------------------|---------------|
| Build & test health | **GitHub Actions** | [`ci.yml`](../.github/workflows/ci.yml) · CI badge in the README |
| Red-main alerting | **Actions + auto-issue** | [`ci-failure-issue.yml`](../.github/workflows/ci-failure-issue.yml) opens/updates a `ci-failure` tracking issue when `ci` fails on `main` |
| Test coverage | **Actions + coverage badge** | coverage badge (endpoint JSON on the `badges` branch) |
| Mutation strength | **mutmut** in CI | `scripts/mutation_gate.py` (≥80% killed) |
| Static security | **CodeQL** | [`codeql.yml`](../.github/workflows/codeql.yml) · Security tab |
| Dependency updates | **Dependabot** | [`dependabot.yml`](../.github/dependabot.yml) |
| Release notes | **release-drafter** | drafted GitHub releases |
| Per-run summary | **Actions step summary** | the "Summary" panel of each CI run |

Each CI run publishes a **job summary** (coverage %, test/smoke counts) to the
run's Summary panel via `$GITHUB_STEP_SUMMARY` — so you can read the numbers
without opening logs. All of the above are configured in-repo and cost nothing;
adding a hosted error-tracking service (e.g. Sentry) would be the natural next
step *only if* boost ever runs as a long-lived process rather than a CLI.
