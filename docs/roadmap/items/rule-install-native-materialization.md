---
id: rule-install-native-materialization
board: code
section: internals
status: shipped
category: Install engine · Rules
complexity: L
impact: High
wow: 4
note: rules are indexed but never installed
order: 21
owner: loop/rule-install
pr: 141
title: Rule install — materialize rules into each agent's native format
---
Today <code>store.install</code> refuses every non-skill kind
           (<em>"rules and workflows show up in <code>boost search</code>/<code>boost taps</code>
           for now"</em>), so rules are indexed for discovery but land nowhere —
           there is no <code>boost install</code> path for a rule. Add one that
           writes each rule into the form the target agent actually reads, since
           there is no single cross-agent "rules folder": Cursor/Windsurf/Cline
           consume a rules directory (<code>.cursorrules</code> /
           <code>.windsurfrules</code> / <code>.clinerules</code> / <code>.mdc</code>),
           but <strong>Claude Code has no rules folder</strong> — its standing
           rules are <code>CLAUDE.md</code>. So installing a rule for Claude means
           merging it into <code>CLAUDE.md</code> (a managed, idempotent block),
           while for the others it means dropping the file into their rules dir.
           Needs a store/lock model for rules (uninstall must cleanly remove the
           merged block), mirroring how skills symlink into <code>enabled_agents()</code>.
