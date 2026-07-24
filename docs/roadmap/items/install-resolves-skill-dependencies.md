---
id: install-resolves-skill-dependencies
board: code
section: dx
status: inflight
category: Core · Package manager
complexity: M
impact: High
wow: 4
note: the Homebrew move
order: 45
owner: loop/install-deps
pr: 227
title: <code>boost install</code> resolves a skill's <code>requires:</code> closure
---
Skills already declare relationships in frontmatter (<code>requires:</code> /
           <code>conflicts:</code>), and <code>boost info</code> / <code>boost deps</code>
           <em>show</em> them — but <code>boost install X</code> only ever installed
           exactly what you named, never what X depends on. That is the one headline
           package-manager behavior boost was missing: installing a skill should pull
           in the skills it needs, in the right order. Add a pure, mutation-tested
           resolver in <code>core/resolve.py</code> — post-order DFS over the
           <code>requires:</code> graph, cycle-safe, deduped, already-installed nodes
           pruned — and wire it into <code>cmd_install</code> so a named skill installs
           its transitive <code>requires:</code> closure (dependencies first), with a
           <code>--no-deps</code> escape hatch. Declared <code>conflicts:</code> against
           an installed or co-installed skill surface as an advisory warning, and a
           <code>requires:</code> naming a skill in no tap is flagged, not fatal.
           Surfaced by mining boost's own catalog: the densest skill cluster is
           dependency management, which every package manager treats as table stakes.
