---
id: capability-policy-skips-rules-and-workflows
board: code
section: trust
status: inflight
category: Security · Bug
complexity: S
impact: High
wow: 3
note:
owner: loop/capability-policy-rule-workflow
order: 129
title: <code>denied_capabilities</code> policy never applied to rule/workflow installs
---
<code>capabilities.py</code>'s own docstring frames this as "not <i>which</i> skill, but <i>what
it is allowed to make the agent do</i>" — no kind restriction. <code>store.install()</code> agrees
in practice for one of the three installable kinds: the skill path calls
<code>_enforce_capability_policy</code> right before copying, so a skill that declares (or, under
the opt-in strict flag, merely looks like it uses) a denied capability is refused with "policy
blocks installing X: declares the 'shell' capability, denied by policy". <code>install_from_path</code>
(the local-import path used by <code>import</code>/<code>create --install</code>/<code>distill
--install</code>) got the same gate wired in by a prior card
(<code>install-from-path-bypasses-policy-and-pin-checks</code>).

<code>_install_rule</code> and <code>_install_workflow</code> — the other two of the three kinds
CLAUDE.md itself says "all three install" — never call it. A rule with <code>capabilities:
[shell]</code> in its frontmatter merges straight into <code>~/.claude/CLAUDE.md</code>, the
standing instructions the agent reads every session (which this repo's own docs already call
"more invasive than a skill, not less"); a workflow with the same frontmatter drops straight into
an agent's <code>commands/</code> or <code>agents/</code> dir as a slash command or subagent run
verbatim. Either way <code>denied_capabilities</code> is silently a no-op — a team that configures
"deny shell" to keep untrusted taps from installing anything that shells out is only half
enforced, and the half that isn't is the more invasive half.

Distinct from <code>rules-install-but-cannot-be-governed</code> (PR 464, which swept 20 commands
that couldn't <i>see</i> an installed rule/workflow afterwards) and from
<code>install-from-path-bypasses-policy-and-pin-checks</code> (the local-import path, already
fixed): this is the tap-install path for the other two kinds skipping a pre-install gate that
already exists and already works for skills, not a governance-after-the-fact problem.

<b>Fix.</b> <code>_enforce_capability_policy</code> never actually required a
<code>SKILL.md</code>-shaped path — it just reads a Markdown file and checks its frontmatter +
body against policy — so <code>_install_rule</code> and <code>_install_workflow</code> now call it
on their own source file before materializing anything, the same placement (right after the
"source vanished from tap" check, before any write) the skill path already uses. Covered by new
unit tests in both <code>TestRuleInstall</code>/<code>TestWorkflowInstall</code> (denied capability
refuses and leaves no lock entry / no materialized file; a non-denied capability still installs)
and new functional tests in <code>test_capabilities_policy.py</code> exercising the same denial
end to end through <code>boost install</code> for a tapped rule and a tapped workflow.
