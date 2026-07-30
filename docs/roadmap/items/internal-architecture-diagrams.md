---
id: internal-architecture-diagrams
board: code
section: docsite
status: shipped
category: Docs · Onboarding
complexity: M
impact: Med
wow: 3
note: 45 core modules and an enforced layering rule, with no diagram of either
order: 12
owner: loop/architecture-diagrams
pr: 343
title: The engine had no architecture diagram &mdash; and the one written rule was documented backwards
---
boost had <b>no internal architecture diagram of any kind</b>. <code>docs/rag-architecture.md</code>
covers retrieval and <code>docs/DEBUGGING.md</code> covers diagnostics, but nothing described the
shape of the thing: 45 modules in <code>boost_cli/core</code>, 78 commands across 12 command
modules, four agent targets that are deliberately <i>not</i> symmetric, and a
<code>cli&nbsp;&rarr;&nbsp;commands&nbsp;&rarr;&nbsp;core</code> layering rule that
<code>import-linter</code> enforces on every build. A new contributor — or a new agent session —
had to reconstruct all of that from <code>ls</code>.

Shipped as C4-model diagrams in Mermaid under <code>docs/architecture/</code>, so they render on
GitHub and stay reviewable in a diff rather than being a binary nobody updates: context, containers,
core components, and a dynamic walk through <code>boost install</code>. Mermaid was already a
dependency-free choice here — the repo had none before this, so nothing new ships.

Writing them turned up a documentation bug worth more than the diagrams. <code>CLAUDE.md</code>
stated <b>"Only <code>skill</code> installs — <code>store.install</code> refuses non-skill kinds;
rules/workflows are search/tap-only."</b> That is backwards: <code>store.install</code> dispatches
to <code>_install_rule</code> and <code>_install_workflow</code>, every kind honours
<code>scope</code>, and it raises only for a kind outside the three. The consequence is not
cosmetic — installing a <i>rule</i> materialises it into the agent's context file, so a
<code>boost install</code> of a rule appends to <code>~/.claude/CLAUDE.md</code> and is read every
session afterwards. Every agent reading <code>CLAUDE.md</code> to learn this repo was being told the
most invasive install kind could not happen. Corrected in the same change, with the landing places
for all three kinds spelled out.

The diagrams are hand-written rather than generated, which is a deliberate trade: they describe
structure — layers, boundaries, which component owns which decision — not anything that moves on a
routine edit, so drift should be rare and visible in review. <code>docs/architecture/README.md</code>
lists the four claims most worth re-checking against the code when the engine changes, so the
staleness question has an answer rather than being left to erode.
