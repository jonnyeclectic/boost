<!--
Write the description as the commit message: release-drafter turns it into the
release notes, so it is read by people who never open the PR. Say what changed
and why; the diff already says how.
-->

## What and why

<!-- Replace this. If it fixes a roadmap item, link the item file:
     docs/roadmap/items/<id>.md -->

## Checks

- [ ] `make check` passes locally (lint · eval · test · smoke · mutation).
- [ ] Behaviour changes have tests. Anything under `boost_cli/core/` is
      mutation-tested, so the tests need to kill mutants, not just cover lines.
- [ ] No third-party imports added under `boost_cli/` — the runtime is
      stdlib-only.
- [ ] Layers respected: `core/` imports neither `commands/` nor `cli`.

## Generated files

Regenerate as the **last** step before opening the PR, so the artifact can't
drift from its source. `make generate` does all of them; CI runs the matching
`--check` and fails on drift.

- [ ] Touched `scripts/build_registries.py` → re-ran it
      (`boost_cli/data/registries.json` is generated).
- [ ] Added or changed a roadmap item under `docs/roadmap/items/` → re-ran
      `scripts/build_roadmap.py`. The cards and counters in `docs/roadmap.html`
      and `docs/design-roadmap.html` are **never** hand-edited.
- [ ] Added or changed a command or one of its flags → re-ran
      `scripts/build_command_reference.py` (`docs/commands.html`).
- [ ] N/A — this PR touches no generated file.

<!--
Claiming a roadmap item so parallel work doesn't collide: set `status:` and
`owner:` in that item's own file on your branch. Two branches claiming
different items touch different files and merge cleanly; two claiming the same
item conflict on purpose, and first-to-merge wins.
-->
