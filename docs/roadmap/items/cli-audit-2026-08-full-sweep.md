---
id: cli-audit-2026-08-full-sweep
board: code
section: dx
status: shipped
category: CLI · Audit
complexity: L
impact: High
wow: 2
note: 81 commands, ~2,000+ invocations, 367 findings, 161 clusters, 107 cards on the board
order: 304
owner:
pr:
title: "August 2026 full-CLI audit: every one of the 81 <code>boost</code> commands exercised and verified"
---
Coverage record of the August 2026 CLI audit. All 81 commands in <code>cli.py COMMANDS</code> were exercised across 18 batches (b01&ndash;b18), each in a fresh sandbox <code>HOME</code> against 20 pinned taps / 10,152 catalog items &mdash; ~2,000+ logged invocations in total, run both piped and under a TTY, with JSON output validated, timings recorded, and results cross-checked against on-disk state (store, lock file, config, caches).

Each batch produced a findings file plus an independent non-issue verification pass that re-tested disputed calls: 310 findings and 57 disputed records, 367 in all (30 high &middot; 159 med &middot; 178 low). Deduplication folded them into 161 clusters, and every cluster then went through an adversarial two-lens verification &mdash; a live repro lens and a code-reading lens &mdash; yielding 160 confirmed, 0 not confirmed, 0 unverified; the repro verdicts across all 160 came back 158 reproduced / 2 partially. The confirmed clusters were drafted into 107 board cards (one card may carry several clusters).

Two bookkeeping notes. The one <em>known</em> cluster, <code>wrap-law-remaining-spots</code>, was folded into the existing narrow-pane item instead of a new card: its contribution is the concrete list of 13 unwrapped call sites (sync/doctor warnings, install/count panels, info tags, import/bundle warns, adapt note, chat rows, recommend rows, impact's fixed-76 fill, replay/cohort footers, rollback warns). And any cluster that fails verification is recorded in the audit artifacts (batch logs, <code>clusters.json</code>, <code>cards.json</code>, per-cluster verify files), not on the board &mdash; the board carries confirmed work only. Found by the 2026-08 CLI audit; repro commands for every finding are in the per-batch audit logs.
