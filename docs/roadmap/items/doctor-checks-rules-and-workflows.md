---
id: doctor-checks-rules-and-workflows
board: code
section: health
status: inflight
category: Diagnostics · Install engine
complexity: S
impact: Med
wow: 2
note: doctor was skill-only after rule/workflow install
order: 24
owner: loop/doctor-all-kinds
pr:
title: <code>boost doctor</code> checks installed rules and workflows
---
After rule (<code>#141</code>) and workflow (<code>#150</code>) install landed,
           <code>boost doctor</code>'s health loop still only walked the lock
           file's <code>skills</code> — so a rule or workflow whose materialized
           file a user deleted (or whose <code>CLAUDE.md</code> managed block was
           hand-removed) went undetected. Extend the doctor loop to verify every
           recorded rule/workflow materialization is still on disk: a file drop
           must exist, and a Claude rule's <code>CLAUDE.md</code> must still carry
           its managed block. A missing materialization is flagged with a
           <code>boost reinstall</code> hint and flips the verdict, matching how
           skill-drift is surfaced.
