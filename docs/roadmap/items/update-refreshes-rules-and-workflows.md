---
id: update-refreshes-rules-and-workflows
board: code
section: internals
status: shipped
category: Install engine · UX
complexity: S
impact: Med
wow: 2
note: update was skill-only after rule/workflow install
order: 25
owner: loop/update-all-kinds
pr: 156
title: <code>boost update</code> refreshes installed rules and workflows
---
After rule (<code>#141</code>) and workflow (<code>#150</code>) install landed,
           <code>boost update</code> still upgraded only skills — a rule or
           workflow stayed frozen at its install-time content even after its tap
           moved. Extend the update pass: for each installed rule/workflow from a
           refreshed tap, re-materialize (force reinstall) when the source
           version bumped or its file content sha changed, mirroring the skill
           upgrade loop. Rules/workflows carry no pin/quarantine flags and their
           source is a single file, so there is no risky-diff gate — re-applying
           a file drop or a <code>CLAUDE.md</code> managed block is cheap and the
           refresh is reported per item.
