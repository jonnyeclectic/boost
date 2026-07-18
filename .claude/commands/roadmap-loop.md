---
description: Claim, implement, and ship one data-driven roadmap item (safe for parallel /loop sessions)
argument-hint: "[optional: item id or board to focus on]"
---

You are one of several parallel sessions improving the `boost` repo by working its
data-driven roadmap. Each run: claim ONE unclaimed item, implement it, ship it.
Coordinate ONLY through item files so parallel loops never collide.
$ARGUMENTS

## Setup
- Work in your OWN git worktree off `origin/main` — never `~/boost` or another loop's
  tree. Run `git worktree list` + `git status` first; a dirty tree is owned, use
  another. A fresh worktree needs its own venv:
  ```
  python3 -m venv .venv && .venv/bin/pip install -e . \
    && .venv/bin/pip install pytest pytest-cov coverage mutmut ruff mypy
  ```
- `git fetch origin main`.

## Pick & claim (the anti-collision protocol — before any work)
- Read `docs/roadmap/items/*.md`. Pick ONE item that is `status: planned` or `next`,
  `owner:` empty, well-scoped, high-impact, and NOT already covered by an open PR
  (`gh pr list`). Prefer `board: code` items you can implement with tests. If the user
  named an item/board above, honor it.
- `git checkout -B loop/<short-topic> origin/main`.
- In THAT item's file set `status: inflight` and `owner: loop/<short-topic>`, run
  `python3 scripts/build_roadmap.py`, commit, push, and open a **draft PR** named for
  the item. That publishes your claim (shows as "In flight" on the live dashboard).
- If another loop already claimed it, your item-file edit conflicts on merge — the
  intended "already claimed" signal. Drop it and pick another.

## Implement
- Do the work the card describes, following `CLAUDE.md`: stdlib-only runtime; new or
  changed `boost_cli/core` logic needs tests that COVER and KILL mutants; keep changes
  file-scoped and additive.
- NEVER hand-edit `docs/roadmap.html` / `docs/design-roadmap.html`. Only edit item
  files and regenerate — CI `build_roadmap.py --check` fails on any hand-edit.

## Finish the item
- Set the item's `status: shipped` and `pr: <#>`. Regenerate LAST:
  `python3 scripts/build_roadmap.py` (and `python3 scripts/build_registries.py` if you
  touched registries). Commit the item file + regenerated output.

## Gate & ship
- `make check` must pass (lint + tests ≥80% cov + smoke + mutation ≥80%).
- Mark the PR ready. Branch rules require checks + up-to-date, so if behind:
  `git fetch origin main && git rebase origin/main`, re-run `--check`, push.
- Merge with `gh pr merge <#> --squash` once ALL checks are green — never onto a red
  release. After merging, confirm the `release` workflow goes green.

## Then iterate: pick the next unclaimed item.

## Rules
- One item per branch/PR. Every merge to `main` cuts a PyPI release — land one coherent
  change per PR.
- Don't run a second "scan and rewrite the whole roadmap" loop. Add a net-new item (a
  new `docs/roadmap/items/<id>.md`) only if you find something genuinely untracked.
- Keep any sub-agent fan-out small (2–4). If blocked or uncertain on an item, un-claim
  it (clear `owner`, set `status` back to `planned`, regenerate) and pick another.
