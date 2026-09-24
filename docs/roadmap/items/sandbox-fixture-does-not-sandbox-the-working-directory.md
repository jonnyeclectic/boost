---
id: sandbox-fixture-does-not-sandbox-the-working-directory
board: code
section: internals
status: planned
category: Test hygiene · Bug
complexity: M
impact: Medium
wow: 2
order: 347
owner: ""
pr: ""
title: The sandbox fixture sandboxes every env var except the one project scope reads
note: `make check` leaves a project install in the repo root; a later run reads it back and fails twelve unrelated tests.
---

`tests/conftest.py`'s `sandbox` fixture is thorough about the environment — it
redirects `HOME`, clears `BOOST_HOME`, `BOOST_AGENTS_STORE` and `CODEX_HOME`,
and sets five `BOOST_NO_*` guards so no test reaches AI, the network, the seed
or a confirm prompt by accident. It never touches the **working directory**,
and that is the one input project scope resolves against: `scopes.resolve_base`
walks up from `os.getcwd()`, so a test that installs with `scope="project"` and
no explicit `base`, or drives `boost install --local` without
`monkeypatch.chdir`, writes into the developer's own checkout.

What lands there is not a stray temp file. A project install materializes the
full agent fan-out at the repo root — `.boost/skill-lock.json`, `.claude/skills/`,
`.cursor/`, `.windsurf/`, `.gemini/`, `.codex/` — plus, for a rule, the context
files themselves: `AGENTS.md` and `CLAUDE.local.md`, both of which every agent
working the repo then loads as instructions.

It is also self-propagating, because the state outlives the run that wrote it.
A killed run left a project-scope `brainstorming` at the root; the next full
suite read it back and failed twelve tests across four files that assert an
empty install state — the `test_cli_quality.py` case for a machine that never
installed anything saw `brainstorming ok project`, and `boost list`, `boost
info` and the pane-width tests all inherited a row nothing in them had
installed. The failures name none
of the tests responsible, and they clear only when someone thinks to look at
`git status` — where `.boost/` is gitignored and does not appear.

No committed test writes there in its shipped form: `tests/unit`,
`tests/functional` and `tests/smoke.sh` each leave the checkout clean when run
directly, watched by a teardown hook that names the offending nodeid. A full
`make check` does not — it ends with `.boost/skill-lock.json` and five agent
dotdirs at the repo root, all stamped inside the mutation stage. That stage
runs those same tests against mutated `boost_cli/core`, so the blast radius of
a mutant that weakens a scope guard is the developer's own working tree, and
4,343 of them survive each run. Which is the whole argument for the guard: the
suite is one edit — or one mutant — away from writing here, and when it does,
the failures it causes name everything except their cause.

Two halves, both cheap:

- **Chdir the sandbox.** Point `cwd` at a directory under `tmp_path` in the
  fixture, so a forgotten `chdir` resolves to the sandbox instead of the repo.
  Needs an audit first — any test that reads a repo-relative path (the
  generated-file `--check` gates, `test_spdx_headers.py`) must take the repo
  root explicitly rather than inheriting it.
- **Fail loudly if it happens anyway.** A session-scoped autouse check that
  snapshots the known project-scope artifact names at the repo root and fails
  the run — naming the test — when one appears. That is the half that would
  have turned twelve misleading failures into one accurate one.
