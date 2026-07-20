---
id: workflow-install-native-materialization
board: code
section: internals
status: inflight
category: Install engine · Workflows
complexity: M
impact: High
wow: 3
note: rules install (#141); workflows were still tap-only
order: 22
owner: loop/workflow-install
pr:
title: Workflow install — drop commands/subagents into each agent's native dir
---
After rules landed (<code>#141</code>), <code>store.install</code> still refused
           <code>kind == "workflow"</code>, so slash commands and subagents were
           indexed for discovery but installed nowhere — <code>browse</code> could
           surface a workflow but not install it. Add the install path. Unlike
           rules (no cross-agent rules folder, so Claude needs a
           <code>CLAUDE.md</code> merge), workflows are a clean file drop: a
           command markdown lands in the agent's <code>commands/</code> dir and a
           subagent in its <code>agents/</code> dir, with the slot derived from the
           source path (<code>commands/</code>/<code>workflows/</code> →
           <code>commands</code>, <code>agents/</code>/<code>subagents/</code> →
           <code>agents</code>). Mirrors the rule store/lock model so uninstall
           removes exactly what install wrote.
